#include "dsp.h"

#include <cstdio>
#include <cstdlib>
#include <algorithm>
#include <cstring>
#include <array>
#include <chrono>
#include <cmath>
#include <map>
#include <thread>

#include <fcntl.h>
#include <sched.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

#include "dsp56kEmu/dsp.h"
#include "dsp56kEmu/dspBootCode.h"
#include "dsp56kEmu/esai.h"
#include "dsp56kEmu/esaiclock.h"
#include "dsp56kEmu/hdi08.h"
#include "dsp56kEmu/jit.h"
#include "dsp56kEmu/jitconfig.h"
#include "dsp56kEmu/memory.h"
#include "dsp56kEmu/peripherals.h"
#include "dsp56kBase/logging.h"
#include "dsp56kBase/threadtools.h"

namespace dsp56k
{
	void dspExecInterrupts(DSP* _dsp) noexcept;	// O17 diagnostic: the vendored interrupt-function names (dsp.cpp)
	void dspExecNop(DSP*) noexcept;
}

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
		// Payload A's DSR2 poll (P:0x4b..0x53: movep DSR2, cmp/beq x2, add #<$1,b, bra): the
		// head, and its length in instructions (rtWorker's poll fast-forward).
		constexpr uint32_t g_dsr2PollPc = 0x4b, g_dsr2PollLen = 7;
		constexpr uint32_t g_rtLoopWindow = 15;
		// Payload A's HTDE wait after the bank word (P:0x97, `brclr #HSR_HTDE,x:<<M_HSR,*`):
		// THE host wait -- the one poll whose end is the ColdFire's act (the take), so
		// its idle step is bounded by the poll lead, not the work lead (dsp.h).
		constexpr uint32_t g_htdeWaitPc = 0x97;

		// O17: the rt mode's knobs (OT_RT_*, diagnostics: the defaults are the mode)
		double envDouble(const char* _name, const double _default)
		{
			const char* e = std::getenv(_name);
			return e && *e ? std::atof(e) : _default;
		}
		double threadCpuSeconds()
		{
			timespec ts{};
			if(clock_gettime(CLOCK_THREAD_CPUTIME_ID, &ts))
				return 0.0;
			return static_cast<double>(ts.tv_sec) + static_cast<double>(ts.tv_nsec) * 1e-9;
		}
		inline void cpuRelax()
		{
#if defined(__aarch64__)
			__asm__ __volatile__("yield" ::: "memory");
#elif defined(__x86_64__)
			__asm__ __volatile__("pause" ::: "memory");
#endif
		}
		using Clock = std::chrono::steady_clock;
		double secondsSince(const Clock::time_point _t0) { return std::chrono::duration<double>(Clock::now() - _t0).count(); }
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
		// O17: the ESAI counters are written on the core's worker thread in the rt
		// mode and read by the ColdFire (cvrWrite's frames-per-command, rtstatus,
		// the report): relaxed atomics, a plain ++ in the lockstep modes.
		std::atomic<uint64_t> rxFrames{0}, txFrames{0};	// ESAI frames taken in (silence) / put out -- the X-side port
		std::atomic<uint64_t> rxFrames1{0}, txFrames1{0};	// the same for ESAI_1 on the Y side (❌ the two were summed until 8 Sep, and "frames per host frame" read double)
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
		std::atomic<uint64_t> slotCounter{0}; std::atomic<uint32_t> slotDsr2{0};	// O16c: the DSP counter and DSR2 at the last ESAI frame callback (a slot exec); O17: atomics, the guard experiment reads them across threads
		uint32_t lastPcLo = 0, lastPcHi = 0;	// the PC window of the last few instructions
		int windowRun = 0;
		std::atomic<uint32_t> lastTx[2]{{0}, {0}};		// slot 0 of the last output frame, TX0/TX1 (O17: the sink's thread writes, the report reads)
		// O9: the audio. Frames counted from the ESAI's first, the transport
		// start latched at the first 0x8c so a WAV can be trimmed to it.
		std::vector<int32_t> capture;
		std::atomic<bool> firstCmdSeen{false};			// O17: cvrWrite (ColdFire) sets, the ESAI input callback (worker) reads
		std::atomic<uint64_t> txAtFirstCmd{0}, rxAtFirstCmd{0};
		bool rotSeen = false; uint32_t rotMin = 0, rotMax = 0;	// ring-word rotation of the ESAI slot counter (O9c)
		std::array<uint64_t, DspPair::g_audioSlots> txNZ = {}, rxNZ = {};
		uint64_t surplus = 0, zeroDelta = 0;	// instruction-counter delta beyond one per interpreter call / calls that moved it not at all
		// O9b: bank id -> host take latency, in this core's instructions (4160 = one sample)
		uint64_t bankWriteAt = 0, bankTakeMax = 0, bankTakeSum = 0, bankTakes = 0, bankTakeMaxAt = 0, bankWritesInPull = 0;
		std::array<std::array<uint32_t, 1024>, 2> nzWrites = {};	// [X/Y][region of 256 words]: non-zero writes since the last flush
		uint64_t ringNzWrites = 0, ringFirstAt = 0;	// non-zero writes into the ESAI-out ring X:0x8000-0x80ff
		uint32_t ringFirstAddr = 0, ringFirstVal = 0;
		// The host-side registers this model keeps itself; the rest are
		// derived from the vendored HDI08 on every read.
		uint8_t icr = 0, ivr = 0x0f, txh = 0, txm = 0;
		std::atomic<uint8_t> cvr{0x32};		// O17: HC is cleared from the core's thread (the interrupt-taken hook)
		uint32_t lastRx = 0;		// the last word taken: RXH/RXM read it back
		std::atomic<bool> hcPending{false};
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
		std::array<uint64_t, 1024> vectorsTaken = {};	// O9b: interrupt vector -> count (every interrupt the vendored core took; O17: an array, the hook runs on the core's thread)
		uint64_t timerEnabledAt = 0; uint32_t timerTcsr = 0; std::array<uint32_t, 8> timerPcs = {}; std::array<uint32_t, 8> timerR = {}, timerM = {};	// the first moment TCSR0.TE is seen set, and the PCs before it
		uint64_t drainCmdAt = 0, drainFirstPop = 0, drainN = 0; size_t drainWords = 0; double drainFirstSum = 0.0, drainEmptySum = 0.0, drainWordsSum = 0.0;	// O17 diagnostic: the receive ring's drain after a host command, in the core's own instructions
		std::atomic<uint64_t> drainEmptyAt{0};	// the core's counter when its receive ring last became empty
		std::atomic<uint64_t> cmdKickDue{0}; uint64_t cmdLatN = 0; double cmdLatSum = 0.0, cmdLatMax = 0.0;	// O17 diagnostic: the frame command's latency (write -> taken), due units
		std::atomic<uint64_t> drainPushDue{0}; std::atomic<uint32_t> drainPushWords{0}, drainPushFirst{0};	// O17 diagnostic: the last eDMA push (the ColdFire's due count, its words) ...
		uint64_t pushN = 0; double pushFirstSum = 0.0, pushEmptySum = 0.0, pushWordsSum = 0.0;	// ... and the core's first pop / emptying after it, in executed units

		dsp56k::HDI08& hdi() { return px->getHDI08(); }
		const dsp56k::HDI08& hdi() const { return px->getHDI08(); }
	};

	void DspPair::memoryRanges(std::vector<std::pair<uint8_t*, size_t>>& _out) const
	{
		for(const auto& k : m_cores)
			for(const auto area : {dsp56k::MemArea_P, dsp56k::MemArea_X, dsp56k::MemArea_Y})
				_out.emplace_back(reinterpret_cast<uint8_t*>(k->mem->getMemAreaPtr(area)),
					static_cast<size_t>(0x1000000) * sizeof(dsp56k::TWord));
	}

	DspPair::DspPair(const double _ratio, const double _ips, const bool _rt)
		: m_ratio(_ratio), m_ips(_ips), m_shared(_rt ? 0 : g_shareHi - g_shareLo, 0)
	{
		m_rt = _rt;
		// The vendored library logs every ESAI register write and every
		// transmit underrun to stdout (3,260 lines over one boot). Off unless
		// asked: `setVerbose(true)` restores them.
		setVerbose(false);
		if(const char* e = std::getenv("OT_DSP_EDGELOG"); e && *e && *e != '0') m_edgeLog = true;	// O16c: one stderr line per bank write seen from a chunk (the guard's evidence)
		if(const char* e = std::getenv("OT_FENCE_TRACE"); e && *e && *e != '0') m_fenceTrace = true;	// O17b: the per-frame protocol on stderr
		if(const char* e = std::getenv("OT_DSP_FRAMETRACE"); e && *e && *e != '0') { m_frameTraceOn = true; refreshInstrumented(); }	// O17c: core 0's frame timeline on stderr (dsp.h)
		for(int i = 0; i < 2; ++i)
		{
			m_cores.emplace_back(new Core);
			Core& c = *m_cores.back();
			// The sizes `tools/harness/dsp_host` uses (the library's own tests').
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
			// O17: in the rt mode the window is one memory through the MMU
			// (rtSetup): the JIT reads and writes DSP memory through host
			// pointers, so a redirect inside Memory::get/set could not reach
			// it, and the cross-core opcode-cache hook would touch the other
			// core's JIT from this core's thread. The write hook is the
			// interpreter's too (the JIT writes memory directly): not installed.
			if(!m_rt)
			c.mem->setSharedWindow(g_shareLo, g_shareHi, m_shared.data(), [this](dsp56k::TWord _a)
			{
				for(auto& k : m_cores)
					k->dsp->clearOpcodeCache(_a);
			});
			if(!m_rt)
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
			// O17: with the cores on their own threads the read-back words
			// queue on the DSP's side (hdi08.h, setTransmitFifoDepth: the
			// DMA fills the FIFO in one peripheral service) instead of a
			// per-word round trip between the two threads; HTDE, the bit
			// the bank-word handshake polls, still reads "the host took
			// everything". Measured in the spike: without it the 768-word
			// read-back outlasted the frame and the protocol stopped.
			if(m_rt)
				c.hdi().setTransmitFifoDepth(1024);
			// HOST-STEPPED (tools/patches/dsp56300.patch): a hardware DO loop is stepped,
			// not run to completion in one call -- the firmware's 50-word loader
			// polls the host port INSIDE one (`dor`), and the ColdFire has to
			// run between its iterations -- and interrupts go through the
			// interpreter, not the JIT. ✅ Both measured 8 Sep 2026: a stack
			// sample of the first attempt sat in DSP::op_Dor_S -> do_exec ->
			// op_Brclr_pp forever; the second faulted in the JIT's funcCreate
			// on the first DSP interrupt (lldb, EXC_BAD_ACCESS).
			c.dsp->setHostStepped(!m_rt);
			if(m_rt)
			{
				// O17: two of O8's defects apply to a JIT core on its own
				// thread too, as flags of their own (the host-stepped mode
				// carries them for the interpreter): the peripheral service
				// under a masked interrupt (defect 3: core A boots with `ori
				// #3,mr`) and the DMA trigger on arming (defect 8: DMA2 is
				// armed with TDE already set; measured again under the JIT,
				// core 0 parked at P:0x4b with DSR2 never moving).
				c.dsp->setPeripheralsUnderMaskedInterrupt(true);
				c.dsp->setDmaTriggerOnArm(true);
			}
			// HC and HCP clear when the DSP TAKES the host command. ✅ Measured
			// 8 Sep 2026: watching for the PC to land on the vector never fired
			// -- a fast interrupt runs the vector's two words inline -- so the
			// frame handler polled HC forever and the sequencer ran 0 frames.
			c.dsp->setInterruptTakenHook([this, i](dsp56k::TWord _vba)
			{
				Core& k = *m_cores[i];
				++k.vectorsTaken[_vba & 1023];
				if(m_rt && i == 0 && _vba == 0x18)
				{
					// O17 diagnostic (OT_DSP_STATS, rt only): the drain of a pushed block, in the core's own time
					k.drainCmdAt = k.dsp->getInstructionCounter();
					k.drainFirstPop = 0;
					k.drainWords = k.hdi().rxData().size();
					// ... and the command's latency: the core's executed count at the take minus the ColdFire's due count at the write
					const double exec = static_cast<double>(k.drainCmdAt) + (m_rt ? static_cast<double>(m_rtc[0].offset.load(std::memory_order_relaxed)) : static_cast<double>(k.executed) - static_cast<double>(k.drainCmdAt));
					const double kick = static_cast<double>(k.cmdKickDue.load(std::memory_order_relaxed));
					if(kick > 0.0)
					{
						++k.cmdLatN;
						k.cmdLatSum += exec - kick;
						if(exec - kick > k.cmdLatMax) k.cmdLatMax = exec - kick;
					}
				}
				if(!k.hcPending.load(std::memory_order_acquire) || _vba != k.hcVector)
					return;
				k.hcPending.store(false, std::memory_order_release);
				k.cvr.fetch_and(0x7f);
				if(!m_rt)	// O17: HSR is the core's own register; the rt host side never raises HCP in it (see cvrWrite)
				{
					auto& h = k.hdi();
					h.writeStatusRegister(h.readStatusRegister() & ~(1u << dsp56k::HDI08::HSR_HCP));
				}
				noteFrom(i, "hc-taken", _vba);
			});
			// O17: THE BANK-WORD EDGE under the JIT. There is no per-instruction
			// step to see P:0x73 go by; instead every peripheral write made by
			// JIT code carries the PC of the instruction that made it (the
			// vendored Jitmem::storePcCurrentOp, tools/patches/dsp56300.patch),
			// and the HDI08's write callback fires on the core's thread inside
			// that write. A write of HOTX from P:0x73 on core 0 is the edge: an
			// atomic count the ColdFire's burst loop ends on (Rtos::runLoop,
			// Coprocessor::edgePending) and rtSync turns into the host-word
			// hook, on its own thread. Raised inside a read-back pull too, as
			// the interpreter's stepBody has it (the spike measured the stall
			// that dropping it caused: 3 frames).
			if(m_rt)
				c.hdi().setWriteTxCallback([this, &c, i]
				{
					if(i != 0 || c.dsp->getPcCurrentInstruction() != g_bankIdPc || !m_hookArmed.load(std::memory_order_acquire))
						return;
					if(m_pulling.load(std::memory_order_acquire))
					{
						++c.bankWritesInPull;
						m_edgesRaisedInPull.fetch_add(1, std::memory_order_relaxed);
					}
					// O17b: the edge's position is the DSP's own clock (executed
					// units); it goes on the ring, and THE FENCE CLOSES -- the next
					// bank word waits for the ColdFire to finish this frame.
					const uint64_t exec = c.dsp->getInstructionCounter() + m_rtc[0].offset.load(std::memory_order_relaxed);
					const uint32_t w = m_edgeW.load(std::memory_order_relaxed);
					if(w - m_edgeR.load(std::memory_order_relaxed) >= g_edgeRing)
					{
						m_edgesDropped.fetch_add(1, std::memory_order_relaxed);	// only without the fence, with the ColdFire a whole ring behind
						return;
					}
					m_edgeRing[w % g_edgeRing].store(exec, std::memory_order_relaxed);
					m_edgeGateSumI.fetch_add(static_cast<int64_t>(exec) - static_cast<int64_t>(m_rtDue.load(std::memory_order_relaxed)), std::memory_order_relaxed);
					m_fenceOpen.store(false, std::memory_order_release);
					m_bankTakePending.store(true, std::memory_order_relaxed);
					m_edgesRaised.fetch_add(1, std::memory_order_relaxed);
					if(m_skipArmed.load(std::memory_order_acquire))
						m_skipEdge.store(true, std::memory_order_release);	// the idle skip ends here (tickSamples)
					m_edgeW.store(w + 1, std::memory_order_release);
					if(m_fenceTrace)
						std::fprintf(stderr, "ftrace %.3f bank core0 exec=%llu fifo %zu (rt, fence closed)\n", static_cast<double>(exec) / g_dspIps, static_cast<unsigned long long>(exec), c.hdi().txData().size());
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
			// block landed in bank A (git show 3ceba41:docs/history/COLDFIRE_PORT.md O8, "the bank is the
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
				if((c.firstCmdSeen.load(std::memory_order_acquire) || m_inputFromBoot) && (m_tones || m_inputChannels))
				{
					const uint64_t n = m_inputFromBoot ? c.rxFrames.load(std::memory_order_relaxed) : c.rxFrames.load(std::memory_order_relaxed) - c.rxAtFirstCmd.load(std::memory_order_relaxed);
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
				c.rxFrames.fetch_add(1, std::memory_order_relaxed);
			};
			auto sink = [this, &c, i](uint64_t&, const dsp56k::Audio::TxFrame& _f)
			{
				c.txFrames.fetch_add(1, std::memory_order_relaxed);
				if(_f.size())
				{
					c.lastTx[0].store(_f[0][0], std::memory_order_relaxed);
					c.lastTx[1].store(_f[0][1], std::memory_order_relaxed);
				}
				// O9c: the ESAI's slot counter and the output DMA's ring index
				// are NOT in a fixed phase across runs (the tone on ring words
				// 2/4 came out on TX slots 1/3 in one run and 0/2 in another),
				// so count and keep the frame by RING WORD: DSR2 has just
				// delivered this frame's eight words, so slot s carried ring
				// word (DSR2 - 9 + s) mod 8 -- minus nine, not eight: the DMA has
				// already loaded the next frame's first word when this frame
				// completes (checked against a --dsp-peek of the ring: the
				// tone on ring words 2/4 reports as 2/4).
				const uint32_t dsr2 = c.px->read(0xffffe7, dsp56k::Nop);
				// O16c: the edge guard's grid point -- this callback runs inside
				// a slot exec, after that slot's DMA word (execTX: writeSlotToFrame
				// then writeTXimpl), so (counter, DSR2) here pin the slot cadence.
				c.slotCounter.store(c.dsp->getInstructionCounter(), std::memory_order_relaxed);
				c.slotDsr2.store(dsr2 & 0xffffff, std::memory_order_relaxed);
				const uint32_t rot = (dsr2 - 9) & 7;
				if(!c.rotSeen) { c.rotMin = c.rotMax = rot; c.rotSeen = true; }
				c.rotMin = std::min(c.rotMin, rot); c.rotMax = std::max(c.rotMax, rot);
				int32_t words[g_audioSlots];		// this frame by ring word, sign-extended (the pipe's ring takes the whole frame at once)
				if(m_rt && i == 0 && dsr2 >= 0x8000 && dsr2 <= 0x80ff)
				{
					// O17c diagnostic: the eight words the ESAI put out against the ring
					// words the DMA should have taken them from (the -9 rule): a
					// mismatch means the DMA2 -> TX0 -> slot path delivered something
					// other than the ring's content (rtstatus esaimism)
					const uint32_t* ring = c.mem->getMemAreaPtr(dsp56k::MemArea_X) + 0x8000;
					for(uint32_t s = 0; s < g_audioSlots && s < _f.size(); ++s)
					{
						const uint32_t rw = ring[(dsr2 - 9 + s) & 0xff] & 0xffffff;
						if(rw != (_f[s][0] & 0xffffff))
						{
							m_esaiMismatch.fetch_add(1, std::memory_order_relaxed);
							if(m_esaiMismatchLog.size() < 12)
							{
								char t[96];
								std::snprintf(t, sizeof t, "frame %llu slot %u dsr2 %06x ring %06x esai %06x", static_cast<unsigned long long>(c.txFrames.load(std::memory_order_relaxed)), s, dsr2, rw, _f[s][0] & 0xffffff);
								std::lock_guard<std::mutex> g(m_streamMx);
								m_esaiMismatchLog.emplace_back(t);
							}
						}
					}
					m_esaiChecked.fetch_add(1, std::memory_order_relaxed);
				}
				for(uint32_t ch = 0; ch < g_audioSlots; ++ch)
				{
					const uint32_t s = (ch - rot) & 7;
					const uint32_t w = s < _f.size() ? (_f[s][0] & 0xffffff) : 0;
					if(w)
						++c.txNZ[ch];
					words[ch] = static_cast<int32_t>(w << 8) >> 8;
					if(m_capture)
						c.capture.push_back(words[ch]);
				}
				if(i == 0)
				{
					// O23: the ring group (8-word sample, 0..31) the main pair (ch 2)
					// of this frame came from -- the -9 rule per slot, so a rotated
					// frame's pair is placed by ITS ring words, not the frame's
					// first -- names the half (group >> 4: 0 = X:0x8000-0x807f, the
					// bank-B mixdown; 1 = 0x8080-0x80ff, bank A) and the sample
					// (group & 15) whose stems the tap staged for it.
					const int group = static_cast<int>(((dsr2 - 9 + ((2 - rot) & 7)) & 0xff) >> 3);
					if(m_rt)
					{
						// O17: the pipe's ring is filled on this core's thread and
						// drained on the ColdFire's (takeAudioStream): one mutex.
						std::lock_guard<std::mutex> g(m_streamMx);
						if(m_streamMode != StreamMode::Off)
							streamPush(words, group);
					}
					else if(m_streamMode != StreamMode::Off)
						streamPush(words, group);
				}
			};
			auto silence1 = [&c](uint64_t&, dsp56k::Audio::RxFrame& _f)
			{
				for(uint32_t i = 0; i < dsp56k::Audio::MaxSlotsPerFrame; ++i)
					for(auto& w : _f[i])
						w = 0;
				_f.resize(dsp56k::Audio::MaxSlotsPerFrame);
				c.rxFrames1.fetch_add(1, std::memory_order_relaxed);
			};
			auto sink1 = [&c](uint64_t&, const dsp56k::Audio::TxFrame&) { c.txFrames1.fetch_add(1, std::memory_order_relaxed); };
			if(m_rt && i == 0)
				c.hdi().setReadRxCallback([this, &c]
				{
					// O17 diagnostic: a word popped from the receive ring (the DSP's DMA0 or a HORX read)
					const auto now = c.dsp->getInstructionCounter();
					if(const auto pushDue = c.drainPushDue.load(std::memory_order_relaxed))
					{
						const double exec = static_cast<double>(now) + (m_rt ? static_cast<double>(m_rtc[0].offset.load(std::memory_order_relaxed)) : static_cast<double>(c.executed) - static_cast<double>(now));
						if(!c.drainPushFirst.load(std::memory_order_relaxed))
						{
							c.drainPushFirst.store(1, std::memory_order_relaxed);
							c.pushFirstSum += exec - static_cast<double>(pushDue);
						}
						if(!c.hdi().hasRXData())
						{
							++c.pushN;
							c.pushEmptySum += exec - static_cast<double>(pushDue);
							c.pushWordsSum += c.drainPushWords.load(std::memory_order_relaxed);
							c.drainPushDue.store(0, std::memory_order_relaxed);
						}
					}
					if(c.drainCmdAt && !c.drainFirstPop)
						c.drainFirstPop = now;
					if(!c.hdi().hasRXData())
						c.drainEmptyAt.store(now, std::memory_order_relaxed);
					if(!c.hdi().hasRXData() && c.drainCmdAt)
					{
						++c.drainN;
						c.drainFirstSum += static_cast<double>(c.drainFirstPop - c.drainCmdAt);
						c.drainEmptySum += static_cast<double>(now - c.drainCmdAt);
						c.drainWordsSum += static_cast<double>(c.drainWords);
						c.drainCmdAt = 0;
					}
				});
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
					// O17: `full` is the flag of a one-word SPSC channel between the
					// two worker threads (the data before the flag, release/acquire).
					switch(_a)
					{
					case 0xffffd3: _v = m_mail[i ^ 1].full.load(std::memory_order_acquire) ? 2u : 0u; return true;
					case 0xffffd4:
						_v = m_mail[i ^ 1].data;
						if(m_rt)	// O17c: the taking core's clock, for the sender's wait (rtWorker, THE WAITS)
							m_mail[i ^ 1].takenAt.store(m_cores[i]->dsp->getInstructionCounter() + m_rtc[i].offset.load(std::memory_order_relaxed), std::memory_order_relaxed);
						m_mail[i ^ 1].full.store(false, std::memory_order_release);
						return true;
					case 0xffffd6: _v = m_mail[i].full.load(std::memory_order_acquire) ? 2u : 0u; return true;
					case 0xffffd7: _v = m_mail[i].data; return true;
					default: return false;
					}
				},
				[this, i](dsp56k::TWord _a, dsp56k::TWord _v)
				{
					if(_a != 0xffffd7)
						return false;
					m_mail[i].data = _v & 0xffffff;
					if(m_rt)	// O17c: the sending core's clock, for the receiver's wait (rtWorker, THE WAITS)
						m_mail[i].sentAt.store(m_cores[i]->dsp->getInstructionCounter() + m_rtc[i].offset.load(std::memory_order_relaxed), std::memory_order_relaxed);
					m_mail[i].full.store(true, std::memory_order_release);
					++m_mail[i].words;
					noteFrom(i, "mail", _v & 0xffffff);
					return true;
				});
		}
		if(m_rt)
			m_rtOk = rtSetup();
	}

	// =====================================================================
	// O17 (12 Sep 2026): THE REAL-TIME MODE -- the two cores as JIT WORKERS ON
	// THE LOCKSTEP SCHEDULE (--dsp-rt; git show 666b6154:docs/firmware/COLDFIRE_PORT.md O17).
	//
	// THE PREMISE. The ColdFire stays the master of emulated time: every tick
	// books `m_due` exactly as O16c has it. What changes is WHO runs the
	// backlog: two worker threads, one per core, each under the vendored JIT,
	// each run to the due count on its own -- never past it -- instead of
	// runChunk on the ColdFire's thread. The touch points are O16c's (sync at
	// burst ends and exact steps, host-port read/write, the eDMA's push /
	// pull / ring gate, the idle skip, the probes); at each the due count is
	// POSTED (rtPost: one atomic store per core when it moved by a quantum),
	// and the ColdFire is held only when a core LAGS by more than m_rtLagMax
	// (rtWait: the lag is read, not waited for, at every touch point). The
	// asymmetry is the design: a core BEHIND the ColdFire's clock only makes
	// the host look faster to it (a word lands earlier in DSP time, a command
	// is taken earlier), which the firmware's protocol lives with (the
	// hardware host is faster than this model); a core AHEAD of it is what
	// broke the spike (a bank word inside a read-back pull), and the target
	// forbids it by construction.
	//
	// THE EDGE. Core 0's bank word (P:0x73 -> HOTX, the frame interrupt) is
	// identified on the worker by the writing PC (the vendored JIT stores it
	// before every peripheral write) and raised as an atomic count; the
	// ColdFire's burst loop ends on it (Coprocessor::edgePending) and rtSync
	// applies the host-word hook on the ColdFire's thread. So the edge is
	// seen where the worker raised it plus the handoff latency (~100 ns of
	// wall = a few ColdFire instructions) plus the core's lag at that
	// moment -- normally nil, at most m_rtLagMax. O16c's edge guard (exact
	// ticking three slots before the boundary) is NOT the default here: its
	// per-tick rendezvous is measured by OT_RT_GUARD=1 (rtTickInstructions),
	// and the lateness it would remove is recorded per edge (rtstatus
	// edgelate) so the trade is a number, not a guess.
	//
	// THE TWO CORES meet through the mailbox and the shared window inside a
	// frame (core 0 hands core 1 its work at P:0x74 and waits for it at
	// P:0xa3); a core running far ahead of the other in wall time would
	// spend its budget spinning on it, so each worker holds itself within
	// m_rtSkew instructions of the other (rtSkewWait) -- lockstep's
	// interleave, in wall-time form -- and a read-back pull, which runs its
	// core past the due count until the word is there, is followed by the
	// other core to the same point (lockstep's runCoreUntil steps both).
	//
	// THE POLLS. Core 0 spends most of its frame polling HTDE (P:0x97, the
	// host taking its bank word) and DSR2 (P:0x4b); under the JIT each poll
	// is a peripheral read through C++ (~200 MIPS, against the 183.5 that
	// real time needs). A worker that re-enters the same three-word window
	// eight times with no DO loop open and nothing pending fast-forwards to
	// its next peripheral event (DSP::idleStep -- the interpreter's idle step
	// of O8, JIT edition) and then executes the poll once, so an idle core
	// costs its ESAI and DMA work and little else.
	//
	// WHAT IS NOT LOCKSTEP'S: the edge lateness above, the interleave
	// within the skew, the poll fast-forward's peripheral-interval grain, the
	// host command taken at the next peripheral service (up to 32
	// instructions) instead of the next instruction, the FIFO read-back. The
	// audio contract for this mode is functional (same onset within 16
	// samples, level within 1 dB, same content), not the Phase B bytes.
	//
	// O17c (13 Sep 2026): THE WAITS AND THE RENDEZVOUS. The bytes were not
	// the lockstep bytes because the DSP's clock at the points where it waits
	// for the host or the other core, and the ColdFire's clock at the points
	// where it waits for the DSP, were wherever the wall left them. Now: a
	// wait's fast-forward never passes the other party's clock and its exit
	// lands on the event's clock (THE WAITS), the ColdFire holds its own clock
	// at the bank take, the command poll and the drain gate until the worker
	// has answered (THE RENDEZVOUS AT THE TAKE, THE COMMAND RENDEZVOUS, THE
	// GATE WAITS FOR THE DRAIN), the boot is exact (THE EXACT BOOT: the DSP's
	// frame phase against the RTOS clock is lockstep's), and the frame
	// handler's pushes complete at the lockstep interpreter's drain times
	// (rtos.cpp THE DRAIN TIMES). On the clean fixture the rt capture is
	// bit-identical to the lockstep capture (docs O17c).
	// =====================================================================

	bool DspPair::rtSetup()
	{
		// The knobs (diagnostics; the defaults are the mode). OT_RT_LAG: how
		// far a core may lag the due count before the ColdFire waits for it
		// (DSP instructions; 4160 = one sample). OT_RT_SKEW: how far one core
		// may run ahead of the other. OT_RT_POSTQ: the due count is re-posted
		// when it moved by this much. OT_RT_CHECKQ: the lag is checked when it
		// moved by this much. OT_RT_TICKPOST: the boot's post interval in
		// ticks. OT_RT_SPIN_US: a worker spins this long on an empty target
		// before it parks. OT_RT_FF=0: no poll fast-forward. OT_RT_GUARD=1: the
		// O16c edge guard as a per-tick rendezvous (the measurement).
		// OT_RT_DOITER: the JIT's maxDoIterations (0 = a DO loop runs inside
		// its block).
		m_rtLagMax = static_cast<uint64_t>(envDouble("OT_RT_LAG", 4160.0));
		{
			// O17b: the lead is a whole frame by default (OT_RT_LEAD=frame, or a
			// number in DSP instructions): the fence below, not the lead, keeps
			// the frame protocol in order, so the cores may run a frame ahead.
			const char* e = std::getenv("OT_RT_LEAD");
			const double frame = 16.0 * m_ips;
			m_rtLead = static_cast<uint64_t>(!e || !*e || !std::strcmp(e, "frame") ? frame : std::atof(e));
		}
		m_fence = envDouble("OT_RT_FENCE", 1.0) != 0.0;
		// O17c: THE HOST WAIT KEEPS THE COLDFIRE'S CLOCK. The poll lead is 0: core
		// 0's clock at P:0x97 never runs past the ColdFire's, and when the host
		// acts (the bank take, the end of a pull) the worker brings its clock up
		// to the exact count of that act before the poll runs (rtWorker, THE
		// HOST-WAIT CATCH-UP) -- lockstep's timing of the take, which the frame's
		// ring write depends on (measured 13 Sep 2026: the DSP saw the take at
		// E+0..2.2 samples of its own clock with the 2-sample lead, wrote the
		// audio ring after DMA2 had entered the half, and the first sample of
		// the block came out stale; docs O17c). The knob stays for the measurement.
		m_rtPollLead = static_cast<uint64_t>(envDouble("OT_RT_POLLLEAD", 0.0));
		// O17c: THE EXACT BOOT (OT_RT_BOOTEXACT=0 to switch it off, for the
		// measurement). Until the ColdFire's frame clock is on, the workers run
		// with no lead and every host-port read is a rendezvous at the exact
		// count: the ColdFire's boot polls the DSP for every word of the
		// upload, so the number of instructions its boot takes -- which is the
		// DSP's clock at the RTOS handoff, i.e. the phase of the DSP's frames
		// against the RTOS's own clock -- was wall-time-dependent (measured 13
		// Sep 2026: 3213-3329 samples per run against lockstep's 2877.39), and
		// the sequencer's microtiming of a voice against the frame grid with it
		// (a second voice 7 samples off the reference; docs O17c).
		m_rtBootExact = envDouble("OT_RT_BOOTEXACT", 1.0) != 0.0;
		m_rtPollHist = envDouble("OT_RT_POLLHIST", 0.0) != 0.0;
		m_rtBulk = envDouble("OT_RT_BULK", 1.0) != 0.0;
		m_rtWaitLog = envDouble("OT_RT_WAITLOG", 0.0) != 0.0;
		m_rtSkew = static_cast<uint64_t>(envDouble("OT_RT_SKEW", 512.0));
		m_rtPostQuantum = static_cast<uint64_t>(envDouble("OT_RT_POSTQ", 4160.0));
		m_rtCheckQuantum = static_cast<uint64_t>(envDouble("OT_RT_CHECKQ", 512.0));
		m_rtTickPost = static_cast<uint64_t>(envDouble("OT_RT_TICKPOST", 512.0));
		m_rtSpinUs = envDouble("OT_RT_SPIN_US", 200.0);
		m_rtReadQuantum = static_cast<uint64_t>(envDouble("OT_RT_READQ", 4160.0));
		m_rtReadWait = envDouble("OT_RT_READWAIT", 0.0) != 0.0;
		m_rtFastForward = envDouble("OT_RT_FF", 1.0) != 0.0;
		m_rtGuard = envDouble("OT_RT_GUARD", 0.0) != 0.0;
		// O17b: a DO loop yields its block every 64 iterations (the vendored
		// JIT's time slice for interrupts and peripherals) so a host command
		// or a pushed block is served within a few microseconds however long
		// the effect's loop is -- the gated eDMA completions the frame handler
		// assumes prompt (below, THE STALL) need the core to answer inside a
		// fraction of a sample; measured 13 Sep 2026 at 64: 1033 emulated ms
		// per wall s against 993-1016 with the loops unbounded.
		m_rtDoIter = static_cast<uint32_t>(envDouble("OT_RT_DOITER", 64.0));
		m_rtTraceOn = envDouble("OT_RT_TRACE", 0.0) != 0.0;
		if(m_rtPostQuantum == 0) m_rtPostQuantum = 1;
		if(m_rtCheckQuantum == 0) m_rtCheckQuantum = 1;
		if(m_rtTickPost == 0) m_rtTickPost = 1;
		m_edgeGuard = 1e300;
		m_edgeWindowEnd = m_rtGuard ? 0.0 : 1e300;

		// 1. THE SHARED WINDOW, ONE MEMORY, SIX VIEWS. The vendored Memory is
		// MMU-backed (MemoryBuffer: every area is a fixed mapping of one
		// backing store), so the window's pages in each of the six views (2
		// cores x P/X/Y) are replaced by one 256 KB shm object mapped six
		// times -- the JIT's host pointers then alias the way the chip's bus
		// does (CHIP.md, measured on hardware; O8 for why the firmware needs
		// it). Refused when the memory is not MMU-backed: nothing else
		// reaches the JIT's pointers.
		for(auto& k : m_cores)
			if(!k->mem->hasMmuSupport())
			{
				m_rtWhy = "the vendored DSP memory is not MMU-backed on this host";
				return false;
			}
		const size_t bytes = static_cast<size_t>(g_shareHi - g_shareLo) * sizeof(dsp56k::TWord);
		const size_t off = static_cast<size_t>(g_shareLo) * sizeof(dsp56k::TWord);
		char name[64];
		std::snprintf(name, sizeof name, "/ot_emu_win_%d_%p", static_cast<int>(getpid()), static_cast<void*>(this));
		m_shmFd = shm_open(name, O_RDWR | O_CREAT | O_EXCL, 0600);
		if(m_shmFd < 0)
		{
			m_rtWhy = "shm_open failed";
			return false;
		}
		shm_unlink(name);
		if(ftruncate(m_shmFd, static_cast<off_t>(bytes)))
		{
			m_rtWhy = "ftruncate failed";
			return false;
		}
		for(int i = 0; i < 2; ++i)
			for(const auto area : {dsp56k::MemArea_P, dsp56k::MemArea_X, dsp56k::MemArea_Y})
			{
				auto* base = reinterpret_cast<uint8_t*>(m_cores[i]->mem->getMemAreaPtr(area));
				void* target = base + off;
				void* p = mmap(target, bytes, PROT_READ | PROT_WRITE, MAP_SHARED | MAP_FIXED, m_shmFd, 0);
				if(p != target)
				{
					m_rtWhy = "mmap MAP_FIXED of the window view failed";
					return false;
				}
			}
		m_sharedPtr = m_cores[0]->mem->getMemAreaPtr(dsp56k::MemArea_X) + g_shareLo;
		{
			// The alias, checked the way CHIP.md checked it on hardware: a word
			// written through one view reads back through every other, and
			// the words beside the window stay private.
			auto* p0 = m_cores[0]->mem->getMemAreaPtr(dsp56k::MemArea_P) + g_shareLo;
			auto* y1 = m_cores[1]->mem->getMemAreaPtr(dsp56k::MemArea_Y) + g_shareLo;
			auto* x1 = m_cores[1]->mem->getMemAreaPtr(dsp56k::MemArea_X) + g_shareHi - 1;
			p0[0] = 0x123456; m_sharedPtr[g_shareHi - g_shareLo - 1] = 0xabcdef;
			const bool ok = y1[0] == 0x123456 && m_sharedPtr[0] == 0x123456 && x1[0] == 0xabcdef
				&& m_cores[0]->mem->get(dsp56k::MemArea_Y, g_shareLo) == 0x123456 && m_cores[1]->mem->get(dsp56k::MemArea_P, g_shareHi - 1) == 0xabcdef
				&& m_cores[1]->mem->get(dsp56k::MemArea_P, g_shareLo - 1) == 0 && m_cores[0]->mem->get(dsp56k::MemArea_X, g_shareHi) == 0;
			p0[0] = 0; m_sharedPtr[g_shareHi - g_shareLo - 1] = 0;
			if(!ok)
			{
				m_rtWhy = "the six views of the window do not alias";
				return false;
			}
		}

		// 2. THE JIT. Dynamic peripheral addressing on (a register-indirect
		// access that lands in the peripheral space goes to the peripherals,
		// as the interpreter has it); the optimizer off (its constant folding
		// took 30-52 ms and 512 KB of stack on one block of this firmware:
		// the spike's crash reports); and THE DISPATCHER LIVES IN THE VECTOR
		// AREA: payload A's main loop is at P:0x40-0xaf and payload B's at
		// P:0x57.., inside the interrupt vectors, reached by a plain `jmp`
		// from the entry at P:0x30013 -- the JIT compiles every block below
		// Vba_End as a two-word fast interrupt that returns to the
		// interrupted PC, so `move #>$8000,b` at P:0x40 ran forever (the
		// spike, 340 MIPS with the PC never moving). dynamicFastInterrupts
		// is the library's own switch for firmware that runs code there,
		// with the pushPCSR fix in the vendored patch (a `jsr` from such a
		// block pushed the interrupted PC and re-entered its routine forever).
		for(auto& k : m_cores)
		{
			auto cfg = k->dsp->getJit().getConfig();
			cfg.dynamicPeripheralAddressing = true;
			cfg.dynamicFastInterrupts = true;
			cfg.enableOptimizer = false;
			cfg.maxDoIterations = m_rtDoIter;
			cfg.linkJitBlocks = envDouble("OT_RT_LINK", 1.0) != 0.0;
			cfg.maxInstructionsPerBlock = static_cast<uint32_t>(envDouble("OT_RT_MAXINSTR", 0.0));
			cfg.cacheSingleOpBlocks = true;
			k->dsp->getJit().setConfig(cfg);
			// THE FUNCTION TABLE COVERS ALL OF P. The JIT's table of entry
			// points grows only with the P addresses THIS core writes; core
			// 1's entry P:0x38000 is written by core 0 through the window
			// (O8), so core 1 jumped into an empty table (the spike's first
			// crash: a null call on the DSP core 1 thread). Size it to the
			// whole P memory once, here, before any block exists: the
			// emitted code holds the table's address.
			k->dsp->getJit().notifyProgramMemWrite(g_pSize - 1);
		}
		// O17b: THE FENCE needs core 0 back in its worker loop right before the
		// bank-word write: a volatile P address is never linked as a child
		// block and every block stops before it (the vendored patch's
		// Jit::addVolatileP), so P:0x73 is always entered from rtWorker.
		if(m_fence)
			m_cores[0]->dsp->getJit().addVolatileP(g_bankIdPc);
		// ... and at the head of its DSR2 poll (P:0x4b): the poll fast-forward
		// must fire at the head, before the `movep DSR2` read -- an idle step
		// after the read would compare a stale value and miss the one-word
		// boundary window -- and the JIT links the loop's `bra` straight into
		// the head, so the worker never saw it (measured 13 Sep 2026: the
		// DSR2 poll was executed, ~30k instructions a frame at ~200 MIPS).
		if(envDouble("OT_RT_DSR2FF", 1.0) != 0.0)	// diagnostic: 0 = the DSR2 poll executed, as O17 had it
			m_cores[0]->dsp->getJit().addVolatileP(g_dsr2PollPc);
		// O17c: THE WAITS' exits are block entries (rtWorker catches the core's
		// clock up to the event there): the blocks after the polls
		m_cores[0]->dsp->getJit().addVolatileP(0x99);
		m_cores[0]->dsp->getJit().addVolatileP(0xa5);
		m_cores[1]->dsp->getJit().addVolatileP(0x59);
		m_cores[1]->dsp->getJit().addVolatileP(0x8f);
		// O23: THE STEM TAP's block entry (rtWorker): the instruction after the
		// mixdown's loop on either path (`bra` from P:0x291, the fall-through
		// from P:0x2d3) -- one more block boundary a frame, always
		m_cores[0]->dsp->getJit().addVolatileP(g_stemTapPc);
		if(m_frameTraceOn)
		{
			// O17c diagnostic: the output stage's head and tail as block entries, so the frame trace sees them
			m_cores[0]->dsp->getJit().addVolatileP(0x1cb);
			m_cores[0]->dsp->getJit().addVolatileP(0x205);
		}

		// 3. THE THREADS. Each waits for its boot ROM to finish (sendWord says
		// so), then runs execJit() to the posted targets until told to stop.
		// pthread, not std::thread: the JIT compiles blocks on the core's
		// thread and its emitter recursed past std::thread's 512 KB in the
		// spike (a stack-guard SIGBUS on core 1); 16 MB, as the main thread's 8.
		for(int i = 0; i < 2; ++i)
		{
			pthread_attr_t attr;
			pthread_attr_init(&attr);
			pthread_attr_setstacksize(&attr, static_cast<size_t>(16) << 20);
			auto* arg = new std::pair<DspPair*, int>(this, i);
			if(pthread_create(&m_rtc[i].thread, &attr, [](void* _a) -> void*
				{
					auto* a = static_cast<std::pair<DspPair*, int>*>(_a);
					a->first->rtWorker(a->second);
					delete a;
					return nullptr;
				}, arg))
			{
				delete arg;
				pthread_attr_destroy(&attr);
				m_rtWhy = "pthread_create failed";
				return false;
			}
			pthread_attr_destroy(&attr);
			m_rtc[i].started = true;
		}
		return true;
	}

	void DspPair::rtFault(const int _i, const char* _why)
	{
		Core& c = *m_cores[_i];
		RtCore& r = m_rtc[_i];
		if(r.faulted.load(std::memory_order_acquire))
			return;
		c.why = _why;
		r.faulted.store(true, std::memory_order_release);
	}

	// The per-core thread. Idle = at the posted target (or the pull's word is
	// there, or the skip's edge fired): publish the counter, spin m_rtSpinUs,
	// then park on the condition variable until a post wakes it. Work = run
	// one block (execJit: the peripheral service, then the block and any
	// linked children), with the poll fast-forward before it when the window
	// rule holds, and the skew bound against the other core every g_rtPublish
	// instructions. Every cross-thread value is an atomic in RtCore.
	//
	// O17b -- THE FENCE AND THE SERVICE. Core 0 is held in this loop right
	// before its bank-word write (P:0x73, a volatile P address: never entered
	// from a linked block) while the fence is closed, i.e. until the ColdFire
	// has finished the previous frame's whole host-port exchange
	// (frameHandled: INTC0 source 1 unmasked). A held or idle core still
	// SERVES the host: a host command (kick), pushed words (svc) or a pull
	// (pred) runs its interrupt handlers through their rti and its
	// peripheral service (the host DMA's drain and FIFO fill) with the main
	// line stopped where it is (rtService) -- the chip's DMA and interrupts
	// run beside the core, and nothing the handlers do depends on the main
	// line's progress. A fenced core's clock is frozen (its ESAI does not
	// tick), so the DSP's own timeline is unchanged by the hold; only wall
	// time passes.
	void DspPair::rtWorker(const int _i)
	{
		dsp56k::ThreadTools::setCurrentThreadName(_i ? "DSP core 1" : "DSP core 0");
		if(envDouble("OT_RT_WORKER_QOS", 1.0) != 0.0)	// diagnostic: 0 = the default class (measuring the scheduling band's effect)
			dsp56k::ThreadTools::setCurrentThreadPriority(dsp56k::ThreadPriority::High);
		RtCore& r = m_rtc[_i];
		RtCore& o = m_rtc[_i ^ 1];
		Core& c = *m_cores[_i];
		auto& dsp = *c.dsp;
		while(!m_stop.load(std::memory_order_acquire) && !m_bootDone[_i].load(std::memory_order_acquire))
		{
			std::unique_lock<std::mutex> lk(r.mx);
			if(!m_bootDone[_i].load(std::memory_order_acquire) && !m_stop.load(std::memory_order_acquire))
				r.cv.wait_for(lk, std::chrono::milliseconds(1));
		}
		if(m_stop.load(std::memory_order_acquire))
			return;
		const uint64_t off = r.offset.load(std::memory_order_acquire);
		uint64_t lastPub = ~0ull, lastSkew = 0, blocks = 0;
		uint64_t statCtr = dsp.getInstructionCounter(), statSkipped = 0, statBlocks = 0;
		uint64_t spins = 0;
		uint32_t last = ~0u, prevPc = ~0u;	// prevPc: the entry PC of the last block executed (O17c, THE WAITS)
		uint64_t lastStemTap = ~0ull;		// O23: the counter at the last stem tap (one per arrival at P:0x2d5)
		int run = 0, same = 0;
		auto tStat = Clock::now(), tSpin = tStat, tState = tStat;
		// the wall-time split: 0 busy (executing blocks or a service), 1 idle at
		// the target (spinning, then parked), 2 fenced
		int state = 1;
		double stateS[3] = {0.0, 0.0, 0.0};
		bool wasIdle = true;
		const double cpu0 = threadCpuSeconds();
		const auto enter = [&](const int _state)
		{
			if(_state == state)
				return;
			const auto now = Clock::now();
			stateS[state] += std::chrono::duration<double>(now - tState).count();
			tState = now;
			state = _state;
		};
		const auto publishRegs = [&]
		{
			// the core's registers for rtstatus (RtCore: the ColdFire reads the atomics, never the core)
			r.hsr.store(c.hdi().peekStatusRegister() & 0xff, std::memory_order_relaxed);
			r.hpcr.store(c.hdi().readPortControlRegister() & 0xff, std::memory_order_relaxed);
			r.tgt.store(static_cast<int64_t>(dsp.getPeriph(0)->getTargetClock()) - static_cast<int64_t>(dsp.getInstructionCounter()), std::memory_order_relaxed);
			r.tcr.store(c.px->read(0xffffb5, dsp56k::Nop) & 0xffffff, std::memory_order_relaxed);
			r.dcr2.store(c.px->read(0xffffe4, dsp56k::Nop) & 0xffffff, std::memory_order_relaxed);
			r.dsr2.store(c.px->read(0xffffe7, dsp56k::Nop) & 0xffffff, std::memory_order_relaxed);
			r.dco2.store(c.px->read(0xffffe5, dsp56k::Nop) & 0xffffff, std::memory_order_relaxed);
			r.ctr.store(dsp.getInstructionCounter(), std::memory_order_relaxed);
		};
		const auto publishStats = [&](const uint64_t _ctr)
		{
			const auto now = Clock::now();
			const double s = std::chrono::duration<double>(now - tStat).count();
			if(s < 0.25)
				return;
			const uint64_t skipped = r.skipped.load(std::memory_order_relaxed);
			r.mips.store(static_cast<double>(_ctr - statCtr) / s * 1e-6, std::memory_order_relaxed);
			r.xmips.store(static_cast<double>((_ctr - statCtr) - (skipped - statSkipped)) / s * 1e-6, std::memory_order_relaxed);
			double cur[3] = {stateS[0], stateS[1], stateS[2]};
			cur[state] += std::chrono::duration<double>(now - tState).count();
			r.busy.store((cur[0] - r.busyS.load(std::memory_order_relaxed)) / s, std::memory_order_relaxed);
			r.busyS.store(cur[0], std::memory_order_relaxed);
			r.idleS.store(cur[1], std::memory_order_relaxed);
			r.fenceS.store(cur[2], std::memory_order_relaxed);
			r.cpuS.store(threadCpuSeconds() - cpu0, std::memory_order_relaxed);
			r.blocks.store(blocks, std::memory_order_relaxed);
			r.pc.store(dsp.getPC().toWord(), std::memory_order_relaxed);
			statCtr = _ctr; statSkipped = skipped; statBlocks = blocks;
			tStat = now;
			publishRegs();
		};
		for(;;)
		{
			if(m_stop.load(std::memory_order_relaxed))
				break;
			const uint64_t ctr = dsp.getInstructionCounter();
			const uint32_t gen = m_rtGen.load(std::memory_order_acquire);
			const uint64_t dueNow = m_rtDue.load(std::memory_order_acquire);
			const uint64_t due = dueNow + ((m_rtBootExact && !m_frameOn.load(std::memory_order_relaxed)) ? 0 : m_rtLead);	// the LEAD (the file comment): executed work may run this far ahead; O17c: none before the frame clock (THE EXACT BOOT)
			uint64_t target = due > off ? due - off : 0;
			const uint64_t pollTarget = dueNow + m_rtPollLead > off ? dueNow + m_rtPollLead - off : 0;	// ... a poll's idle step only this far (THE POLL LEAD, dsp.h)
			const int pred = r.pred.load(std::memory_order_acquire);
			// the pull's follower: the other core runs past the due count until
			// its word is there, this one follows it (lockstep's runCoreUntil
			// steps the other core to the same point)
			const int pullCore = m_pullCore.load(std::memory_order_acquire);
			if(pullCore == (_i ^ 1))
			{
				const uint64_t oExec = o.reached.load(std::memory_order_acquire) + o.offset.load(std::memory_order_relaxed);
				if(oExec > off && oExec - off > target)
					target = oExec - off;
			}
			if(r.kick.load(std::memory_order_acquire))
			{
				// a host command (cvrWrite): into the core's interrupt queue now,
				// taken at the next exec() -- the interpreter's next instruction
				r.kick.store(false, std::memory_order_relaxed);
				dsp.processExternalInterrupts();
			}
			const uint32_t pc = dsp.getPC().toWord();
			// O17c: THE WAITS. Three of payload A/B's polls wait for something
			// that is not on this core's own clock: core 0's HTDE wait after the
			// bank word (P:0x97: the host's take, and the end of its read-back
			// pull), core 0's wait for core 1 to take its mailbox word (P:0xa3)
			// and core 1's waits for core 0's two words (P:0x57, P:0x8d). Under
			// lockstep the waiting core's clock IS the other party's clock (the
			// ColdFire's count; the other core interleaved by the quantum), so it
			// leaves the wait at the event's clock. Here each such wait (1) is
			// fast-forwarded no further than the other party's clock (the posted
			// count for the host; the other core's published count plus the skew
			// for the mailbox) instead of the work lead, so the waiting core never
			// runs past the event, and (2) on its exit -- the block after the poll
			// -- the core's clock is brought UP to the event's clock through its
			// peripheral events (idleStep) if it is behind: the host's act posts
			// its exact count (m_hostEventAt, rxTake / pullHalfwords), the mailbox
			// hooks record the sending / taking core's clock (Mailbox::sentAt /
			// takenAt). ❌ Measured before this (13 Sep 2026): with a 2-sample poll
			// lead core 0 left P:0x97 at E+0..2.2 samples of its own clock for a
			// take at E+0.004, and with the work lead as the bound of P:0xa3 it left
			// the mailbox wait 3-24 samples late when core 1 sat idle at ITS lead
			// -- the frame's ring write then landed after DMA2 had entered the
			// half (the block's first samples came out stale, whole blocks on a
			// long wait), and a 24-sample wait skipped a frame and dried DMA2 (the
			// O17b stall). With the waits on the other party's clock the DSP's
			// frame timeline is lockstep's to within the burst grain.
			const bool hostWait = _i == 0 && pc == g_htdeWaitPc;
			const bool mailWait = _i == 0 ? pc == 0xa3 : (pc == 0x57 || pc == 0x8d);
			uint64_t waitBound = target;
			if(hostWait)
				waitBound = pollTarget;
			else if(mailWait && m_bootDone[_i ^ 1].load(std::memory_order_acquire) && !o.faulted.load(std::memory_order_relaxed))
			{
				const uint64_t oExec = o.reached.load(std::memory_order_acquire) + o.offset.load(std::memory_order_relaxed) + m_rtSkew;
				const uint64_t b = oExec > off ? oExec - off : 0;
				if(b < waitBound)
					waitBound = b;
			}
			if(m_rtFastForward && pc != prevPc && ((_i == 0 && ((pc == 0x99 && prevPc == g_htdeWaitPc) || (pc == 0xa5 && prevPc == 0xa3)))
				|| (_i == 1 && ((pc == 0x59 && prevPc == 0x57) || (pc == 0x8f && prevPc == 0x8d)))))
			{
				// the wait's exit: the event's clock, in this core's counter units
				const uint64_t ev = _i == 0 ? (pc == 0x99 ? m_hostEventAt.load(std::memory_order_acquire) : m_mail[0].takenAt.load(std::memory_order_acquire))
					: m_mail[0].sentAt.load(std::memory_order_acquire);
				const uint64_t tgt = ev > off ? ev - off : 0;
				uint64_t cu = dsp.getInstructionCounter();
				if(cu < tgt)
				{
					r.waitCatchUps.fetch_add(1, std::memory_order_relaxed);
					r.waitCatchUpSum.fetch_add(tgt - cu, std::memory_order_relaxed);
				}
				while(cu < tgt && !m_stop.load(std::memory_order_relaxed))
				{
					const auto skipped = dsp.idleStep(tgt - cu);
					r.skipped.fetch_add(skipped, std::memory_order_relaxed);
					cu = dsp.getInstructionCounter();
				}
				prevPc = pc;
				if(_i == 0 && pc == 0x99)
					m_takeSeen.store(true, std::memory_order_release);	// THE RENDEZVOUS AT THE TAKE (rxTake): the wait is left
			}
			// THE FENCE: core 0 at its bank-word write while the ColdFire is
			// still inside the previous frame's exchange
			const bool fenced = _i == 0 && m_fence && pc == g_bankIdPc && !m_fenceOpen.load(std::memory_order_acquire)
				&& (m_frameOn.load(std::memory_order_acquire) || m_inExchange.load(std::memory_order_acquire));
			bool work = ctr < target && !fenced;
			// THE POLL LEAD (dsp.h) / O17c THE WAITS: a wait at its bound waits for the other party's clock instead of burning its own
			// -- unless what it waits for is already there (the poll then exits: run it). ❌ Without the
			// exception core 1 sat idle at P:0x57 with its bound at core 0's clock while core 0 sat idle
			// at P:0xa3 with its bound at core 1's: the word was there and neither ran its poll (a 2 s
			// wait timeout, a faulted core, measured 13 Sep 2026).
			const bool waitDone = hostWait ? !c.hdi().hasTX() : (mailWait && (_i == 0 ? !m_mail[0].full.load(std::memory_order_acquire) : m_mail[0].full.load(std::memory_order_acquire)));
			if((hostWait || mailWait) && same >= 8 && ctr >= waitBound && m_rtFastForward && !waitDone)
				work = false;
			if(pred == 1 && !c.hdi().hasTX() && !fenced)
				work = true;
			if(r.faulted.load(std::memory_order_relaxed))
				work = false;
			if(m_skipArmed.load(std::memory_order_relaxed) && m_skipEdge.load(std::memory_order_acquire))
				work = false;
			if(!work)
			{
				// THE SERVICE: the host acted on a stopped core -- a command
				// (its interrupt is pending), pushed words (svc), a pull whose
				// word is not there (pred): run the handlers and the peripheral
				// service with the main line held at `pc`, then look again.
				if(!r.faulted.load(std::memory_order_relaxed)
					&& (r.svc.load(std::memory_order_acquire) || dsp.pendingInterruptCount() || (pred == 1 && !c.hdi().hasTX())))
				{
					enter(0);
					r.svc.store(false, std::memory_order_relaxed);
					rtService(_i, pc);
					same = 0;		// the poll's condition may have changed (HTDE after the take, a word in the ring): run it once before deciding it is still a poll
					run = 0;
					if(lastPub != dsp.getInstructionCounter())
					{
						r.reached.store(dsp.getInstructionCounter(), std::memory_order_release);
						lastPub = dsp.getInstructionCounter();
					}
					continue;
				}
				if(lastPub != ctr)
				{
					r.reached.store(ctr, std::memory_order_release);
					lastPub = ctr;
				}
				r.idleGen.store(gen, std::memory_order_release);
				if(!wasIdle || (fenced != r.fenced.load(std::memory_order_relaxed)))
				{
					if(!wasIdle)
					{
						wasIdle = true;
						tSpin = Clock::now();
						publishRegs();
						r.pc.store(dsp.getPC().toWord(), std::memory_order_relaxed);
						r.idle.store(true, std::memory_order_release);
						spins = 0;
					}
					if(fenced && !r.fenced.load(std::memory_order_relaxed))
						r.fenceWaits.fetch_add(1, std::memory_order_relaxed);
					r.fenced.store(fenced, std::memory_order_release);
					enter(fenced ? 2 : 1);
				}
				if((++spins & 63) == 0)
				{
					publishStats(ctr);
					const auto nowNs = std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now().time_since_epoch()).count();
					if(secondsSince(tSpin) * 1e6 >= m_rtSpinUs && nowNs - m_lastHostNs.load(std::memory_order_relaxed) > g_rtHostBusyNs)
					{
						// Park. The poster stores its target then loads `parked`
						// (both seq_cst); this thread stores `parked` then loads
						// the target under the lock (seq_cst): one of the two
						// sees the other's write, so a post is never lost. The
						// same protocol covers the fence's opening, a kick, a
						// push (svc) and a pull (pred).
						r.parked.store(true, std::memory_order_seq_cst);
						m_rtParked.store(true, std::memory_order_seq_cst);
						{
							std::unique_lock<std::mutex> lk(r.mx);
							const bool still = !m_stop.load(std::memory_order_seq_cst)
								&& !r.kick.load(std::memory_order_seq_cst)
								&& !r.svc.load(std::memory_order_seq_cst)
								&& m_rtGen.load(std::memory_order_seq_cst) == gen
								&& r.pred.load(std::memory_order_seq_cst) == pred
								&& m_pullCore.load(std::memory_order_seq_cst) == pullCore
								&& (!fenced || (!m_fenceOpen.load(std::memory_order_seq_cst) && (m_frameOn.load(std::memory_order_seq_cst) || m_inExchange.load(std::memory_order_seq_cst))));
							if(still)
								r.cv.wait_for(lk, std::chrono::milliseconds(2));
						}
						r.parked.store(false, std::memory_order_relaxed);
						m_rtParked.store(m_rtc[_i ^ 1].parked.load(std::memory_order_relaxed), std::memory_order_relaxed);
						tSpin = Clock::now();
						++r.parks;
					}
				}
				else
					cpuRelax();
				continue;
			}
			if(wasIdle)
			{
				wasIdle = false;
				r.idle.store(false, std::memory_order_relaxed);
				r.fenced.store(false, std::memory_order_relaxed);
			}
			enter(0);
			// the skew bound: hold this core within m_rtSkew of the other
			if(ctr - lastSkew >= g_rtPublish)
			{
				lastSkew = ctr;
				rtSkewWait(_i, ctr + off);
			}
			if(pc >= g_pSize)
			{
				// The JIT's table is sized to P; a PC past it would be a call
				// through garbage. Stop the core, keep the last PCs (the report).
				char msg[96];
				std::snprintf(msg, sizeof msg, "PC %#x is outside P memory (%#x words) (rt worker)", pc, g_pSize);
				c.why = msg;
				r.faulted.store(true, std::memory_order_release);
				continue;
			}
			c.pcRing[c.pcRingPos++ % c.pcRing.size()] = pc;
			// THE POLL FAST-FORWARD (the file comment). The interpreter's rule is
			// eight instructions inside a three-word window with no DO loop open
			// and nothing pending; on block entries that is eight re-entries at
			// the head of a loop whose blocks all start within g_rtLoopWindow
			// words of it (a two-word poll is one block re-entered; payload A's
			// DSR2 poll at P:0x4b-0x53 is three blocks per iteration, re-entered
			// at 0x4b -- the loop core 0 spends most of a frame in, which the
			// three-word rule never sees). A DSP56300 program loops with DO for
			// anything counted; a branch-back loop is a poll, and its condition
			// changes only at a peripheral event, which is exactly where the
			// idle step lands (then the poll runs once and sees it).
			// Two shapes: (1) the same block re-entered -- a one-instruction poll
			// (P:0x57, 0x8d, 0x97, 0xa3: `brclr/brset` on itself), the interpreter's
			// three-word window in block terms; (2) payload A's DSR2 poll, whose
			// three blocks re-enter at its head P:0x4b -- a known loop, the one
			// multi-block shape allowed (a counted branch-back loop of several
			// blocks could look the same and must not be skipped).
			if(pc == last)
				++same;
			else
			{
				same = 0;
				last = pc;
			}
			if(_i == 0 && pc == g_dsr2PollPc)
				++run;
			else if(_i == 0 && (pc < g_dsr2PollPc || pc > g_dsr2PollPc + g_rtLoopWindow))
				run = 0;
			if((same >= 8 || (run >= 8 && pc == g_dsr2PollPc)) && m_rtFastForward && pred == 0 && !(dsp.regs().sr.var & 0x8000) && !dsp.hasPendingInterrupts())
			{
				const uint64_t bound = waitBound;	// THE POLL LEAD / THE WAITS: a wait's idle step stops at the other party's clock; the DSP's own wait (the ring boundary, P:0x4b) runs to the work lead
				const uint64_t room = bound > ctr ? bound - ctr : 1;
				const auto skipped = dsp.idleStep(room);
				r.skipped.fetch_add(skipped, std::memory_order_relaxed);
				if(m_rtPollHist)
				{
					auto& h = m_pollHist[_i];
					auto it = std::find_if(h.begin(), h.end(), [pc](const auto& e) { return e.first == pc; });
					if(it == h.end()) h.emplace_back(pc, skipped); else it->second += skipped;
				}
				// Payload A's DSR2 poll counts its iterations in b1 (`add #<$1,b`
				// at P:0x52; the count goes to X:$3f80/$3f81 after the bank
				// word -- the DSP's own idle meter): the iterations skipped are
				// added, seven instructions each, so the meter reads what the
				// executed polls would have made it.
				if(_i == 0 && pc == g_dsr2PollPc)
					dsp.regs().b.var += static_cast<int64_t>(skipped / g_dsr2PollLen) << 24;
			}
			if(m_rtTraceOn && pred == 1 && m_rtTrace.size() < 4000)
			{
				// O17 diagnostic (OT_RT_TRACE=1): the pulled core's blocks while it runs past the due count for the read-back
				const auto f = dsp.getInterruptFunc();
				const char kind = f == dsp.getExecPeripheralsFunc() ? 'P' : f == &dsp56k::dspExecInterrupts ? 'I' : f == &dsp56k::dspExecNop ? 'N' : 'D';
				char line[112];
				std::snprintf(line, sizeof line, "PULL%d %llu pc=%06x mode=%d f=%c tgt=%lld txfifo=%zu rx=%zu past=%lld", _i,
					static_cast<unsigned long long>(ctr), pc, static_cast<int>(dsp.getProcessingMode()), kind,
					static_cast<long long>(static_cast<int64_t>(dsp.getPeriph(0)->getTargetClock()) - static_cast<int64_t>(ctr)), c.hdi().txData().size(), c.hdi().rxData().size(),
					static_cast<long long>(static_cast<int64_t>(ctr) - static_cast<int64_t>(target)));
				m_rtTrace.emplace_back(line);
			}
			if(_i == 0 && m_rtTraceOn && c.drainPushDue.load(std::memory_order_relaxed) && m_rtTrace.size() < 4000)
			{
				// O17 diagnostic (OT_RT_TRACE=1): core 0's blocks after an eDMA push -- PC, processing mode,
				// the interrupt function (P = peripherals, I = interrupts, N = nop / long interrupt, D = prevent),
				// the peripheral target clock minus the counter, the receive ring's size
				const auto f = dsp.getInterruptFunc();
				const char kind = f == dsp.getExecPeripheralsFunc() ? 'P' : f == &dsp56k::dspExecInterrupts ? 'I' : f == &dsp56k::dspExecNop ? 'N' : 'D';
				char line[96];
				std::snprintf(line, sizeof line, "%llu pc=%06x mode=%d f=%c tgt=%lld ring=%zu",
					static_cast<unsigned long long>(ctr - m_rtTraceCtr0), pc, static_cast<int>(dsp.getProcessingMode()), kind,
					static_cast<long long>(static_cast<int64_t>(dsp.getPeriph(0)->getTargetClock()) - static_cast<int64_t>(ctr)), c.hdi().rxData().size());
				m_rtTrace.emplace_back(line);
			}
			if(m_frameTraceOn)
				frameTraceLine(c, pc, ctr + off, static_cast<double>(dueNow));
			// O23: THE STEM TAP -- P:0x2d5 is a volatile P address on core 0 (rtSetup),
			// so the block after the mixdown is always entered here; once per
			// arrival (the counter moves between two arrivals, never within one)
			if(_i == 0 && pc == g_stemTapPc && ctr != lastStemTap && m_stemsOn.load(std::memory_order_acquire))
			{
				lastStemTap = ctr;
				stemTap(c);
			}
			dsp.exec();
			prevPc = pc;
			++blocks;
			const uint64_t ctr2 = dsp.getInstructionCounter();
			if(ctr2 - lastPub >= g_rtPublish || lastPub > ctr2)
			{
				r.reached.store(ctr2, std::memory_order_release);
				lastPub = ctr2;
			}
			if((blocks & 1023) == 0)
			{
				publishStats(ctr2);
			}
		}
		{
			const uint64_t ctr = dsp.getInstructionCounter();
			r.reached.store(ctr, std::memory_order_release);
			r.pc.store(dsp.getPC().toWord(), std::memory_order_relaxed);
			r.idle.store(true, std::memory_order_release);
			r.fenced.store(false, std::memory_order_release);
		}
	}

	// O17b: THE SERVICE -- the host's side of a stopped core. Every pending
	// interrupt (a host command moved in from the external queue) runs
	// through its handler to its rti with the main line held at `_pcHold`
	// (execInterrupts dispatches one vector through the JIT; a handler the
	// JIT returned from mid-way -- an unlinked block -- is finished by
	// exec() until the rti brings the PC back), then the peripheral service
	// (the vendored execPeripherals: the HDI08's receive DMA drains the
	// pushed words, its transmit DMA fills the FIFO for a pull, the ESAI and
	// the timers see the counter where it is) -- none of it advances the
	// core's clock beyond the handlers' own instructions.
	void DspPair::rtService(const int _i, const uint32_t _pcHold)
	{
		Core& c = *m_cores[_i];
		auto& dsp = *c.dsp;
		RtCore& r = m_rtc[_i];
		r.services.fetch_add(1, std::memory_order_relaxed);
		for(int round = 0; round < 64 && !m_stop.load(std::memory_order_relaxed); ++round)
		{
			dsp.processExternalInterrupts();
			const size_t n = dsp.pendingInterruptCount();
			if(!n)
				break;
			if(dsp.getProcessingMode() == dsp56k::DSP::DefaultPreventInterrupt)
				dsp.execDefaultPreventInterrupt();	// the previous handler's rti left it: normalise before the next dispatch
			if(dsp.getProcessingMode() != dsp56k::DSP::Default)
				break;
			dsp.execInterrupts();	// one interrupt: masked -> the peripherals only; else its vector through the JIT to its rti, or into the handler
			int guard = 0;
			while(!m_stop.load(std::memory_order_relaxed) && (dsp.getProcessingMode() == dsp56k::DSP::LongInterrupt || dsp.getPC().toWord() != _pcHold) && ++guard < 1000000)
				dsp.exec();
			if(dsp.getProcessingMode() == dsp56k::DSP::DefaultPreventInterrupt)
				dsp.execDefaultPreventInterrupt();
			r.svcInterrupts.fetch_add(1, std::memory_order_relaxed);
			if(dsp.pendingInterruptCount() == n)
				break;		// masked: it waits for the core's own mask, as the chip would
		}
		dsp.template execPeripherals<dsp56k::Peripherals56362, dsp56k::Peripherals56367>();
	}

	// Worker: the other core may be behind this one by at most m_rtSkew
	// (executed units, i.e. on the due count). A core still in its boot ROM is
	// at the due count (lockstep's `executed := limit`), a faulted one is
	// skipped, and a wait that outlasts 200 ms gives up and counts itself.
	void DspPair::rtSkewWait(const int _i, const uint64_t _myExec)
	{
		RtCore& r = m_rtc[_i];
		RtCore& o = m_rtc[_i ^ 1];
		if(!m_bootDone[_i ^ 1].load(std::memory_order_acquire) || o.faulted.load(std::memory_order_relaxed))
			return;
		const uint64_t oOff = o.offset.load(std::memory_order_relaxed);
		if(_myExec <= o.reached.load(std::memory_order_acquire) + oOff + m_rtSkew)
			return;
		r.skewWaits.fetch_add(1, std::memory_order_relaxed);
		const auto t0 = Clock::now();
		uint64_t spins = 0;
		while(_myExec > o.reached.load(std::memory_order_acquire) + oOff + m_rtSkew)
		{
			if(m_stop.load(std::memory_order_relaxed) || o.faulted.load(std::memory_order_relaxed))
				return;
			// The other core has nothing to run for the CURRENT post (it is at
			// its target, stopped at the idle skip's edge, or its pull's word
			// is there): it cannot come closer until the ColdFire posts again,
			// and this core will find the same stop at its loop top. A core
			// idle for an OLDER post has simply not seen the new one yet
			// (the poster stores the target, then bumps gen): wait for it.
			// ❌ Measured before this: core 0 stopped at a skip's edge, core 1
			// ahead of it waited the whole 200 ms, 728 times in one `run 250`.
			if(o.idleGen.load(std::memory_order_acquire) == m_rtGen.load(std::memory_order_acquire))
				return;
			if(o.fenced.load(std::memory_order_acquire))	// O17b: held by the ColdFire's frame, not by this core
				return;
			if(m_skipArmed.load(std::memory_order_relaxed) && m_skipEdge.load(std::memory_order_acquire))
				return;
			// O17b: the host is waiting on THIS core -- a command (kick), pushed
			// words (svc) or a pull (pred): serve it first (one block: the
			// dispatch, or the peripheral service at the block's entry), then
			// hold again. ❌ Measured without this: core 1, ahead of a core 0
			// that had just been frozen for its bank take, sat here through
			// the ColdFire's 0x89 and its read-back pull waited ~19 µs a
			// frame for the fill (pullword 0.246 s per 4 s of play).
			if(r.kick.load(std::memory_order_acquire) || r.svc.load(std::memory_order_acquire) || r.pred.load(std::memory_order_acquire) == 1)
				return;
			if((++spins & 255) == 0 && secondsSince(t0) > 0.2)
			{
				r.skewTimeouts.fetch_add(1, std::memory_order_relaxed);
				if(m_rtWaitLog)
					std::fprintf(stderr, "rtwaitlog skew timeout core%d at exec=%llu | other pc=%06x reached=%llu idle=%d fenced=%d idleGen=%u gen=%u parked=%d\n", _i,
						static_cast<unsigned long long>(_myExec), o.pc.load(), static_cast<unsigned long long>(o.reached.load() + oOff), o.idle.load() ? 1 : 0, o.fenced.load() ? 1 : 0,
						o.idleGen.load(), m_rtGen.load(), o.parked.load() ? 1 : 0);
				return;
			}
			cpuRelax();
		}
	}

	// ColdFire: publish the due count. One store per core when it moved by
	// the quantum (or forced), plus a wake when the worker has parked.
	// ColdFire: publish the due count -- ONE line both workers read (each
	// subtracts its own offset), one store and one generation bump, then a
	// wake for a parked worker. `_quantum` is the least move that is worth a
	// post (writes: m_rtPostQuantum; reads: m_rtReadQuantum; 0: always).
	void DspPair::rtPost(const uint64_t _quantum)
	{
		const uint64_t due = static_cast<uint64_t>(m_due);
		if(due == m_rtPosted)
			return;
		if(_quantum && due > m_rtPosted && due - m_rtPosted < _quantum)
			return;
		const auto t0 = Clock::now();	// O17b: the posts are a sample apart now (the quantum), cheap enough to time
		m_rtPosted = due;
		++m_rtPosts;
		m_rtDue.store(due, std::memory_order_relaxed);
		m_rtGen.fetch_add(1, std::memory_order_seq_cst);
		if(m_rtParked.load(std::memory_order_seq_cst))
			for(int i = 0; i < 2; ++i)
				if(m_rtc[i].parked.load(std::memory_order_seq_cst))
					rtWake(i);
		m_rtPostS += secondsSince(t0);
	}

	void DspPair::rtWake(const int _i)
	{
		RtCore& r = m_rtc[_i];
		std::lock_guard<std::mutex> lk(r.mx);
		r.cv.notify_one();
		++m_rtWakes;
	}

	// ColdFire: hold until every booted, unfaulted core is within `_slack`
	// instructions of its posted target (0 = at it: the worker publishes its
	// exact counter when it goes idle). Spins, then yields; a core that does
	// not get there in 2 s is faulted so the ColdFire never blocks for good.
	bool DspPair::rtWait(const uint64_t _slack, const int _core)
	{
		bool waited = false;
		Clock::time_point t0{};
		uint64_t spins = 0;
		for(;;)
		{
			bool ok = true;
			int lagging = -1;
			const uint64_t due = m_rtPosted;
			for(int i = 0; i < 2; ++i)
			{
				if(_core >= 0 && i != _core)
					continue;
				if(!m_bootDone[i].load(std::memory_order_relaxed))
					continue;
				RtCore& r = m_rtc[i];
				if(r.faulted.load(std::memory_order_acquire))
					continue;
				if(r.fenced.load(std::memory_order_acquire))
					continue;	// O17b: held before its bank-word write by the ColdFire's own frame -- it cannot come, and the ColdFire must go on to open it
				const uint64_t got = r.reached.load(std::memory_order_acquire) + r.offset.load(std::memory_order_relaxed);
				if(got + _slack < due)
				{
					ok = false;
					lagging = i;
					break;
				}
			}
			if(ok)
			{
				if(waited)
				{
					const double w = secondsSince(t0);
					m_rtWaitS += w;
					if(m_rtWaitLog && w > 0.005)
						std::fprintf(stderr, "rtwaitlog lag wait %.1f ms due=%.0f | core0 pc=%06x reached=%llu idle=%d fenced=%d | core1 pc=%06x reached=%llu idle=%d fenced=%d\n", w * 1e3, m_due,
							m_rtc[0].pc.load(), static_cast<unsigned long long>(m_rtc[0].reached.load() + m_rtc[0].offset.load()), m_rtc[0].idle.load() ? 1 : 0, m_rtc[0].fenced.load() ? 1 : 0,
							m_rtc[1].pc.load(), static_cast<unsigned long long>(m_rtc[1].reached.load() + m_rtc[1].offset.load()), m_rtc[1].idle.load() ? 1 : 0, m_rtc[1].fenced.load() ? 1 : 0);
				}
				return true;
			}
			if(!waited)
			{
				waited = true;
				++m_rtWaits;
				t0 = Clock::now();
			}
			if(m_stop.load(std::memory_order_relaxed))
				return false;
			if(++spins < 2048)
				cpuRelax();
			else
			{
				sched_yield();
				if((spins & 255) == 0 && secondsSince(t0) > 2.0)
				{
					++m_rtWaitTimeouts;
					m_rtWaitS += secondsSince(t0);
					rtFault(lagging, "the worker did not reach the due count within 2 s (rt wait)");
					return false;
				}
			}
		}
	}

	// The touch point. A write (a host word, a command, the eDMA's push) only
	// needs the cores never AHEAD of the due count, which the target
	// guarantees: post it (when it moved by the quantum) and bound the lag
	// (a read of the published counters when the due count moved by the
	// check quantum; a wait only past m_rtLagMax). A touch point that
	// OBSERVES the cores (a host-port read, the eDMA's drain gate) wants
	// what lockstep's catchUp gave it -- the cores at the due count: post the
	// exact count and wait for it (two atomic loads when they are there
	// already). ❌ Measured with the lag bound alone at the gate: the eDMA's
	// completion was refused on a ring the worker had not yet drained
	// because its target lagged the due count by up to the tick-post
	// interval, and the ColdFire stepped EXACTLY (~100 ns an instruction)
	// through 1218 DSP instructions per block instead of lockstep's 494 --
	// 48 M exact steps in 2 s of play, the gap between 330 and 1000
	// emulated ms per wall s.
	void DspPair::rtCatchUp(const bool _observe)
	{
		if(_observe)
		{
			// A read posts the count (the core it observes then runs to it) and,
			// with OT_RT_READWAIT=1, holds until that core is within the lead of
			// it; by default the lead is bounded at the burst ends only (rtSync,
			// every m_rtCheckQuantum), and a read sees the core as it is -- at
			// most the lead plus a check quantum behind the count, which only
			// makes a poll go round once more.
			if(m_rtBootExact && !m_frameOn.load(std::memory_order_relaxed))
			{
				// O17c: THE EXACT BOOT -- the observed core at the exact count, as
				// lockstep's catchUp has it (rtSetup says why)
				rtPost(0);
				++m_rtBootReads;
				if(rtWait(0, m_sel & 1))
					m_rtAtPosted = m_rtPosted;
				return;
			}
			rtPost(m_rtReadQuantum);
			if(!m_rtReadWait)
				return;
			if(m_rtAtPosted == m_rtPosted)
				return;
			if(rtWait(m_rtLagMax, m_sel & 1))
				m_rtAtPosted = m_rtPosted;
			return;
		}
		rtPost(m_rtPostQuantum);
		const uint64_t due = m_rtPosted;
		if(due - m_rtChecked < m_rtCheckQuantum)
			return;
		m_rtChecked = due;
		rtWait(m_rtLagMax);
	}

	// ColdFire: the host-word hook for every pending edge THE CLOCK HAS
	// REACHED (O17b: an edge produced ahead of the ColdFire's clock waits on
	// the ring until m_due reaches its executed count -- the frame interrupt
	// arrives at the sample the DSP's clock says, as under lockstep; the
	// lateness is then the burst's grain, and the DSP's lead at the raise is
	// recorded apart, rtstatus edgegate).
	void DspPair::rtApplyEdges(const bool _inSkip)
	{
		for(;;)
		{
			const uint32_t w = m_edgeW.load(std::memory_order_acquire);
			const uint32_t rd = m_edgeR.load(std::memory_order_relaxed);
			if(w == rd)
				return;
			const double e = static_cast<double>(m_edgeRing[rd % g_edgeRing].load(std::memory_order_relaxed));
			if(e > m_due)
				return;
			m_edgeR.store(rd + 1, std::memory_order_relaxed);
			const double late = m_due - e;
			if(late > 16.0 * m_ips)
				++m_rtEdgesStale;		// the boot's bank word, delivered where the frame clock came on (O9b): not a lateness of the schedule
			else if(_inSkip)
			{
				// the skip's own grain (whole samples), as lockstep's edges-in-idle-skips
				++m_rtSkipEdges;
				m_rtSkipEdgeLateSum += late;
				if(late > m_rtSkipEdgeLateMax) m_rtSkipEdgeLateMax = late;
			}
			else
			{
				++m_rtEdgeLateN;
				m_rtEdgeLateSum += late;
				if(late > m_rtEdgeLateMax) m_rtEdgeLateMax = late;
			}
			if(m_pulling.load(std::memory_order_relaxed))
				++m_rtEdgesInPull;
			m_edgeLastApplied = e;
			m_edgeSeen = true;
			++m_rtEdgesApplied;
			protoNote('e', 0, static_cast<uint32_t>(late));
			if(m_hostWordHook)
				m_hostWordHook(0);
		}
	}

	// ColdFire: the O16c edge prediction on the workers' published grid, for
	// the guard experiment only (OT_RT_GUARD=1; predictEdge's arithmetic with
	// the boot offset in place of executed - counter).
	void DspPair::rtPredictEdge()
	{
		++m_stats.predictions;
		Core& c = *m_cores[0];
		const double now = m_due;
		const double cps = static_cast<double>(c.esaiCyclesPerSlot);
		const double frame = cps * static_cast<double>(g_esaiSlots);
		m_edgeSeen = false;
		m_edgeGuard = 1e300;
		m_edgeWindowEnd = now + frame;
		if(!m_bootDone[0].load(std::memory_order_relaxed) || m_rtc[0].faulted.load(std::memory_order_relaxed) || !m_hostWordHook)
			return;
		const uint32_t dsr2 = c.slotDsr2.load(std::memory_order_relaxed);
		const uint64_t slotCounter = c.slotCounter.load(std::memory_order_relaxed);
		if(dsr2 < 0x8000 || dsr2 > 0x80ff || slotCounter == m_edgeSlot)
		{
			m_edgeSlot = slotCounter;
			return;
		}
		m_edgeSlot = slotCounter;
		const uint32_t w = dsr2 & 0xff;
		const uint32_t togo = w <= 0x70 ? 0x70 - w : w <= 0xf0 ? 0xf0 - w : 0x70 + 0x100 - w;
		const double tb = static_cast<double>(slotCounter) + static_cast<double>(togo) * cps + static_cast<double>(m_rtc[0].offset.load(std::memory_order_relaxed));
		if(tb + cps < now)
			return;
		m_edgeGuard = tb - 3.0 * cps;
		m_edgeWindowEnd = tb + cps + 256.0;
		++m_rtGuardWindows;
	}

	// The run loop's sync (every burst end and exact step): the edges first,
	// then the touch point.
	void DspPair::rtSync()
	{
		rtApplyEdges();
		if(m_rtGuard && (m_edgeSeen || m_due >= m_edgeWindowEnd))
			rtPredictEdge();
		rtCatchUp(false);
	}

	// ColdFire: executed / idle-skipped / faulted from the workers' published
	// counters (the lockstep fields the probes and the report read).
	void DspPair::rtRefresh()
	{
		for(int i = 0; i < 2; ++i)
		{
			Core& c = *m_cores[i];
			RtCore& r = m_rtc[i];
			if(m_bootDone[i].load(std::memory_order_acquire))
				c.executed = r.reached.load(std::memory_order_acquire) + r.offset.load(std::memory_order_relaxed);
			else
				c.executed = static_cast<uint64_t>(m_due);
			c.idleSkipped = r.skipped.load(std::memory_order_relaxed);
			if(r.faulted.load(std::memory_order_acquire))
				c.faulted = true;
		}
	}

	// The ColdFire's idle skip, whole samples. O17b: an edge the DSP has
	// already produced (its position on the ring) bounds the skip -- the
	// clock never runs past an edge the DSP has produced: at or behind it
	// the edge is delivered first (no skip); ahead of it the skip ends on
	// the sample boundary after the edge, where the edge is delivered. With
	// no edge yet, the whole skip is posted with the workers armed to stop
	// at the first bank-word edge inside it (m_skipArmed / m_skipEdge), and
	// the clock then lands on the sample boundary after that edge, as
	// lockstep's per-sample loop lands it.
	double DspPair::rtTickSamples(const double _n)
	{
		const double start = m_due;
		double lim = _n;
		{
			const uint32_t w = m_edgeW.load(std::memory_order_acquire);
			if(w != m_edgeR.load(std::memory_order_relaxed))
			{
				const double e = static_cast<double>(m_edgeRing[m_edgeR.load(std::memory_order_relaxed) % g_edgeRing].load(std::memory_order_relaxed));
				if(e <= start)
				{
					// an edge is already due: deliver it before skipping anything
					// (the loop's tickTimers/deliver take it from here)
					rtApplyEdges(true);
					return 0.0;
				}
				const double k = std::ceil((e - start) / m_ips);
				if(k < lim)
					lim = k;
			}
		}
		m_skipEdge.store(false, std::memory_order_relaxed);
		m_skipArmed.store(true, std::memory_order_seq_cst);
		m_due = start + lim * m_ips;
		rtPost(0);
		// wait: every booted core at its target, or stopped at the skip's edge
		// (idle for this post), or fenced, or faulted
		const auto t0 = Clock::now();
		uint64_t spins = 0;
		bool waited = false, edge = false;
		for(;;)
		{
			edge = m_skipEdge.load(std::memory_order_acquire);
			bool ok = true;
			int lagging = -1;
			for(int i = 0; i < 2; ++i)
			{
				if(!m_bootDone[i].load(std::memory_order_relaxed))
					continue;
				RtCore& r = m_rtc[i];
				if(r.faulted.load(std::memory_order_acquire))
					continue;
				if(r.fenced.load(std::memory_order_acquire))
					continue;
				if(r.reached.load(std::memory_order_acquire) + r.offset.load(std::memory_order_relaxed) + m_rtLagMax >= m_rtPosted)
					continue;
				if(edge && r.idleGen.load(std::memory_order_acquire) == m_rtGen.load(std::memory_order_relaxed))
					continue;
				ok = false;
				lagging = i;
				break;
			}
			if(ok)
				break;
			if(!waited)
			{
				waited = true;
				++m_rtSkipWaits;
			}
			if(m_stop.load(std::memory_order_relaxed))
				break;
			if(++spins < 2048)
				cpuRelax();
			else
			{
				sched_yield();
				if((spins & 255) == 0 && secondsSince(t0) > 2.0)
				{
					++m_rtWaitTimeouts;
					rtFault(lagging, "the worker did not reach the due count within 2 s (rt idle skip)");
					break;
				}
			}
		}
		if(waited)
		{
			const double w = secondsSince(t0);
			m_rtSkipWaitS += w;
			if(m_rtWaitLog && w > 0.005)
				std::fprintf(stderr, "rtwaitlog skip wait %.1f ms posted=%llu | core0 pc=%06x reached=%llu idle=%d fenced=%d | core1 pc=%06x reached=%llu idle=%d fenced=%d\n", w * 1e3, static_cast<unsigned long long>(m_rtPosted),
					m_rtc[0].pc.load(), static_cast<unsigned long long>(m_rtc[0].reached.load() + m_rtc[0].offset.load()), m_rtc[0].idle.load() ? 1 : 0, m_rtc[0].fenced.load() ? 1 : 0,
					m_rtc[1].pc.load(), static_cast<unsigned long long>(m_rtc[1].reached.load() + m_rtc[1].offset.load()), m_rtc[1].idle.load() ? 1 : 0, m_rtc[1].fenced.load() ? 1 : 0);
		}
		double done = lim;
		if(edge)
		{
			// The clock lands on the whole sample after the edge (at least one
			// sample of the skip is consumed unless the edge fired at its very
			// start), bounded by the skip's own end; the workers' targets come
			// down to it -- a core may have stopped a block past it, which is
			// the lockstep skip's own grain.
			const uint32_t w = m_edgeW.load(std::memory_order_acquire);
			const uint32_t rd = m_edgeR.load(std::memory_order_relaxed);
			if(w != rd)
			{
				const double e = static_cast<double>(m_edgeRing[rd % g_edgeRing].load(std::memory_order_relaxed));
				double k = std::ceil((e - start) / m_ips);
				if(!(k >= 0.0)) k = 0.0;
				if(k > lim) k = lim;
				done = k;
				m_due = start + done * m_ips;
				m_rtPosted = static_cast<uint64_t>(m_due) + 1;	// != due: the lowered target is posted
				rtPost(0);
				++m_stats.edgesIdle;
			}
		}
		m_skipArmed.store(false, std::memory_order_release);
		rtApplyEdges(true);
		return done;
	}

	std::string DspPair::rtStatus()
	{
		char b[3000];
		const Core& c0 = *m_cores[0];
		const Core& c1 = *m_cores[1];
		uint64_t exec[2], lag[2];
		for(int i = 0; i < 2; ++i)
		{
			const RtCore& r = m_rtc[i];
			const bool booted = m_bootDone[i].load(std::memory_order_relaxed);
			exec[i] = booted ? r.reached.load(std::memory_order_relaxed) + r.offset.load(std::memory_order_relaxed) : 0;
			const uint64_t due = static_cast<uint64_t>(m_due);
			lag[i] = booted && due > exec[i] ? due - exec[i] : 0;
		}
		std::string esaiLog;
		{
			std::lock_guard<std::mutex> g(m_streamMx);
			for(const auto& l : m_esaiMismatchLog) { esaiLog += l; esaiLog += "; "; }
		}
		std::snprintf(b, sizeof b,
			"rtstatus ok=%d mips0=%.1f mips1=%.1f xmips0=%.1f xmips1=%.1f busy0=%.2f busy1=%.2f cpu0=%.2f cpu1=%.2f "
			"frames=%llu due=%.0f exec0=%llu exec1=%llu lag0=%llu lag1=%llu "
			"posts=%llu wakes=%llu parks0=%llu parks1=%llu waits=%llu waitto=%llu wait=%.3f skipwaits=%llu skipwait=%.3f "
			"edges=%llu applied=%llu edgesinpull=%llu edgelate mean=%.1f max=%.0f (dsp instr) skipedges=%llu skipedgelate mean=%.1f max=%.0f "
			"skewwaits0=%llu skewwaits1=%llu skewto0=%llu skewto1=%llu waitcu0=%llu(%llu) waitcu1=%llu(%llu) ff0=%llu ff1=%llu blocks0=%llu blocks1=%llu "
			"pulls=%llu pull=%.3f pullshort=%llu dropped=%llu faulted=%d%d guardticks=%llu guardwindows=%llu treqdropped=%llu "
			"| pc0=%06x pc1=%06x rxring0=%zu rxring1=%zu tx0=%d cmds0=%llu cmds1=%llu banktakemax=%.2f "
			"| fence=%s inexch=%d frameon=%d edgesq=%u c0fenced=%d c0idle=%d c1idle=%d fenceopens=%llu fencewaits=%llu edgegate mean=%.1f dropped=%llu stale=%llu svc0=%llu svc1=%llu svcint0=%llu svcint1=%llu pullsfast=%llu pushes=%llu "
			"| cfwait skip=%.3f lag=%.3f pull=%.3f pullword=%.3f(%llu) kick=%.3f(%llu) push=%.3f post=%.3f fenceopen=%.3f take=%.3f(%llu,to %llu) (wall s) "
			"| worker0 busy=%.3f idle=%.3f fence=%.3f worker1 busy=%.3f idle=%.3f fence=%.3f (wall s) "
			"| core0 hsr=%02x hcr=%02x hpcr=%02x tgt=%lld tcr=%06x dcr2=%06x dsr2=%06x dco2=%06x ctr=%llu | core1 hsr=%02x tgt=%lld ctr=%llu "
			"| esaimism=%llu/%llu %s bootreads=%llu hcwait=%.3f(%llu,to %llu) gatedrain=%.3f(%llu,to %llu) | knobs lag=%llu lead=%llu polllead=%llu skew=%llu postq=%llu readq=%llu checkq=%llu spin=%.0fus ff=%d guard=%d doiter=%u fenceknob=%d",
			m_rtOk ? 1 : 0,
			m_rtc[0].mips.load(), m_rtc[1].mips.load(), m_rtc[0].xmips.load(), m_rtc[1].xmips.load(),
			m_rtc[0].busy.load(), m_rtc[1].busy.load(), m_rtc[0].cpuS.load(), m_rtc[1].cpuS.load(),
			static_cast<unsigned long long>(c0.txFrames.load(std::memory_order_relaxed)), m_due,
			static_cast<unsigned long long>(exec[0]), static_cast<unsigned long long>(exec[1]),
			static_cast<unsigned long long>(lag[0]), static_cast<unsigned long long>(lag[1]),
			static_cast<unsigned long long>(m_rtPosts), static_cast<unsigned long long>(m_rtWakes),
			static_cast<unsigned long long>(m_rtc[0].parks.load()), static_cast<unsigned long long>(m_rtc[1].parks.load()),
			static_cast<unsigned long long>(m_rtWaits), static_cast<unsigned long long>(m_rtWaitTimeouts), m_rtWaitS,
			static_cast<unsigned long long>(m_rtSkipWaits), m_rtSkipWaitS,
			static_cast<unsigned long long>(m_edgesRaised.load()), static_cast<unsigned long long>(m_rtEdgesApplied),
			static_cast<unsigned long long>(m_edgesRaisedInPull.load()),
			m_rtEdgeLateN ? m_rtEdgeLateSum / static_cast<double>(m_rtEdgeLateN) : 0.0, m_rtEdgeLateMax,
			static_cast<unsigned long long>(m_rtSkipEdges), m_rtSkipEdges ? m_rtSkipEdgeLateSum / static_cast<double>(m_rtSkipEdges) : 0.0, m_rtSkipEdgeLateMax,
			static_cast<unsigned long long>(m_rtc[0].skewWaits.load()), static_cast<unsigned long long>(m_rtc[1].skewWaits.load()),
			static_cast<unsigned long long>(m_rtc[0].skewTimeouts.load()), static_cast<unsigned long long>(m_rtc[1].skewTimeouts.load()),
			static_cast<unsigned long long>(m_rtc[0].waitCatchUps.load()), static_cast<unsigned long long>(m_rtc[0].waitCatchUpSum.load()),
			static_cast<unsigned long long>(m_rtc[1].waitCatchUps.load()), static_cast<unsigned long long>(m_rtc[1].waitCatchUpSum.load()),
			static_cast<unsigned long long>(m_rtc[0].skipped.load()), static_cast<unsigned long long>(m_rtc[1].skipped.load()),
			static_cast<unsigned long long>(m_rtc[0].blocks.load()), static_cast<unsigned long long>(m_rtc[1].blocks.load()),
			static_cast<unsigned long long>(m_rtPulls), m_rtPullS,
			static_cast<unsigned long long>(c0.pullShort + c1.pullShort), static_cast<unsigned long long>(c0.dropped + c1.dropped),
			m_rtc[0].faulted.load() ? 1 : 0, m_rtc[1].faulted.load() ? 1 : 0,
			static_cast<unsigned long long>(m_rtGuardTicks), static_cast<unsigned long long>(m_rtGuardWindows),
			static_cast<unsigned long long>(m_rtIcrTreqDropped),
			m_rtc[0].pc.load(), m_rtc[1].pc.load(), c0.hdi().rxData().size(), c1.hdi().rxData().size(), c0.hdi().hasTX() ? 1 : 0,
			static_cast<unsigned long long>(c0.commands), static_cast<unsigned long long>(c1.commands),
			static_cast<double>(c0.bankTakeMax) / g_dspIps,
			m_fenceOpen.load(std::memory_order_relaxed) ? "open" : "closed", m_inExchange.load() ? 1 : 0, m_frameOn.load() ? 1 : 0,
			m_edgeW.load(std::memory_order_acquire) - m_edgeR.load(std::memory_order_relaxed), m_rtc[0].fenced.load() ? 1 : 0, m_rtc[0].idle.load() ? 1 : 0, m_rtc[1].idle.load() ? 1 : 0,
			static_cast<unsigned long long>(m_fenceOpens),
			static_cast<unsigned long long>(m_rtc[0].fenceWaits.load()),
			m_edgesRaised.load() ? static_cast<double>(m_edgeGateSumI.load()) / static_cast<double>(m_edgesRaised.load()) : 0.0,
			static_cast<unsigned long long>(m_edgesDropped.load()), static_cast<unsigned long long>(m_rtEdgesStale),
			static_cast<unsigned long long>(m_rtc[0].services.load()), static_cast<unsigned long long>(m_rtc[1].services.load()),
			static_cast<unsigned long long>(m_rtc[0].svcInterrupts.load()), static_cast<unsigned long long>(m_rtc[1].svcInterrupts.load()),
			static_cast<unsigned long long>(m_rtPullsFast), static_cast<unsigned long long>(m_rtPushes),
			m_rtSkipWaitS, m_rtWaitS, m_rtPullS, m_rtPullWordS, static_cast<unsigned long long>(m_rtPullWordWaits),
			m_rtKickS, static_cast<unsigned long long>(m_rtKicks), m_rtPushS, m_rtPostS, m_fenceOpenS,
			m_takeWaitS, static_cast<unsigned long long>(m_takeWaits), static_cast<unsigned long long>(m_takeWaitTimeouts),
			m_rtc[0].busyS.load(), m_rtc[0].idleS.load(), m_rtc[0].fenceS.load(),
			m_rtc[1].busyS.load(), m_rtc[1].idleS.load(), m_rtc[1].fenceS.load(),
			m_rtc[0].hsr.load(), c0.hdi().readControlRegister() & 0xff, m_rtc[0].hpcr.load(),
			static_cast<long long>(m_rtc[0].tgt.load()),
			m_rtc[0].tcr.load(), m_rtc[0].dcr2.load(), m_rtc[0].dsr2.load(), m_rtc[0].dco2.load(),
			static_cast<unsigned long long>(m_rtc[0].ctr.load()),
			m_rtc[1].hsr.load(),
			static_cast<long long>(m_rtc[1].tgt.load()),
			static_cast<unsigned long long>(m_rtc[1].ctr.load()),
			static_cast<unsigned long long>(m_esaiMismatch.load()), static_cast<unsigned long long>(m_esaiChecked.load()), esaiLog.c_str(), static_cast<unsigned long long>(m_rtBootReads),
			m_hcWaitS, static_cast<unsigned long long>(m_hcWaits), static_cast<unsigned long long>(m_hcWaitTimeouts),
			m_gateDrainS, static_cast<unsigned long long>(m_gateDrainWaits), static_cast<unsigned long long>(m_gateDrainTimeouts),
			static_cast<unsigned long long>(m_rtLagMax), static_cast<unsigned long long>(m_rtLead), static_cast<unsigned long long>(m_rtPollLead), static_cast<unsigned long long>(m_rtSkew),
			static_cast<unsigned long long>(m_rtPostQuantum), static_cast<unsigned long long>(m_rtReadQuantum), static_cast<unsigned long long>(m_rtCheckQuantum),
			m_rtSpinUs, m_rtFastForward ? 1 : 0, m_rtGuard ? 1 : 0, m_rtDoIter, m_fence ? 1 : 0);
		std::string out = b;
		{
			// the last protocol events, oldest first (c = command, p = push, l = pull, k = eDMA kick (channel), d = eDMA completion (channel), a = the CPU acknowledged a vector (0x41 frame, 0x48+ch eDMA), e = edge applied (value = lateness), h = frame handled, m = handler masked its source, f = frame clock)
			out += " | proto:";
			const uint32_t w = m_protoW.load(std::memory_order_acquire);
			const uint32_t n = w < 200 ? w : 200;	// the last 200 of the 1024 kept
			for(uint32_t k = w - n; k < w; ++k)
			{
				const auto& e = m_proto[k % m_proto.size()];
				char f[48];
				std::snprintf(f, sizeof f, " %c%d:%x@%.1f", e.kind, e.core, e.val, e.due / g_dspIps);
				out += f;
			}
		}
		if(!m_rtShortLog.empty())
		{
			out += " | shortlog:";
			for(const auto& l : m_rtShortLog)
				out += " [" + l + "]";
		}
		return out;
	}

	DspPair::~DspPair()
	{
		if(m_rt)
		{
			// O17: stop the workers and join them before anything they touch
			// is destroyed (a worker inside exec() returns within a block; a
			// parked one wakes on the notify or its 2 ms timeout).
			m_stop.store(true, std::memory_order_release);
			for(int i = 0; i < 2; ++i)
				if(m_rtc[i].started)
					rtWake(i);
			for(int i = 0; i < 2; ++i)
				if(m_rtc[i].started)
					pthread_join(m_rtc[i].thread, nullptr);
			if(m_shmFd >= 0)
				close(m_shmFd);
			if(m_rtTraceOn)
				for(const auto& l : m_rtTrace)
					std::fprintf(stderr, "rttrace %s\n", l.c_str());
			if(m_rtPollHist)
				for(int i = 0; i < 2; ++i)
				{
					std::fprintf(stderr, "pollhist core %d:", i);
					std::sort(m_pollHist[i].begin(), m_pollHist[i].end(), [](const auto& a, const auto& b) { return a.second > b.second; });
					for(const auto& e : m_pollHist[i])
						std::fprintf(stderr, " %06x:%llu", e.first, static_cast<unsigned long long>(e.second));
					std::fputc('\n', stderr);
				}
		}
		// O16b: the pair's own counters, opt-in (OT_DSP_STATS=1), on stderr at
		// exit -- what `dspstat` reported in the speed-dsp prototype, without
		// a command. Nothing on stdout, nothing without the variable.
		if(const char* e = std::getenv("OT_DSP_STATS"); e && *e && *e != '0')
		{
			std::fprintf(stderr, "dspstat runDue=%llu passes=%llu stepCore=%llu",
				static_cast<unsigned long long>(m_stats.runDue), static_cast<unsigned long long>(m_stats.passes),
				static_cast<unsigned long long>(m_stats.stepCalls));
			// O16c: the lazy side (all zero on the exact schedule but the host counts).
			std::fprintf(stderr, " | lazy=%.0f hostR=%llu hostW=%llu syncs=%llu chunks=%llu chunkmean=%.1f chunkmax=%.0f edges=%llu edgelate mean=%.2f max=%.0f (dsp instr) edges-late=%llu edges-in-idle-skips=%llu guardticks=%llu predictions=%llu",
				m_lazy, static_cast<unsigned long long>(m_stats.hostReads), static_cast<unsigned long long>(m_stats.hostWrites),
				static_cast<unsigned long long>(m_stats.syncs), static_cast<unsigned long long>(m_stats.chunks),
				m_stats.chunks ? m_stats.chunkSum / static_cast<double>(m_stats.chunks) : 0.0, m_stats.chunkMax,
				static_cast<unsigned long long>(m_stats.edges),
				m_stats.edges ? m_stats.edgeLateSum / static_cast<double>(m_stats.edges) : 0.0, m_stats.edgeLateMax,
				static_cast<unsigned long long>(m_stats.edgesLate), static_cast<unsigned long long>(m_stats.edgesIdle),
				static_cast<unsigned long long>(m_stats.guardTicks), static_cast<unsigned long long>(m_stats.predictions));
			for(int i = 0; i < 2; ++i)
			{
				const Core& c = *m_cores[i];
				std::fprintf(stderr, " | core %d exec=%llu skip=%llu interp=%llu idlesteps=%llu surplus=%llu zerodelta=%llu",
					i, static_cast<unsigned long long>(c.executed), static_cast<unsigned long long>(c.idleSkipped),
					static_cast<unsigned long long>(m_stats.interp[i]), static_cast<unsigned long long>(m_stats.idleSteps[i]),
					static_cast<unsigned long long>(c.surplus), static_cast<unsigned long long>(c.zeroDelta));
			}
			std::fprintf(stderr, " | gate calls=%llu refused=%llu blocks=%llu meanspan=%.1f (dsp instr from a refusal to the grant) grantlate mean=%.1f (due minus the core's own emptying)",
				static_cast<unsigned long long>(m_gateCalls), static_cast<unsigned long long>(m_gateFalse), static_cast<unsigned long long>(m_gateBlocks),
				m_gateBlocks ? m_gateSpanSum / static_cast<double>(m_gateBlocks) : 0.0, m_gateBlocks ? m_gateLateSum / static_cast<double>(m_gateBlocks) : 0.0);
			{
				const Core& c = *m_cores[0];
				std::fprintf(stderr, " | drain core0: cmds=%llu words mean=%.1f firstpop mean=%.1f empty mean=%.1f (dsp instr after the command interrupt) | pushes=%llu words mean=%.1f firstpop mean=%.1f empty mean=%.1f (after the eDMA push, due units)",
					static_cast<unsigned long long>(c.drainN), c.drainN ? c.drainWordsSum / static_cast<double>(c.drainN) : 0.0,
					c.drainN ? c.drainFirstSum / static_cast<double>(c.drainN) : 0.0, c.drainN ? c.drainEmptySum / static_cast<double>(c.drainN) : 0.0,
					static_cast<unsigned long long>(c.pushN), c.pushN ? c.pushWordsSum / static_cast<double>(c.pushN) : 0.0,
					c.pushN ? c.pushFirstSum / static_cast<double>(c.pushN) : 0.0, c.pushN ? c.pushEmptySum / static_cast<double>(c.pushN) : 0.0);
				std::fprintf(stderr, " | cmd latency core0: n=%llu mean=%.1f max=%.0f (due units, CVR write -> vector 0x18 taken)",
					static_cast<unsigned long long>(c.cmdLatN), c.cmdLatN ? c.cmdLatSum / static_cast<double>(c.cmdLatN) : 0.0, c.cmdLatMax);
			}
			std::fputc('\n', stderr);
		}
	}

	// O17b: the ColdFire finished a frame's host-port exchange (Rtos: INTC0
	// source 1 unmasked). The fence opens here in the real-time mode.
	void DspPair::frameHandled()
	{
		++m_frameHandledN;
		if(m_fenceTrace)
			std::fprintf(stderr, "ftrace %.3f handled n=%llu\n", m_due / g_dspIps, static_cast<unsigned long long>(m_frameHandledN));
		if(!m_rt)
			return;
		protoNote('h', 0, static_cast<uint32_t>(m_frameHandledN));
		// THE FENCE OPENS: core 0 may write its next bank word. The store then
		// the look at `parked` are seq_cst against the worker's park protocol
		// (rtWorker), so the opening is never lost.
		const auto t0 = Clock::now();
		m_inExchange.store(false, std::memory_order_seq_cst);
		m_fenceOpen.store(true, std::memory_order_seq_cst);
		++m_fenceOpens;
		if(m_rtc[0].parked.load(std::memory_order_seq_cst))
		{
			rtWake(0);
			++m_fenceOpenWakes;
		}
		m_fenceOpenS += secondsSince(t0);
	}

	void DspPair::setFrameClock(const bool _on)
	{
		if(!m_rt)
			return;
		m_frameOn.store(_on, std::memory_order_seq_cst);
		protoNote('f', 0, _on ? 1u : 0u);
		if(!_on && m_rtc[0].parked.load(std::memory_order_seq_cst))
			rtWake(0);		// nobody will take frames: a core held at the fence goes on once no exchange is in flight (rtWorker re-evaluates)
	}

	void DspPair::setVerbose(const bool _on)
	{
		// (A null function crashes the vendored logger; give it a printer.)
		Logging::setLogFunc(_on ? [](const std::string& _s) { std::puts(_s.c_str()); } : [](const std::string&) {});
	}

	void DspPair::note(const char* _kind, const uint32_t _val)
	{
		noteFrom(m_sel & 1, _kind, _val);
	}

	// O17: a note with the core said, not swapped into m_sel (the ColdFire's
	// select register, its thread's alone); the log is locked in the rt mode
	// (the hooks run on the workers' threads).
	void DspPair::noteFrom(const int _core, const char* _kind, const uint32_t _val)
	{
		if(!m_logOn)
			return;
		std::unique_lock<std::mutex> lk(m_logMx, std::defer_lock);
		if(m_rt)
			lk.lock();
		if(m_log.size() >= 4000000)
			return;
		Event e{};
		e.due = static_cast<uint64_t>(m_due);
		e.core = _core & 1;
		std::strncpy(e.kind, _kind, sizeof e.kind - 1);
		e.val = _val;
		m_log.push_back(e);
	}

	// O18: the memory instrument's line -- every record this object can grow.
	// Sizes only, read on the CPU's thread; the worker-owned ones (the poll
	// histogram, the rt trace) are not touched.
	std::string DspPair::memStat() const
	{
		size_t capture = 0, hdiTx = 0, hdiRx = 0;
		for(const auto& c : m_cores)
		{
			capture += c->capture.size();
			hdiTx += c->hdi().txData().size();
			hdiRx += c->hdi().rxData().size();
		}
		char b[320];
		std::snprintf(b, sizeof b, "dspLog=%zu trace=%zu map=%zu writeMap=%zu stream=%zu pcWatchHits=%zu watchHits=%zu"
			" rtShort=%zu esaiMism=%zu capture=%zu hdiTx=%zu hdiRx=%zu input=%zu",
			m_log.size(), m_trace.size(), m_map.size(), m_writeMap.size(), m_stream.size(), m_pcWatchHits.size(),
			m_watchHits.size(), m_rtShortLog.size(), m_esaiMismatchLog.size(), capture, hdiTx, hdiRx, m_input.size());
		return b;
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
			{
				// O17: the receive ring is the core's thread's to pop; a clear
				// from this thread would race it. The firmware writes INIT|RREQ
				// only (measured in the spike, 3595 INIT writes, 0 with TREQ);
				// in the rt mode a TREQ clear is dropped and counted.
				if(m_rt)
					++m_rtIcrTreqDropped;
				else
					h.clearRX();
			}
		}
		if(m_rt)
			h.setPendingHostFlags01(((_v >> 3) & 1) | (((_v >> 4) & 1) << 1));	// the core's thread applies them (HSR is its register)
		else
			h.setHostFlags((_v >> 3) & 1, (_v >> 4) & 1);
	}

	void DspPair::cvrWrite(const uint32_t _v)
	{
		Core& c = cur();
		c.cvr.store(static_cast<uint8_t>(_v & 0xff), std::memory_order_release);
		note("cvr", _v & 0xff);
		if(!(_v & 0x80))
			return;
		// HC set: a host command interrupt at P:(HV * 2). The frame handler's
		// 0x8c is vector 0x18. HC (and the DSP's HCP) stay set until the DSP
		// takes it -- `runDue` clears both when the PC lands on the vector.
		c.hcVector = (_v & 0x7f) << 1;
		c.cmdArgs[0] = c.lastSent[0];
		c.cmdArgs[1] = c.lastSent[1];
		c.hcPending.store(true, std::memory_order_release);
		++c.commands;
		if(m_fenceTrace)
			std::fprintf(stderr, "ftrace %.3f cmd core%d %02x args %06x %06x\n", m_due / g_dspIps, m_sel & 1, _v & 0xff, c.cmdArgs[0], c.cmdArgs[1]);
		if(m_rt)
			protoNote('c', m_sel & 1, _v & 0xff);
		if(m_rt && c.hcVector == 0x18 && m_sel == 0)
			c.cmdKickDue.store(static_cast<uint64_t>(m_due), std::memory_order_relaxed);	// O17 diagnostic
		if(c.hcVector == 0x18 && m_writesOn && m_sel == 0 && m_writeMap.size() < 20000)
		{
			std::string line = "cmd " + std::to_string(c.commands) + " tx " + std::to_string(c.txFrames.load(std::memory_order_relaxed));
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
			std::string line = "cmd " + std::to_string(c.commands) + " tx " + std::to_string(c.txFrames.load(std::memory_order_relaxed));
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
		const uint64_t txFrames = c.txFrames.load(std::memory_order_relaxed);
		if(c.hcVector == 0x18 && !c.firstCmdSeen.load(std::memory_order_relaxed))
		{
			c.txAtFirstCmd.store(txFrames, std::memory_order_relaxed);
			c.rxAtFirstCmd.store(c.rxFrames.load(std::memory_order_relaxed), std::memory_order_relaxed);
			c.firstCmdSeen.store(true, std::memory_order_release);
		}
		if(c.hcVector == 0x18 && txFrames)
		{
			// Frames per frame: count from the second 0x8c on, once the ESAI
			// is running, so the boot-time gap is not the minimum.
			if(c.txAtCommand)
			{
				const auto d = txFrames - c.txAtCommand;
				c.fpcMin = std::min(c.fpcMin, d);
				c.fpcMax = std::max(c.fpcMax, d);
				if(d == 16) ++c.fpcSixteen;
				++c.fpcSamples;
			}
			c.txAtCommand = txFrames;
		}
		if(m_rt)
		{
			// O17: the host command goes through the library's own cross-thread
			// door (an SPSC queue the core drains at its next peripheral
			// service, which the zero delay below brings forward to its next
			// block); HCP is not raised in HSR (the core's thread's register
			// -- a read-modify-write from here would race it).
			const auto t0 = Clock::now();
			m_lastHostNs.store(std::chrono::duration_cast<std::chrono::nanoseconds>(t0.time_since_epoch()).count(), std::memory_order_relaxed);
			c.dsp->injectExternalInterrupt(c.hcVector);
			// The worker moves it into the core's own interrupt queue before its
			// next block (rtWorker: `kick`), as the interpreter's injectInterrupt
			// takes it at the next instruction. ❌ A zero peripheral delay
			// stored from here was overwritten by the core's own service and
			// the command waited for the next ESAI slot (up to 520
			// instructions): 29 M extra exact ColdFire steps behind the eDMA's
			// drain gate in 2 s of play. O17b: a stopped worker (idle at its
			// target, or fenced) runs the handler at once (rtService).
			m_rtc[m_sel & 1].kick.store(true, std::memory_order_seq_cst);
			if(m_rtc[m_sel & 1].parked.load(std::memory_order_seq_cst))
				rtWake(m_sel & 1);
			++m_rtKicks;
			m_rtKickS += secondsSince(t0);
			return;
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
			if(c.boot->hdiWriteTX(_word) && m_rt)
			{
				// O17: the ROM jumped -- the core's thread may run from here.
				// Its offset is lockstep's `executed := limit` while held: from
				// now on executed = the DSP's own counter + the due count now.
				const int i = m_sel & 1;
				m_rtc[i].offset.store(static_cast<uint64_t>(m_due), std::memory_order_release);
				m_bootDone[i].store(true, std::memory_order_release);
				rtWake(i);
			}
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
		bool bankTake = false;	// O17c: this take is core 0's bank word (the rendezvous below)
		{
			Core& c = cur();
			if(m_rt)
			{
				// O17: the latency is the ColdFire's due count at the take minus
				// the edge's executed count (the worker published it); the
				// lockstep arithmetic in the same unit.
				if(!m_pulling.load(std::memory_order_relaxed) && m_sel == 0 && m_bankTakePending.exchange(false, std::memory_order_relaxed))
				{
					bankTake = true;
					m_takeSeen.store(false, std::memory_order_seq_cst);	// before the pop: the worker's poll may pass on its own service
					const double e = m_edgeLastApplied;
					const auto lat = m_due > e ? static_cast<uint64_t>(m_due - e) : 0;
					++c.bankTakes; c.bankTakeSum += lat;
					if(lat > c.bankTakeMax) { c.bankTakeMax = lat; c.bankTakeMaxAt = c.bankTakes; }
				}
			}
			else if(!m_pulling.load(std::memory_order_relaxed) && c.bankWriteAt)
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
			if(m_rt && !m_pulling.load(std::memory_order_relaxed))
			{
				// O17b: the take of a bank word: the core polls HTDE at P:0x97, which its own peripheral service sets -- a core idle at its poll bound gets that service now (rtService)
				// O17c: the exact count of the take goes first, so the worker's
				// host-wait catch-up lands its clock on the take (rtWorker, THE WAITS)
				rtPost(0);
				m_hostEventAt.store(static_cast<uint64_t>(m_due), std::memory_order_release);
				RtCore& r = m_rtc[m_sel & 1];
				r.svc.store(true, std::memory_order_seq_cst);
				if(r.parked.load(std::memory_order_seq_cst))
					rtWake(m_sel & 1);
				if(bankTake)
				{
					// O17c: THE RENDEZVOUS AT THE TAKE. On the chip (and under
					// lockstep) core 0 sees HTDE within an instruction of the host's
					// take and leaves its wait (P:0x97) before the host's next command
					// -- the 0x89 that refills HOTX with the read-back -- arrives ~45
					// ColdFire instructions later; here the worker's service and poll
					// take microseconds of wall, so without this the read-back's FIFO
					// fill cleared HTDE first and core 0 stayed at P:0x97 through the
					// whole pull (0.7 samples: measured 13 Sep 2026, `waitcu0` ~1 per
					// frame of ~1500 instructions), its frame work and ring write
					// that much late. The ColdFire holds here until the worker has
					// left the wait (the exit sets m_takeSeen; rtWorker, THE WAITS),
					// bounded at 2 ms for a dead core.
					const auto t0 = Clock::now();
					uint64_t spins = 0;
					++m_takeWaits;
					while(!m_takeSeen.load(std::memory_order_acquire) && !m_stop.load(std::memory_order_relaxed))
					{
						if(r.faulted.load(std::memory_order_relaxed) || ((++spins & 255) == 0 && secondsSince(t0) > 0.002))
						{
							++m_takeWaitTimeouts;
							break;
						}
						cpuRelax();
					}
					m_takeWaitS += secondsSince(t0);
				}
			}
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
		// O16c: the DSP is where the ColdFire would have found it -- the
		// backlog runs before the register is read (a no-op when exact).
		// O17: a rendezvous in the rt mode (rtCatchUp: the cores AT the count)
		// -- except inside a read-back pull, whose words are the FIFO's (the
		// pull waited for them) and whose 256 reads per block would each pay
		// the two remote loads for nothing.
		++m_stats.hostReads;
		if(!(m_rt && m_pulling.load(std::memory_order_relaxed)))
			catchUp(true);
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
			case 1:
				if(m_rt && c.hcPending.load(std::memory_order_acquire) && !m_pulling.load(std::memory_order_relaxed))
				{
					// O17c: THE COMMAND RENDEZVOUS. Under lockstep the DSP takes a host
					// command at its next instruction, so the handler's HC poll sees
					// it taken at its first read; the worker takes it at its next
					// block, microseconds of wall later, and the poll went round a
					// wall-dependent number of times (its instruction count with it).
					// Hold here -- the ColdFire's clock does not move -- until the
					// worker has taken it, bounded at 2 ms for a dead core.
					RtCore& r = m_rtc[m_sel & 1];
					const auto t0 = Clock::now();
					uint64_t spins = 0;
					++m_hcWaits;
					while(c.hcPending.load(std::memory_order_acquire) && !m_stop.load(std::memory_order_relaxed))
					{
						if(r.faulted.load(std::memory_order_relaxed) || ((++spins & 255) == 0 && secondsSince(t0) > 0.002))
						{
							++m_hcWaitTimeouts;
							break;
						}
						cpuRelax();
					}
					m_hcWaitS += secondsSince(t0);
				}
				b = c.cvr.load(std::memory_order_acquire);
				break;
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
		++m_stats.hostWrites;
		catchUp();		// O16c: the word lands on the DSP the ColdFire is looking at
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
		if(m_fenceTrace)
			std::fprintf(stderr, "ftrace %.3f push core%d %zu words\n", m_due / g_dspIps, m_sel & 1, _hw.size() / 2);
		if(m_rt)
			protoNote('p', m_sel & 1, static_cast<uint32_t>(_hw.size()));
		catchUp();		// O16c: DMA0's state below is the DSP's NOW, not a burst ago
		// ⚠️ DMA0 AS OF THE KICK IS THE **PREVIOUS** BLOCK'S ARMING, and that is
		// not a defect. The command's two argument words and the CVR write all
		// precede the kick, but the CVR only INJECTS the interrupt: the DSP has
		// not taken it yet, so its handler has not read the arguments. The FIFO
		// is what makes this correct -- the arguments sit ahead of the data in
		// the ring, so when the DSP does take the interrupt it reads them first,
		// arms DMA0, and only then drains the block. ✅ Measured 8 Sep 2026:
		// read here, DCO0 always holds the count of the block BEFORE this one.
		// The third instance this session of a note taken at the wrong moment.
		if(!m_rt)	// O17: the DMA registers are the core's thread's (blockNote says so in the rt mode)
		{
			Core& c = cur();
			c.ddrAtArm = c.px->read(0xffffee, dsp56k::Nop);
			c.dcoAtArm = c.px->read(0xffffed, dsp56k::Nop);
		}
		// The cycles the eDMA would make: a 32-bit write at _addr is two
		// halfwords at +0 and +2, and both land on the same two registers.
		const auto tPush = Clock::now();
		if(m_rt)
			m_lastHostNs.store(std::chrono::duration_cast<std::chrono::nanoseconds>(tPush.time_since_epoch()).count(), std::memory_order_relaxed);
		bool bulk = false;
		if(m_rt)
		{
			// O17b: THE BULK PUSH. Every halfword of a block lands on TXM:TXL
			// and sends (the lane model in `read`), so the words are known
			// without the per-byte register walk: (TXH stale) << 16 | halfword,
			// into the ring in one call when it has the room (the chip's ring
			// would have overwritten HRX: the per-word path counts a drop).
			Core& c = cur();
			auto& h = c.hdi();
			const size_t n = _hw.size();
			if(m_rtBulk && c.boot->finished() && !m_logOn && n >= 2 && h.rxData().remaining() >= n)
			{
				m_pushScratch.resize(n);
				for(size_t i = 0; i < n; ++i)
					m_pushScratch[i] = (static_cast<uint32_t>(c.txh) << 16) | _hw[i];
				h.writeRX(m_pushScratch.data(), n);
				c.wordsIn += n;
				c.lastSent[0] = m_pushScratch[n - 2];
				c.lastSent[1] = m_pushScratch[n - 1];
				m_stats.hostWrites += n;
				bulk = true;
			}
		}
		if(!bulk)
			for(size_t i = 0; i < _hw.size(); ++i)
				write(_addr + 2 * static_cast<uint32_t>(i & 1), 2, _hw[i]);
		if(m_rt)
		{
			// the core drains the ring in its peripheral service: a worker idle
			// at its target or fenced is told to run one now (rtService)
			RtCore& r = m_rtc[m_sel & 1];
			r.svc.store(true, std::memory_order_seq_cst);
			if(r.parked.load(std::memory_order_seq_cst))
				rtWake(m_sel & 1);
			++m_rtPushes;
			m_rtPushS += secondsSince(tPush);
		}
		if(m_rt && m_sel == 0 && _hw.size() >= 8)
		{
			// O17 diagnostic (OT_DSP_STATS, rt only): the block's drain, from the push (in due units) to core 0's own first pop and emptying
			Core& c = *m_cores[0];
			if(m_rtTraceOn && m_rtTrace.size() < 4000)
			{
				m_rtTraceCtr0 = m_rtc[0].reached.load(std::memory_order_relaxed);
				char line[96];
				std::snprintf(line, sizeof line, "PUSH %zu words due=%.0f reached0=%llu", _hw.size() / 2, m_due, static_cast<unsigned long long>(m_rtTraceCtr0));
				m_rtTrace.emplace_back(line);
			}
			c.drainPushDue.store(static_cast<uint64_t>(m_due), std::memory_order_relaxed);
			c.drainPushWords.store(static_cast<uint32_t>(_hw.size() / 2), std::memory_order_relaxed);
			c.drainPushFirst.store(0, std::memory_order_relaxed);
		}
	}

	size_t DspPair::pullHalfwords(const uint32_t _addr, const int _core, std::vector<uint16_t>& _out, const size_t _n)
	{
		catchUp();		// O16c (runCoreUntil does too; here for the m_sel swap's sake)
		const int sel = m_sel;
		m_sel = _core & 1;
		Core& c = cur();
		size_t missing = 0;
		if(m_fenceTrace)
			std::fprintf(stderr, "ftrace %.3f pull core%d %zu words (fifo %zu)\n", m_due / g_dspIps, m_sel & 1, _n, c.hdi().txData().size());
		if(m_rt)
			protoNote('l', m_sel & 1, static_cast<uint32_t>(_n));
		m_pulling.store(true, std::memory_order_release);
		const auto tPull = Clock::now();
		if(m_rt)
			m_lastHostNs.store(std::chrono::duration_cast<std::chrono::nanoseconds>(tPull.time_since_epoch()).count(), std::memory_order_relaxed);
		if(m_rt)
		{
			// O17: the core runs on its own thread, past the due count until
			// HOTX holds a word (the predicate: RtCore::pred), the other core
			// following it as lockstep's runCoreUntil steps the other core
			// (rtWorker's `follow`). The wait is bounded so a dead core counts
			// as `not in time` instead of hanging the machine; with the TX FIFO
			// the DMA delivers the whole block in one peripheral service, so
			// the first word is the only one that waits.
			RtCore& r = m_rtc[m_sel & 1];
			m_pullCore.store(m_sel & 1, std::memory_order_seq_cst);
			r.pred.store(1, std::memory_order_seq_cst);
			if(r.parked.load(std::memory_order_seq_cst))
				rtWake(m_sel & 1);
			if(m_rtc[(m_sel & 1) ^ 1].parked.load(std::memory_order_seq_cst))
				rtWake((m_sel & 1) ^ 1);	// the follower
			for(size_t i = 0; i < _n; ++i)
			{
				bool ready = true;
				if(!c.hdi().hasTX())
				{
					const auto t0 = Clock::now();
					uint64_t spins = 0;
					++m_rtPullWordWaits;
					while(!c.hdi().hasTX())
					{
						if(r.faulted.load(std::memory_order_relaxed) || m_stop.load(std::memory_order_relaxed) || ((++spins & 1023) == 0 && secondsSince(t0) > 0.1))
						{
							ready = false;
							break;
						}
						if(spins < 4096) cpuRelax(); else sched_yield();
					}
					m_rtPullWordS += secondsSince(t0);
				}
				// O17b: THE FAST PATH -- the words already in the FIFO (the core's
				// DMA filled it in one service) are popped without the per-byte
				// register walk: the same word, the same counters, no log line
				// (the log keeps the per-word path).
				if(ready && m_rtBulk && !m_logOn)
				{
					size_t avail = c.hdi().txData().size();
					if(avail > _n - i)
						avail = _n - i;
					if(avail > 1)
					{
						if(i + avail == _n)
							r.pred.store(0, std::memory_order_release);
						m_pullScratch.resize(avail);
						avail = c.hdi().readTXBulk(m_pullScratch.data(), avail);
						for(size_t k = 0; k < avail; ++k)
						{
							const auto w = m_pullScratch[k];
							c.lastRx = w;
							++c.wordsOut;
							_out.push_back(static_cast<uint16_t>(w & 0xffff));
							++c.pulled;
						}
						++m_rtPullsFast;
						i += avail - 1;
						continue;
					}
				}
				if(i + 1 == _n)
					r.pred.store(0, std::memory_order_release);	// the last word is there: no run past it (❌ cleared before the wait, the worker idled at its target and the last word of every core-1 pull timed out)
				if(!ready)
				{
					++missing;
					if(m_rtShortLog.size() < 24)
					{
						char f[200];
						std::snprintf(f, sizeof f, "core%d word %zu/%zu: idle=%d idleGen=%u gen=%u pred=%d reached=%llu target=%llu pc=%06x follower idle=%d reached=%llu target=%llu pc=%06x due=%.0f",
							m_sel & 1, i, _n, r.idle.load() ? 1 : 0, r.idleGen.load(), m_rtGen.load(), r.pred.load(),
							static_cast<unsigned long long>(r.reached.load()), static_cast<unsigned long long>(m_rtPosted), r.pc.load(),
							m_rtc[(m_sel & 1) ^ 1].idle.load() ? 1 : 0, static_cast<unsigned long long>(m_rtc[(m_sel & 1) ^ 1].reached.load()),
							static_cast<unsigned long long>(m_rtPosted), m_rtc[(m_sel & 1) ^ 1].pc.load(), m_due);
						m_rtShortLog.emplace_back(f);
					}
				}
				uint32_t v = 0;
				read(_addr + 2 * static_cast<uint32_t>(i & 1), 2, v);
				_out.push_back(static_cast<uint16_t>(v));
				++c.pulled;
			}
			r.pred.store(0, std::memory_order_release);
			m_pullCore.store(-1, std::memory_order_release);
			if(!c.hdi().hasTX())
			{
				// O17c: the host took the last read-back word -- HTDE, which core 0
				// polls at P:0x97 through the whole pull, comes back with the
				// core's next service: post the exact count of this moment and ask
				// for that service, so the poll passes at the ColdFire's clock of
				// the pull's end (rtWorker, THE HOST-WAIT CATCH-UP), as lockstep's
				// per-word catchUp had it
				rtPost(0);
				if((m_sel & 1) == 0)
					m_hostEventAt.store(static_cast<uint64_t>(m_due), std::memory_order_release);
				r.svc.store(true, std::memory_order_seq_cst);
				if(r.parked.load(std::memory_order_seq_cst))
					rtWake(m_sel & 1);
			}
		}
		else
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
		m_pulling.store(false, std::memory_order_release);
		if(m_rt)
		{
			++m_rtPulls;
			m_rtPullS += secondsSince(tPull);
		}
		m_sel = sel;
		return missing;
	}

	bool DspPair::runCoreUntil(const int _core, const std::function<bool()>& _ready, const uint64_t _budget)
	{
		if(m_rt)
			return _ready();	// O17: the cores run themselves (pullHalfwords posts the predicate)
		catchUp();		// O16c: the pull runs the core AHEAD of the due count; the backlog goes first
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
		if(m_rt)
		{
			// O17: a tick only books the due count; the workers are told at the
			// touch points and the run loop's sync, and here every m_rtTickPost
			// ticks for the boot (which has neither). The guard experiment
			// (OT_RT_GUARD=1, dsp.h) makes every tick inside the edge window a
			// full rendezvous: the O16c guard's per-tick handoff, measured.
			if(m_rtGuard && m_due >= m_edgeGuard && m_due <= m_edgeWindowEnd)
			{
				++m_rtGuardTicks;
				rtPost(0);
				rtWait(0);
				return;
			}
			if((m_rtTicks += _n) >= m_rtTickPost)
			{
				m_rtTicks = 0;
				rtPost(m_rtPostQuantum);
			}
			return;
		}
		// O16c: exact (m_lazy == 0) runs the cores now, every tick; lazy only
		// books the tick and replays the backlog when it reaches the cap
		// inside a burst -- the run loop's sync() and the host-port touch
		// points replay it otherwise -- or at once while the edge guard's
		// window is open (dsp.h), which is the exact tick again.
		if(m_lazy <= 0.0)
		{
			runDue();
			return;
		}
		m_pendingTicks += _n;
		if(m_due - m_ranDue >= m_lazy || m_due >= m_edgeGuard)
			runChunk();
	}

	// O16c: THE CHUNK. The ticks booked since the cores last ran, replayed
	// as the exact schedule would have run them: the same `+= m_ratio`
	// additions from the same value (so every limit is the same double), and
	// for each, core 0 to it then core 1 to it -- runDue's one pass per tick
	// (its quantum never bites on a tick, O16b). The cross-core interleave,
	// every idle step's room and every peripheral event therefore fall on
	// the same DSP instruction as under the exact schedule; what the chunk
	// saves is the per-tick call and its pass bookkeeping. ❌ A first
	// version ran the backlog through runDue itself, i.e. in 64-instruction
	// quanta: core 0's mailbox waits on core 1 then ended up to a quantum
	// early or late, and with them the bank write and the host ring's drain
	// -- the frame interrupt and the eDMA completion moved by up to 61
	// ColdFire instructions, a UART block crossed a run boundary and the
	// audio moved by thousands of LSB where a parameter ramp met a frame
	// (out/_agents/speed-b2/, the guard-interdsp reports).
	void DspPair::runChunk()
	{
		const uint64_t n = m_pendingTicks;
		if(!n)
			return;
		m_pendingTicks = 0;
		const double due = m_due;
		++m_stats.chunks;
		m_stats.chunkSum += due - m_ranDue;
		if(due - m_ranDue > m_stats.chunkMax) m_stats.chunkMax = due - m_ranDue;
		if(due >= m_edgeGuard && due <= m_edgeWindowEnd)
			++m_stats.guardTicks;
		double d = m_ranDue;
		m_ranDue = due;		// before the passes: a probe from inside them finds nothing pending
		Core& c0 = *m_cores[0];
		Core& c1 = *m_cores[1];
		const bool plain0 = !c0.faulted && c0.boot->finished(), plain1 = !c1.faulted && c1.boot->finished();
		for(uint64_t k = 0; k < n; ++k)
		{
			d += m_ratio;
			if(plain0)
			{
				while(static_cast<double>(c0.executed) < d)
					if(!stepBody(c0, 0, d))	// false only on a fault, which set executed := limit
						break;
			}
			else
				stepCore(0, d);				// held / faulted: executed := limit, as runDue has it
			if(plain1)
			{
				while(static_cast<double>(c1.executed) < d)
					if(!stepBody(c1, 1, d))
						break;
			}
			else
				stepCore(1, d);
		}
		if(m_edgeSeen || due >= m_edgeWindowEnd)
			predictEdge();
	}

	// O16c: the edge guard's prediction (dsp.h). Called at the end of a lazy
	// runDue when the window is behind us or an edge has just fired. The
	// grid: the last ESAI frame callback ran inside a slot exec at counter
	// `slotCounter` with DMA2's pointer at `slotDsr2` (that slot's word
	// included); every later slot exec is one esaiCyclesPerSlot on and moves
	// the pointer one word, so the boundary slot is `togo` slots on. The
	// exec that crossed the grid point can be late by the instruction that
	// crossed it (a `rep` counts its iterations at once): the guard opens
	// three slots early to cover it, and closes one slot after the boundary
	// (the poll's window is that one slot; a write after it never comes).
	void DspPair::predictEdge()
	{
		++m_stats.predictions;
		Core& c = *m_cores[0];
		const double now = m_due;
		const double cps = static_cast<double>(c.esaiCyclesPerSlot);
		const double frame = cps * static_cast<double>(g_esaiSlots);	// one ESAI frame (a sample): the callback's own cadence
		m_edgeSeen = false;
		m_edgeGuard = 1e300;
		m_edgeWindowEnd = now + frame;			// no window: look again after the next callback can have run
		if(!c.boot->finished() || c.faulted || !m_hostWordHook)
			return;
		const uint32_t dsr2 = c.slotDsr2.load(std::memory_order_relaxed);
		const uint64_t slotCounter = c.slotCounter.load(std::memory_order_relaxed);
		if(dsr2 < 0x8000 || dsr2 > 0x80ff || slotCounter == m_edgeSlot)
		{
			// Not payload A's ring, or no ESAI frame since the last look
			// (the ESAI is not running, or the last window closed within
			// the frame of the callback it was made from): nothing to
			// predict from -- a frame on there is a fresh grid point. ❌ A
			// first version waited a whole ring half (128 slots) here, which
			// is the boundaries' own period, so every retry landed after
			// the next boundary: 152 of 413 edges late (edgelog.txt).
			m_edgeSlot = slotCounter;
			return;
		}
		m_edgeSlot = slotCounter;
		const uint32_t w = dsr2 & 0xff;
		const uint32_t togo = w <= 0x70 ? 0x70 - w : w <= 0xf0 ? 0xf0 - w : 0x70 + 0x100 - w;
		// Counter units -> executed units (the pair's `executed` runs on the
		// same counter, offset by the boot ROM's hold) -> due units (core 0
		// is at the due count at the end of every runDue, give or take an
		// instruction).
		const double offset = static_cast<double>(c.executed) - static_cast<double>(c.dsp->getInstructionCounter());
		const double tb = static_cast<double>(slotCounter) + static_cast<double>(togo) * cps + offset;
		if(tb + cps < now)
			return;		// the boundary slot is behind us already (a window that passed): the next look is an ESAI frame on
		m_edgeGuard = tb - 3.0 * cps;
		m_edgeWindowEnd = tb + cps + 256.0;
	}

	// O16c: the backlog, now. Nothing to do when exact (m_ranDue == m_due
	// after every tick) or when a nested caller (a probe from inside runDue's
	// own hooks) finds runDue already on it.
	void DspPair::catchUp(const bool _observe)
	{
		++m_stats.syncs;
		if(m_rt)
		{
			rtCatchUp(_observe);
			return;
		}
		if(m_pendingTicks)
			runChunk();
	}

	double DspPair::tickSamples(const double _n)
	{
		if(m_rt)
			return rtTickSamples(_n);
		catchUp();		// O16c: the burst before the idle skip, before its own per-sample steps
		if(!m_hostWordHook)
		{
			m_due += _n * m_ips;
			runDue();
			return _n;
		}
		// One sample at a time, so that a frame edge inside a ColdFire idle
		// skip ends the skip AT the edge, not a period later.
		double done = 0.0;
		m_inSamples = true;
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
		m_inSamples = false;
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
	double DspPair::g_quantum = 64.0;

	bool DspPair::stepCore(const int _i, const double _limit)
	{
		Core& c = *m_cores[_i];
		++m_stats.stepCalls;
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
		return stepBody(c, _i, _limit);
	}

	// O16b: the per-instruction body, split from the checks above so that
	// runDue can loop on it with the limit test inline (the call that only
	// returned false is gone), and with everything that is not needed on every
	// instruction -- the fault message, the TIMER0 capture, the stopwatch, the
	// PC watch, the trace line -- in cold helpers behind one `m_instrumented`
	// flag. The order of side effects is stepCore's of O9b-O15: PC ring, fault
	// check, idle window, bank flag, timer capture, stopwatch, PC watch, the
	// instruction, the loop end, the counters, the bank hook, the trace.
	bool DspPair::stepBody(Core& c, const int i, const double _limit)
	{
		const auto pc = c.dsp->getPC().toWord();
		c.pcRing[c.pcRingPos++ % c.pcRing.size()] = pc;
		if(pc >= g_pSize)
			return faultPc(c, pc, _limit);
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
			++m_stats.idleSteps[i];
		}
		// O9b: the bank id is the ONE host-port word the frame handler
		// reads with no ready check: payload A's `movep r3,x:<<M_HOTX`
		// at P:0x73, right after the bank wait, once per ring half.
		// (Keying on "port non-empty outside a pull" instead fired on
		// every command echo too: 5-6 ESAI frames per host frame.)
		const bool bankWrite = i == 0 && pc == g_bankIdPc && m_hostWordHook;
		// O23: THE STEM TAP, before the instruction at P:0x2d5 (the mixdown just ran)
		if(i == 0 && pc == g_stemTapPc && m_stemsOn.load(std::memory_order_relaxed))
			stemTap(c);
		// O9b: nobody in either payload writes a timer register, yet core 1
		// took TIMER0 Compare (vector 0x54 -- payload B's `move x0,y:(r4)+`)
		// 230,027 times. Catch the first enable with the PCs before it.
		// (readTCSR is an inline load; the capture itself is the cold part.)
		if(!c.timerEnabledAt && (c.px->getTimers().readTCSR(0) & 1))
			timerCapture(c);
		if(m_instrumented)
			instrumentBefore(c, i, pc);
		++m_stats.interp[i];
		c.dsp->execInterpreter();
		// doLoopEnd's first test is SR_LF (0x008000): with no hardware DO loop
		// open it returns false at once, so the call is made only then.
		if(c.dsp->regs().sr.var & 0x8000)
			c.dsp->doLoopEnd();
		const auto d = c.dsp->getInstructionCounter() - before;
		c.executed += d ? d : 1;
		if(d > skipped + 1) c.surplus += d - skipped - 1;
		if(!d) ++c.zeroDelta;
		if(bankWrite)
		{
			c.bankWriteAt = c.executed;
			{ const int sel = m_sel; m_sel = i; note("bank", c.hdi().txData().size()); m_sel = sel; }
			if(m_lazy > 0.0)
			{
				// O16c: how far the ColdFire's booked count is past this edge
				// = how late the ColdFire will see it (0 on the exact schedule).
				// An edge inside an idle skip is counted apart: there the
				// ColdFire's clock jumps a whole sample at a time with or
				// without lazy batching (tickSamples), and the lateness is the
				// skip's own.
				m_edgeSeen = true;
				if(m_inSamples)
					++m_stats.edgesIdle;
				else
				{
					const double late = m_due - static_cast<double>(c.executed);
					++m_stats.edges;
					if(late > 0.0) { m_stats.edgeLateSum += late; if(late > m_stats.edgeLateMax) m_stats.edgeLateMax = late; }
					if(late > 2.0)		// more than the tick's own step: the guard's window was not open
						++m_stats.edgesLate;
					if(m_edgeLog)
						std::fprintf(stderr, "edge exec=%llu due=%.0f late=%.0f guard=%.0f end=%.0f slotctr=%llu slotdsr2=%06x dsr2now=%06x ctr=%llu pcring=%x %x %x %x\n",
							static_cast<unsigned long long>(c.executed), m_due, late, m_edgeGuard, m_edgeWindowEnd,
							static_cast<unsigned long long>(c.slotCounter.load()), c.slotDsr2.load(), c.px->read(0xffffe7, dsp56k::Nop) & 0xffffff,
							static_cast<unsigned long long>(c.dsp->getInstructionCounter()),
							c.pcRing[(c.pcRingPos + 62) % 64], c.pcRing[(c.pcRingPos + 61) % 64], c.pcRing[(c.pcRingPos + 60) % 64], c.pcRing[(c.pcRingPos + 59) % 64]);
				}
			}
			if(m_fenceTrace)
				std::fprintf(stderr, "ftrace %.3f bank core0 exec=%llu fifo %zu\n", m_due / g_dspIps, static_cast<unsigned long long>(c.executed), c.hdi().txData().size());
			if(m_hostWordHook(0))
				m_hostWordFired = true;
		}
		if(m_instrumented && m_traceEvery && c.executed >= c.nextTrace && c.executed >= m_traceFrom && m_trace.size() < 100000)
			traceLine(c, i, pc);
		return true;
	}

	// -- the cold parts of the step (O16b) -----------------------------------

	bool DspPair::faultPc(Core& c, const uint32_t _pc, const double _limit)
	{
		c.faulted = true;
		char msg[96];
		std::snprintf(msg, sizeof msg, "PC %#x is outside P memory (%#x words)", _pc, g_pSize);
		c.why = msg;
		c.executed = static_cast<uint64_t>(_limit);
		return false;
	}

	void DspPair::timerCapture(Core& c)
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

	// The stopwatch and the PC watch, in that order, before the instruction.
	// O17c diagnostic (dsp.h m_frameTraceOn): the marker PCs of payload A's frame on core 0.
	// P:0x73 the bank word (after the fence), P:0x99 the take seen (the HTDE poll passed),
	// P:0xa5 core 1's mailbox reply seen, P:0x1cb the output stage (the ring write), P:0x4b
	// the return to the DSR2 poll (the frame's work done; printed once per return).
	// Core 1 (payload B): P:0x57 its wait for the bank id, 0x59 the id consumed, 0x8d its wait for
	// core 0's second word, 0x8f that word consumed.
	void DspPair::frameTraceLine(Core& c, const uint32_t pc, const uint64_t exec, const double due)
	{
		const bool core1 = &c == m_cores[1].get();
		if(core1)
		{
			if(pc != 0x57 && pc != 0x59 && pc != 0x8d && pc != 0x8f)
				return;
			if((pc == 0x57 || pc == 0x8d) && m_ftrLast1 == pc)
				return;
			m_ftrLast1 = pc;
			std::fprintf(stderr, "ftr1 pc=%03x exec=%.4f due=%.4f ctr=%llu\n", pc, static_cast<double>(exec) / g_dspIps, due / g_dspIps,
				static_cast<unsigned long long>(c.dsp->getInstructionCounter()));
			return;
		}
		if(pc != 0x73 && pc != 0x99 && pc != 0xa5 && pc != 0x1cb && pc != 0x205 && pc != 0x4b && pc != 0x54 && pc != 0x64)
			return;
		if(pc == 0x4b && m_ftrLast == 0x4b)
			return;
		m_ftrLast = pc;
		std::fprintf(stderr, "ftr pc=%03x exec=%.4f due=%.4f dsr2=%06x ctr=%llu\n", pc, static_cast<double>(exec) / g_dspIps, due / g_dspIps,
			c.px->read(0xffffe7, dsp56k::Nop) & 0xffffff, static_cast<unsigned long long>(c.dsp->getInstructionCounter()));
	}

	void DspPair::instrumentBefore(Core& c, const int i, const uint32_t pc)
	{
		if(m_frameTraceOn)
			frameTraceLine(c, pc, c.executed, m_due);
		if(m_sw.core == i)
		{
			if(pc == m_sw.start) { m_sw.t0 = c.executed; m_sw.armed = true; }
			else if(pc == m_sw.stop && m_sw.armed)
			{
				const uint64_t d = c.executed - m_sw.t0;
				m_sw.armed = false; ++m_sw.n; m_sw.sum += d; if(d > m_sw.max) m_sw.max = d; if(d < m_sw.min) m_sw.min = d;
				if(m_sw.last.size() < 4096) m_sw.last.push_back(static_cast<uint32_t>(d));
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
				static_cast<uint32_t>(r.r[1].var & 0xffffff), static_cast<uint32_t>(r.n[1].var & 0xffffff),
				static_cast<uint32_t>(r.r[7].var & 0xffffff),
				static_cast<uint32_t>(r.m[7].var & 0xffffff), static_cast<uint32_t>(r.m[0].var & 0xffffff),
				static_cast<uint32_t>(r.n[7].var & 0xffffff)});
		}
	}

	void DspPair::traceLine(Core& c, const int i, const uint32_t pc)
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

	void DspPair::runDue()
	{
		// Round-robin in quanta of g_quantum instructions until both cores
		// are at the due count. O16b: the same passes in the same order --
		// core 0 to its quantum, core 1 to its, again until a pass runs
		// nothing -- without the calls that could not run anything: a core
		// already at the due count is skipped on a compare (stepCore would
		// have returned false at once; only a FAULTED core has a side effect
		// there, its `executed = limit`, so that call is kept), and a live
		// core is stepped through stepBody with the limit test inline.
		const double due = m_due;
		++m_stats.runDue;
		m_ranDue = due;		// O16c: the cores are at the due count after this (tickSamples books whole samples; a lazy chunk goes through runChunk)
		for(;;)
		{
			bool ran = false;
			++m_stats.passes;
			for(int i = 0; i < 2; ++i)
			{
				Core& c = *m_cores[i];
				if(!c.faulted && static_cast<double>(c.executed) >= due)
					continue;
				const double lim = std::min(due, static_cast<double>(c.executed) + g_quantum);
				if(c.faulted || !c.boot->finished())
				{
					// One call, returns false: the held / faulted core's executed := limit.
					while(stepCore(i, lim))
						ran = true;
					continue;
				}
				while(static_cast<double>(c.executed) < lim)
				{
					if(!stepBody(c, i, lim))	// false only on a fault, which set executed := limit
						break;
					ran = true;
				}
			}
			if(!ran)
				break;
		}
		if(m_lazy > 0.0 && (m_edgeSeen || due >= m_edgeWindowEnd))
			predictEdge();
	}

	// -- probes ---------------------------------------------------------------

	// O16c: a probe observes the pair NOW, which under lazy batching means
	// after the backlog. The probes are const in the interface; the backlog
	// is the pair's own bookkeeping, hence the cast (a no-op when exact).
	uint32_t DspPair::peekP(const int _core, const uint32_t _addr) const
	{
		const_cast<DspPair*>(this)->catchUp();
		return m_cores[_core & 1]->mem->get(dsp56k::MemArea_P, _addr);
	}
	// The shared window is read from the pair's own array: Memory::get
	// answers 0 for any offset past the core's own size before it looks at
	// the window, so a peek at 0x30000+ through it was blind (O9, 8 Sep).
	uint32_t DspPair::peekX(const int _core, const uint32_t _addr) const
	{
		const_cast<DspPair*>(this)->catchUp();
		if(_addr >= g_shareLo && _addr < g_shareHi)
			return m_rt ? m_sharedPtr[_addr - g_shareLo] : m_shared[_addr - g_shareLo];
		return m_cores[_core & 1]->mem->get(dsp56k::MemArea_X, _addr);
	}
	uint32_t DspPair::peekY(const int _core, const uint32_t _addr) const
	{
		const_cast<DspPair*>(this)->catchUp();
		if(_addr >= g_shareLo && _addr < g_shareHi)
			return m_rt ? m_sharedPtr[_addr - g_shareLo] : m_shared[_addr - g_shareLo];
		return m_cores[_core & 1]->mem->get(dsp56k::MemArea_Y, _addr);
	}
	// O17: in the rt mode a probe of a core's own state waits for the worker to
	// reach the due count first (it is then idle: what it observes is the
	// core NOW, and the worker's publish orders its writes before the read).
	uint32_t DspPair::pc(const int _core) const
	{
		if(m_rt) { const_cast<DspPair*>(this)->rtWait(0); return m_rtc[_core & 1].pc.load(std::memory_order_acquire); }
		const_cast<DspPair*>(this)->catchUp(); return m_cores[_core & 1]->dsp->getPC().toWord();
	}
	bool DspPair::faulted(const int _core) const { return m_rt ? m_rtc[_core & 1].faulted.load(std::memory_order_acquire) : m_cores[_core & 1]->faulted; }
	uint64_t DspPair::idleSkipped(const int _core) const
	{
		if(m_rt) { const_cast<DspPair*>(this)->rtRefresh(); return m_cores[_core & 1]->idleSkipped; }
		const_cast<DspPair*>(this)->catchUp(); return m_cores[_core & 1]->idleSkipped;
	}
	// The DSP's own host DMA, as its frame handlers arm it (P:0x588 reads two
	// host words into DDR0/DCO0 and starts DMA0 = HORX -> X memory; P:0x597
	// does the same for DMA1 = X memory -> HOTX). Reading them says where the
	// block being moved is actually landing, at the moment it lands, which is
	// what an end-of-run peek of a buffer the DSP has already consumed cannot.
	std::string DspPair::blockNote(const int _core)
	{
		catchUp();
		Core& c = *m_cores[_core & 1];
		char b[192];
		if(m_rt)
		{
			// O17: the DMA registers and X memory are the core's thread's while it
			// runs; the note keeps what this thread owns.
			std::snprintf(b, sizeof b, "dsp: cmd args %06x %06x | rx ring %zu (rt: DMA registers not read from the ColdFire's thread)",
				c.cmdArgs[0], c.cmdArgs[1], c.hdi().rxData().size());
			return b;
		}
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
		{
			const_cast<DspPair*>(this)->catchUp();
			return const_cast<dsp56k::Peripherals56362*>(m_cores[_core & 1]->px.get())->read(0xffffee, dsp56k::Nop);
		}
		return _space == 'P' ? peekP(_core, _addr) : _space == 'Y' ? peekY(_core, _addr) : peekX(_core, _addr);
	}

	bool DspPair::hostRingEmpty(const int _core) const
	{
		// O16c: the gate asks about the ring NOW. (O17 diagnostic, OT_DSP_STATS:
		// the calls, the refusals, and the due-count span from a refusal to the
		// next grant -- how long the DSP takes to drain a block, in its own time.)
		auto* self = const_cast<DspPair*>(this);
		if(m_rt)
		{
			// O17: the gate observes this core's ring: that core at the count first
			const int sel = m_sel;
			self->m_sel = _core & 1;
			self->catchUp(true);
			self->m_sel = sel;
		}
		else
			self->catchUp(true);
		bool empty = !m_cores[_core & 1]->hdi().hasRXData();
		if(!m_rt)
			return empty;
		if(!empty && !m_rtc[_core & 1].faulted.load(std::memory_order_relaxed))
		{
			// O17c: THE GATE WAITS FOR THE DRAIN. The completion is booked at the
			// kick plus the lockstep drain time (rtos.cpp THE DRAIN TIMES) and
			// the worker drains the block in one service, microseconds of wall
			// after the push -- usually long before the booked time, but a
			// worker inside a long block or a wait got there later, the gate
			// held, and the ColdFire's clock stepped on past the booked time
			// (measured 13 Sep 2026: 350-430 completions per 4 s of PLAY later
			// than booked, up to a sample; every divergence from the reference
			// began at one). Hold here instead -- the ColdFire's clock does not
			// move -- until the ring is drained, bounded at 2 ms for a dead core.
			RtCore& r = self->m_rtc[_core & 1];
			r.svc.store(true, std::memory_order_seq_cst);
			if(r.parked.load(std::memory_order_seq_cst))
				self->rtWake(_core & 1);
			const auto t0 = Clock::now();
			uint64_t spins = 0;
			++self->m_gateDrainWaits;
			while(m_cores[_core & 1]->hdi().hasRXData() && !m_stop.load(std::memory_order_relaxed))
			{
				if(r.faulted.load(std::memory_order_relaxed) || ((++spins & 255) == 0 && secondsSince(t0) > 0.002))
				{
					++self->m_gateDrainTimeouts;
					break;
				}
				cpuRelax();
			}
			self->m_gateDrainS += secondsSince(t0);
			empty = !m_cores[_core & 1]->hdi().hasRXData();
		}
		++self->m_gateCalls;
		if(!empty)
		{
			++self->m_gateFalse;
			if(self->m_gateOpenAt < 0.0)
				self->m_gateOpenAt = m_due;
		}
		else if(self->m_gateOpenAt >= 0.0)
		{
			++self->m_gateBlocks;
			self->m_gateSpanSum += m_due - self->m_gateOpenAt;
			self->m_gateOpenAt = -1.0;
			// how long after the core emptied its ring (in its own time, executed units) the gate saw it
			const Core& c0 = *m_cores[0];
			const double emptied = static_cast<double>(c0.drainEmptyAt.load(std::memory_order_relaxed)) + (m_rt ? static_cast<double>(m_rtc[0].offset.load(std::memory_order_relaxed)) : static_cast<double>(c0.executed) - static_cast<double>(c0.dsp->getInstructionCounter()));
			if(_core == 0 && emptied > 0.0)
				self->m_gateLateSum += m_due - emptied;
		}
		return empty;
	}
	uint64_t DspPair::pulled(const int _core) const { return m_cores[_core & 1]->pulled; }
	uint64_t DspPair::pullShort(const int _core) const { return m_cores[_core & 1]->pullShort; }
	uint64_t DspPair::mailboxWords(const int _from) const { return m_mail[_from & 1].words; }
	bool DspPair::bootFinished(const int _core) const { return m_cores[_core & 1]->boot->finished(); }
	// --dsp-reset-on (dsp.h): the MODEL of a reset line, not a claim that one
	// exists. Both cores go back to the state the ColdFire's upload expects
	// at a power-on: the boot state machine at Length, the host port's
	// registers reset with HTDE set and its RECEIVE ring empty, HPCR back to
	// the mode the ROM leaves it in (HEN alone -- the payload's start sets
	// bit 7 on top of it, which is what OS SWITCH's park has to undo), and
	// the core not stepped until a program has been loaded again.
	//
	// The receive ring matters, and cost a debug: the probe's control pass
	// sends words into the RUNNING payload's host port, which does not read
	// them. Without the clear they survived the modelled reset, and the
	// stock bootstrap that the re-upload loads read them as its first
	// record -- type 7, a garbage count, a `dor` waiting for words no one
	// was sending, while the ColdFire waited for its echo. A chip reset
	// empties the interface; so does this.
	//
	// What is NOT modelled: the cores' X/Y/P keep the payload's bytes, as
	// they do on the chip; the transmit ring is left as it is (no API, and
	// the probe reads its one word back); and ICR INIT, which on the chip
	// also resets the interface, still does nothing here.
	void DspPair::bootReset()
	{
		++m_bootResets;
		for(int i = 0; i < 2; ++i)
		{
			Core& c = *m_cores[i];
			c.boot->reset();
			c.hdi().reset();
			c.hdi().clearRX();
			c.hdi().writePortControlRegister(1 << dsp56k::HDI08::HPCR_HEN);
			m_bootDone[i].store(false, std::memory_order_release);
		}
	}
	uint64_t DspPair::executed(const int _core) const
	{
		if(m_rt) { const_cast<DspPair*>(this)->rtRefresh(); return m_cores[_core & 1]->executed; }
		const_cast<DspPair*>(this)->catchUp(); return m_cores[_core & 1]->executed;
	}
	uint64_t DspPair::hostWordsIn(const int _core) const { return m_cores[_core & 1]->wordsIn; }
	uint64_t DspPair::hostWordsOut(const int _core) const { return m_cores[_core & 1]->wordsOut; }
	uint64_t DspPair::hostCommands(const int _core) const { return m_cores[_core & 1]->commands; }
	uint64_t DspPair::framesPerCommandMin(const int _core) const { const Core& c = *m_cores[_core & 1]; return c.fpcSamples ? c.fpcMin : 0; }
	uint64_t DspPair::framesPerCommandMax(const int _core) const { return m_cores[_core & 1]->fpcMax; }
	uint64_t DspPair::framesPerCommandSixteen(const int _core) const { return m_cores[_core & 1]->fpcSixteen; }
	uint32_t DspPair::bootLength(const int _core) const { return m_cores[_core & 1]->boot->getLength(); }
	uint32_t DspPair::bootAddress(const int _core) const { return m_cores[_core & 1]->boot->getInitialPC(); }
	const std::vector<int32_t>& DspPair::audioOut(const int _core) const { return m_cores[_core & 1]->capture; }

	// -- audio over the pipe (12 Sep 2026): a bounded ring of core 0's frames --
	void DspPair::setAudioStream(const StreamMode _mode)
	{
		std::unique_lock<std::mutex> lk(m_streamMx, std::defer_lock);
		if(m_rt)
			lk.lock();
		m_streamMode = _mode;
		m_stream.clear();
		m_stream.shrink_to_fit();
		m_streamHead = m_streamCount = 0;
		m_streamCaptured = m_streamDropped = 0;
		if(_mode != StreamMode::Off)
			m_stream.assign(static_cast<size_t>(g_streamCapFrames) * streamWords(_mode), 0);
		// O23: the stems are staged only while the Tracks mode is on (the
		// tap's flag is read on core 0's thread; the staging is cleared here
		// so a restarted stream never carries a previous run's half)
		std::memset(m_stems, 0, sizeof m_stems);
		m_stemTaps.store(0, std::memory_order_relaxed);
		m_stemsOn.store(_mode == StreamMode::Tracks, std::memory_order_release);
	}

	void DspPair::streamPush(const int32_t* _words, const int _group)
	{
		const auto n = streamWords(m_streamMode);
		if(!n)
			return;
		if(m_streamCount == g_streamCapFrames)
		{
			// Full: the oldest frame goes, and is counted (`audio status dropped=`).
			m_streamHead = (m_streamHead + 1) % g_streamCapFrames;
			--m_streamCount;
			++m_streamDropped;
		}
		auto* dst = &m_stream[((m_streamHead + m_streamCount) % g_streamCapFrames) * n];
		const uint32_t first = m_streamMode == StreamMode::Main ? 2 : m_streamMode == StreamMode::Cue ? 4 : 0;
		const uint32_t esai = m_streamMode == StreamMode::Tracks ? g_audioSlots : n;
		for(uint32_t k = 0; k < esai; ++k)
			dst[k] = static_cast<int16_t>(_words[first + k] >> 8);		// 24-bit word -> 16-bit, as writeWav24's top bytes
		if(m_streamMode == StreamMode::Tracks)
		{
			// O23: the 16 stem words staged for this sample's ring half (THE STEM TAP)
			if(_group >= 0 && _group < 32)
				std::memcpy(dst + g_audioSlots, m_stems[_group >> 4][_group & 15], sizeof(int16_t) * g_stemWords);
			else
				std::memset(dst + g_audioSlots, 0, sizeof(int16_t) * g_stemWords);
		}
		++m_streamCount;
		++m_streamCaptured;
	}

	// O23: THE STEM TAP (dsp.h). Core 0 is at P:0x2d5: the mixdown of one ring
	// half has just run. What it read is still in place -- the forwarded
	// per-track blocks at X:$204 (0x4400 bank A / 0x2400 bank B: track k's 16
	// stereo samples at +32k, L at +2j, R at +2j+1, 24-bit signed after the
	// hi/lo join at P:0xed), the per-track main gains at Y:0x4a + 20j + k (the
	// ramp of P:0x203-0x237; the cue mix overwrites Y:0x40-0x5f only later,
	// at P:0x32d) -- and the half is named by X:$203 (the ring pointer r0 of
	// the bank take: 0x8080 = the half 0x80-0xff, 0x8000 = 0x00-0x7f). The
	// mixdown's arithmetic per term: `mpy/mac y0,x0` (a fractional 24x24
	// product, the accumulator holds it <<1), `asl #2`, then the move of the
	// accumulator to a 24-bit word (limited). The tap forms each track's term
	// alone the same way, so the sum of the eight stems is the main word up
	// to the per-term truncation (the mixdown truncates the sum once) and
	// the two input terms / the click, which no track owns. Under the
	// MASTER TRACK path (P:0x292, bit 10 of x:(r6+$7e)) the main pair is
	// track 8 alone and tracks 1-7 feed it: the stems are then each track's
	// term with its own gain, which is what the master receives, not what
	// the main carries -- documented, not special-cased.
	void DspPair::stemTap(Core& c)
	{
		const uint32_t* X = c.mem->getMemAreaPtr(dsp56k::MemArea_X);
		const uint32_t* Y = c.mem->getMemAreaPtr(dsp56k::MemArea_Y);
		const uint32_t ring = X[0x203] & 0xffffff;
		const uint32_t fwd = X[0x204] & 0xffffff;
		if((ring != 0x8000 && ring != 0x8080) || (fwd != 0x4400 && fwd != 0x2400))
			return;			// not the dispatcher's frame state (a boot-time arrival): nothing staged
		const int half = ring == 0x8080 ? 1 : 0;
		auto* out = m_stems[half];
		for(uint32_t j = 0; j < 16; ++j)
		{
			for(uint32_t k = 0; k < 8; ++k)
			{
				const int32_t g = static_cast<int32_t>(Y[0x4a + 20 * j + k] << 8) >> 8;		// 24-bit signed fractional
				for(uint32_t ch = 0; ch < 2; ++ch)
				{
					const int32_t x = static_cast<int32_t>(X[fwd + 32 * k + 2 * j + ch] << 8) >> 8;
					int64_t acc = (static_cast<int64_t>(x) * static_cast<int64_t>(g)) << 3;	// the product <<1, then asl #2
					int64_t w = acc >> 24;								// the accumulator's 24-bit word (a1)
					if(w > 0x7fffff) w = 0x7fffff; else if(w < -0x800000) w = -0x800000;		// the move's limiter
					out[j][2 * k + ch] = static_cast<int16_t>(w >> 8);	// 16-bit, as the ESAI words
				}
			}
		}
		m_stemTaps.fetch_add(1, std::memory_order_relaxed);
	}

	size_t DspPair::takeAudioStream(std::vector<int16_t>& _out, const size_t _maxFrames)
	{
		std::unique_lock<std::mutex> lk(m_streamMx, std::defer_lock);
		if(m_rt)
			lk.lock();
		const auto n = streamWords(m_streamMode);
		const size_t take = std::min(_maxFrames, m_streamCount);
		if(!n || !take)
			return 0;
		const size_t firstRun = std::min(take, static_cast<size_t>(g_streamCapFrames) - m_streamHead);	// up to the ring's end, then the wrap
		_out.insert(_out.end(), m_stream.begin() + m_streamHead * n, m_stream.begin() + (m_streamHead + firstRun) * n);
		if(firstRun < take)
			_out.insert(_out.end(), m_stream.begin(), m_stream.begin() + (take - firstRun) * n);
		m_streamHead = (m_streamHead + take) % g_streamCapFrames;
		m_streamCount -= take;
		return take;
	}
	DspPair::StreamStatus DspPair::streamStatus() const
	{
		std::unique_lock<std::mutex> lk(m_streamMx, std::defer_lock);
		if(m_rt)
			lk.lock();
		return {m_streamMode, m_streamCaptured, m_streamCount, m_streamDropped};
	}
	void DspPair::dirty(uint32_t _seed)
	{
		uint32_t x = _seed ? _seed : 0x2545f491;
		auto next = [&x]
		{
			x ^= x << 13; x ^= x >> 17; x ^= x << 5;
			return x & 0xffffff;
		};
		for(auto& c : m_cores)
			for(dsp56k::TWord ad = 0; ad < g_shareLo; ++ad)
			{
				c->mem->set(dsp56k::MemArea_X, ad, next());
				c->mem->set(dsp56k::MemArea_Y, ad, next());
			}
		for(auto& w : m_shared)
			w = next();
	}

	void DspPair::setAudioInput(std::vector<int32_t> _interleaved, const uint32_t _channels) { m_input = std::move(_interleaved); m_inputChannels = _channels; }
	uint64_t DspPair::txAtFirstCommand(const int _core) const { return m_cores[_core & 1]->txAtFirstCmd.load(std::memory_order_relaxed); }
	uint64_t DspPair::rxAtFirstCommand(const int _core) const { return m_cores[_core & 1]->rxAtFirstCmd.load(std::memory_order_relaxed); }
	uint64_t DspPair::txSlotNonZero(const int _core, const uint32_t _slot) const { return m_cores[_core & 1]->txNZ[_slot & 7]; }
	uint64_t DspPair::rxSlotNonZero(const int _core, const uint32_t _slot) const { return m_cores[_core & 1]->rxNZ[_slot & 7]; }
	uint64_t DspPair::counterSurplus(const int _core) const { return m_cores[_core & 1]->surplus; }
	uint64_t DspPair::zeroDeltaCalls(const int _core) const { return m_cores[_core & 1]->zeroDelta; }

	std::string DspPair::report() const
	{
		if(m_rt)
		{
			// O17: the workers at the due count and idle before their state is read
			const_cast<DspPair*>(this)->rtWait(0);
			const_cast<DspPair*>(this)->rtRefresh();
		}
		else
			const_cast<DspPair*>(this)->catchUp();		// O16c: the report is of the pair NOW
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
				"                     audio (O9): transport start at ESAI frame %llu out / %llu in; TX0 non-zero per RING WORD (slot + rotation %u..%u) %llu %llu %llu %llu %llu %llu %llu %llu; RX0 non-zero per slot %llu %llu %llu %llu %llu %llu %llu %llu; DSP counter %llu, surplus over interpreter calls %llu (%.3f%%), zero-delta calls %llu\n"
				"                     bank id -> host take: %llu takes, mean %.2f samples, max %.2f at take %llu (a ring half is 16; DMA2 dies past it); bank writes inside a pull %llu\n",
				i, c.boot->finished() ? "done" : "WAITING", c.boot->getLength(), c.boot->getInitialPC(),
				c.dsp->getPC().toWord(), static_cast<unsigned long long>(c.executed),
				static_cast<unsigned long long>(c.wordsIn), static_cast<unsigned long long>(c.wordsOut),
				static_cast<unsigned long long>(c.commands),
				c.dropped ? " (words DROPPED on a full ring)" : "",
				static_cast<unsigned long long>(c.rxFrames.load()), static_cast<unsigned long long>(c.txFrames.load()),
				static_cast<unsigned long long>(c.rxFrames1.load()), static_cast<unsigned long long>(c.txFrames1.load()),
				c.lastTx[0].load(), c.lastTx[1].load(), static_cast<unsigned long long>(c.idleSkipped),
				static_cast<unsigned long long>(m_mail[i].words),
				static_cast<unsigned long long>(c.pulled), static_cast<unsigned long long>(c.pullShort),
				static_cast<unsigned long long>(c.fpcSamples ? c.fpcMin : 0), static_cast<unsigned long long>(c.fpcMax),
				static_cast<unsigned long long>(c.fpcSixteen), static_cast<unsigned long long>(c.fpcSamples),
				c.px->read(0xffffb6, dsp56k::Nop), ((c.px->read(0xffffb6, dsp56k::Nop) >> 9) & 0x1f) + 1,
				c.esaiCyclesPerSlot,
				static_cast<unsigned long long>(c.txAtFirstCmd.load()), static_cast<unsigned long long>(c.rxAtFirstCmd.load()), c.rotMin, c.rotMax,
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
				for(uint32_t k = 0; k < g_shareHi - g_shareLo; ++k) if((m_rt ? m_sharedPtr[k] : m_shared[k]) & 0xffffff) ++nz;
				s += "                     shared window (P/X/Y 0x30000-0x3ffff, one memory" + std::string(m_rt ? ", MMU-aliased" : "") + "): " + std::to_string(nz) + " non-zero words now\n";
			}
			{
				std::string v = "                     interrupt vectors taken:";
				for(uint32_t vba = 0; vba < c.vectorsTaken.size(); ++vba)
				{
					const auto n = c.vectorsTaken[vba];
					if(!n)
						continue;
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
