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
#include "dsp.h"

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
	// ⚠️ LINE-BUFFERED, ALWAYS. Redirected to a file, printf is block-buffered,
	// so a run that dies mid-way writes NOTHING -- the O6 auto-map runaway
	// crashed three times before anyone saw a line of the report that would
	// have named it. Same family as the panic printer O7 could not finish.
	std::setvbuf(stdout, nullptr, _IOLBF, 0);
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
	std::string cmdLog;		// every ATA COMMAND in order, for diffing against route A
	uint64_t pcRing = 0;		// instructions to record from the first ATA command
	double loadMs = 6000.0;		// emulated ms to run after LOAD PROJECT is posted
	std::string setName = "OCTABAM", projectName = "ONEAUX";
	std::string serialOut;
	double runMs = 1000.0;
	double ips = 3990.0;
	bool frame = false;			// the DSP frame clock; off by default, as in route A
	bool sequencer = false;		// M6c: load, start the transport, run the sequencer for real
	int frames = 400;			// with --sequencer: DSP frames to run after the transport start
	int pokeTrig = 0;			// with --sequencer: set a trig on track 1 at this step (1-64)
	bool internalClock = false;	// with --sequencer: clear CLOCK RECEIVE
	int bankOverride = -1;		// with --sequencer: switch to this bank (default: the file's saved bank)
	std::string m6cGolden;		// the M6c facts as JSON, for tools/ot_emu/oracle.py
	std::string watchMem;		// ADDR,LEN -- log every write into that range (route A's own flag)
	std::string watchPc;		// comma-separated addresses -- log registers there (route A's own flag)
	bool namesEarly = false;	// write the SET/PROJECT names BEFORE the mount -- see O7b
	std::string hostPortLog;	// every write into the DSP host-port window -> FILE (O8)
	bool dsp = false;			// O8: put the two real DSP cores behind the host port
	double dspRatio = 1.14, dspIps = 4535.0;	// their clock, in DSP instructions per ColdFire instruction / per sample
	std::string dspLog;			// every host-side event on the DSP pair -> FILE
	uint64_t dspTrace = 0;		// a status line per core every N DSP instructions
	bool dspNoIdle = false;		// execute every poll of an idle core (fidelity check; slow)
	bool dspVerbose = false;	// the vendored DSP library's own log lines
	std::string edmaLog;		// every eDMA kick with its TCD fields -> FILE (O8 step 4)
	std::string dspPeek;		// core:space:addr,len[;...] -- DSP memory to print at the end

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
		else if(a == "--cmd-log" && i + 1 < _argc)		cmdLog = _argv[++i];
		else if(a == "--pc-ring" && i + 1 < _argc)	pcRing = std::strtoull(_argv[++i], nullptr, 0);
		else if(a == "--load-ms" && i + 1 < _argc)	loadMs = std::atof(_argv[++i]);
		else if(a == "--set" && i + 1 < _argc)		setName = _argv[++i];
		else if(a == "--project" && i + 1 < _argc)	projectName = _argv[++i];
		else if(a == "--serial-out" && i + 1 < _argc)	serialOut = _argv[++i];
		else if(a == "--ms" && i + 1 < _argc)	runMs = std::atof(_argv[++i]);
		else if(a == "--ips" && i + 1 < _argc)	ips = std::atof(_argv[++i]);
		else if(a == "--frame")					frame = true;
		else if(a == "--sequencer")				sequencer = true;
		// --sequencer needs a mounted card and a loaded project: it implies both.
		else if(a == "--frames" && i + 1 < _argc)	frames = std::atoi(_argv[++i]);
		else if(a == "--poke-trig" && i + 1 < _argc)	pokeTrig = std::atoi(_argv[++i]);
		else if(a == "--internal-clock")			internalClock = true;
		else if(a == "--bank" && i + 1 < _argc)		bankOverride = std::atoi(_argv[++i]);
		else if(a == "--m6c-golden" && i + 1 < _argc)	m6cGolden = _argv[++i];
		else if(a == "--watch-mem" && i + 1 < _argc)	watchMem = _argv[++i];
		else if(a == "--watch-pc" && i + 1 < _argc)	watchPc = _argv[++i];
		else if(a == "--names-early")			namesEarly = true;
		else if(a == "--hostport-log" && i + 1 < _argc)	hostPortLog = _argv[++i];
		else if(a == "--dsp")					dsp = true;
		else if(a == "--dsp-ratio" && i + 1 < _argc)	dspRatio = std::atof(_argv[++i]);
		else if(a == "--dsp-ips" && i + 1 < _argc)	dspIps = std::atof(_argv[++i]);
		else if(a == "--dsp-log" && i + 1 < _argc)	dspLog = _argv[++i];
		else if(a == "--dsp-trace" && i + 1 < _argc)	dspTrace = std::strtoull(_argv[++i], nullptr, 0);
		else if(a == "--dsp-no-idle")			dspNoIdle = true;
		else if(a == "--dsp-verbose")			dspVerbose = true;
		else if(a == "--edma-log" && i + 1 < _argc)	edmaLog = _argv[++i];
		else if(a == "--dsp-peek" && i + 1 < _argc)	dspPeek = _argv[++i];
		else
		{
			std::printf("usage: ot_emu [--image FILE] [--max N] [--periph] [--profile]\n"
			"              [--golden FILE] [--ms N]\n");
			return 2;
		}
	}

	if(sequencer)
		mount = true;			// M6c needs the card mounted and the project loaded

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
	// ⚠️ BEFORE THE BOOT RUNS. Installed after it (where it used to be, behind
	// `rtos.install()`), a watch on a BOOT address reported zero hits whether
	// the address ran or not -- and the only caller of the DSP program loader
	// is at 0x4000050c, which is a boot address (O8, 8 Sep 2026).
	if(!watchPc.empty())
	{
		std::vector<uint32_t> addrs;
		size_t q = 0;
		while(q < watchPc.size())
		{
			auto e = watchPc.find(',', q);
			if(e == std::string::npos) e = watchPc.size();
			addrs.push_back(static_cast<uint32_t>(std::strtoul(watchPc.substr(q, e - q).c_str(), nullptr, 0)));
			q = e + 1;
		}
		m.watchPc(addrs);
		std::printf("watch-pc   : %zu address(es), armed before the boot\n", addrs.size());
	}
	if(!hostPortLog.empty())
		m.setHostPortLog(true);		// before the boot: the DSP upload happens IN it
	// The DSP pair, BEFORE the boot for the same reason: the firmware programs
	// both cores through the host port at instruction ~4.27M of the boot.
	std::unique_ptr<ot::DspPair> dspPair;
	if(dsp)
	{
		dspPair = std::make_unique<ot::DspPair>(dspRatio, dspIps);
		dspPair->setLog(!dspLog.empty());
		dspPair->setTrace(dspTrace);
		dspPair->setIdleSkip(!dspNoIdle);
		ot::DspPair::setVerbose(dspVerbose);
		m.setCoprocessor(dspPair.get());
		std::printf("dsp        : two cores behind the host port, %.2f instructions per ColdFire instruction, %.0f per sample\n",
			dspRatio, dspIps);
	}
	const auto stop = m.run(maxInstructions);

	static const char* const g_names[] = {"HANDOFF", "ILLEGAL", "BUDGET", "FAULT"};
	std::printf("stopped    : %s -- %s\n", g_names[static_cast<int>(stop)], m.why().c_str());
	std::printf("instructions: %llu (%llu supplied by the V4e layer)\n",
		static_cast<unsigned long long>(m.instructions()),
		static_cast<unsigned long long>(m.v4eExecuted()));
	if(dspPair)
		std::printf("dsp        : after the boot\n%s", dspPair->report().c_str());

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
		std::ofstream edmaOut;
		if(!edmaLog.empty())
		{
			edmaOut.open(edmaLog);
			rtos.edma().setTransferHook([&](const uint32_t _ch, const bool _paced)
			{
				const auto& e = rtos.edma();
				char line[256];
				std::snprintf(line, sizeof line,
					"kick ch %2u %s sample %.1f saddr %08x soff %d attr %04x nbytes %08x slast %d daddr %08x doff %d citer %04x dlast %d biter %04x csr %04x\n",
					_ch, _paced ? "paced" : "burst", rtos.sample(),
					e.tcdField(_ch, 0, 4), static_cast<int16_t>(e.tcdField(_ch, 4, 2)), e.tcdField(_ch, 6, 2),
					e.tcdField(_ch, 8, 4), static_cast<int32_t>(e.tcdField(_ch, 0xc, 4)), e.tcdField(_ch, 0x10, 4),
					static_cast<int16_t>(e.tcdField(_ch, 0x16, 2)), e.tcdField(_ch, 0x14, 2),
					static_cast<int32_t>(e.tcdField(_ch, 0x18, 4)), e.tcdField(_ch, 0x1c, 2), e.tcdField(_ch, 0x1e, 2));
				edmaOut << line;
			});
		}
		if(!watchMem.empty())
		{
			const auto comma = watchMem.find(',');
			const auto wa = static_cast<uint32_t>(std::strtoul(watchMem.c_str(), nullptr, 0));
			const auto wl = comma == std::string::npos ? 4u
				: static_cast<uint32_t>(std::strtoul(watchMem.c_str() + comma + 1, nullptr, 0));
			rtos.watchMem(wa, wl);
			std::printf("watch-mem  : %#x..%#x\n", wa, wa + wl - 1);
		}
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
			ot::Rtos::LoadResult load;
			{
				if(pcRing)
					rtos.armPcRing(4096, pcRing);
				const auto forces0 = rtos.forces();
				const auto disp0 = rtos.dispatches().size();
				m.setPeriphTrace(!periphTrace.empty());
				load = rtos.loadProjectLive(setName, projectName, loadMs, 3000.0, namesEarly);
				const auto& r = load;
				m.setPeriphTrace(false);
				std::printf("             card ready: %#x, LOAD PROJECT posted: %s, "
					"PART_PTR: %#x, %.1f ms emulated%s%s\n",
					r.ready, r.posted ? "yes" : "no", r.partPtr, r.ms,
					r.postWhy.empty() ? "" : " | post: ", r.postWhy.c_str());
				// ⚠️ PART_PTR reads bank A's blob base BEFORE any load, so it
				// is not on its own evidence that a project loaded (O7). The
				// bank the engine PARSED is: it comes from the write the
				// BANK= parse makes, and it is the number route A reports.
				std::printf("             names %s the mount; sys's media case %s before the name\n",
					namesEarly ? "BEFORE (--names-early: expect a second load)" : "after",
					r.mediaCaseSeen ? "ran" : "did NOT run");
				std::printf("             saved_bank: %d, final bank: %u%s\n",
					r.savedBank, r.finalBank,
					r.savedBank >= 0 && r.finalBank != static_cast<uint32_t>(r.savedBank)
						? "  (sys applied the engine's own reset-time 'select bank 0' "
						  "after the BANK= parse -- RTOS_FORK.md section 7)" : "");
				{
					static const char* const g_loadStop[] = {"GATE", "TIME", "FAULT", "ILLEGAL"};
					std::printf("             load run ended: %s%s%s\n",
						g_loadStop[static_cast<int>(r.stop)],
						r.stopWhy.empty() ? "" : " -- ", r.stopWhy.c_str());
				}
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
					std::printf("             pc ring (last %zu of %zu instructions since the first ATA command):\n",
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
			// The whole command sequence, in route A's own log order, so the
			// two can be diffed: the FIRST divergence names the defect.
			if(!cmdLog.empty())
			{
				std::ofstream t(cmdLog);
				size_t n = 0;
				for(const auto& e : card->log())
				{
					char line[160];
					// ⚠️ THE FIRST FIELD GROUP MUST STAY BYTE-COMPATIBLE with route
					// A's dump, because diffing the two logs is what proved
					// the port's first 1,407 commands were route A's (O7).
					// Everything O7b needs goes after a `|`, so
					// `cut -d'|' -f1` still reproduces the old form exactly.
					std::snprintf(line, sizeof line, "%s %u %u | #%zu pc %#010x %s",
						e.what.c_str(), e.lba, e.count, n++, e.pc, ot::taskName(e.tcb));
					t << line << '\n';
				}
				std::printf("             cmd log: %s (%zu commands)\n",
					cmdLog.c_str(), card->log().size());
			}
			for(size_t i = 0; i < card->log().size() && i < 12; ++i)
				std::printf("             %-16s lba %-8u count %u\n", card->log()[i].what.c_str(),
					card->log()[i].lba, card->log()[i].count);

			// -- M6c: the sequencer, for real (milestone O6) -----------------
			// Route A's `--sequencer` branch, step for step. The order is
			// load-bearing and every step of it is compensation or detour that
			// route A documents: the bank switch and the sequencer re-select
			// compensate for an emulator ordering defect (the unit comes up on
			// the saved bank and plays it), and the transport start is the
			// "M5 detour" RTOS_FORK.md §5 allows for M6c.
			if(sequencer)
			{
				const int bank = bankOverride >= 0 ? bankOverride : load.savedBank;
				uint32_t finalBank = load.finalBank;
				if(bank >= 0 && finalBank != static_cast<uint32_t>(bank))
					finalBank = rtos.selectBankLive(static_cast<uint32_t>(bank));
				const auto pattern = m.peek32(ot::g_curPattern) >> 24;
				const auto seq = rtos.seqSelectLive(finalBank, pattern);
				if(internalClock)
					std::printf("midi byte  : %#04x -> clock receive cleared\n", rtos.internalClock());
				// The frame clock and the exact instruction clock come on
				// HERE, after the boot and the load, exactly as route A turns
				// them on: on hardware the frame exchange runs from boot, and
				// nothing the trig test reads depends on it having done so.
				rtos.setFrame(true);
				if(!rtos.startTransportLive())
					std::printf("transport  : FAILED -- %s\n", rtos.why().c_str());
				if(pokeTrig)
					std::printf("poke trig  : track 1 step %d -> mask byte 7 = %#04x\n",
						pokeTrig, rtos.pokeTrig(static_cast<uint32_t>(pokeTrig)));
				rtos.installTrigLog();
				// Frame 0 = the first frame delivered after the transport
				// start returned, which is what the cold tool calls frame 0:
				// the two reports compare directly.
				const auto frame0 = rtos.frameCount() + 1;
				const auto ticks0 = rtos.ticks();
				const auto ackTail = rtos.acks().size();
				if(pcRing)
					rtos.armPcRingNow(pcRing);
				const auto target = frame0 + static_cast<uint64_t>(frames);
				const auto rs2 = rtos.runUntil(frames * ot::g_framePeriod / ot::g_sampleHz * 1000.0 * 5 + 2000.0,
					[&] { return rtos.frameCount() >= target; });
				static const char* const g_seqStop[] = {"REACHED", "TIME", "FAULT", "ILLEGAL"};
				std::printf("sequencer  : playing bank %u pattern %u "
					"(re-selected through the load's own last step)\n", seq.first, seq.second);
				std::printf("frames run : %llu since transport start (target %d), run ended %s%s%s\n",
					static_cast<unsigned long long>(rtos.frameCount() - frame0), frames,
					g_seqStop[static_cast<int>(rs2)],
					rs2 == ot::Rtos::Stop::Gate ? "" : " -- ", rs2 == ot::Rtos::Stop::Gate ? "" : rtos.why().c_str());
				// ⚠️ THREE CAUSES, ONE SYMPTOM. A frame that never arrives is a
				// masked source, a source installed at level 0, or a line that
				// is not asserting -- and the eDMA count says whether the
				// handler that did run got as far as kicking its chain.
				std::printf("             INTC0 src 1 (frame): masked %d, icr %u, asserting %d, latch %d; "
					"src 32 (tick): icr %u\n",
					rtos.intc0().masked(1), rtos.intc0().icr(1), rtos.intc0().assertedSource(1),
					rtos.framePending(), rtos.intc0().icr(32));
				{
					std::map<std::pair<uint32_t, uint32_t>, uint64_t> byVec;
					const auto& ks = rtos.acks();
					for(size_t i = ackTail; i < ks.size(); ++i)
						++byVec[{ks[i].vector, ks[i].slot}];
					std::printf("             vectors acknowledged since the transport start (%zu):",
						ks.size() - ackTail);
					for(const auto& [key, cnt] : byVec)
						std::printf(" v%#x->%#x x%llu", key.first, key.second, static_cast<unsigned long long>(cnt));
					std::printf("\n");
					for(size_t i = ks.size() > 8 ? ks.size() - 8 : 0; i < ks.size(); ++i)
						std::printf("               [%9.1f] v%#04x lvl %u in %-10s at pc %#x -> slot %#x\n",
							ks[i].sample, ks[i].vector, ks[i].level, ot::taskName(ks[i].tcb), ks[i].pc, ks[i].slot);
				}
				if(dspPair)
			std::printf("             host port: %llu blocks / %llu words to the DSPs, %llu blocks / %llu words back (%llu not in time); %llu ticks a burst waited for the DSP to drain\n",
				static_cast<unsigned long long>(rtos.hostBlocksOut()), static_cast<unsigned long long>(rtos.hostWordsOut()),
				static_cast<unsigned long long>(rtos.hostBlocksIn()), static_cast<unsigned long long>(rtos.hostWordsIn()),
				static_cast<unsigned long long>(rtos.hostWordsShort()), static_cast<unsigned long long>(rtos.edma().gatedWaits()));
		std::printf("             ticks %llu, eDMA transfers %llu\n",
					static_cast<unsigned long long>(rtos.ticks() - ticks0),
					static_cast<unsigned long long>(rtos.edmaStarted()));
				if(pcRing && rtos.pcRingArmed())
				{
					const auto& ring = rtos.pcRing();
					const auto pos = rtos.pcRingPos();
					const size_t n = std::min(ring.size(), pos);
					std::printf("             pc ring (last %zu of %zu instructions since the transport start):\n",
						n, pos);
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
				std::printf("FW_LIVE_NIBBLE (%#x) writes (%zu), frames since transport start:\n",
					ot::g_fwLiveNibble, rtos.liveNibbleLog().size());
				for(const auto& w : rtos.liveNibbleLog())
					std::printf("   frame %5lld track %u byte %#04x  nibble %x  flags %#04x  at pc %#x\n",
						static_cast<long long>(w.frame - frame0), w.index, w.value,
						w.value & 0xf, w.value & 0xf0, w.pc);
				std::printf("FW_TRIG_WORDS (%#x) nonzero writes (%zu)\n",
					ot::g_fwTrigWords, rtos.trigWordsLog().size());
				if(!m6cGolden.empty())
				{
					ot::Rtos::M6c f;
					f.frame0 = frame0;
					f.ticks0 = ticks0;
					f.ticks = rtos.ticks();
					f.frames = rtos.frameCount() - frame0;
					f.savedBank = load.savedBank;
					f.finalBank = finalBank;
					f.seqBank = seq.first;
					f.seqPattern = seq.second;
					rtos.writeM6cJson(m6cGolden, f);
					std::printf("m6c golden : %s\n", m6cGolden.c_str());
				}
			}
		}

		if(!watchPc.empty())
		{
			std::printf("watch-pc   : %zu hit(s) (the timestamp is the instruction count: "
				"the BOOT has no sample clock, and a watch that could not see the boot "
				"reported 0 for a boot address whether it ran or not)\n", m.pcHits().size());
			for(const auto& h : m.pcHits())
				std::printf("   [%12llu] at %#x d0=%#x d1=%#x a0=%#x a1=%#x "
					"[sp %#x: %#x %#x %#x %#x %#x]\n",
					static_cast<unsigned long long>(h.instruction), h.pc, h.d0, h.d1, h.a0, h.a1,
					h.sp, h.stack[0], h.stack[1], h.stack[2], h.stack[3], h.stack[4]);
		}
		if(!watchMem.empty())
		{
			// ⚠️ PRINT THEM ALL (capped only against a flood). A watch that
			// hides its hits is the silent-instrument trap route A records
			// twice over: an address that never fired and one that fired every
			// frame have to look different.
			std::printf("watch-mem  : %zu write(s)\n", rtos.memWrites().size());
			for(const auto& w : rtos.memWrites())
				std::printf("   [%10.1f] [%#x] <- %#x (%u) at pc %#x in %s\n",
					w.sample, w.addr, w.val, w.size, w.pc, ot::taskName(w.tcb));
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

	if(dspPair)
	{
		std::printf("dsp        : at the end\n%s", dspPair->report().c_str());
		size_t q = 0;
		while(q < dspPeek.size())
		{
			auto e = dspPeek.find(';', q);
			if(e == std::string::npos) e = dspPeek.size();
			const auto spec = dspPeek.substr(q, e - q);
			q = e + 1;
			int core = 0; char space = 'X'; unsigned addr = 0, len = 8;
			if(std::sscanf(spec.c_str(), "%d:%c:%x,%u", &core, &space, &addr, &len) < 3)
				continue;
			std::printf("             core %d %c:%#07x:", core, space, addr);
			for(unsigned k = 0; k < len; ++k)
			{
				const auto w = space == 'P' ? dspPair->peekP(core, addr + k)
					: space == 'Y' ? dspPair->peekY(core, addr + k) : dspPair->peekX(core, addr + k);
				std::printf(" %06x", w);
			}
			std::printf("\n");
		}
		for(const auto& t : dspPair->trace())
			std::printf("             %s\n", t.c_str());
		if(!dspLog.empty())
		{
			std::ofstream t(dspLog);
			for(const auto& e : dspPair->log())
			{
				char line[96];
				std::snprintf(line, sizeof line, "%-8s core %d %06x  due %llu\n", e.kind, e.core, e.val,
					static_cast<unsigned long long>(e.due));
				t << line;
			}
			std::printf("dsp log    : %s (%zu events)\n", dspLog.c_str(), dspPair->log().size());
		}
	}

	if(!hostPortLog.empty())
	{
		// The raw writes, and the 24-bit words reassembled from the
		// 0x14/0x18/0x1c triples the loader sends (high, mid, low -- the order
		// `0x40001d82`.. writes them). ❌ "0x81 to 0x20000000 is start the DSP"
		// (ARCHITECTURE.md §6) is retracted: the window is the HI08 host-side
		// register file, 0x81 is ICR INIT|RREQ, and 0x8c to 0x20000004 is a
		// host command (HC | vector 0x0c) -- see dsp.h (O8, 8 Sep 2026).
		std::ofstream t(hostPortLog);
		uint32_t w = 0; int have = 0; uint64_t words = 0;
		for(const auto& e : m.hostPortLog())
		{
			char line[128];
			std::snprintf(line, sizeof line, "W %08x %u %04x  pc %#010x  #%llu",
				e.addr, e.size, e.val & 0xffff, e.pc,
				static_cast<unsigned long long>(e.instruction));
			t << line;
			// ✅ THE BYTE LANES, from the loader's own code at 0x40001d74..:
			//   movel %d0,%d1 / swap %d1 / extl %d1 / movew %d1,0x20000014
			//   movel %d0,%d1 / asrl #8,%d1        / movew %d1,0x20000018
			//   movew %d0,0x2000001c
			// so only the LOW BYTE of each halfword matters, and it is bits
			// 23:16, 15:8 and 7:0 in that order. ⚠️ Getting the lanes backwards
			// made word 2 read 0x001003 instead of 0x031000 -- which is the
			// LOAD ADDRESS the loader was called with, and the thing that says
			// the decode is right.
			if(e.addr == 0x20000014)      { w = (w & 0x00ffff) | ((e.val & 0xff) << 16); have = 1; }
			else if(e.addr == 0x20000018) { w = (w & 0xff00ff) | ((e.val & 0xff) << 8); have |= 2; }
			else if(e.addr == 0x2000001c)
			{
				w = (w & 0xffff00) | (e.val & 0xff);
				if((have | 4) == 7)
				{
					char word[32];
					std::snprintf(word, sizeof word, "   word %06x", w);
					t << word;
					++words;
				}
				have = 0; w = 0;
			}
			t << '\n';
		}
		std::printf("hostport   : %s (%zu writes, %llu complete 24-bit words)\n",
			hostPortLog.c_str(), m.hostPortLog().size(), static_cast<unsigned long long>(words));
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
