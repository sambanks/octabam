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
#include <map>
#include <memory>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <string>
#include <vector>
#include <algorithm>
#include <utility>
#include <string>

#include "machine.h"
#include "rtos.h"

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
	std::string golden;
	std::string cardImage;		// a FAT16 card image built by emu_rtos.stage_project
	bool mount = false;			// post the card-mount request to the SYS task
	std::string ataTrace;		// write every task-file access here, for diffing against route A
	std::string periphTrace;	// every peripheral access over the load, for the same diff
	std::string peeks;			// comma-separated hex addresses to print after the load
	uint64_t pcRing = 0;		// instructions to record from the first ATA command
	double loadMs = 6000.0;		// emulated ms to run after LOAD PROJECT is posted
	std::string setName = "OCTABAM", projectName = "ONEAUX";
	std::string serialOut;
	double runMs = 1000.0;
	double ips = 3990.0;
	bool frame = false;			// the DSP frame clock; off by default, as in route A

	for(int i = 1; i < _argc; ++i)
	{
		const std::string a = _argv[i];
		if(a == "--image" && i + 1 < _argc)		image = _argv[++i];
		else if(a == "--max" && i + 1 < _argc)	maxInstructions = std::strtoull(_argv[++i], nullptr, 0);
		else if(a == "--periph")				showPeripherals = true;
		else if(a == "--profile")				profile = true;
		else if(a == "--golden" && i + 1 < _argc)	golden = _argv[++i];
		else if(a == "--card" && i + 1 < _argc)		cardImage = _argv[++i];
		else if(a == "--mount")						mount = true;
		else if(a == "--ata-trace" && i + 1 < _argc)	ataTrace = _argv[++i];
		else if(a == "--periph-trace" && i + 1 < _argc)	periphTrace = _argv[++i];
		else if(a == "--peek" && i + 1 < _argc)		peeks = _argv[++i];
		else if(a == "--pc-ring" && i + 1 < _argc)	pcRing = std::strtoull(_argv[++i], nullptr, 0);
		else if(a == "--load-ms" && i + 1 < _argc)	loadMs = std::atof(_argv[++i]);
		else if(a == "--set" && i + 1 < _argc)		setName = _argv[++i];
		else if(a == "--project" && i + 1 < _argc)	projectName = _argv[++i];
		else if(a == "--serial-out" && i + 1 < _argc)	serialOut = _argv[++i];
		else if(a == "--ms" && i + 1 < _argc)	runMs = std::atof(_argv[++i]);
		else if(a == "--ips" && i + 1 < _argc)	ips = std::atof(_argv[++i]);
		else if(a == "--frame")					frame = true;
		else
		{
			std::printf("usage: ot_emu [--image FILE] [--max N] [--periph] [--profile]\n"
			"              [--golden FILE] [--ms N]\n");
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

	// -- past the handoff: the RTOS itself (milestone O4) -------------------
	if(stop == ot::Machine::Stop::Handoff)
	{
		std::printf("vbr        : %#x (the firmware's own `movec %%a0,%%vbr` at 0x40000db6)\n", m.vbr());
		ot::Rtos rtos(m, ips, 264e6, frame);
		// The card is attached BEFORE install, as route A attaches it before
		// `Rtos.install()`: its four memory maps have to be in place before
		// anything runs, and the boot's replayed writes must not start a
		// transfer on a window that is about to change owner.
		std::unique_ptr<ot::AtaCard> card;
		if(!cardImage.empty())
		{
			std::ifstream cf(cardImage, std::ios::binary);
			if(!cf)
			{
				std::printf("card       : %s could not be opened\n", cardImage.c_str());
				return 1;
			}
			std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(cf)),
				std::istreambuf_iterator<char>());
			card = std::make_unique<ot::AtaCard>(std::move(bytes));
			rtos.attachCard(*card);
			rtos.setAtaTrace(!ataTrace.empty());
			std::printf("card       : %s, %u sectors\n", cardImage.c_str(), card->totalSectors());
		}
		rtos.install();
		const auto rs = rtos.run(runMs);
		static const char* const g_rtosNames[] = {"GATE", "TIME", "FAULT", "ILLEGAL"};
		std::printf("rtos       : %s -- %s\n", g_rtosNames[static_cast<int>(rs)], rtos.why().c_str());
		std::printf("             %.2f ms, %zu tasks created, %zu dispatches, %zu ran, "
			"PIT0 fired %llu, %llu idle skips, seeded from %zu boot writes\n",
			rtos.ms(), rtos.created().size(), rtos.dispatches().size(), rtos.ran().size(),
			static_cast<unsigned long long>(rtos.pit0Fired()),
			static_cast<unsigned long long>(rtos.idleSkips()), rtos.seeded());
		std::printf("frame      : %s -- %llu frame interrupt(s) taken, %llu eDMA transfer(s) started\n",
			frame ? "on" : "off (route A's default: main unmasks source 1 unconditionally)",
			static_cast<unsigned long long>(rtos.frameCount()),
			static_cast<unsigned long long>(rtos.edmaStarted()));
		std::vector<std::string> problems;
		const bool ok = rtos.gate(&problems);
		std::printf("M6a gate   : %s\n", ok ? "PASS" : "FAIL");
		for(const auto& p : problems)
			std::printf("   - %s\n", p.c_str());
		// THE MOUNT. Reaching the M6a gate is not enough: the card case runs
		// in the SYS task, so the machine has to be parked at main's spin
		// before the request can be posted, and then run on so SYS can do it.
		if(mount && card)
		{
			{
				if(pcRing)
					rtos.armPcRing(4096, pcRing);
				const auto forces0 = rtos.forces();
				const auto disp0 = rtos.dispatches().size();
				m.setPeriphTrace(!periphTrace.empty());
				const auto r = rtos.loadProjectLive(setName, projectName, loadMs);
				m.setPeriphTrace(false);
				std::printf("             card ready: %#x, LOAD PROJECT posted: %s, "
					"PART_PTR: %#x, %.1f ms emulated%s%s\n",
					r.ready, r.posted ? "yes" : "no", r.partPtr, r.ms,
					r.postWhy.empty() ? "" : " | post: ", r.postWhy.c_str());
				std::printf("             forces %llu, dispatches %zu over the load; now in %s at pc %#x\n",
					static_cast<unsigned long long>(rtos.forces() - forces0),
					rtos.dispatches().size() - disp0, ot::taskName(rtos.currentTcb()), m.pc());
				std::printf("             dispatch tail:\n");
				const auto& ds = rtos.dispatches();
				for(size_t i = ds.size() > 14 ? ds.size() - 14 : 0; i < ds.size(); ++i)
					std::printf("               [%9.1f] %-10s pc=%#x\n", ds[i].sample, ot::taskName(ds[i].tcb), ds[i].pc);
				{
					// Vectors by (vector, slot): how many times each was taken,
					// and the tail in order. A slot holding the kernel's
					// trampoline 0x40000d74 is an interrupt nobody claimed.
					std::map<std::pair<uint32_t, uint32_t>, uint64_t> byVec;
					for(const auto& k : rtos.acks())
						++byVec[{k.vector, k.slot}];
					std::printf("             vectors acknowledged (%zu):", rtos.acks().size());
					for(const auto& [key, cnt] : byVec)
						std::printf(" v%#x->%#x x%llu", key.first, key.second, static_cast<unsigned long long>(cnt));
					std::printf("\n             ack tail:\n");
					const auto& ks = rtos.acks();
					for(size_t i = ks.size() > 12 ? ks.size() - 12 : 0; i < ks.size(); ++i)
						std::printf("               [%9.1f] v%#04x lvl %u in %-10s at pc %#x -> slot %#x\n",
							ks[i].sample, ks[i].vector, ks[i].level, ot::taskName(ks[i].tcb), ks[i].pc, ks[i].slot);
				}
				if(pcRing && rtos.pcRingArmed())
				{
					const auto& ring = rtos.pcRing();
					const auto pos = rtos.pcRingPos();
					std::printf("             pc ring (last %zu of %zu recorded from the first ATA command):\n",
						std::min(ring.size(), pos), pos);
					const size_t n = std::min(ring.size(), pos);
					uint32_t last = 0; uint64_t runlen = 0;
					for(size_t i = 0; i < n; ++i)
					{
						const auto v = ring[(pos - n + i) % ring.size()];
						if(v == last) { ++runlen; continue; }
						if(runlen > 1) std::printf(" (x%llu)", static_cast<unsigned long long>(runlen));
						if(i) std::printf("\n");
						std::printf("               %#010x", v);
						last = v; runlen = 1;
					}
					if(runlen > 1) std::printf(" (x%llu)", static_cast<unsigned long long>(runlen));
					std::printf("\n");
				}
				if(!peeks.empty())
				{
					std::printf("             peek:");
					size_t p = 0;
					while(p < peeks.size())
					{
						auto q = peeks.find(',', p);
						if(q == std::string::npos) q = peeks.size();
						const auto addr = static_cast<uint32_t>(std::strtoul(peeks.substr(p, q - p).c_str(), nullptr, 16));
						std::printf(" [%#x]=%#x", addr, m.peek32(addr));
						p = q + 1;
					}
					std::printf("\n");
				}
				if(!periphTrace.empty())
				{
					std::ofstream t(periphTrace);
					for(const auto& e : m.periphTrace())
					{
						char line[64];
						std::snprintf(line, sizeof line, "%c %08x %u %08x %08x", e.kind == 'R' ? 'R' : 'W', e.addr, e.size, e.val, e.pc);
						t << line << '\n';
					}
					std::printf("             periph trace: %s (%zu accesses)\n", periphTrace.c_str(), m.periphTrace().size());
				}
			}
			size_t reads = 0, identifies = 0;
			for(const auto& e : card->log())
			{
				if(e.what == "READ")
					++reads;
				else if(e.what == "IDENTIFY")
					++identifies;
			}
			std::printf("             ATA interrupts taken: %llu; line still asserted: %s\n",
				static_cast<unsigned long long>(rtos.ataInterrupts()),
				rtos.ataLineAsserted() ? "YES" : "no");
			std::printf("             %zu ATA command(s): %zu IDENTIFY, %zu READ, "
				"%llu sector(s) read, %llu written\n",
				card->log().size(), identifies, reads,
				static_cast<unsigned long long>(card->sectorsRead()),
				static_cast<unsigned long long>(card->sectorsWritten()));
			if(!ataTrace.empty())
			{
				std::ofstream t(ataTrace);
				for(const auto& l : rtos.ataTrace())
					t << l << '\n';
				std::printf("             ATA trace: %s (%zu accesses)\n", ataTrace.c_str(), rtos.ataTrace().size());
			}
			for(size_t i = 0; i < card->log().size() && i < 12; ++i)
				std::printf("             %-16s lba %-8u count %u\n", card->log()[i].what.c_str(),
					card->log()[i].lba, card->log()[i].count);
		}

		if(!serialOut.empty())
		{
			for(const auto& [suffix, tx] : {std::make_pair("a", &rtos.serialTxA()),
				std::make_pair("b", &rtos.serialTxB())})
			{
				std::ofstream o(serialOut + "." + suffix, std::ios::binary);
				o.write(reinterpret_cast<const char*>(tx->data()), static_cast<std::streamsize>(tx->size()));
			}
			std::printf("serial out : %s.a (%zu B), %s.b (%zu B)\n",
				serialOut.c_str(), rtos.serialTxA().size(), serialOut.c_str(), rtos.serialTxB().size());
		}
		if(!golden.empty())
		{
			rtos.writeGoldenJson(golden);
			std::printf("golden     : %s\n", golden.c_str());
		}
	}

	// ⚠️ Unmapped memory: route A FAULTS here and this machine answers
	// all-ones, so anything in this list is a place the two emulators can
	// disagree without either of them saying so. Grouped by address, with the
	// PC of the first touch, because the address is the work item.
	if(m.unmappedCount())
	{
		std::map<uint32_t, std::pair<uint64_t, ot::Machine::Unmapped>> byAddr;
		for(const auto& u : m.unmapped())
		{
			auto it = byAddr.find(u.addr);
			if(it == byAddr.end())
				byAddr.emplace(u.addr, std::make_pair(uint64_t(1), u));
			else
				++it->second.first;
		}
		std::printf("auto-mapped: %llu access(es) outside every declared region and window "
			"(%llu read, %llu written), %zu distinct address(es)%s\n",
			static_cast<unsigned long long>(m.unmappedCount()),
			static_cast<unsigned long long>(m.unmappedReads()),
			static_cast<unsigned long long>(m.unmappedWrites()), byAddr.size(),
			m.unmapped().size() < m.unmappedCount() ? " (log capped at 4096)" : "");
		std::printf("             %llu zero page(s) grown, %llu KB -- route A grows the same "
			"four spans (COLDFIRE_PORT.md O5)\n",
			static_cast<unsigned long long>(m.autoMappedPages()),
			static_cast<unsigned long long>(m.autoMappedPages() * 4));
		// By 64 KB page and by the PC doing it -- uncapped, so a loop that
		// runs millions of times is one line rather than a truncated list.
		// Contiguous 64 KB pages are COALESCED into one span: the interesting
		// number is how far a runaway clear reached, and 700 page lines hide it.
		std::map<uint32_t, uint64_t> pages(m.unmappedPages().begin(), m.unmappedPages().end());
		std::printf("             spans:");
		uint32_t runFirst = 0, runLast = 0;
		uint64_t runCount = 0;
		bool inRun = false;
		const auto flush = [&]()
		{
			if(!inRun)
				return;
			std::printf(" %#010x-%#010x x%llu", runFirst << 16, ((runLast + 1) << 16) - 1,
				static_cast<unsigned long long>(runCount));
		};
		for(const auto& [page, count] : pages)
		{
			if(inRun && page == runLast + 1)
			{
				runLast = page;
				runCount += count;
				continue;
			}
			flush();
			runFirst = runLast = page;
			runCount = count;
			inRun = true;
		}
		flush();
		std::printf("\n");
		std::vector<std::pair<uint32_t, uint64_t>> pcs(m.unmappedPcs().begin(), m.unmappedPcs().end());
		std::sort(pcs.begin(), pcs.end(), [](const auto& _a, const auto& _b) { return _a.second > _b.second; });
		std::printf("             pcs:");
		for(size_t i = 0; i < pcs.size() && i < 6; ++i)
			std::printf(" %#010x x%llu", pcs[i].first, static_cast<unsigned long long>(pcs[i].second));
		std::printf("%s\n", pcs.size() > 6 ? " ..." : "");
		std::vector<std::pair<uint32_t, uint64_t>> rpcs(m.unmappedReadPcs().begin(), m.unmappedReadPcs().end());
		std::sort(rpcs.begin(), rpcs.end(), [](const auto& _a, const auto& _b) { return _a.second > _b.second; });
		std::printf("             read pcs:");
		for(size_t i = 0; i < rpcs.size() && i < 6; ++i)
			std::printf(" %#010x x%llu", rpcs[i].first, static_cast<unsigned long long>(rpcs[i].second));
		std::printf("%s\n", rpcs.size() > 6 ? " ..." : "");
		size_t n = 0;
		for(const auto& [addr, e] : byAddr)
		{
			if(n++ == 8)
			{
				std::printf("   ... %zu more logged\n", byAddr.size() - 8);
				break;
			}
			std::printf("   %c%u %#010x  x%llu  first at pc %#010x -> %#x\n",
				e.second.kind, e.second.size, addr, static_cast<unsigned long long>(e.first),
				e.second.pc, e.second.val);
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
