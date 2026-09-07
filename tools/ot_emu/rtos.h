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
