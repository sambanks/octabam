// The machine RUNNING: the firmware's own scheduler, its tasks, its timers.
//
// This is the C++ counterpart of `tools/emu_rtos.py`'s `Rtos` class, and route
// A is the oracle (`docs/COLDFIRE_PORT.md`). Everything here is a translation
// of a named piece of that file, with its measurements and its warnings
// carried across rather than summarised.
//
// ⚠️ ONE DELIBERATE DIFFERENCE FROM ROUTE A, and it is the only one: route A
// hand-rolls exception entry and exit (`_push`, `_pop`) because Unicorn's
// CFV4E will not dispatch them -- its VBR is a no-op and its `rte` never
// arrives. The vendored Musashi DOES both: `m68ki_stack_frame_0000` has the
// ColdFire 2-longword frame (format `4 | A7[1:0]`, vector, SR, then PC --
// MCF5206e UM 3.4) and `m68ki_jump_vector` reads REG_VBR, which the firmware
// sets itself with a `movec %a0,%vbr` at 0x40000db6. So this port lets the
// CPU take its own exceptions, which is the hardware mechanism rather than a
// model of it. The oracle diff is what proves the two agree; if it ever
// disagrees, THAT is the finding, and the hand-rolled path is the fallback.
//
// Time is counted in SAMPLES, as route A counts it, because the two clocks the
// firmware cares about are fixed ratios of the sample clock. Instructions per
// sample (`ips`) is a knob with a default, not a truth.
#pragma once

#include <array>

#include <cstdint>
#include <functional>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "card.h"
#include "machine.h"
#include "periph.h"

namespace ot
{
	// The kernel, byte-exact (docs/RTOS_FORK.md §2, and route A's own header).
	inline constexpr uint32_t g_vbr       = 0x40000000;		// [0x400b9668], set at 0x40000db6
	inline constexpr uint32_t g_sched     = 0x40000550;		// one handler for trap #0 and PIT0
	inline constexpr uint32_t g_schedRte  = 0x400005a6;		// the scheduler's rte: a task is (re)entered
	inline constexpr uint32_t g_create    = 0x400005fc;		// create(tcb, entry, prio, stack, size)
	inline constexpr uint32_t g_curTcb    = 0x800068fc;		// current TCB
	inline constexpr uint32_t g_mainSpin  = 0x4001fc9c;		// `bras .` -- main's park, the idle point
	inline constexpr uint32_t g_mainTcb   = 0x46c7ae84;
	inline constexpr uint32_t g_bootTcb   = 0x46c7ae30;		// the context the first trap saves
	inline constexpr uint32_t g_handoff   = 0x40000e46;		// the boot's trap #0

	inline constexpr uint32_t g_kernelPost    = 0x40000c3c;	// post(queue, msg): never blocks
	inline constexpr uint32_t g_sysQueue      = 0x460d17ae;	// the sys task's command queue
	inline constexpr uint32_t g_sysMsgScratch = 0x46c00000;	// scratch for a hand-built message
	inline constexpr uint32_t g_ataSource     = 54;			// INTC1 source 54 -> vector 0xb6

	// The project load, from `emu_card.py`'s constants.
	inline constexpr uint32_t g_cardReady   = 0x460d1cb8;	// := 1 after a successful init+mount
	inline constexpr uint32_t g_setName     = 0x100f8480;	// current SET folder (0x104 bytes)
	inline constexpr uint32_t g_projectName = 0x100f8378;	// current PROJECT folder
	inline constexpr uint32_t g_postLoad    = 0x40023c7c;	// (name*) -> posts engine command 4
	inline constexpr uint32_t g_partPtr     = 0x46c82456;	// null until a project loads

	// ✅ O7b, 8 Sep 2026. `sys`'s media case reloads the current project when
	// one is named: `0x4006203a` calls `0x40056744` and, if it answers ZERO,
	// calls `0x4002574c` -- which is `if(strlen(0x100f8378)) post LOAD
	// PROJECT`. So whether a mount triggers a SECOND full load depends on
	// nothing but whether the project NAME has been written by the time `sys`
	// next gets the CPU. `g_mediaCaseJoin` is where that decision rejoins the
	// case, and waiting for it is how the harness makes the order a CHOICE
	// instead of a race (see `Rtos::loadProjectLive`).
	inline constexpr uint32_t g_mediaCaseJoin = 0x40062050;
	inline constexpr uint32_t g_projectExists = 0x4002574c;	// if(strlen(name)) post LOAD PROJECT

	// -- M6c: the sequencer, from route A's own constants ------------------
	// The bank blobs in RAM: PART_PTR = g_bankBlob + bank * g_bankStride,
	// i.e. the CURRENT bank's data. 0x400e21e0 is bank A, 0x4017d520 bank B.
	// ⚠️ PART_PTR reads the bank-A base BEFORE any load, so a non-null
	// PART_PTR is not on its own evidence that a project loaded (O7).
	inline constexpr uint32_t g_bankBlob        = 0x400e21e0;
	inline constexpr uint32_t g_bankStride      = 635712;
	inline constexpr uint32_t g_curBank         = 0x80000002;
	inline constexpr uint32_t g_curPattern      = 0x80000004;
	inline constexpr uint32_t g_engineBankWrite = 0x40087d44;	// LOAD PROJECT writes PART_PTR from BANK= here
	inline constexpr uint32_t g_selectBankCase  = 21;			// sys table[20]: "select bank msg[1]"

	inline constexpr uint32_t g_fwTransport   = 0x4009b964;	// (arg) transport start/stop; start posts to the UI queue
	inline constexpr uint32_t g_fwStartTrack  = 0x4009b5c8;	// (track) promote a track to running
	inline constexpr uint32_t g_fwSeqSelect   = 0x400a1030;	// sequencer select(bank, pattern): LOAD PROJECT's last step
	inline constexpr uint32_t g_fwSeqBank     = 0x800065bd;	// the sequencer's own playing bank byte
	inline constexpr uint32_t g_fwSeqPattern  = 0x800065be;	// ... and playing pattern
	inline constexpr uint32_t g_fwMidiSettings= 0x80000028;	// project MIDI byte: bit 0 = CLOCK RECEIVE
	inline constexpr uint32_t g_fwLiveNibble  = 0x46104d15;	// per-track byte a fired trig actually changes
	inline constexpr uint32_t g_fwTrigWords   = 0x46104d26;	// per-track word Bryan named; zero in every run so far
	// The sequencer tick: the frame handler's countdown expires and FORCES
	// INTC0 source 32, whose vector is 0x60 -- and the source is never
	// unmasked, because a forced request is not affected by the mask
	// (MCF54455RM rev 5 §17.2.3, and RTOS_FORK.md §8.2). Counting the
	// acknowledgements of that vector is counting ticks.
	inline constexpr uint8_t  g_tickVector    = 0x60;

	inline constexpr uint32_t g_intc0 = 0xfc048000, g_intc1 = 0xfc04c000;
	inline constexpr uint32_t g_pit0  = 0xfc080000, g_pit1  = 0xfc084000;
	inline constexpr uint32_t g_dspi  = 0xfc05c000;
	inline constexpr uint32_t g_uartA = 0xfc064000, g_uartB = 0xfc068000;

	// The tasks, as MEASURED under the real scheduler (route A's
	// EXPECTED_TASKS, 6 Sep 2026): tcb, entry, prio, stack, size, creator.
	// Main is created by the boot before any hook exists. ⚠️ RTOS_FORK §2's
	// table of eight was read from the five `jsr` create sites a literal scan
	// finds; the other five call through a register and were missed. Ten are
	// created.
	struct TaskSpec { uint32_t tcb, entry, prio, stack, size, creator; };
	extern const TaskSpec g_expectedTasks[10];

	const char* taskName(uint32_t _tcb);

	class Rtos
	{
	public:
		// ⚠️ `_frame` is OFF by default, as it is in route A, and the reason
		// is not caution: main's own boot tail unmasks INTC0 source 1
		// unconditionally (0x4001fc2e), so once the clock is modelled it
		// fires every 16 samples in EVERY run whether or not anything needs
		// the sequencer -- about 16x more dispatches, since PIT0's 220-sample
		// period is the coarsest timer otherwise. M6a's gate and the O5
		// serial comparison were both established without it. The register
		// state is real either way; only the model's assertion is gated.
		explicit Rtos(Machine& _m, double _ips = 3990.0, double _pitClockHz = 264e6,
			bool _frame = false);

		// A DELIBERATE DEPARTURE FROM ROUTE A, for the negative control only.
		// The gate compares the serial byte count, and a gate that has never
		// failed proves nothing (the standing rule, and why
		// `tools/verify_bus.py` carries a selftest). `test_rtos` runs the
		// machine a second time with `clearTransmitInterrupt` false and
		// requires the count to CHANGE, which is what makes the comparison
		// evidence rather than decoration. Nothing but the test sets it.
		struct Quirks { bool clearTransmitInterrupt = true; };
		void setQuirks(const Quirks& _q) { m_quirks = _q; }

		// Install the models over the peripheral window and SEED them by
		// replaying every write the boot made into the stub. Route A's
		// `install()`; it must be called after the boot and before `run`.
		void install();

		enum class Stop { Gate, Time, Fault, Illegal };
		Stop run(double _ms, bool _untilGate = true);
		// The same loop -- idle skip included, which is what makes a frame
		// run cheap -- stopping on a caller's condition instead of the gate.
		// Returns Stop::Gate when the condition came true.
		Stop runUntil(double _ms, const std::function<bool()>& _stop);

		// Run until the PC is parked at main's spin -- what `callAsMain`
		// needs before it can borrow the slot.
		Stop runToMainSpin(double _ms = 5000.0);

		// ---- the card ------------------------------------------------------
		// Interpose on the task-file window so the card raises INTRQ the way
		// ATA does (handler 0x40015304: one sector per interrupt, completion
		// signalled when the count reaches zero): asserted when a command
		// completes or a sector is ready, after each sector consumed with
		// more to come, and after each sector absorbed by a WRITE; cleared by
		// a read of the STATUS register, not the alternate status.
		//
		// ⚠️ This is route A's `cold_hooks=False` path: the kernel's own event
		// wait really blocks and the ATA interrupt really completes the
		// command. `emu_card.attach`'s `on_wait`/`on_nowait` shortcuts are
		// deliberately NOT translated -- they are for the cold detours, not
		// for a machine running its own RTOS.
		void attachCard(AtaCard& _card);
		void mapCardMemory();

		// Borrow main's idle slot to call an OS subroutine the way a UI action
		// would, with the normal trap-dispatch loop still live underneath, so
		// any REAL wait inside the call runs correctly against every other
		// task and interrupt. Convention: retaddr at [sp], args at [sp+4]...
		//
		// ⚠️ ONLY for a call that CANNOT genuinely block. Main is priority 0
		// and never legitimately blocks on hardware, so it is the kernel's de
		// facto idle backstop and main being non-ready is a state the block
		// path never expects -- route A proved it the hard way by borrowing
		// main for a call that waits on a real timer: main blocked, nothing
		// else was ready either, and the scheduler dispatched a garbage TCB.
		// A call that CAN block belongs to a real task: post it a message.
		bool callAsMain(uint32_t _addr, const std::vector<uint32_t>& _args, uint32_t& _d0,
			uint64_t _budget = 4000000);
		bool postMessage(uint32_t _queue, uint32_t _msg, uint32_t& _d0);

		// Post to the SYS task's own queue the message its dispatch table
		// sends to the card case: it checks "card ready" and, if clear, calls
		// the card init FOR REAL from SYS's context (priority 1, safe to
		// block). msg[0]=16 selects the case; msg[1] must be non-zero to
		// reach it (`tstb a2@(1)`, else the handler returns having done
		// nothing).
		bool requestCardMount();

		// -- M6c: the sequencer under the real scheduler ---------------------
		// Turn the DSP frame clock on HERE, after the boot and the load, which
		// is where route A's `--sequencer` turns it on -- not from boot.
		// ✅ Route A cannot be run with it on from boot at all (a bare
		// `Rtos(frame=True)` faults on unmapped memory before anything has
		// primed its auto-map hook), so the from-boot form has no oracle.
		void setFrame(bool _on);

		// Switch the working bank through sys's own case -- the very message
		// the engine's reset posts with bank 0 (RTOS_FORK.md §7): PART_PTR :=
		// the bank's blob, the blob is copied into SRAM, the bank byte
		// follows. Returns the bank byte.
		uint8_t selectBankLive(uint32_t _bank, double _ms = 500.0);

		// The sequencer's own bank/pattern select, the LOAD PROJECT handler's
		// LAST step. It writes the sequencer's playing bank/pattern -- the
		// bytes FW_START_TRACK and the step handler index the bank blob by.
		// ⚠️ Route A needs this re-issued after the load: by the time the
		// handler reaches its last step, `sys` has applied the engine's own
		// reset-time "select bank 0" in the handler's real card waits, so the
		// sequencer is left on bank A with an empty bank's pattern record.
		// It is COMPENSATION for an emulator ordering defect, not firmware
		// behaviour -- the unit comes up on the saved bank and plays it -- and
		// it goes when the load's timing is made faithful.
		std::pair<uint8_t, uint8_t> seqSelectLive(uint32_t _bank, uint32_t _pattern);

		// Clear the project's CLOCK RECEIVE bit so the sequencer runs on its
		// own clock. With it set -- as Sam's projects save it, the Rytm is
		// master -- the frame handler takes the external-clock path and the
		// countdown never moves: 400 frames, zero ticks, no trig.
		uint8_t internalClock();

		// Start the sequencer through the real tasks, the "M5 detour" §5
		// allows for M6c: FW_TRANSPORT(0)'s start case only sets state and
		// posts to the UI queue, and FW_START_TRACK(t) writes a per-track
		// state byte directly. Neither has a wait primitive on its path, so
		// both are safe under callAsMain.
		bool startTransportLive();

		// Set a trig on track 1 at `step` (1-64) in whichever bank PART_PTR
		// currently names: byte 7 - (step-1)/8, bit (step-1)%8 -- the layout
		// `ot_project.set_pattern_trig` writes on disk.
		uint8_t pokeTrig(uint32_t _step);

		// Watch the per-track live nibble and the trig words, keyed by this
		// machine's own frame count -- route A's `install_trig_log`.
		// Route A's `--watch-mem ADDR,LEN`: every write into a range, with the
		// sample, the task, the PC and the value. The counterpart instrument
		// to route A's, so a divergence can be diffed line for line instead of
		// reasoned about.
		// Route A's `--watch-pc`: the registers and the top of the stack each
		// time one of these addresses is ABOUT to execute -- so a hit on a
		// callee names its caller and its arguments. ⚠️ The check runs per
		// instruction, so it is guarded on the list being empty; with no
		// address watched it costs one compare.
		void watchPc(const std::vector<uint32_t>& _addrs);

		struct MemWrite { double sample; uint32_t tcb, pc, addr, val; uint8_t size; };
		void watchMem(uint32_t _addr, uint32_t _len);
		const std::vector<MemWrite>& memWrites() const { return m_memWrites; }

		void installTrigLog();
		struct TrigWrite { uint64_t frame; uint32_t index, value, pc; };
		const std::vector<TrigWrite>& liveNibbleLog() const { return m_liveNibble; }
		const std::vector<TrigWrite>& trigWordsLog() const { return m_trigWords; }
		// Sequencer ticks: acknowledgements of vector 0x60.
		uint64_t ticks() const;

		// ⚠️ The SET name is an ABSOLUTE path on the card -- the firmware's
		// own default is "/PRESETS". Without the leading slash the project
		// loads (relative to the root) and then every bank is "missing",
		// because the loader has already changed into the project directory.
		void setNames(const std::string& _set, const std::string& _project);

		// The whole M6b sequence: park, ask SYS to mount, wait for the card
		// to come ready, set the names, and post LOAD PROJECT the way the UI
		// does. ⚠️ Deliberately does NOT call the "does SET/PROJECT exist"
		// helper: with no card it short-circuits, but once a card IS present
		// it does real FAT lookups and BLOCKS -- and borrowing main for a
		// call that blocks is the crash `callAsMain` warns about.
		// `savedBank` is the bank the engine parsed from the project file's
		// BANK= key and wrote to PART_PTR (-1 if that write never happened --
		// the load did not get that far); `finalBank` is the current bank at
		// the end of the run. ⚠️ THE TWO CAN DIFFER, and that is a real
		// cross-task ordering rather than a load failure: SYS consumes the
		// engine reset's queued "select bank 0" whenever the scheduler next
		// gives it the CPU, and if that is AFTER the BANK= parse it switches
		// the working bank back to A (RTOS_FORK.md §7).
		struct LoadResult { uint32_t ready = 0, partPtr = 0; bool posted = false; double ms = 0;
			int savedBank = -1; uint32_t finalBank = 0;
			// Did `sys`'s media case run before the name was written? If it
			// did not, the mount may have triggered a second load.
			bool mediaCaseSeen = false;
			std::string postWhy;
			// How the load's own run ENDED. Time is the ordinary case (the
			// budget ran out); Fault/Illegal say the machine stopped, which
			// the ATA counts alone cannot distinguish from a stall.
			Stop stop = Stop::Time; std::string stopWhy; };
		// ⚠️ `_namesEarly` DECIDES WHETHER THE PROJECT LOADS ONCE OR TWICE, and
		// it is a property of the HARNESS, not of the firmware. See
		// `g_mediaCaseJoin`: with the name already written when `sys` runs its
		// media case, the firmware reloads the project and the run issues
		// 12,373 ATA commands instead of 6,189. Both orders are real -- on the
		// unit the name is set long before a card goes in, so the reload IS
		// what hardware does -- but only one of them is comparable with route
		// A's own numbers, so `false` (the name written after the media case)
		// is the default and is what the O7 gate measures.
		LoadResult loadProjectLive(const std::string& _set, const std::string& _project,
			double _runMs = 6000.0, double _mountMs = 3000.0, bool _namesEarly = false);
		// Run until the PC reaches an address, or the budget runs out.
		Stop runToPc(uint32_t _pc, double _ms);

		// -- what the oracle compares ---------------------------------------
		struct Created { double sample; uint32_t tcb, entry, prio, stack, size, creator; };
		struct Dispatch { double sample; uint32_t tcb, pc; };

		const std::vector<Created>& created() const { return m_created; }
		const std::vector<Dispatch>& dispatches() const { return m_dispatches; }
		std::unordered_set<uint32_t> ran() const;
		std::pair<uint32_t, uint32_t> firstSwitch() const { return m_firstSwitch; }
		double sample() const { return m_sample; }
		double ms() const { return m_sample / g_sampleHz * 1000.0; }
		uint64_t pit0Fired() const { return m_pit0.fired(); }
		uint64_t frameCount() const { return m_frameCount; }
		bool framePending() const { return m_framePending; }
		const Intc& intc0() const { return m_intc0; }
		const Intc& intc1() const { return m_intc1; }
		uint64_t edmaStarted() const { return m_edma.started(); }
		Edma& edma() { return m_edma; }
		// O8 step 4: blocks the eDMA carried over the host port, and words a
		// read-back could not get from the DSP in time.
		uint64_t hostBlocksOut() const { return m_hostBlocksOut; }
		uint64_t hostBlocksIn() const { return m_hostBlocksIn; }
		uint64_t hostWordsOut() const { return m_hostWordsOut; }
		uint64_t hostWordsIn() const { return m_hostWordsIn; }
		uint64_t hostWordsShort() const { return m_hostWordsShort; }
		// ⚠️ THE COUNT THAT DECIDES WHETHER ANY OF IT MEANS ANYTHING. Blocks and
		// words moved say the plumbing runs; only a non-zero count says the
		// frames carry content. An end-of-run peek of the DSP's record buffer
		// cannot tell "the port sent zeros" from "the DSP consumed and cleared
		// it" -- these are counted at the moment of the move.
		uint64_t hostNonZeroOut() const { return m_hostNonZeroOut; }
		uint64_t hostNonZeroIn() const { return m_hostNonZeroIn; }
		void setBlockLog(bool _on) { m_blockLogOn = _on; }
		const std::vector<std::string>& blockLog() const { return m_blockLog; }
		uint64_t ataInterrupts() const { return m_ataInterrupts; }
		bool ataLineAsserted() const { return m_ataIrq; }
		// Every access to the task-file window, in order, for diffing against
		// route A's: "R|W off size value pc". The first divergence names the
		// defect; reasoning about it does not.
		void setAtaTrace(bool _on) { m_ataTraceOn = _on; }
		const std::vector<std::string>& ataTrace() const { return m_ataTrace; }

		uint64_t idleSkips() const { return m_idleSkips; }
		uint64_t forces() const { return m_forces; }
		uint32_t currentTcb() { return curTcb(); }
		void setAtaLatency(double _samples) { m_ataLatency = _samples; }
		void armPcRing(size_t _size, uint64_t _budget) { m_pcRing.assign(_size, 0); m_pcRingBudget = _budget; }
		// Arm the ring HERE rather than at the first ATA command: the frame
		// handler runs long after the load, and "what did the one frame we
		// took actually do" is a different question from "what did the ISR do".
		void armPcRingNow(size_t _size) { m_pcRing.assign(_size, 0); m_pcRingPos = 0; m_pcRingArmed = true; }
		const std::vector<uint32_t>& pcRing() const { return m_pcRing; }
		size_t pcRingPos() const { return m_pcRingPos; }
		bool pcRingArmed() const { return m_pcRingArmed; }
		// Every vector the CPU acknowledged: (sample, vector, level, tcb, pc it
		// interrupted, slot contents). Which handler an interrupt actually
		// went to is a measurement, not a table lookup.
		struct Ack { double sample; uint8_t vector, level; uint32_t tcb, pc, slot; };
		const std::vector<Ack>& acks() const { return m_acks; }
		size_t seeded() const { return m_seeded; }
		size_t serialSent() const { return m_uart64.tx().size() + m_uart68.tx().size(); }
		const std::vector<uint8_t>& serialTxA() const { return m_uart64.tx(); }
		const std::vector<uint8_t>& serialTxB() const { return m_uart68.tx(); }
		size_t serialA() const { return m_uart64.tx().size(); }
		size_t serialB() const { return m_uart68.tx().size(); }
		const std::string& why() const { return m_why; }

		// Route A's `gate_m6a`: every expected task created with its fields,
		// every TCB dispatched at least once, and the first switch boot->main.
		bool gate(std::vector<std::string>* _problems = nullptr) const;

		void writeGoldenJson(const std::string& _path) const;

		// The M6c facts, in the same shape route A's `--sequencer --golden`
		// writes them, for `tools/ot_emu/oracle.py`: the trig log with frame
		// numbers relative to the transport start, the tick count, the frames
		// run, and the four bank/pattern bytes.
		struct M6c { uint64_t frame0 = 0, ticks0 = 0, frames = 0, ticks = 0;
			int savedBank = -1; uint32_t finalBank = 0, seqBank = 0, seqPattern = 0; };
		void writeM6cJson(const std::string& _path, const M6c& _m) const;

	private:
		uint32_t curTcb();
		bool peripheralRead(uint32_t _addr, uint8_t _size, uint32_t& _out);
		void peripheralWrite(uint32_t _addr, uint8_t _size, uint32_t _val, bool _replay);
		Stop runInternal(double _ms, bool _untilGate, const std::function<bool()>* _stop);
		void tickTimers();
		// One instruction plus everything the run loop does around it, so a
		// borrowed call runs against the same live machine the loop does.
		bool stepOnce();
		bool deliver();
		bool anyPending() const;
		bool nextExpiry(double& _out) const;
		void recordCreate();

		Machine& m_machine;
		double m_ips;
		double m_sample = 0.0;

		Pit m_pit0, m_pit1;
		Edma m_edma;
		Intc m_intc0, m_intc1;
		Uart m_uart64{"UART@fc064000", g_uartA}, m_uart68{"UART@fc068000", g_uartB};
		Dspi m_dspi;
		std::array<int, 16> m_kickSel = {};		// which core each channel was kicked against
		uint64_t m_hostBlocksOut = 0, m_hostBlocksIn = 0, m_hostWordsOut = 0, m_hostWordsIn = 0, m_hostWordsShort = 0;
		uint64_t m_hostNonZeroOut = 0, m_hostNonZeroIn = 0;
		struct PendingOut { uint32_t saddr = 0; std::vector<uint16_t> hw; uint64_t nonZero = 0; };
		std::array<PendingOut, 16> m_pendingOut;
		bool m_blockLogOn = false;
		std::vector<std::string> m_blockLog;
		void noteBlock(char _dir, uint32_t _ch, uint32_t _ramAddr, const std::vector<uint16_t>& _hw,
			uint64_t _nonZero, const std::string& _note);
		void installHostPortMover();
		AtaCard* m_card = nullptr;
		// ⚠️ INTRQ IS NOT INSTANTANEOUS, and the firmware depends on it. The
		// driver writes the command and THEN calls the RTOS event wait; a
		// drive that asserted INTRQ on the same instruction would run the ISR,
		// signal the event, and finish before the waiter ever waits -- and the
		// wait then blocks forever on a signal that already happened.
		// Measured 8 Sep 2026: that is exactly what this port did (1 IDENTIFY,
		// card-ready never set). Route A survives it only by accident of
		// granularity -- it delivers interrupts at burst boundaries, which
		// gives the caller time to reach the wait. A real CF card takes tens
		// of microseconds to fetch a sector, so the latency below is the
		// PHYSICAL behaviour and route A's is the artefact.
		bool m_ataIrq = false;
		double m_ataIrqDue = 0.0;			// 0 = nothing pending
		double m_ataLatency = 1.0;			// samples; ~23 us at 44.1 kHz
		uint64_t m_ataInterrupts = 0;
		std::vector<std::string> m_ataTrace;
		bool m_ataTraceOn = false;
		std::vector<Ack> m_acks;
		// A PC ring armed by the first ATA command: what the ISR does and
		// where the machine goes afterwards, which is the whole question.
		std::vector<uint32_t> m_pcRing;
		size_t m_pcRingPos = 0;
		bool m_pcRingArmed = false;
		uint64_t m_pcRingBudget = 0;

		std::vector<Created> m_created;
		std::vector<Dispatch> m_dispatches;
		std::pair<uint32_t, uint32_t> m_firstSwitch{0, 0};
		uint64_t m_idleSkips = 0, m_forces = 0;
		// ⚠️ A LATCH, NOT A COUNT. While the source is masked -- through the
		// boot, and through the handler's own self-mask for the whole DSP
		// exchange -- a real edge source remembers ONE edge, not how many it
		// missed. Route A counted them once and delivered ~540 phantom frames
		// back to back the moment main unmasked (measured 6 Sep 2026). The
		// handler re-arms itself only through the eDMA exchange; the ISR's
		// `rte` is not the ack.
		std::vector<TrigWrite> m_liveNibble, m_trigWords;
		std::vector<MemWrite> m_memWrites;
		bool m_trigLogInstalled = false;
		bool m_partPtrWatched = false;
		int m_savedBank = -1;
		bool m_frame = false;
		bool m_framePending = false;
		double m_nextFrame = g_framePeriod;
		uint64_t m_frameCount = 0;
		size_t m_seeded = 0;
		std::string m_why;
		Quirks m_quirks;
		bool m_installed = false;
		bool m_gateDirty = true;
		uint32_t m_injectedLevel = 0, m_injectedVector = 0;   // the line currently offered
	};
}
