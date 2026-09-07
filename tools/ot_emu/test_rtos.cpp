// The run loop, gated: does the firmware's own scheduler actually run?
//
// The FULL gate is the oracle diff (`tools/ot_emu/oracle.py` against a golden
// file route A writes), because only route A can say whether this machine
// agrees with the one that has been measured for a fortnight. That needs
// Python, a venv and a card image, so it is not a unit test.
//
// This is the self-contained half: boot the stock image, run the kernel, and
// assert route A's own M6a gate -- every expected task created with its exact
// fields, every one dispatched at least once, and the first switch boot->main.
// It catches a regression in the port without needing the oracle present.
#include <cstdio>
#include <fstream>
#include <string>
#include <vector>

#include "machine.h"
#include "rtos.h"

namespace
{
	int g_failures = 0;

	void check(const char* _what, const bool _ok, const std::string& _detail = {})
	{
		if(!_ok)
			++g_failures;
		std::printf("  [%s] %s%s%s\n", _ok ? "PASS" : "FAIL", _what,
			_detail.empty() ? "" : "  ", _detail.c_str());
	}
}

int main(int _argc, char** _argv)
{
	const std::string image = _argc > 1 ? _argv[1] : "out/raw/section_3_MAIN_OS.bin";
	std::ifstream f(image, std::ios::binary);
	if(!f)
	{
		// The stock image is the operator's own copy (`make os`), never in the
		// repo -- a missing one is a skip, not a failure.
		std::printf("SKIP: %s is not present (run `make os`)\n", image.c_str());
		return 0;
	}
	const std::vector<uint8_t> img((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());

	std::printf("rtos gate (route A's M6a, self-contained):\n");
	ot::Machine m(img);
	const auto boot = m.run(50'000'000);
	check("boots to the RTOS handoff", boot == ot::Machine::Stop::Handoff, m.why());
	if(boot != ot::Machine::Stop::Handoff)
		return 1;

	check("the firmware set VBR itself", m.vbr() == ot::g_vbr,
		"vbr " + std::to_string(m.vbr()));

	ot::Rtos rtos(m);
	rtos.install();
	const auto stop = rtos.run(1000.0);
	check("the kernel runs and the M6a gate passes", stop == ot::Rtos::Stop::Gate, rtos.why());

	std::vector<std::string> problems;
	const bool ok = rtos.gate(&problems);
	check("every expected task created, every one ran, first switch boot->main", ok);
	for(const auto& p : problems)
		std::printf("        - %s\n", p.c_str());

	check("ten tasks created", rtos.created().size() == 10,
		std::to_string(rtos.created().size()));
	check("eleven TCBs ran (the ten plus main)", rtos.ran().size() == 11,
		std::to_string(rtos.ran().size()));
	check("the gate is reached at about 205 ms",
		rtos.ms() > 150.0 && rtos.ms() < 260.0, std::to_string(rtos.ms()) + " ms");

	std::printf("%s\n", g_failures ? "RTOS GATE FAILED" : "rtos gate passed.");
	return g_failures ? 1 : 0;
}
