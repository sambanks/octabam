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

#include <cstdint>
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
		explicit Rtos(Machine& _m, double _ips = 3990.0, double _pitClockHz = 264e6);

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
		struct LoadResult { uint32_t ready = 0, partPtr = 0; bool posted = false; double ms = 0; };
		LoadResult loadProjectLive(const std::string& _set, const std::string& _project,
			double _runMs = 6000.0, double _mountMs = 3000.0);

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
		uint64_t ataInterrupts() const { return m_ataInterrupts; }
		bool ataLineAsserted() const { return m_ataIrq; }
		uint64_t idleSkips() const { return m_idleSkips; }
		uint64_t forces() const { return m_forces; }
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

	private:
		uint32_t curTcb();
		bool peripheralRead(uint32_t _addr, uint8_t _size, uint32_t& _out);
		void peripheralWrite(uint32_t _addr, uint8_t _size, uint32_t _val, bool _replay);
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
		Intc m_intc0, m_intc1;
		Uart m_uart64{"UART@fc064000", g_uartA}, m_uart68{"UART@fc068000", g_uartB};
		Dspi m_dspi;
		AtaCard* m_card = nullptr;
		bool m_ataIrq = false;
		uint64_t m_ataInterrupts = 0;

		std::vector<Created> m_created;
		std::vector<Dispatch> m_dispatches;
		std::pair<uint32_t, uint32_t> m_firstSwitch{0, 0};
		uint64_t m_idleSkips = 0, m_forces = 0;
		size_t m_seeded = 0;
		std::string m_why;
		Quirks m_quirks;
		bool m_installed = false;
		bool m_gateDirty = true;
		uint32_t m_injectedLevel = 0, m_injectedVector = 0;   // the line currently offered
	};
}
