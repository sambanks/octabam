// Stock contracts the Repitch patch depends on, and the patched image's
// behaviour at each hook, run through the firmware's own code on ot::Machine.
// Full playback (a project, both DSP cores, a live tempo change) is
// tools/verify/verify_repitch.py; the page drawings under the Python
// emulator are tools/verify/verify_repitch_ui.py.
#include <algorithm>
#include <cstdio>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>
#include "machine.h"
#include "mc68k/Musashi/m68k.h"
#include "mc68k/cpuState.h"

namespace
{
constexpr uint32_t imageBase = 0x40000400;
constexpr uint32_t lanes = 0x80000510, voices = 0x800049d8, states = 0x80004898;
constexpr uint32_t curState = 0x800062a4, projectTempo = 0x8000181c, uiTrack = 0x80000000;
constexpr uint32_t knob = 0x400479b4, select4 = 0x40046c28, select5 = 0x40046ab4;
constexpr uint32_t trampoline = 0x47000000, stack = 0x47100000, settings = 0x47200000;
constexpr uint32_t sentinel = 0x47300000;

struct Probe
{
	std::vector<uint8_t> image;
	int failures = 0;

	uint32_t read32(const uint32_t a) const
	{
		const auto i = a - imageBase;
		return (uint32_t(image[i]) << 24) | (uint32_t(image[i + 1]) << 16) |
		       (uint32_t(image[i + 2]) << 8) | uint32_t(image[i + 3]);
	}
	std::string cstr(const uint32_t a) const
	{
		std::string out;
		for(auto i = a - imageBase; i < image.size() && image[i]; ++i)
			out.push_back(char(image[i]));
		return out;
	}
	void check(const char* what, const bool ok)
	{
		failures += !ok;
		std::printf("  [%s] %s\n", ok ? "PASS" : "FAIL", what);
	}

	// Run from `site` with MACSR = 0x20 (the builder's own mode) until `until`.
	static bool runTo(ot::Machine& m, const uint32_t site, const uint32_t until, const unsigned budget = 400)
	{
		const uint8_t code[] = {0xa9, 0x3c, 0x00, 0x00, 0x00, 0x20, 0x4e, 0xf9,
			uint8_t(site >> 24), uint8_t(site >> 16), uint8_t(site >> 8), uint8_t(site)};
		for(unsigned i = 0; i < sizeof(code); ++i)
			m.write8(trampoline + i, code[i]);
		m68k_set_reg(m.getCpuState(), M68K_REG_PC, trampoline);
		unsigned steps = 0;
		while(m.pc() != until && steps++ < budget)
			if(!m.step()) return false;
		return m.pc() == until;
	}

	struct Rate { unsigned track, tstr, tsmode, source, project; uint16_t ptch, rate; uint8_t machine = 1; };

	// The voice renderer's TSTR resolution, from 0x40007d96 (d1 resolved from
	// SETUP or the sample, the voice's machine at +20, its previous value at
	// +24) to 0x40007dc0, the store's successor: the value stored at voice
	// +24, and every register.
	struct Resolved { uint8_t stored; uint32_t loopStart; uint32_t regs[16]; bool ok; };
	Resolved resolve(const uint32_t value, const uint8_t machine, const uint8_t previous) const
	{
		ot::Machine m(image);
		auto* cpu = m.getCpuState();
		constexpr uint32_t voice = 0x47006000, frame = 0x47008000;
		m.write8(voice + 20, machine);
		m.write8(voice + 24, previous);
		m.write32(voice + 64, 0x11111111);
		m.write32(voice + 68, 0x22222222);
		m68k_set_reg(cpu, M68K_REG_D1, value);
		m68k_set_reg(cpu, M68K_REG_D0, 0x89abcdef);
		m68k_set_reg(cpu, M68K_REG_D2, 0x13579bdf);
		m68k_set_reg(cpu, M68K_REG_D3, 0x2468ace0);
		m68k_set_reg(cpu, M68K_REG_A0, 0x47010000);
		m68k_set_reg(cpu, M68K_REG_A1, 0x47020000);
		m68k_set_reg(cpu, M68K_REG_A2, voice);
		m68k_set_reg(cpu, M68K_REG_A6, frame);
		m68k_set_reg(cpu, M68K_REG_SP, stack);
		m68k_set_reg(cpu, M68K_REG_PC, 0x40007d96);
		unsigned steps = 0;
		while(m.pc() != 0x40007dc0 && steps++ < 40)
			if(!m.step()) break;
		Resolved r{m.read8(voice + 24), m.read32(voice + 64), {}, m.pc() == 0x40007dc0};
		for(int i = 0; i < 16; ++i)
			r.regs[i] = m68k_get_reg(cpu, m68k_register_t(M68K_REG_D0 + i));
		return r;
	}

	// The playback increment the builder stores at state +36, from the
	// recompute-flag test at 0x4000406a to the store's successor 0x40004108.
	uint32_t increment(const Rate& r, bool& ok) const
	{
		ot::Machine m(image);
		auto* cpu = m.getCpuState();
		const uint32_t state = states + 40 * r.track, lane = lanes + 48 * r.track;
		m.write32(curState, state);
		m.write32(stack + 64, 0x10);
		m.write16(lane, r.ptch);
		m.write16(lane + 6, r.rate);
		m.write16(lane + 10, 0);
		m.write8(lane + 27, 0);
		m.write8(lane + 28, uint8_t(r.tstr));
		m.write32(voices + 168 * r.track + 8, settings);
		m.write8(voices + 168 * r.track + 20, r.machine);
		m.write32(settings + 0x110, r.tsmode);
		m.write32(settings + 0x114, r.source);
		m.write32(projectTempo, r.project);
		m68k_set_reg(cpu, M68K_REG_A3, state);
		m68k_set_reg(cpu, M68K_REG_A6, lane);
		m68k_set_reg(cpu, M68K_REG_D5, 26);
		m68k_set_reg(cpu, M68K_REG_SP, stack);
		ok &= runTo(m, 0x4000406a, 0x40004108) && m68k_get_reg(cpu, M68K_REG_SP) == stack;
		return m.read32(state + 36);
	}
};
}

int main(int argc, char** argv)
{
	const bool patched = argc > 1 && std::string(argv[1]) == "--patched";
	const std::string path = patched
		? (argc > 2 ? argv[2] : "out/mainos_bus.bin")
		: (argc > 1 ? argv[1] : "out/raw/section_3_MAIN_OS.bin");
	std::ifstream input(path, std::ios::binary);
	if(!input) {
		std::printf("SKIP: %s is not present (run `make os`)\n", path.c_str());
		return 0;
	}
	Probe p;
	p.image.assign(std::istreambuf_iterator<char>(input), {});
	// A patched image only ever grows (build_bus.py's _appends), so the
	// patched run accepts >= stock length; the stock-only run must be exact.
	constexpr size_t stockSize = 1112560;
	if(patched ? p.image.size() < stockSize : p.image.size() != stockSize) {
		std::printf("  [FAIL] %s is %zu bytes, expected %s stock 1.40C MAIN OS (%zu)\n",
		            path.c_str(), p.image.size(), patched ? "at least the" : "exactly the", stockSize);
		return 2;
	}

	if(!patched) {
		std::printf("Repitch stock contracts:\n");
		p.check("STATIC and FLEX TSTR each expose four values",
		        p.read32(0x400d30de) == 4 && p.read32(0x400d3270) == 4);
		p.check("PICKUP TSTR exposes values 1..3",
		        p.read32(0x400d36f6) == 1 && p.read32(0x400d3726) == 3);
		p.check("all three TSTR slots use formatter 0x4003b6a4",
		        p.read32(0x400d310e) == 0x4003b6a4 && p.read32(0x400d32a0) == 0x4003b6a4 &&
		        p.read32(0x400d3756) == 0x4003b6a4);
		p.check("raw TSTR mapping is OFF, AUTO, NORM, BEAT",
		        p.cstr(p.read32(0x400a7e2e)) == "OFF" && p.cstr(p.read32(0x400a7e32)) == "AUTO" &&
		        p.cstr(p.read32(0x400a7e36)) == "NORM" && p.cstr(p.read32(0x400a7e3a)) == "BEAT");
		p.check("TSTR draws on the four-position select, PTCH on the knob",
		        p.read32(0x400d313e) == select4 && p.read32(0x400d32d0) == select4 &&
		        p.read32(0x400d3116) == knob && p.read32(0x400d32a8) == knob);
		// The select widgets differ only in their bound and icon table; the
		// five-position one is referenced by nothing in stock.
		const auto at = [&](const uint32_t a) { return p.image[a - imageBase]; };
		p.check("select widgets bound at #3 and #4 with 4- and 5-entry icon tables",
		        at(0x40046c7d) == 3 && at(0x40046b09) == 4 &&
		        p.read32(0x40046d12) == 0x400be306 && p.read32(0x40046b9e) == 0x400be316);
		bool unreferenced = true;
		for(size_t i = 0; i + 4 <= p.image.size(); i += 2)
			unreferenced &= p.read32(imageBase + uint32_t(i)) != select5;
		p.check("the five-position select is referenced by nothing", unreferenced);
		p.check("the per-frame builder call passes the recompute flag 0x10",
		        p.read32(0x4000d518) == 0x48780010);
		p.check("audio editor ATTR TIMESTRETCH strings: OFF, NORMAL, BEAT, ERROR",
		        p.cstr(0x400b4e78) == "OFF" && p.cstr(0x400b5eb0) == "NORMAL" &&
		        p.cstr(0x400b572d) == "BEAT" && p.cstr(0x400b94f6) == "ERROR");

		// The voice renderer (0x40007960..0x40008f80) reads the resolved TSTR
		// (voice +24, a2) at nine sites, each as zero/nonzero or against 3
		// (BEAT) -- so a track that resolves to 0 renders exactly as OFF
		// (REPITCH's hook at 0x40007d96). Two of them advance the position by
		// OUTPUT samples on any nonzero value instead of the frames consumed.
		{
			const auto w16 = [&](const uint32_t a) {
				return uint16_t((p.image[a - imageBase] << 8) | p.image[a - imageBase + 1]);
			};
			std::vector<uint32_t> tests, compares;
			for(uint32_t a = 0x40007960; a < 0x40008f80; a += 2) {
				if(w16(a + 2) != 0x0018) continue;
				if(w16(a) == 0x4a2a) tests.push_back(a);                       // tst.b 24(a2)
				else if(w16(a) == 0x712a) compares.push_back(a);               // mvs.b 24(a2),d0
			}
			const std::vector<uint32_t> wantTests{0x40007ede, 0x400081b2, 0x40008210, 0x4000886c,
			                                      0x4000898a, 0x400089de, 0x40008e42};
			const std::vector<uint32_t> wantCompares{0x40007da8, 0x400082a8, 0x4000847e};
			bool against3 = true;   // the stored value is compared with the previous one, then 3
			for(const auto a : compares)
				against3 &= a == 0x40007da8 ? w16(a + 4) == 0xb280 && w16(a + 8) == 0x7603
				                            : (w16(a + 4) & 0xf1ff) == 0x7003;
			p.check("the renderer reads the resolved TSTR only as zero/nonzero and against BEAT (3)",
			        tests == wantTests && compares == wantCompares && against3);
			p.check("any nonzero TSTR advances the position by output samples (0x4000886c, 0x40008e42)",
			        w16(0x4000886c + 4) == 0x6708 && w16(0x40008872) == 0x222e && w16(0x40008874) == 0x0018 &&
			        w16(0x40008876) == 0x2d41 && w16(0x40008878) == 0x0014 &&
			        w16(0x40008e46) == 0x6708 && w16(0x40008e48) == 0x222e && w16(0x40008e4a) == 0x0018 &&
			        w16(0x40008e4c) == 0x2d41 && w16(0x40008e4e) == 0x0014);
		}

		// The rate block: OFF is dry, every nonzero TSTR granular.
		constexpr uint32_t frame = 0x47000000, lane = 0x47001000, set = 0x47002000;
		int rateFailures = 0;
		for(const unsigned tempo : {1440u, 2160u, 2880u, 4320u, 5760u})
		for(const unsigned rateMode : {0u, 1u})
		for(const unsigned tstr : {0u, 1u, 2u, 3u, 4u}) {
			ot::Machine m(p.image);
			auto* cpu = m.getCpuState();
			m68k_set_reg(cpu, M68K_REG_A6, frame);
			m68k_set_reg(cpu, M68K_REG_A2, voices);
			m68k_set_reg(cpu, M68K_REG_D2, tempo);
			m.write32(frame - 72, lane);
			m.write32(frame - 76, set);
			m.write32(frame - 80, tempo);
			m.write16(lane, 0x4000);
			m.write8(lane + 27, rateMode);
			m.write8(voices + 24, tstr);
			m.write32(set + 0x114, 2880);
			m.write32(set + 0x118, 0x12345678);
			m68k_set_reg(cpu, M68K_REG_PC, 0x400081c2);
			unsigned steps = 0;
			while(m.pc() != 0x4000822a && steps++ < 80)
				if(!m.step()) break;
			const auto actual = m68k_get_reg(cpu, M68K_REG_A4);
			const auto grain = m68k_get_reg(cpu, M68K_REG_A3) & 0xffff;
			const auto reciprocal = m68k_get_reg(cpu, M68K_REG_A5);
			const bool ok = m.pc() == 0x4000822a && actual == tempo &&
			                grain == (tstr ? 2880u : tempo) &&
			                reciprocal == (tstr ? 0x12345678u : 0x80000000u / tempo);
			rateFailures += !ok;
		}
		p.check("stock rate block treats OFF as dry and every nonzero TSTR value as granular",
		        rateFailures == 0);

		bool ok = true;
		Probe::Rate neutral{0, 0, 2, 2880, 2880, 0x4000, 0x7f00}, up = neutral, down = neutral;
		up.ptch = 0x7c00; down.ptch = 0x0400;
		const auto n = p.increment(neutral, ok), u = p.increment(up, ok), d = p.increment(down, ok);
		p.check("the builder's increment: neutral 1.0, PTCH +60 2.0, PTCH -60 0.5 (Q26)",
		        ok && n == 0x04000000 && u == 0x08000000 && d == 0x02000000);
		std::printf("%d failure(s); stock contracts\n", p.failures);
		return p.failures ? 1 : 0;
	}

	std::printf("Repitch patched-image contracts:\n");
	const auto formatter = p.read32(0x400d310e);
	if(p.read32(0x400d30de) != 5 || formatter == 0x4003b6a4) {
		std::printf("SKIP: %s is not a REPITCH remix image\n", path.c_str());
		return 0;
	}
	p.check("STATIC/FLEX TSTR count 5; PICKUP untouched (1..3)",
	        p.read32(0x400d30de) == 5 && p.read32(0x400d3270) == 5 &&
	        p.read32(0x400d36f6) == 1 && p.read32(0x400d3726) == 3 &&
	        p.read32(0x400d3756) == 0x4003b6a4 && p.read32(0x400d3786) == select4);
	p.check("STATIC/FLEX TSTR: one new formatter, the five-position select",
	        formatter == p.read32(0x400d32a0) &&
	        p.read32(0x400d313e) == select5 && p.read32(0x400d32d0) == select5);
	const auto widget = p.read32(0x400d3116);
	p.check("STATIC/FLEX PTCH: one new widget", widget != knob && widget == p.read32(0x400d32a8));

	{
		bool labelsOk = true;
		const char* labels[] = {"OFF", "AUTO", "NORM", "BEAT", "RPCH", "???"};
		for(unsigned value = 0; value < 6; ++value) {
			ot::Machine m(p.image);
			auto* cpu = m.getCpuState();
			constexpr uint32_t buf = 0x47004000;
			m.write32(stack, sentinel);
			m.write32(stack + 4, buf);
			m.write32(stack + 8, value);
			m.write32(buf, 0);
			m68k_set_reg(cpu, M68K_REG_SP, stack);
			m68k_set_reg(cpu, M68K_REG_PC, formatter);
			unsigned steps = 0;
			while(m.pc() != sentinel && steps++ < 2000)
				if(!m.step()) break;
			std::string got;
			for(unsigned i = 0; i < 16 && m.read8(buf + i); ++i)
				got.push_back(char(m.read8(buf + i)));
			labelsOk &= m.pc() == sentinel && got == labels[value];
			if(got != labels[value])
				std::printf("  [FAIL] TSTR %u printed '%s', expected '%s'\n", value, got.c_str(), labels[value]);
		}
		p.check("formatter prints OFF, AUTO, NORM, BEAT, RPCH (4 characters), ??? past the end", labelsOk);
	}

	// The stock image, for the same inputs through the same code.
	std::ifstream stockInput("out/raw/section_3_MAIN_OS.bin", std::ios::binary);
	Probe stock;
	stock.image.assign(std::istreambuf_iterator<char>(stockInput), {});
	const bool haveStock = stock.image.size() == stockSize;
	if(!haveStock)
		std::printf("SKIP: the renderer and rate contracts need out/raw/section_3_MAIN_OS.bin\n");

	if(haveStock) {
		// REPITCH resolves to OFF in the voice renderer; every other value, and
		// the pickup rule (0 -> 2), is stock's. Registers included.
		int bad = 0;
		for(uint32_t value = 0; value < 6; ++value)
		for(const uint8_t machine : {uint8_t(0), uint8_t(1), uint8_t(4)})
		for(const uint8_t previous : {uint8_t(0), uint8_t(2), uint8_t(3)}) {
			const auto got = p.resolve(value, machine, previous);
			const auto want = stock.resolve(value == 4 ? 0 : value, machine, previous);
			const bool same = got.ok && want.ok && got.stored == want.stored && got.loopStart == want.loopStart &&
			                  std::equal(std::begin(got.regs), std::end(got.regs), std::begin(want.regs));
			if(!same && bad++ < 8)
				std::printf("  [FAIL] resolve %u on machine %u (was %u): stored %u, want %u%s\n", value, machine,
				            previous, got.stored, want.stored, got.ok && want.ok ? " (+64 or registers differ)" : " (did not reach 0x40007dc0)");
		}
		p.check("the renderer resolves REPITCH as OFF (a pickup's as 2), registers and every other value as stock", bad == 0);
	}

	// The increment against the stock image's own for the same inputs.
	{
		if(haveStock) {
			int same = 0, scaled = 0, bad = 0;
			for(const unsigned track : {0u, 5u})
			for(const uint8_t machine : {uint8_t(1), uint8_t(4)})
			for(const unsigned tstr : {0u, 1u, 2u, 3u, 4u})
			for(const unsigned tsmode : {0u, 2u, 4u})
			for(const unsigned source : {0u, 700u, 2880u, 1440u, 7300u})
			for(const unsigned project : {720u, 2160u, 2880u, 4320u, 7200u})
			for(const uint16_t ptch : {uint16_t(0x4000), uint16_t(0x5800), uint16_t(0x1c00)})
			for(const uint16_t rate : {uint16_t(0x7f00), uint16_t(0x3f00)}) {
				const Probe::Rate r{track, tstr, tsmode, source, project, ptch, rate, machine};
				bool ok1 = true, ok2 = true;
				const auto got = p.increment(r, ok1);
				const bool repitch = (tstr == 4 || (tstr == 1 && tsmode == 4)) && source >= 720 && source <= 7200 &&
				                     machine != 4;
				uint32_t want;
				if(repitch) {
					Probe::Rate n = r; n.ptch = 0x4000;
					const uint64_t base = stock.increment(n, ok2);
					want = uint32_t(std::min<uint64_t>(0x08000000, base * project / source));
					++scaled;
				} else {
					want = stock.increment(r, ok2);
					++same;
				}
				if(!(ok1 && ok2 && got == want)) {
					if(bad++ < 8)
						std::printf("  [FAIL] T%u machine %u TSTR %u TSMODE %u %u/%u PTCH %#x RATE %#x: %#010x, want %#010x%s\n",
						            track + 1, machine, tstr, tsmode, project, source, ptch, rate, got, want,
						            ok1 && ok2 ? "" : " (did not reach 0x40004108 cleanly)");
				}
			}
			std::printf("       %d stock-identical and %d scaled increments\n", same, scaled);
			p.check("increments: stock-identical unless REPITCH (SETUP, or AUTO + the sample's own) off a pickup, "
			        "with a tempo in 720..7200; then neutral PTCH x project/sample, RATE kept, clamped to 2x", bad == 0);
		}
	}

	{
		bool ok = true;
		for(const unsigned tstr : {0u, 1u, 4u})
		for(const unsigned tsmode : {2u, 4u}) {
			ot::Machine m(p.image);
			auto* cpu = m.getCpuState();
			constexpr unsigned track = 2;
			m.write8(uiTrack, track);
			m.write8(lanes + 48 * track + 28, tstr);
			m.write32(voices + 168 * track + 8, settings);
			m.write32(settings + 0x110, tsmode);
			m.write32(settings + 0x114, 2880);
			const uint32_t args[] = {0x11, 0x22, 0x33, 64, 0x55, 0x66, 0x77};
			m.write32(stack, sentinel);
			for(unsigned i = 0; i < 7; ++i)
				m.write32(stack + 4 + 4 * i, args[i]);
			m68k_set_reg(cpu, M68K_REG_SP, stack);
			m68k_set_reg(cpu, M68K_REG_PC, widget);
			unsigned steps = 0;
			while(m.pc() != knob && steps++ < 200)
				if(!m.step()) break;
			const auto sp = m68k_get_reg(cpu, M68K_REG_SP);
			const bool off = tstr == 4 || (tstr == 1 && tsmode == 4);
			bool argsOk = m.pc() == knob;
			for(unsigned i = 0; i < 7; ++i)
				argsOk &= m.read32(sp + 4 + 4 * i) == (i == 3 && off ? 0xffffffffu : args[i]);
			argsOk &= off ? sp != stack : (sp == stack && m.read32(sp) == sentinel);
			ok &= argsOk;
			if(!argsOk)
				std::printf("  [FAIL] PTCH widget, TSTR %u TSMODE %u: value %#x\n", tstr, tsmode, m.read32(sp + 16));
		}
		p.check("PTCH knob: value -1 (frame only) on a REPITCH track, untouched tail call otherwise", ok);
	}

	{
		const auto step = [&](const uint32_t site, const uint32_t until, const unsigned from, const bool downward, bool& ok) {
			ot::Machine m(p.image);
			auto* cpu = m.getCpuState();
			m.write32(settings + 0x110, from);
			m68k_set_reg(cpu, M68K_REG_A0, settings);
			m68k_set_reg(cpu, M68K_REG_D0, downward ? 2 : from);
			m68k_set_reg(cpu, M68K_REG_D1, 2);
			m68k_set_reg(cpu, M68K_REG_SP, stack);
			m68k_set_reg(cpu, M68K_REG_PC, site);
			unsigned steps = 0;
			while(m.pc() != until && steps++ < 60)
				if(!m.step()) break;
			ok &= m.pc() == until && m68k_get_reg(cpu, M68K_REG_SP) == stack;
			return m.read32(settings + 0x110);
		};
		bool ok = true;
		const auto u2 = step(0x4006ee56, 0x4006eef0, 2, false, ok), u3 = step(0x4006ee56, 0x4006eef0, 3, false, ok),
		           u4 = step(0x4006ee56, 0x4006eef0, 4, false, ok);
		const auto d2 = step(0x4006ef7c, 0x4006f026, 2, true, ok), d3 = step(0x4006ef7c, 0x4006f026, 3, true, ok),
		           d4 = step(0x4006ef7c, 0x4006f026, 4, true, ok), d0 = step(0x4006ef7c, 0x4006f026, 0, true, ok);
		p.check("ATTR TIMESTRETCH up 2->3->4, stops at 4; down 4->3->2->0, stops at 0",
		        ok && u2 == 3 && u3 == 4 && u4 == 4 && d4 == 3 && d3 == 2 && d2 == 0 && d0 == 0);

		bool labelOk = true;
		for(const unsigned value : {4u, 1u, 5u}) {
			ot::Machine m(p.image);
			auto* cpu = m.getCpuState();
			m68k_set_reg(cpu, M68K_REG_D0, value);
			m68k_set_reg(cpu, M68K_REG_SP, stack);
			m68k_set_reg(cpu, M68K_REG_PC, 0x4006e71c);
			unsigned steps = 0;
			while(m.pc() != 0x4006e878 && steps++ < 20)
				if(!m.step()) break;
			const auto sp = m68k_get_reg(cpu, M68K_REG_SP);
			std::string got;
			for(uint32_t a = m.read32(sp); m.read8(a) && got.size() < 16; ++a)
				got.push_back(char(m.read8(a)));
			labelOk &= m.pc() == 0x4006e878 && sp == stack - 4 && got == (value == 4 ? "REPITCH" : "ERROR");
		}
		p.check("ATTR TIMESTRETCH prints REPITCH for 4 and stock ERROR past it", labelOk);
	}

	std::printf("%d failure(s); patched-image contracts\n", p.failures);
	return p.failures ? 1 : 0;
}
