// ot_emu -- drive the headless Octatrack machine from the command line.
//
//   out/emu/ot_emu --image out/raw/section_3_MAIN_OS.bin [--max N] [--periph]
//
// MILESTONE O1: boot to the RTOS handoff. Route A is the oracle -- it reaches
// `trap #0` and reports the same peripheral touches -- so the useful output
// here is (a) where this stopped and (b) what it touched on the way, both
// directly comparable with `tools/emu_rtos.py` / `emu_bringup.boot`.
//
// Expect it to stop on an unimplemented opcode long before the handoff: the
// vendored Musashi is ColdFire V2 and this firmware is V4e. That report is
// the work list for the ISA half of the port, one opcode at a time.
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <string>
#include <vector>
#include <algorithm>
#include <utility>

#include "machine.h"

namespace
{
	std::vector<uint8_t> readFile(const std::string& _path)
	{
		std::ifstream f(_path, std::ios::binary);
		if(!f)
			return {};
		return std::vector<uint8_t>(std::istreambuf_iterator<char>(f), std::istreambuf_iterator<char>());
	}
}

int main(int _argc, char** _argv)
{
	std::string image = "out/raw/section_3_MAIN_OS.bin";
	uint64_t maxInstructions = 50'000'000;	// route A's own budget
	bool showPeripherals = false;
	bool profile = false;

	for(int i = 1; i < _argc; ++i)
	{
		const std::string a = _argv[i];
		if(a == "--image" && i + 1 < _argc)		image = _argv[++i];
		else if(a == "--max" && i + 1 < _argc)	maxInstructions = std::strtoull(_argv[++i], nullptr, 0);
		else if(a == "--periph")				showPeripherals = true;
		else if(a == "--profile")				profile = true;
		else
		{
			std::printf("usage: ot_emu [--image FILE] [--max N] [--periph]\n");
			return 2;
		}
	}

	const auto img = readFile(image);
	if(img.empty())
	{
		std::printf("cannot read %s (run `make os` for the stock image, or `make bus` for a built one)\n",
			image.c_str());
		return 1;
	}
	std::printf("image      : %s (%zu bytes) at %#x\n", image.c_str(), img.size(), ot::Machine::g_imageBase);

	ot::Machine m(img);
	if(profile)
		m.setProfile(64);
	const auto stop = m.run(maxInstructions);

	static const char* const g_names[] = {"HANDOFF", "ILLEGAL", "BUDGET", "FAULT"};
	std::printf("stopped    : %s -- %s\n", g_names[static_cast<int>(stop)], m.why().c_str());
	std::printf("instructions: %llu (%llu supplied by the V4e layer)\n",
		static_cast<unsigned long long>(m.instructions()),
		static_cast<unsigned long long>(m.v4eExecuted()));

	if(profile)
	{
		std::vector<std::pair<uint32_t, uint64_t>> hot(m.profile().begin(), m.profile().end());
		std::sort(hot.begin(), hot.end(), [](const auto& _a, const auto& _b){ return _a.second > _b.second; });
		std::printf("hottest addresses (PC sampled every 64 instructions):\n");
		for(size_t i = 0; i < hot.size() && i < 16; ++i)
		{
			char buf[256] = {};
			m.disassemble(hot[i].first, buf);
			std::printf("   %#08x  %8llu  %s\n", hot[i].first,
				static_cast<unsigned long long>(hot[i].second), buf);
		}
	}

	if(!m.autoPokes().empty())
	{
		std::printf("auto-pokes (completion flags no model answers, %zu):\n", m.autoPokes().size());
		for(const auto& p : m.autoPokes())
			std::printf("   loop %#08x -> wrote %#x to %#08x\n", p.pc, p.value, p.addr);
	}

	if(showPeripherals)
	{
		std::printf("peripheral touches (%zu logged):\n", m.peripheralLog().size());
		size_t n = 0;
		for(const auto& a : m.peripheralLog())
		{
			if(++n > 60)
			{
				std::printf("   ... %zu more\n", m.peripheralLog().size() - 60);
				break;
			}
			std::printf("   %c %#08x size %u = %#x   (pc %#06x)\n", a.kind, a.addr, a.size, a.val, a.pc);
		}
	}
	return stop == ot::Machine::Stop::Handoff ? 0 : 1;
}
