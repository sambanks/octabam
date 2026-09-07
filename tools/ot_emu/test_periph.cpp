// The peripheral gate: every rule these models carry, checked against the
// value route A's own model produces.
//
// The rules here are not obvious and several are counter-intuitive; each one
// below exists because getting it wrong produced a specific, silent failure in
// route A first (`docs/RTOS_FORK.md` §8.2, §4). Testing them is how a
// translation stays a translation rather than a rewrite.
#include <cstdio>
#include <cmath>

#include "periph.h"

namespace
{
	int g_failures = 0;

	void check(const char* _what, const bool _ok, const char* _detail = "")
	{
		if(!_ok)
			++g_failures;
		std::printf("  [%s] %s%s%s\n", _ok ? "PASS" : "FAIL", _what,
			*_detail ? "  " : "", _detail);
	}

	void checkEq(const char* _what, const uint64_t _got, const uint64_t _want)
	{
		char d[128];
		std::snprintf(d, sizeof d, "got %#llx want %#llx",
			static_cast<unsigned long long>(_got), static_cast<unsigned long long>(_want));
		check(_what, _got == _want, d);
	}
}

int main()
{
	std::printf("peripheral gate (models translated from tools/emu_rtos.py):\n");

	// ---- PIT -------------------------------------------------------------
	{
		// Route A's PIT0: the kernel's 5 ms tick. At the default 264 MHz
		// prescaler input the period is 220.5 samples, which is what makes the
		// sequencer's tick count come out right (M6a's gate: 28 ticks in 400
		// frames, matching the cold run).
		ot::Pit pit("PIT0", 264e6);
		// prescaler 2^11, PMR such that the period is ~220.5 samples:
		//   (pmr+1) * 2048 / 264e6 * 44100 = 220.5  ->  pmr+1 = 645
		pit.write(2, 2, 644, 0.0);						// PMR
		pit.write(0, 2, ot::Pit::EN | ot::Pit::RLD | ot::Pit::PIE | (11u << 8), 0.0);
		const auto period = pit.periodSamples();
		char d[128];
		std::snprintf(d, sizeof d, "period %.2f samples (want ~220.5)", period);
		check("PIT period comes from (PMR+1) << prescaler", std::fabs(period - 220.5) < 0.5, d);

		check("no expiry before the period is up", pit.advance(period - 1.0) == 0);
		check("one expiry at the period", pit.advance(period + 0.1) == 1);
		check("PIF raises the line while PIE is set", pit.irq());

		// PIF is WRITE-1-TO-CLEAR: writing it back clears it, and the line
		// drops. An emulator that treats the write as "set" leaves the ISR
		// re-entering forever.
		pit.write(0, 2, ot::Pit::EN | ot::Pit::RLD | ot::Pit::PIE | ot::Pit::PIF | (11u << 8), period);
		check("PIF is write-1-to-clear", !pit.irq());

		// RLD: the timer reloads, so a long jump forward fires once per period
		// rather than once in total.
		const auto n = pit.advance(period * 4.5);
		std::snprintf(d, sizeof d, "fired %u times over 3.5 periods", n);
		check("RLD reloads (a jump forward fires every period)", n >= 3 && n <= 4, d);
	}

	// ---- INTC ------------------------------------------------------------
	{
		ot::Intc intc("INTC0", 64);

		// A source is only deliverable once its ICR gives it a level: ICR 0 is
		// never delivered, whatever else is true.
		bool line = true;
		intc.addLine(1, [&]{ return line; });
		intc.write(0x1d, 1, 1);						// CIMR 1: unmask source 1
		check("a source with ICR 0 is never delivered", intc.pending().empty());

		intc.write(0x40 + 1, 1, 5);					// ICR1 = level 5
		const auto p = intc.pending();
		check("unmasked, with a level, it is delivered", p.size() == 1 && p[0].second == 1);

		intc.write(0x1c, 1, 1);						// SIMR 1: mask it again
		check("masked, it is not", intc.pending().empty());

		// ⚠️ THE RULE THAT COST 400 SILENT FRAMES: a FORCED source ignores the
		// mask entirely (MCF54455RM §17.2.3). The sequencer tick is source 32,
		// ICR 3, and nothing in the image ever unmasks it -- masking it here
		// leaves the sequencer dead.
		intc.write(0x40 + 32, 1, 3);				// ICR32 = level 3
		intc.write(0x1c, 1, 32);					// and MASK source 32
		intc.write(0x10, 4, 1u);					// INTFRCH bit 0 = source 32
		bool forcedDelivered = false;
		for(const auto& e : intc.pending())
			if(e.second == 32)
				forcedDelivered = true;
		check("a FORCED source is delivered THROUGH the mask (RM 17.2.3)", forcedDelivered);

		// MASKALL, and CIMR clearing it: inferred in route A, and the reason is
		// that nothing in the image writes IMRH/IMRL at all.
		ot::Intc other("INTC1", 128);
		other.addLine(2, []{ return true; });
		other.write(0x40 + 2, 1, 4);
		other.write(0x1c, 1, 0x40);					// SIMR 0x40: mask everything
		check("SIMR 0x40 masks all", other.pending().empty());
		other.write(0x1d, 1, 2);					// CIMR 2
		check("CIMR clears MASKALL with it (inferred)", !other.pending().empty());

		// Highest level first: the run loop delivers the head of this list.
		ot::Intc pri("INTC0", 64);
		pri.addLine(3, []{ return true; });
		pri.addLine(4, []{ return true; });
		pri.write(0x40 + 3, 1, 2);
		pri.write(0x40 + 4, 1, 6);
		pri.write(0x1d, 1, 3);
		pri.write(0x1d, 1, 4);
		const auto order = pri.pending();
		check("pending() is highest level first",
			order.size() == 2 && order[0].second == 4 && order[1].second == 3);

		// IPR reads back what is asserted, which is what the firmware polls.
		checkEq("IPRL reads back the asserted sources", pri.read(0x04, 4), (1u << 3) | (1u << 4));
	}

	std::printf("%s\n", g_failures ? "PERIPHERAL GATE FAILED" : "peripheral gate passed.");
	return g_failures ? 1 : 0;
}
