#include "dsp.h"

#include <cstdio>
#include <algorithm>
#include <cstring>
#include <array>

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
		uint64_t rxFrames = 0, txFrames = 0;	// ESAI frames taken in (silence) / put out
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
			auto silence = [&c](uint64_t&, dsp56k::Audio::RxFrame& _f)
			{
				for(uint32_t i = 0; i < dsp56k::Audio::MaxSlotsPerFrame; ++i)
					for(auto& w : _f[i])
						w = 0;
				_f.resize(dsp56k::Audio::MaxSlotsPerFrame);
				++c.rxFrames;
			};
			auto sink = [&c](uint64_t&, const dsp56k::Audio::TxFrame& _f)
			{
				++c.txFrames;
				if(_f.size())
				{
					c.lastTx[0] = _f[0][0];
					c.lastTx[1] = _f[0][1];
				}
			};
			for(dsp56k::Esai* e : {&c.px->getEsai(), &c.py->getEsai()})
			{
				e->setReadRxCallback(silence);
				e->setWriteTxCallback(sink);
			}
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
		Core& c = cur();
		auto& h = c.hdi();
		if(h.hasTX())
		{
			c.lastRx = h.readTX();
			++c.wordsOut;
			note("rx", c.lastRx);
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
		m_sel = sel;
		return missing;
	}

	bool DspPair::runCoreUntil(const int _core, const std::function<bool()>& _ready, const uint64_t _budget)
	{
		Core& c = *m_cores[_core & 1];
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
			c.dsp->execInterpreter();
			c.dsp->doLoopEnd();
			++c.executed;
		}
		return _ready();
	}

	// -- the clock ------------------------------------------------------------

	void DspPair::tickInstructions(const uint64_t _n)
	{
		m_due += static_cast<double>(_n) * m_ratio;
		runDue();
	}

	void DspPair::tickSamples(const double _n)
	{
		m_due += _n * m_ips;
		runDue();
	}

	void DspPair::runDue()
	{
		for(int i = 0; i < 2; ++i)
		{
			Core& c = *m_cores[i];
			if(!c.boot->finished())
			{
				// Held in the bootstrap ROM until its last word lands; the
				// ROM's jump is the first instruction this core runs.
				if(static_cast<double>(c.executed) < m_due)
					c.executed = static_cast<uint64_t>(m_due);
				continue;
			}
			if(c.faulted)
			{
				c.executed = static_cast<uint64_t>(m_due);
				continue;
			}
			while(static_cast<double>(c.executed) < m_due)
			{
				const auto pc = c.dsp->getPC().toWord();
				c.pcRing[c.pcRingPos++ % c.pcRing.size()] = pc;
				if(pc >= g_pSize)
				{
					c.faulted = true;
					char msg[96];
					std::snprintf(msg, sizeof msg, "PC %#x is outside P memory (%#x words)", pc, g_pSize);
					c.why = msg;
					c.executed = static_cast<uint64_t>(m_due);
					break;
				}
				// The idle fast-forward (dsp.h): eight instructions in a row
				// inside a three-word window, no hardware loop open.
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
					const auto room = static_cast<uint64_t>(m_due - static_cast<double>(c.executed));
					const auto skipped = c.dsp->idleStep(room ? room : 1);
					c.executed += skipped;
					c.idleSkipped += skipped;
				}
				c.dsp->execInterpreter();
				c.dsp->doLoopEnd();
				++c.executed;
				if(m_traceEvery && c.executed >= c.nextTrace && m_trace.size() < 100000)
				{
					char line[256];
					std::snprintf(line, sizeof line,
						"core %d exec %llu dspctr %llu pc %06x sr %06x mode %d pending %d periph-target %llu esai in %llu out %llu SAISR %06x RCR %06x TCR %06x HSR %06x HCR %06x DCR2 %06x DCO2 %06x DSR2 %06x DSR3 %06x DDR3 %06x DCO3 %06x DCR3 %06x DDR0 %06x DCO0 %06x DCR0 %06x DSR1 %06x DCO1 %06x DCR1 %06x",
						i, static_cast<unsigned long long>(c.executed),
						static_cast<unsigned long long>(c.dsp->getInstructionCounter()), pc,
						c.dsp->regs().sr.var & 0xffffff,
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
			}
		}
	}

	// -- probes ---------------------------------------------------------------

	uint32_t DspPair::peekP(const int _core, const uint32_t _addr) const
	{
		return m_cores[_core & 1]->mem->get(dsp56k::MemArea_P, _addr);
	}
	uint32_t DspPair::peekX(const int _core, const uint32_t _addr) const
	{
		return m_cores[_core & 1]->mem->get(dsp56k::MemArea_X, _addr);
	}
	uint32_t DspPair::peekY(const int _core, const uint32_t _addr) const
	{
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

	std::string DspPair::report() const
	{
		std::string s;
		for(int i = 0; i < 2; ++i)
		{
			const Core& c = *m_cores[i];
			char line[512];
			std::snprintf(line, sizeof line,
				"             core %d: boot ROM %s (%u words -> P:%#07x), pc %#07x, %llu instructions, "
				"host words in %llu / out %llu, host commands %llu%s\n"
				"                     ESAI frames in %llu / out %llu, last out slot 0 = %06x %06x; idle-skipped %llu; mailbox sent %llu; read-back words %llu (%llu not in time)\n"
				"                     ESAI frames per host frame (0x8c to 0x8c): min %llu max %llu, exactly 16 on %llu of %llu; TCCR %06x (%u slots), %u instructions per slot\n",
				i, c.boot->finished() ? "done" : "WAITING", c.boot->getLength(), c.boot->getInitialPC(),
				c.dsp->getPC().toWord(), static_cast<unsigned long long>(c.executed),
				static_cast<unsigned long long>(c.wordsIn), static_cast<unsigned long long>(c.wordsOut),
				static_cast<unsigned long long>(c.commands),
				c.dropped ? " (words DROPPED on a full ring)" : "",
				static_cast<unsigned long long>(c.rxFrames), static_cast<unsigned long long>(c.txFrames),
				c.lastTx[0], c.lastTx[1], static_cast<unsigned long long>(c.idleSkipped),
				static_cast<unsigned long long>(m_mail[i].words),
				static_cast<unsigned long long>(c.pulled), static_cast<unsigned long long>(c.pullShort),
				static_cast<unsigned long long>(c.fpcSamples ? c.fpcMin : 0), static_cast<unsigned long long>(c.fpcMax),
				static_cast<unsigned long long>(c.fpcSixteen), static_cast<unsigned long long>(c.fpcSamples),
				c.px->read(0xffffb6, dsp56k::Nop), ((c.px->read(0xffffb6, dsp56k::Nop) >> 9) & 0x1f) + 1,
				c.esaiCyclesPerSlot);
			s += line;
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
