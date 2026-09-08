#include "dsp.h"

#include <cstdio>
#include <algorithm>
#include <cstring>
#include <array>
#include <cmath>
#include <map>

#include "dsp56kEmu/dsp.h"
#include "dsp56kEmu/dspBootCode.h"
#include "dsp56kEmu/esai.h"
#include "dsp56kEmu/esaiclock.h"
#include "dsp56kEmu/hdi08.h"
#include "dsp56kEmu/memory.h"
#include "dsp56kEmu/peripherals.h"
#include "dsp56kBase/logging.h"

namespace ot
{
	namespace
	{
		class AllowAll final : public dsp56k::IMemoryValidator
		{
		public:
			bool memValidateAccess(dsp56k::EMemArea, dsp56k::TWord, bool) const override { return true; }
		};

		// ICR bits, host side.
		constexpr uint32_t ICR_RREQ = 0x01, ICR_TREQ = 0x02, ICR_INIT = 0x80;
		// Payload A's bank-id write, `000073: movep r3,x:<<M_HOTX` in
		// out/dsp/payload_A.asm (O9b). A payload that moves it moves this.
		constexpr uint32_t g_bankIdPc = 0x73;
	}

	struct DspPair::Core
	{
		AllowAll validator;
		std::unique_ptr<dsp56k::Memory> mem;
		std::unique_ptr<dsp56k::Peripherals56362> px;
		std::unique_ptr<dsp56k::Peripherals56367> py;
		std::unique_ptr<dsp56k::DSP> dsp;
		std::unique_ptr<dsp56k::DspBoot> boot;

		uint64_t executed = 0, wordsIn = 0, wordsOut = 0, commands = 0, dropped = 0;
		uint64_t rxFrames = 0, txFrames = 0;	// ESAI frames taken in (silence) / put out -- the X-side port
		uint64_t rxFrames1 = 0, txFrames1 = 0;	// the same for ESAI_1 on the Y side (❌ the two were summed until 8 Sep, and "frames per host frame" read double)
		uint64_t txAtCommand = 0;				// txFrames at the previous host command
		uint64_t fpcMin = ~0ull, fpcMax = 0, fpcSixteen = 0, fpcSamples = 0;	// frames per command
		uint32_t esaiCyclesPerSlot = 0;
		uint64_t idleSkipped = 0;
		uint64_t pulled = 0, pullShort = 0;	// read-back words taken / not produced in time
		uint32_t lastSent[2] = {0, 0};		// a rolling pair of the last two words sent
		uint32_t ddrAtArm = 0, dcoAtArm = 0;	// DMA0 as the DSP's handler left it, before any word drains
		uint32_t cmdArgs[2] = {0, 0};		// ⚠️ SNAPSHOT AT THE COMMAND. Taken at drain time
											// instead, this held the block's last two DATA words
											// and read as if the firmware sent a dest of 0x030000.
		uint64_t nextTrace = 0;			// the fast-forward skips past exact multiples
		uint32_t lastPcLo = 0, lastPcHi = 0;	// the PC window of the last few instructions
		int windowRun = 0;
		uint32_t lastTx[2] = {0, 0};		// slot 0 of the last output frame, TX0/TX1
		// O9: the audio. Frames counted from the ESAI's first, the transport
		// start latched at the first 0x8c so a WAV can be trimmed to it.
		std::vector<int32_t> capture;
		bool firstCmdSeen = false;
		uint64_t txAtFirstCmd = 0, rxAtFirstCmd = 0;
		std::array<uint64_t, DspPair::g_audioSlots> txNZ = {}, rxNZ = {};
		uint64_t surplus = 0, zeroDelta = 0;	// instruction-counter delta beyond one per interpreter call / calls that moved it not at all
		// O9b: bank id -> host take latency, in this core's instructions (4160 = one sample)
		uint64_t bankWriteAt = 0, bankTakeMax = 0, bankTakeSum = 0, bankTakes = 0, bankTakeMaxAt = 0, bankWritesInPull = 0;
		std::array<std::array<uint32_t, 1024>, 2> nzWrites = {};	// [X/Y][region of 256 words]: non-zero writes since the last flush
		uint64_t ringNzWrites = 0, ringFirstAt = 0;	// non-zero writes into the ESAI-out ring X:0x8000-0x80ff
		uint32_t ringFirstAddr = 0, ringFirstVal = 0;
		// The host-side registers this model keeps itself; the rest are
		// derived from the vendored HDI08 on every read.
		uint8_t icr = 0, cvr = 0x32, ivr = 0x0f, txh = 0, txm = 0;
		uint32_t lastRx = 0;		// the last word taken: RXH/RXM read it back
		bool hcPending = false;
		uint32_t hcVector = 0;
		// THE PC RING AND THE FAULT. The interpreter indexes its opcode cache by
		// the PC into a table sized to P memory (0x80000 words here), so a PC
		// beyond it is a garbage member-function pointer and a SIGBUS with no
		// diagnostic -- measured 8 Sep 2026 under lldb (funcCreate, called
		// from DSP::execOp with a garbage `this`). Stop the core instead, and
		// keep the last 64 PCs so the report can say how it got there.
		std::array<uint32_t, 64> pcRing = {};
		uint64_t pcRingPos = 0;
		bool faulted = false;
		std::string why;
		std::map<uint32_t, uint64_t> vectorsTaken;		// O9b: interrupt vector -> count (every interrupt the vendored core took)
		uint64_t timerEnabledAt = 0; uint32_t timerTcsr = 0; std::array<uint32_t, 8> timerPcs = {}; std::array<uint32_t, 8> timerR = {}, timerM = {};	// the first moment TCSR0.TE is seen set, and the PCs before it

		dsp56k::HDI08& hdi() { return px->getHDI08(); }
	};

	DspPair::DspPair(const double _ratio, const double _ips)
		: m_ratio(_ratio), m_ips(_ips), m_shared(g_shareHi - g_shareLo, 0)
	{
		// The vendored library logs every ESAI register write and every
		// transmit underrun to stdout (3,260 lines over one boot). Off unless
		// asked: `setVerbose(true)` restores them.
		setVerbose(false);
		for(int i = 0; i < 2; ++i)
		{
			m_cores.emplace_back(new Core);
			Core& c = *m_cores.back();
			// The sizes `tools/dsp_host` uses (the library's own tests').
			c.mem.reset(new dsp56k::Memory(c.validator, 0x080000, 0x800000, 0x200000));
			// The Y-side peripherals first: the X side's ESAI clock also drives
			// the Y side's ESAI when it is told about it (dsp_host passes
			// nothing, and calls the effects directly, so it never needed to).
			c.py.reset(new dsp56k::Peripherals56367);
			c.px.reset(new dsp56k::Peripherals56362(c.py.get()));
			c.dsp.reset(new dsp56k::DSP(*c.mem, c.px.get(), c.py.get()));
			// ⚠️ NOT dsp_host's window. dsp_host shares X with X and Y with Y and
			// keeps P private, which renders the effects bit-identically and
			// cannot answer aliasing questions (DSP.md). The firmware needs the
			// real thing: ✅ measured 8 Sep 2026, with P private core 1 jumped to
			// its entry P:0x38000 -- written only by core 0's upload -- found
			// zeros, and ran off the end of P memory (the PC ring read 7ffc1..
			// 7ffff, then the fault). A write anywhere in the window drops both
			// cores' decoded opcode for that address, because P is what changed.
			c.mem->setSharedWindow(g_shareLo, g_shareHi, m_shared.data(), [this](dsp56k::TWord _a)
			{
				for(auto& k : m_cores)
					k->dsp->clearOpcodeCache(_a);
			});
			c.mem->setWriteHook([this, &c, i](const dsp56k::EMemArea _area, const dsp56k::TWord _off, const dsp56k::TWord _val)
			{
				// O9b: a P write outside the shared window left the STALE decode
				// in the interpreter's opcode cache (the window hook clears it
				// only for 0x30000+). The firmware uploads each payload twice
				// (O7b), so P:0x1d3 of core 1 ran the FIRST upload's instruction
				// -- a Y write -- where the second had put `tfr b,a x:(r0)+,b0`,
				// and the voice loop count at Y:0x42 became a raw host word.
				if(_area == dsp56k::MemArea_P)
					c.dsp->clearOpcodeCache(_off);
				if(m_watchOn && i == m_watchCore && _off == m_watchAddr
					&& _area == (m_watchSpace == 'Y' ? dsp56k::MemArea_Y : m_watchSpace == 'P' ? dsp56k::MemArea_P : dsp56k::MemArea_X))
				{
					if(m_watchHits.size() >= 16)
						m_watchHits.erase(m_watchHits.begin());
					WatchHit h{c.dsp->getPC().toWord(), _val & 0xffffff, c.executed, {}, 0, 0, 0, 0, static_cast<uint32_t>(c.dsp->regs().r[4].var & 0xffffff), static_cast<uint32_t>(c.dsp->regs().r[6].var & 0xffffff), static_cast<uint32_t>(_area), static_cast<uint32_t>(c.dsp->regs().r[0].var & 0xffffff)};
					for(int k = 0; k < 4; ++k)
						h.last[k] = c.pcRing[(c.pcRingPos + 64 - 1 - static_cast<uint64_t>(k)) % 64];
					h.ddr0 = c.px->read(0xffffee, dsp56k::Nop); h.dco0 = c.px->read(0xffffed, dsp56k::Nop);
					h.dsr1 = c.px->read(0xffffeb, dsp56k::Nop); h.dco1 = c.px->read(0xffffe9, dsp56k::Nop);
					m_watchHits.push_back(h);
				}
				if(!m_writesOn || _area == dsp56k::MemArea_P || !(_val & 0xffffff) || _off >= 0x40000)
					return;
				++c.nzWrites[_area == dsp56k::MemArea_Y ? 1 : 0][_off >> 8];
				if(_area == dsp56k::MemArea_X && _off >= 0x8000 && _off < 0x8100)
				{
					if(!c.ringNzWrites++)
					{
						c.ringFirstAt = c.executed;
						c.ringFirstAddr = _off;
						c.ringFirstVal = _val & 0xffffff;
					}
				}
			});
			// AFTER the DSP: its constructor resets the peripherals, and the
			// boot ROM's first act is to enable the host port (HPCR.HEN).
			c.boot.reset(new dsp56k::DspBoot(*c.dsp));
			// HOTX is ONE register: with this clear the DSP's `movep a,x:<<M_HOTX`
			// blocks on HTDE the way the chip does, instead of queueing 8192
			// words (dsp_host's finding of 2 Sep 2026).
			c.hdi().setTransmitDataAlwaysEmpty(false);
			// The receive DMA moves a word per request, not one per 200
			// instructions (the vendored default is a throttle for a threaded
			// host): a 672-word block at 200 is 30 samples, twice a frame.
			c.hdi().setRXRateLimit(0);
			// HOST-STEPPED (tools/dsp56300.patch): a hardware DO loop is stepped,
			// not run to completion in one call -- the firmware's 50-word loader
			// polls the host port INSIDE one (`dor`), and the ColdFire has to
			// run between its iterations -- and interrupts go through the
			// interpreter, not the JIT. ✅ Both measured 8 Sep 2026: a stack
			// sample of the first attempt sat in DSP::op_Dor_S -> do_exec ->
			// op_Brclr_pp forever; the second faulted in the JIT's funcCreate
			// on the first DSP interrupt (lldb, EXC_BAD_ACCESS).
			c.dsp->setHostStepped(true);
			// HC and HCP clear when the DSP TAKES the host command. ✅ Measured
			// 8 Sep 2026: watching for the PC to land on the vector never fired
			// -- a fast interrupt runs the vector's two words inline -- so the
			// frame handler polled HC forever and the sequencer ran 0 frames.
			c.dsp->setInterruptTakenHook([this, i](dsp56k::TWord _vba)
			{
				Core& k = *m_cores[i];
				++k.vectorsTaken[_vba];
				if(!k.hcPending || _vba != k.hcVector)
					return;
				k.hcPending = false;
				k.cvr &= 0x7f;
				auto& h = k.hdi();
				h.writeStatusRegister(h.readStatusRegister() & ~(1u << dsp56k::HDI08::HSR_HCP));
				const int sel = m_sel;
				m_sel = i;
				note("hc-taken", _vba);
				m_sel = sel;
			});

			// THE ESAI, NON-BLOCKING. ✅ Measured 8 Sep 2026: with the vendored
			// defaults the DSP program's own ESAI setup ran, the first receive
			// frame popped an EMPTY input ring, and the emulator sat in a
			// condition variable forever (stack sample: EsxiClock::exec ->
			// Esai::execRX -> RingBuffer::pop_front -> ConditionVariable::wait).
			// Nothing here supplies audio yet (O9), so the input is silence and
			// the output is counted -- and the clock is ONE FRAME PER SAMPLE at
			// the pair's own instructions-per-sample, so the DSP's audio clock
			// and the ColdFire's sample clock cannot drift apart.
			// ❌ Until 8 Sep 2026 this passed `_ips` straight through, and the
			// vendored clock fires ONE SLOT per "cycles per sample" (Esai::execTX
			// advances m_txSlotCounter once per call; EsxiClock's own
			// derivation halves it "2 samples = 1 frame (stereo)"). With the
			// payload's 8 slots that was an audio clock 8x slow: the 256-word
			// ring at X:0x8000 advanced 16 words per 16-sample frame instead of
			// 128, the dispatcher's DSR2 == 0x80f0 bank never came, and every
			// block landed in bank A (COLDFIRE_PORT.md O8, "the bank is the
			// audio ring's phase"). One slot per `_ips / 8`: 520 at 4160.
			// O9: RX0 carries the input (a file or the tones) from the
			// transport start on, silence before it and on every other slot
			// register; TX0's eight slots are counted per slot and kept.
			auto silence = [this, &c](uint64_t&, dsp56k::Audio::RxFrame& _f)
			{
				for(uint32_t i = 0; i < dsp56k::Audio::MaxSlotsPerFrame; ++i)
					for(auto& w : _f[i])
						w = 0;
				_f.resize(dsp56k::Audio::MaxSlotsPerFrame);
				if(c.firstCmdSeen && (m_tones || m_inputChannels))
				{
					const uint64_t n = c.rxFrames - c.rxAtFirstCmd;
					for(uint32_t s = 0; s < g_audioSlots; ++s)
					{
						int32_t v = 0;
						if(m_tones)
							v = static_cast<int32_t>(std::lrint(0.1 * 8388607.0 * std::sin(2.0 * M_PI * 500.0 * (s + 1) * static_cast<double>(n) / 44100.0)));
						else if(s < m_inputChannels && (n + 1) * m_inputChannels <= m_input.size())
							v = m_input[n * m_inputChannels + s];
						if(v)
							++c.rxNZ[s];
						_f[s][0] = static_cast<uint32_t>(v) & 0xffffff;
					}
				}
				++c.rxFrames;
			};
			auto sink = [this, &c](uint64_t&, const dsp56k::Audio::TxFrame& _f)
			{
				++c.txFrames;
				if(_f.size())
				{
					c.lastTx[0] = _f[0][0];
					c.lastTx[1] = _f[0][1];
				}
				for(uint32_t s = 0; s < g_audioSlots; ++s)
				{
					const uint32_t w = s < _f.size() ? (_f[s][0] & 0xffffff) : 0;
					if(w)
						++c.txNZ[s];
					if(m_capture)
						c.capture.push_back(static_cast<int32_t>(w << 8) >> 8);
				}
			};
			auto silence1 = [&c](uint64_t&, dsp56k::Audio::RxFrame& _f)
			{
				for(uint32_t i = 0; i < dsp56k::Audio::MaxSlotsPerFrame; ++i)
					for(auto& w : _f[i])
						w = 0;
				_f.resize(dsp56k::Audio::MaxSlotsPerFrame);
				++c.rxFrames1;
			};
			auto sink1 = [&c](uint64_t&, const dsp56k::Audio::TxFrame&) { ++c.txFrames1; };
			c.px->getEsai().setReadRxCallback(silence);
			c.px->getEsai().setWriteTxCallback(sink);
			c.py->getEsai().setReadRxCallback(silence1);
			c.py->getEsai().setWriteTxCallback(sink1);
			c.esaiCyclesPerSlot = static_cast<uint32_t>(_ips / g_esaiSlots);
			c.px->getEsaiClock().setCyclesPerSample(c.esaiCyclesPerSlot);

			// The inter-core mailbox (see dsp.h), on the Y-side peripherals.
			c.py->setUnmappedHooks(
				[this, i](dsp56k::TWord _a, dsp56k::TWord& _v)
				{
					switch(_a)
					{
					case 0xffffd3: _v = m_mail[i ^ 1].full ? 2u : 0u; return true;
					case 0xffffd4:
						_v = m_mail[i ^ 1].data;
						m_mail[i ^ 1].full = false;
						return true;
					case 0xffffd6: _v = m_mail[i].full ? 2u : 0u; return true;
					case 0xffffd7: _v = m_mail[i].data; return true;
					default: return false;
					}
				},
				[this, i](dsp56k::TWord _a, dsp56k::TWord _v)
				{
					if(_a != 0xffffd7)
						return false;
					m_mail[i].data = _v & 0xffffff;
					m_mail[i].full = true;
					++m_mail[i].words;
					const int sel = m_sel;
					m_sel = i;
					note("mail", _v & 0xffffff);
					m_sel = sel;
					return true;
				});
		}
	}

	DspPair::~DspPair() = default;

	void DspPair::setVerbose(const bool _on)
	{
		// (A null function crashes the vendored logger; give it a printer.)
		Logging::setLogFunc(_on ? [](const std::string& _s) { std::puts(_s.c_str()); } : [](const std::string&) {});
	}

	void DspPair::note(const char* _kind, const uint32_t _val)
	{
		if(!m_logOn || m_log.size() >= 4000000)
			return;
		Event e{};
		e.due = static_cast<uint64_t>(m_due);
		e.core = m_sel & 1;
		std::strncpy(e.kind, _kind, sizeof e.kind - 1);
		e.val = _val;
		m_log.push_back(e);
	}

	// -- the register file ----------------------------------------------------

	void DspPair::icrWrite(const uint32_t _v)
	{
		Core& c = cur();
		auto& h = c.hdi();
		c.icr = static_cast<uint8_t>(_v & 0x7f);		// INIT reads back clear
		note("icr", _v & 0xff);
		if(_v & ICR_INIT)
		{
			// INIT's effect is selected by TREQ/RREQ (the family manual's
			// table, and the only reading under which the firmware's `0x81`
			// makes sense as a per-core reset before an upload):
			//   RREQ: the DSP-to-host path -- RXDF := 0, HTDE := 1
			//   TREQ: the host-to-DSP path -- TXDE := 1, HRDF := 0
			if(_v & ICR_RREQ)
				while(h.hasTX())
					h.readTX();
			if(_v & ICR_TREQ)
				h.clearRX();
		}
		h.setHostFlags((_v >> 3) & 1, (_v >> 4) & 1);
	}

	void DspPair::cvrWrite(const uint32_t _v)
	{
		Core& c = cur();
		c.cvr = static_cast<uint8_t>(_v & 0xff);
		note("cvr", _v & 0xff);
		if(!(_v & 0x80))
			return;
		// HC set: a host command interrupt at P:(HV * 2). The frame handler's
		// 0x8c is vector 0x18. HC (and the DSP's HCP) stay set until the DSP
		// takes it -- `runDue` clears both when the PC lands on the vector.
		c.hcVector = (_v & 0x7f) << 1;
		c.cmdArgs[0] = c.lastSent[0];
		c.cmdArgs[1] = c.lastSent[1];
		c.hcPending = true;
		++c.commands;
		if(c.hcVector == 0x18 && m_writesOn && m_sel == 0 && m_writeMap.size() < 20000)
		{
			std::string line = "cmd " + std::to_string(c.commands) + " tx " + std::to_string(c.txFrames);
			for(int k = 0; k < 2; ++k)
				for(int space = 0; space < 2; ++space)
					for(uint32_t r = 0; r < 1024; ++r)
					{
						auto& n = m_cores[k]->nzWrites[space][r];
						if(n)
						{
							char f[40];
							std::snprintf(f, sizeof f, " %d%c%05x:%u", k, space ? 'Y' : 'X', r << 8, n);
							line += f;
							n = 0;
						}
					}
			m_writeMap.push_back(line);
		}
		if(c.hcVector == 0x18 && m_mapOn && m_sel == 0 && m_map.size() < 20000)
		{
			std::string line = "cmd " + std::to_string(c.commands) + " tx " + std::to_string(c.txFrames);
			for(int k = 0; k < 2; ++k)
				for(int space = 0; space < 2; ++space)
					for(uint32_t base = 0; base < 0x40000; base += 0x1000)
					{
						uint32_t n = 0;
						for(uint32_t a = base; a < base + 0x1000; ++a)
							if((space ? peekY(k, a) : peekX(k, a)) & 0xffffff)
								++n;
						if(n)
						{
							char f[40];
							std::snprintf(f, sizeof f, " %d%c%05x:%u", k, space ? 'Y' : 'X', base, n);
							line += f;
						}
					}
			m_map.push_back(line);
		}
		if(c.hcVector == 0x18 && !c.firstCmdSeen)
		{
			c.firstCmdSeen = true;
			c.txAtFirstCmd = c.txFrames;
			c.rxAtFirstCmd = c.rxFrames;
		}
		if(c.hcVector == 0x18 && c.txFrames)
		{
			// Frames per frame: count from the second 0x8c on, once the ESAI
			// is running, so the boot-time gap is not the minimum.
			if(c.txAtCommand)
			{
				const auto d = c.txFrames - c.txAtCommand;
				c.fpcMin = std::min(c.fpcMin, d);
				c.fpcMax = std::max(c.fpcMax, d);
				if(d == 16) ++c.fpcSixteen;
				++c.fpcSamples;
			}
			c.txAtCommand = c.txFrames;
		}
		auto& h = c.hdi();
		h.writeStatusRegister(h.readStatusRegister() | (1u << dsp56k::HDI08::HSR_HCP));
		c.dsp->injectInterrupt(c.hcVector);
	}

	uint32_t DspPair::isrRead()
	{
		Core& c = cur();
		auto& h = c.hdi();
		// RXDF: the DSP has written HOTX and the host has not taken it.
		// TXDE: the host's last word has been TAKEN by the DSP (the receive
		// ring is empty) -- or is still being swallowed by the boot ROM, which
		// takes every word at once. TRDY adds "and HRDF is clear", which is
		// the same condition in this single-register model.
		const bool rxdf = h.hasTX();
		const bool txde = !c.boot->finished() || !h.hasRXData();
		uint32_t v = (rxdf ? 1u : 0u) | (txde ? 2u : 0u) | (txde ? 4u : 0u);
		v |= ((h.readControlRegister() >> 3) & 3) << 3;		// HF2/HF3 from the DSP's HCR
		if((rxdf && (c.icr & ICR_RREQ)) || (txde && (c.icr & ICR_TREQ)))
			v |= 0x80;											// HREQ
		return v;
	}

	void DspPair::sendWord(const uint32_t _word)
	{
		Core& c = cur();
		++c.wordsIn;
		note("tx", _word);
		if(!c.boot->finished())
		{
			c.boot->hdiWriteTX(_word);
			return;
		}
		auto& h = c.hdi();
		if(h.dataRXFull())
		{
			// Never block the emulator on a ring: the chip would simply have
			// overwritten HRX. Count it so the report can say so.
			++c.dropped;
			return;
		}
		c.lastSent[0] = c.lastSent[1];
		c.lastSent[1] = _word;
		const dsp56k::TWord w = _word;
		h.writeRX(&w, 1);
	}

	uint32_t DspPair::rxPeek()
	{
		Core& c = cur();
		auto& h = c.hdi();
		return h.hasTX() ? h.txData().front() : c.lastRx;
	}

	uint32_t DspPair::rxTake()
	{
		{
			Core& c = cur();
			if(!m_pulling && c.bankWriteAt)
			{
				const auto lat = c.executed - c.bankWriteAt;
				++c.bankTakes; c.bankTakeSum += lat;
				if(lat > c.bankTakeMax) { c.bankTakeMax = lat; c.bankTakeMaxAt = c.bankTakes; }
				c.bankWriteAt = 0;
			}
		}
		Core& c = cur();
		auto& h = c.hdi();
		if(h.hasTX())
		{
			c.lastRx = h.readTX();
			++c.wordsOut;
			note(m_pulling ? "rxp" : "rx", c.lastRx);
		}
		return c.lastRx;
	}

	bool DspPair::read(const uint32_t _addr, const uint8_t _size, uint32_t& _out)
	{
		if(_addr == g_select && _size == 1)
		{
			_out = static_cast<uint32_t>(m_sel);
			return true;
		}
		if(_addr < g_window || _addr >= g_windowEnd)
			return false;
		// THE LANES. A 16-bit port (CS2, CSCR2 = 0x180): the odd byte of a
		// halfword is the register the stride names, (a >> 2) & 7, and the even
		// byte is the register BEFORE it. ✅ Decoded 8 Sep 2026 from route A's
		// tape: the DSP's count word for every per-frame block is exactly half
		// the block's byte count, so one DSP word rides each 16-bit cycle --
		// the loader's byte-at-a-time writes are consistent with it (TXH:hh at
		// +0x14 lands hh in TXH; hh:mm at +0x18 in TXH:TXM; mm:ll at +0x1c in
		// TXM:TXL and sends), and so is the DSP masking a count it was sent
		// with a single `movew` to +0x1c to 16 bits. A longword access is two
		// cycles, high halfword first. ❌ The first model (odd byte only) made
		// every frame word 8 bits wide.
		uint32_t v = 0;
		for(uint32_t i = 0; i < _size; ++i)
		{
			const auto a = _addr + i;
			const int r = static_cast<int>((a >> 2) & 7) - ((a & 1) ? 0 : 1);
			uint32_t b = 0;
			Core& c = cur();
			switch(r)
			{
			case 0: b = c.icr; break;
			case 1: b = c.cvr; break;
			case 2: b = isrRead(); break;
			case 3: b = c.ivr; break;
			case 5: b = (rxPeek() >> 16) & 0xff; break;
			case 6: b = (rxPeek() >> 8) & 0xff; break;
			case 7: b = rxTake() & 0xff; break;
			default: break;
			}
			v = (v << 8) | (b & 0xff);
		}
		_out = v;
		return true;
	}

	bool DspPair::write(const uint32_t _addr, const uint8_t _size, const uint32_t _val)
	{
		if(_addr == g_select && _size == 1)
		{
			m_sel = static_cast<int>(_val & 1);
			note("sel", _val & 0xff);
			return true;
		}
		if(_addr < g_window || _addr >= g_windowEnd)
			return false;
		for(uint32_t i = 0; i < _size; ++i)
		{
			const auto a = _addr + i;
			const int r = static_cast<int>((a >> 2) & 7) - ((a & 1) ? 0 : 1);
			const uint32_t b = (_val >> (8 * (_size - 1 - i))) & 0xff;
			Core& c = cur();
			switch(r)
			{
			case 0: icrWrite(b); break;
			case 1: cvrWrite(b); break;
			case 3: c.ivr = static_cast<uint8_t>(b); break;
			case 5: c.txh = static_cast<uint8_t>(b); break;
			case 6: c.txm = static_cast<uint8_t>(b); break;
			case 7: sendWord((c.txh << 16) | (c.txm << 8) | b); break;
			default: break;				// ISR is read-only; register 4 is nothing
			}
		}
		return true;
	}

	// -- the eDMA's side ------------------------------------------------------

	void DspPair::pushHalfwords(const uint32_t _addr, const std::vector<uint16_t>& _hw)
	{
		// ⚠️ DMA0 AS OF THE KICK IS THE **PREVIOUS** BLOCK'S ARMING, and that is
		// not a defect. The command's two argument words and the CVR write all
		// precede the kick, but the CVR only INJECTS the interrupt: the DSP has
		// not taken it yet, so its handler has not read the arguments. The FIFO
		// is what makes this correct -- the arguments sit ahead of the data in
		// the ring, so when the DSP does take the interrupt it reads them first,
		// arms DMA0, and only then drains the block. ✅ Measured 8 Sep 2026:
		// read here, DCO0 always holds the count of the block BEFORE this one.
		// The third instance this session of a note taken at the wrong moment.
		{
			Core& c = cur();
			c.ddrAtArm = c.px->read(0xffffee, dsp56k::Nop);
			c.dcoAtArm = c.px->read(0xffffed, dsp56k::Nop);
		}
		// The cycles the eDMA would make: a 32-bit write at _addr is two
		// halfwords at +0 and +2, and both land on the same two registers.
		for(size_t i = 0; i < _hw.size(); ++i)
			write(_addr + 2 * static_cast<uint32_t>(i & 1), 2, _hw[i]);
	}

	size_t DspPair::pullHalfwords(const uint32_t _addr, const int _core, std::vector<uint16_t>& _out, const size_t _n)
	{
		const int sel = m_sel;
		m_sel = _core & 1;
		Core& c = cur();
		size_t missing = 0;
		m_pulling = true;
		for(size_t i = 0; i < _n; ++i)
		{
			// RXDF, the way the eDMA's request line would gate it -- and the
			// DSP's own DMA has to put the next word in HOTX for that.
			const bool ready = runCoreUntil(m_sel, [&c]{ return c.hdi().hasTX(); }, 200000);
			if(!ready)
				++missing;
			uint32_t v = 0;
			read(_addr + 2 * static_cast<uint32_t>(i & 1), 2, v);
			_out.push_back(static_cast<uint16_t>(v));
			++c.pulled;
		}
		c.pullShort += missing;
		m_pulling = false;
		m_sel = sel;
		return missing;
	}

	bool DspPair::runCoreUntil(const int _core, const std::function<bool()>& _ready, const uint64_t _budget)
	{
		Core& c = *m_cores[_core & 1];
		Core& other = *m_cores[(_core & 1) ^ 1];
		for(uint64_t n = 0; n < _budget; ++n)
		{
			if(_ready())
				return true;
			if(c.faulted)
				return false;
			const auto pc = c.dsp->getPC().toWord();
			if(pc >= g_pSize)
			{
				c.faulted = true;
				c.why = "PC outside P memory during a read-back";
				return false;
			}
			// One instruction of this core, then let the other core catch
			// up to it: the pull must not run one core a frame ahead (O9b).
			stepCore(_core & 1, static_cast<double>(c.executed) + 1.0);
			while(other.executed < c.executed && stepCore((_core & 1) ^ 1, static_cast<double>(c.executed)))
				;
		}
		return _ready();
	}

	// -- the clock ------------------------------------------------------------

	void DspPair::tickInstructions(const uint64_t _n)
	{
		m_due += static_cast<double>(_n) * m_ratio;
		runDue();
	}

	double DspPair::tickSamples(const double _n)
	{
		if(!m_hostWordHook)
		{
			m_due += _n * m_ips;
			runDue();
			return _n;
		}
		// One sample at a time, so that a frame edge inside a ColdFire idle
		// skip ends the skip AT the edge, not a period later.
		double done = 0.0;
		while(done < _n)
		{
			const double step = std::min(1.0, _n - done);
			m_hostWordFired = false;
			m_due += step * m_ips;
			runDue();
			done += step;
			if(m_hostWordFired)
				break;
		}
		return done;
	}

	// One instruction of core `_i`, if it is runnable and below `_limit`.
	// Returns whether it ran. runDue and runCoreUntil are both built on it
	// (O9b): the cores used to run one WHOLE budget slice each in turn, and
	// a read-back pull ran core 0 alone for up to a frame -- so core 0's
	// mailbox wait for core 1 (P:0xa3) could outlast the dispatcher's
	// one-word window on the ring pointer (P:0x4b: DSR2 == 0x8070/0x80f0),
	// the output DMA ran out un-re-armed, and the audio died 38 frames after
	// the first trig. Hardware runs the cores in parallel; a small quantum
	// is the nearest thing.
	bool DspPair::stepCore(const int _i, const double _limit)
	{
		Core& c = *m_cores[_i];
		const int i = _i;
		if(!c.boot->finished())
		{
			// Held in the bootstrap ROM until its last word lands; the
			// ROM's jump is the first instruction this core runs.
			if(static_cast<double>(c.executed) < _limit)
				c.executed = static_cast<uint64_t>(_limit);
			return false;
		}
		if(c.faulted)
		{
			c.executed = static_cast<uint64_t>(_limit);
			return false;
		}
		if(static_cast<double>(c.executed) >= _limit)
			return false;

			const auto pc = c.dsp->getPC().toWord();
			c.pcRing[c.pcRingPos++ % c.pcRing.size()] = pc;
			if(pc >= g_pSize)
			{
				c.faulted = true;
				char msg[96];
				std::snprintf(msg, sizeof msg, "PC %#x is outside P memory (%#x words)", pc, g_pSize);
				c.why = msg;
				c.executed = static_cast<uint64_t>(_limit);
				return false;
			}
			// The idle fast-forward (dsp.h): eight instructions in a row
			// inside a three-word window, no hardware loop open.
			// O9: the budget counts the DSP's OWN instruction counter, the
			// one its ESAI clock reads -- a `rep` advances it once per
			// iteration where this loop makes ONE interpreter call, so
			// counting calls ran the ESAI 0.27% fast against the frame
			// clock (17 ESAI frames in a host frame, 17 of 399 -- O8b's
			// residual). The delta is taken across the idle step too.
			const auto before = c.dsp->getInstructionCounter();
			uint64_t skipped = 0;
			if(pc < c.lastPcLo || pc > c.lastPcHi)
			{
				c.lastPcLo = pc;
				c.lastPcHi = pc + 2;
				c.windowRun = 0;
			}
			else if(++c.windowRun >= 8 && m_idleSkip && !(c.dsp->regs().sr.var & 0x8000)
				&& !c.dsp->hasPendingInterrupts())
			{
				// Skip to the next peripheral event (or the due count), then
				// FALL THROUGH and execute the poll once, so it can see what
				// changed. ⚠️ `continue` here left the poll never executed
				// and the uploader waiting for an echo forever (measured
				// 8 Sep 2026: "unrecognised spin at 40001b82").
				const auto room = static_cast<uint64_t>(_limit - static_cast<double>(c.executed));
				skipped = c.dsp->idleStep(room ? room : 1);
				c.idleSkipped += skipped;
			}
			// O9b: the bank id is the ONE host-port word the frame handler
			// reads with no ready check: payload A's `movep r3,x:<<M_HOTX`
			// at P:0x73, right after the bank wait, once per ring half.
			// (Keying on "port non-empty outside a pull" instead fired on
			// every command echo too: 5-6 ESAI frames per host frame.)
			const bool bankWrite = i == 0 && pc == g_bankIdPc && m_hostWordHook;
			// O9b: nobody in either payload writes a timer register, yet core 1
			// took TIMER0 Compare (vector 0x54 -- payload B's `move x0,y:(r4)+`)
			// 230,027 times. Catch the first enable with the PCs before it.
			if(!c.timerEnabledAt && (c.px->getTimers().readTCSR(0) & 1))
			{
				c.timerEnabledAt = c.executed;
				c.timerTcsr = c.px->getTimers().readTCSR(0);
				for(int k = 0; k < 8; ++k)
				{
					c.timerPcs[k] = c.pcRing[(c.pcRingPos + 64 - 1 - static_cast<uint64_t>(k)) % 64];
					c.timerR[k] = c.dsp->regs().r[k].var & 0xffffff;
					c.timerM[k] = c.dsp->regs().m[k].var & 0xffffff;
				}
			}
			if(m_pcWatchOn && i == m_pcWatchCore && pc == m_pcWatchPc && c.executed >= m_pcWatchFrom && !(m_pcWatchFrom && m_pcWatchHits.size() >= 24))
			{
				const auto& r = c.dsp->regs();
				if(m_pcWatchHits.size() >= 24)
					m_pcWatchHits.erase(m_pcWatchHits.begin());
				m_pcWatchHits.push_back({c.executed,
					static_cast<uint32_t>((r.a.var >> 24) & 0xffffff), static_cast<uint32_t>(r.a.var & 0xffffff),
					static_cast<uint32_t>((r.b.var >> 24) & 0xffffff), static_cast<uint32_t>(r.b.var & 0xffffff),
					static_cast<uint32_t>(r.x.var & 0xffffff), static_cast<uint32_t>((r.x.var >> 24) & 0xffffff),
					static_cast<uint32_t>(r.y.var & 0xffffff), static_cast<uint32_t>((r.y.var >> 24) & 0xffffff),
					static_cast<uint32_t>(r.r[0].var & 0xffffff), static_cast<uint32_t>(r.r[4].var & 0xffffff),
					static_cast<uint32_t>(r.r[6].var & 0xffffff), static_cast<uint32_t>(r.n[4].var & 0xffffff),
					static_cast<uint32_t>(r.sp.var & 0xff), static_cast<uint32_t>(r.r[2].var & 0xffffff), static_cast<uint32_t>(r.m[2].var & 0xffffff),
					static_cast<uint32_t>(r.r[1].var & 0xffffff), static_cast<uint32_t>(r.n[1].var & 0xffffff)});
			}
			c.dsp->execInterpreter();
			c.dsp->doLoopEnd();
			const auto d = c.dsp->getInstructionCounter() - before;
			c.executed += d ? d : 1;
			if(d > skipped + 1) c.surplus += d - skipped - 1;
			if(!d) ++c.zeroDelta;
			if(bankWrite)
			{
				c.bankWriteAt = c.executed;
				{ const int sel = m_sel; m_sel = i; note("bank", c.hdi().txData().size()); m_sel = sel; }
				if(m_hostWordHook(0))
					m_hostWordFired = true;
			}
			if(m_traceEvery && c.executed >= c.nextTrace && c.executed >= m_traceFrom && m_trace.size() < 100000)
			{
				char line[256];
				std::snprintf(line, sizeof line,
					"core %d exec %llu dspctr %llu pc %06x sr %06x sp %02x mode %d pending %d periph-target %llu esai in %llu out %llu SAISR %06x RCR %06x TCR %06x HSR %06x HCR %06x DCR2 %06x DCO2 %06x DSR2 %06x DSR3 %06x DDR3 %06x DCO3 %06x DCR3 %06x DDR0 %06x DCO0 %06x DCR0 %06x DSR1 %06x DCO1 %06x DCR1 %06x",
					i, static_cast<unsigned long long>(c.executed),
					static_cast<unsigned long long>(c.dsp->getInstructionCounter()), pc,
					c.dsp->regs().sr.var & 0xffffff, c.dsp->regs().sp.var & 0xff,
					static_cast<int>(c.dsp->getProcessingMode()), c.dsp->hasPendingInterrupts() ? 1 : 0,
					static_cast<unsigned long long>(c.px->getTargetClock()),
					static_cast<unsigned long long>(c.rxFrames), static_cast<unsigned long long>(c.txFrames),
					c.px->read(0xffffb3, dsp56k::Nop), c.px->read(0xffffb7, dsp56k::Nop), c.px->read(0xffffb5, dsp56k::Nop),
					c.hdi().readStatusRegister(), c.hdi().readControlRegister(),
					c.px->read(0xffffe4, dsp56k::Nop), c.px->read(0xffffe5, dsp56k::Nop),
					c.px->read(0xffffe7, dsp56k::Nop), c.px->read(0xffffe3, dsp56k::Nop),
					c.px->read(0xffffe2, dsp56k::Nop), c.px->read(0xffffe1, dsp56k::Nop), c.px->read(0xffffe0, dsp56k::Nop),
					c.px->read(0xffffee, dsp56k::Nop), c.px->read(0xffffed, dsp56k::Nop), c.px->read(0xffffec, dsp56k::Nop),
					c.px->read(0xffffeb, dsp56k::Nop), c.px->read(0xffffe9, dsp56k::Nop), c.px->read(0xffffe8, dsp56k::Nop));
				m_trace.emplace_back(line);
				c.nextTrace = (c.executed / m_traceEvery + 1) * m_traceEvery;
			}
				return true;
	}

	void DspPair::runDue()
	{
		// Round-robin in quanta of g_quantum instructions until both cores
		// are at the due count.
		bool ran = true;
		while(ran)
		{
			ran = false;
			for(int i = 0; i < 2; ++i)
			{
				const double lim = std::min(m_due, static_cast<double>(m_cores[i]->executed) + g_quantum);
				while(stepCore(i, lim))
					ran = true;
			}
		}
	}

	// -- probes ---------------------------------------------------------------

	uint32_t DspPair::peekP(const int _core, const uint32_t _addr) const
	{
		return m_cores[_core & 1]->mem->get(dsp56k::MemArea_P, _addr);
	}
	// The shared window is read from the pair's own array: Memory::get
	// answers 0 for any offset past the core's own size before it looks at
	// the window, so a peek at 0x30000+ through it was blind (O9, 8 Sep).
	uint32_t DspPair::peekX(const int _core, const uint32_t _addr) const
	{
		if(_addr >= g_shareLo && _addr < g_shareHi)
			return m_shared[_addr - g_shareLo];
		return m_cores[_core & 1]->mem->get(dsp56k::MemArea_X, _addr);
	}
	uint32_t DspPair::peekY(const int _core, const uint32_t _addr) const
	{
		if(_addr >= g_shareLo && _addr < g_shareHi)
			return m_shared[_addr - g_shareLo];
		return m_cores[_core & 1]->mem->get(dsp56k::MemArea_Y, _addr);
	}
	uint32_t DspPair::pc(const int _core) const { return m_cores[_core & 1]->dsp->getPC().toWord(); }
	bool DspPair::faulted(const int _core) const { return m_cores[_core & 1]->faulted; }
	uint64_t DspPair::idleSkipped(const int _core) const { return m_cores[_core & 1]->idleSkipped; }
	// The DSP's own host DMA, as its frame handlers arm it (P:0x588 reads two
	// host words into DDR0/DCO0 and starts DMA0 = HORX -> X memory; P:0x597
	// does the same for DMA1 = X memory -> HOTX). Reading them says where the
	// block being moved is actually landing, at the moment it lands, which is
	// what an end-of-run peek of a buffer the DSP has already consumed cannot.
	std::string DspPair::blockNote(const int _core)
	{
		Core& c = *m_cores[_core & 1];
		char b[192];
		std::snprintf(b, sizeof b,
			"dsp: cmd args %06x %06x | DMA0 at kick (previous block) ddr %06x dco %06x -> ended ddr %06x dco %06x | X@%04x %06x %06x | X@%04x %06x %06x | rx ring %zu",
			c.cmdArgs[0], c.cmdArgs[1], c.ddrAtArm, c.dcoAtArm,
			c.px->read(0xffffee, dsp56k::Nop), c.px->read(0xffffed, dsp56k::Nop),
			c.cmdArgs[0] & 0xffff,
			c.mem->get(dsp56k::MemArea_X, c.cmdArgs[0] & 0xffff),
			c.mem->get(dsp56k::MemArea_X, (c.cmdArgs[0] & 0xffff) + 1),
			(c.cmdArgs[0] & 0xffff) - 0x2000,
			c.mem->get(dsp56k::MemArea_X, ((c.cmdArgs[0] & 0xffff) - 0x2000) & 0xffffff),
			c.mem->get(dsp56k::MemArea_X, (((c.cmdArgs[0] & 0xffff) - 0x2000) & 0xffffff) + 1),
			c.hdi().rxData().size());
		return b;
	}

	uint32_t DspPair::peekWord(const int _core, const char _space, const uint32_t _addr) const
	{
		// 'R' is not a memory space: it reads the DSP's own DMA0 destination
		// pointer, which post-increments as the block drains, so the caller can
		// find where the words it just sent actually landed.
		if(_space == 'R')
			return const_cast<dsp56k::Peripherals56362*>(m_cores[_core & 1]->px.get())->read(0xffffee, dsp56k::Nop);
		return _space == 'P' ? peekP(_core, _addr) : _space == 'Y' ? peekY(_core, _addr) : peekX(_core, _addr);
	}

	bool DspPair::hostRingEmpty(const int _core) const { return !m_cores[_core & 1]->hdi().hasRXData(); }
	uint64_t DspPair::pulled(const int _core) const { return m_cores[_core & 1]->pulled; }
	uint64_t DspPair::pullShort(const int _core) const { return m_cores[_core & 1]->pullShort; }
	uint64_t DspPair::mailboxWords(const int _from) const { return m_mail[_from & 1].words; }
	bool DspPair::bootFinished(const int _core) const { return m_cores[_core & 1]->boot->finished(); }
	uint64_t DspPair::executed(const int _core) const { return m_cores[_core & 1]->executed; }
	uint64_t DspPair::hostWordsIn(const int _core) const { return m_cores[_core & 1]->wordsIn; }
	uint64_t DspPair::hostWordsOut(const int _core) const { return m_cores[_core & 1]->wordsOut; }
	uint64_t DspPair::hostCommands(const int _core) const { return m_cores[_core & 1]->commands; }
	uint64_t DspPair::framesPerCommandMin(const int _core) const { const Core& c = *m_cores[_core & 1]; return c.fpcSamples ? c.fpcMin : 0; }
	uint64_t DspPair::framesPerCommandMax(const int _core) const { return m_cores[_core & 1]->fpcMax; }
	uint64_t DspPair::framesPerCommandSixteen(const int _core) const { return m_cores[_core & 1]->fpcSixteen; }
	uint32_t DspPair::bootLength(const int _core) const { return m_cores[_core & 1]->boot->getLength(); }
	uint32_t DspPair::bootAddress(const int _core) const { return m_cores[_core & 1]->boot->getInitialPC(); }
	const std::vector<int32_t>& DspPair::audioOut(const int _core) const { return m_cores[_core & 1]->capture; }
	void DspPair::setAudioInput(std::vector<int32_t> _interleaved, const uint32_t _channels) { m_input = std::move(_interleaved); m_inputChannels = _channels; }
	uint64_t DspPair::txAtFirstCommand(const int _core) const { return m_cores[_core & 1]->txAtFirstCmd; }
	uint64_t DspPair::rxAtFirstCommand(const int _core) const { return m_cores[_core & 1]->rxAtFirstCmd; }
	uint64_t DspPair::txSlotNonZero(const int _core, const uint32_t _slot) const { return m_cores[_core & 1]->txNZ[_slot & 7]; }
	uint64_t DspPair::rxSlotNonZero(const int _core, const uint32_t _slot) const { return m_cores[_core & 1]->rxNZ[_slot & 7]; }
	uint64_t DspPair::counterSurplus(const int _core) const { return m_cores[_core & 1]->surplus; }
	uint64_t DspPair::zeroDeltaCalls(const int _core) const { return m_cores[_core & 1]->zeroDelta; }

	std::string DspPair::report() const
	{
		std::string s;
		for(int i = 0; i < 2; ++i)
		{
			const Core& c = *m_cores[i];
			char line[1024];
			std::snprintf(line, sizeof line,
				"             core %d: boot ROM %s (%u words -> P:%#07x), pc %#07x, %llu instructions, "
				"host words in %llu / out %llu, host commands %llu%s\n"
				"                     ESAI frames in %llu / out %llu (ESAI_1 %llu / %llu), last out slot 0 = %06x %06x; idle-skipped %llu; mailbox sent %llu; read-back words %llu (%llu not in time)\n"
				"                     ESAI frames per host frame (0x8c to 0x8c): min %llu max %llu, exactly 16 on %llu of %llu; TCCR %06x (%u slots), %u instructions per slot\n"
				"                     audio (O9): transport start at ESAI frame %llu out / %llu in; TX0 non-zero per slot %llu %llu %llu %llu %llu %llu %llu %llu; RX0 non-zero per slot %llu %llu %llu %llu %llu %llu %llu %llu; DSP counter %llu, surplus over interpreter calls %llu (%.3f%%), zero-delta calls %llu\n"
				"                     bank id -> host take: %llu takes, mean %.2f samples, max %.2f at take %llu (a ring half is 16; DMA2 dies past it); bank writes inside a pull %llu\n",
				i, c.boot->finished() ? "done" : "WAITING", c.boot->getLength(), c.boot->getInitialPC(),
				c.dsp->getPC().toWord(), static_cast<unsigned long long>(c.executed),
				static_cast<unsigned long long>(c.wordsIn), static_cast<unsigned long long>(c.wordsOut),
				static_cast<unsigned long long>(c.commands),
				c.dropped ? " (words DROPPED on a full ring)" : "",
				static_cast<unsigned long long>(c.rxFrames), static_cast<unsigned long long>(c.txFrames),
				static_cast<unsigned long long>(c.rxFrames1), static_cast<unsigned long long>(c.txFrames1),
				c.lastTx[0], c.lastTx[1], static_cast<unsigned long long>(c.idleSkipped),
				static_cast<unsigned long long>(m_mail[i].words),
				static_cast<unsigned long long>(c.pulled), static_cast<unsigned long long>(c.pullShort),
				static_cast<unsigned long long>(c.fpcSamples ? c.fpcMin : 0), static_cast<unsigned long long>(c.fpcMax),
				static_cast<unsigned long long>(c.fpcSixteen), static_cast<unsigned long long>(c.fpcSamples),
				c.px->read(0xffffb6, dsp56k::Nop), ((c.px->read(0xffffb6, dsp56k::Nop) >> 9) & 0x1f) + 1,
				c.esaiCyclesPerSlot,
				static_cast<unsigned long long>(c.txAtFirstCmd), static_cast<unsigned long long>(c.rxAtFirstCmd),
				static_cast<unsigned long long>(c.txNZ[0]), static_cast<unsigned long long>(c.txNZ[1]), static_cast<unsigned long long>(c.txNZ[2]), static_cast<unsigned long long>(c.txNZ[3]),
				static_cast<unsigned long long>(c.txNZ[4]), static_cast<unsigned long long>(c.txNZ[5]), static_cast<unsigned long long>(c.txNZ[6]), static_cast<unsigned long long>(c.txNZ[7]),
				static_cast<unsigned long long>(c.rxNZ[0]), static_cast<unsigned long long>(c.rxNZ[1]), static_cast<unsigned long long>(c.rxNZ[2]), static_cast<unsigned long long>(c.rxNZ[3]),
				static_cast<unsigned long long>(c.rxNZ[4]), static_cast<unsigned long long>(c.rxNZ[5]), static_cast<unsigned long long>(c.rxNZ[6]), static_cast<unsigned long long>(c.rxNZ[7]),
				static_cast<unsigned long long>(c.dsp->getInstructionCounter()), static_cast<unsigned long long>(c.surplus),
				c.executed ? 100.0 * static_cast<double>(c.surplus) / static_cast<double>(c.executed) : 0.0,
				static_cast<unsigned long long>(c.zeroDelta),
				static_cast<unsigned long long>(c.bankTakes), c.bankTakes ? static_cast<double>(c.bankTakeSum) / static_cast<double>(c.bankTakes) / g_dspIps : 0.0,
				static_cast<double>(c.bankTakeMax) / g_dspIps, static_cast<unsigned long long>(c.bankTakeMaxAt),
				static_cast<unsigned long long>(c.bankWritesInPull));
			s += line;
			if(i == 0)
			{
				uint64_t nz = 0;
				for(const auto w : m_shared) if(w & 0xffffff) ++nz;
				s += "                     shared window (P/X/Y 0x30000-0x3ffff, one memory): " + std::to_string(nz) + " non-zero words now\n";
			}
			{
				std::string v = "                     interrupt vectors taken:";
				for(const auto& [vba, n] : c.vectorsTaken)
				{
					char f[40];
					std::snprintf(f, sizeof f, " %#04x x%llu", vba, static_cast<unsigned long long>(n));
					v += f;
				}
				s += v + "\n";
				if(c.timerEnabledAt)
				{
					char f[200];
					std::snprintf(f, sizeof f, "                     TIMER0 enabled (TCSR %06x) first seen at executed %llu, PCs before: %06x %06x %06x %06x %06x %06x %06x %06x\n",
						c.timerTcsr, static_cast<unsigned long long>(c.timerEnabledAt), c.timerPcs[0], c.timerPcs[1], c.timerPcs[2], c.timerPcs[3], c.timerPcs[4], c.timerPcs[5], c.timerPcs[6], c.timerPcs[7]);
					s += f;
					std::snprintf(f, sizeof f, "                     r0-7 %06x %06x %06x %06x %06x %06x %06x %06x  m0-7 %06x %06x %06x %06x %06x %06x %06x %06x\n",
						c.timerR[0], c.timerR[1], c.timerR[2], c.timerR[3], c.timerR[4], c.timerR[5], c.timerR[6], c.timerR[7],
						c.timerM[0], c.timerM[1], c.timerM[2], c.timerM[3], c.timerM[4], c.timerM[5], c.timerM[6], c.timerM[7]);
					s += f;
				}
			}
			if(m_writesOn)
			{
				char w[200];
				std::snprintf(w, sizeof w, "                     non-zero writes into the ESAI-out ring X:0x8000-0x80ff: %llu%s\n",
					static_cast<unsigned long long>(c.ringNzWrites), c.ringNzWrites ? "" : " (NEVER)");
				s += w;
				if(c.ringNzWrites)
				{
					std::snprintf(w, sizeof w, "                     first at executed %llu: X:%#06x <- %06x\n",
						static_cast<unsigned long long>(c.ringFirstAt), c.ringFirstAddr, c.ringFirstVal);
					s += w;
				}
			}
			if(c.faulted)
			{
				s += "                     FAULT: " + c.why + "; last PCs:";
				const auto n = std::min<uint64_t>(c.pcRingPos, c.pcRing.size());
				for(uint64_t k = c.pcRingPos - n; k < c.pcRingPos; ++k)
				{
					std::snprintf(line, sizeof line, " %x", c.pcRing[k % c.pcRing.size()]);
					s += line;
				}
				s += "\n";
			}
		}
		return s;
	}
}
