// O8's first real gate, and it is self-checking: let the firmware's OWN boot
// program the two DSP cores through the emulated host port, then compare what
// landed in DSP memory against the bytes the image carries -- parsed here
// independently of both the firmware's uploader and the port's register model
// (docs/firmware/DSP.md section 2: 24-bit little-endian words; the bootstrap blobs are
// plain word lists, the payloads are `space, address, count, words` records).
//
// Two mechanisms have to agree for this to pass: the firmware's loader code
// running on the ColdFire side of the window (with its TXDE/RXDF polls and
// its echo check), and the vendored DSP running the chip's bootstrap ROM and
// then the firmware's own 50-word HDI08 loader on the DSP side. Neither can
// be faked into agreement by the other.
#include <cstdio>
#include <fstream>
#include <string>
#include <vector>

#include "dsp.h"
#include "machine.h"

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

	uint32_t le24(const std::vector<uint8_t>& _img, const uint32_t _cfAddr)
	{
		const auto o = _cfAddr - ot::Machine::g_imageBase;
		if(o + 3 > _img.size())
			return 0xffffffff;
		return _img[o] | (_img[o + 1] << 8) | (_img[o + 2] << 16);
	}

	struct Record { uint32_t space, addr, count, dataAt; };

	// The uploader's walk at 0x40001b18, mirrored: an optional header word 3
	// and an optional header word 4 (six bytes each), then records until a
	// space word above 2; the word after the terminator is the jump address.
	std::vector<Record> parsePayload(const std::vector<uint8_t>& _img, const uint32_t _base,
		uint32_t& _jump, uint32_t& _bytes)
	{
		std::vector<Record> out;
		uint32_t a = _base;
		if((le24(_img, a) & 0xff) == 3) a += 6;
		if((le24(_img, a) & 0xff) == 4) a += 6;
		for(;;)
		{
			const auto space = le24(_img, a);
			if((space & 0xff) > 2)
			{
				_jump = le24(_img, a + 3);
				_bytes = a + 6 - _base;
				return out;
			}
			Record r{space & 0xff, le24(_img, a + 3), le24(_img, a + 6), a + 9};
			out.push_back(r);
			a += 9 + 3 * r.count;
			if(a - _base > 0x40000)
				return out;
		}
	}

	uint32_t peek(const ot::DspPair& _d, const int _core, const uint32_t _space, const uint32_t _addr)
	{
		switch(_space)
		{
		case 0: return _d.peekP(_core, _addr);
		case 1: return _d.peekX(_core, _addr);
		default: return _d.peekY(_core, _addr);
		}
	}
}

int main(int _argc, char** _argv)
{
	const std::string image = _argc > 1 ? _argv[1] : "out/raw/section_3_MAIN_OS.bin";
	std::ifstream f(image, std::ios::binary);
	if(!f)
	{
		std::printf("SKIP: %s is not present (run `make os`)\n", image.c_str());
		return 0;
	}
	const std::vector<uint8_t> img((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());

	std::printf("dsp gate (the firmware's own upload lands the image's bytes):\n");
	ot::Machine m(img);
	ot::DspPair pair;
	m.setCoprocessor(&pair);

	// The payload check runs AT THE MOMENT each upload returns -- the
	// instruction after the `jsr 0x40001b18` for core 0 (0x40001e96) and for
	// core 1 (0x40001edc) -- because the window is one memory and the cores
	// go on to use it: ✅ measured 8 Sep 2026, by the handoff core 1 had
	// cleared Y:0x38000.. over its own entry stub, 19 words of payload A.
	struct Payload { int core; uint32_t base, size, at; };
	const Payload payloads[] = {{0, 0x400e2324, 79563, 0x40001e96}, {1, 0x400f59ef, 77061, 0x40001edc}};
	struct Result { bool seen = false; uint64_t words = 0, bad = 0, sent = 0, echoed = 0; std::string firstBad; };
	Result results[2];
	m.setStepHook([&](ot::Machine&, const uint32_t _pc)
	{
		for(const auto& p : payloads)
		{
			if(_pc != p.at || results[p.core].seen)
				continue;
			Result& r = results[p.core];
			r.seen = true;
			uint32_t jump = 0, bytes = 0;
			for(const auto& rec : parsePayload(img, p.base, jump, bytes))
				for(uint32_t i = 0; i < rec.count; ++i)
				{
					const auto want = le24(img, rec.dataAt + 3 * i);
					const auto got = peek(pair, p.core, rec.space, rec.addr + i);
					++r.words;
					if(want != got && !r.bad++)
					{
						char b[96];
						std::snprintf(b, sizeof b, " -- first at %c:%#x want %06x got %06x",
							"PXY"[rec.space], rec.addr + i, want, got);
						r.firstBad = b;
					}
				}
			r.sent = pair.hostWordsIn(p.core);
			r.echoed = pair.hostWordsOut(p.core);
		}
	});
	const auto boot = m.run(50'000'000);
	check("boots to the RTOS handoff with the DSPs attached", boot == ot::Machine::Stop::Handoff, m.why());
	if(boot != ot::Machine::Stop::Handoff)
		return 1;
	std::printf("%s", pair.report().c_str());

	// -- the bootstrap ROM: count, address, words, jump -----------------------
	struct Boot { int core; uint32_t src, bytes, addr; };
	for(const Boot b : {Boot{0, 0x400e21e0, 0x96, 0x31000}, Boot{1, 0x400e2276, 0xae, 0x32000}})
	{
		char what[96];
		std::snprintf(what, sizeof what, "core %d: the boot ROM took %u words for P:%#x and jumped", b.core, b.bytes / 3, b.addr);
		check(what, pair.bootFinished(b.core) && pair.bootLength(b.core) == b.bytes / 3
			&& pair.bootAddress(b.core) == b.addr);
		uint32_t bad = 0, first = 0;
		for(uint32_t i = 0; i < b.bytes / 3; ++i)
		{
			const auto want = le24(img, b.src + 3 * i);
			const auto got = pair.peekP(b.core, b.addr + i);
			if(want != got && !bad++)
				first = i;
		}
		char detail[128];
		std::snprintf(detail, sizeof detail, "%u/%u words%s", b.bytes / 3 - bad, b.bytes / 3,
			bad ? " -- first mismatch at word " : "");
		std::snprintf(what, sizeof what, "core %d: P:%#x holds the bootstrap the image carries", b.core, b.addr);
		check(what, bad == 0, bad ? detail + std::to_string(first) : detail);
	}

	// -- the payload: every record, in the space it names, at upload time ----
	for(const Payload& p : payloads)
	{
		uint32_t jump = 0, bytes = 0;
		const auto recs = parsePayload(img, p.base, jump, bytes);
		char what[128], detail[160];
		std::snprintf(what, sizeof what, "core %d: the payload parses to its last byte", p.core);
		std::snprintf(detail, sizeof detail, "%zu records, %u of %u bytes, jump %#x", recs.size(), bytes, p.size, jump);
		check(what, bytes == p.size, detail);

		const Result& r = results[p.core];
		std::snprintf(what, sizeof what, "core %d: the upload returned to the firmware (pc %#x)", p.core, p.at);
		check(what, r.seen);
		std::snprintf(what, sizeof what, "core %d: every payload record had landed where it names", p.core);
		std::snprintf(detail, sizeof detail, "%llu/%llu words%s",
			static_cast<unsigned long long>(r.words - r.bad), static_cast<unsigned long long>(r.words), r.firstBad.c_str());
		check(what, r.seen && r.bad == 0, detail);

		// What the firmware sent: 2 ROM words + the bootstrap, then per record
		// space/address/count + the words, then the terminator and the jump.
		uint64_t expect = 2 + (p.core ? 0xae : 0x96) / 3 + 2;
		for(const auto& rec : recs)
			expect += 3 + rec.count;
		// And what came back: one echo per record's space word, one for the
		// terminator (the loader at P:0x31000 echoes the word it dispatches on).
		const uint64_t echoes = recs.size() + 1;
		std::snprintf(what, sizeof what, "core %d: the host sent and took back exactly what the walk predicts", p.core);
		std::snprintf(detail, sizeof detail, "%llu sent (%llu predicted), %llu echoed (%llu predicted)",
			static_cast<unsigned long long>(r.sent), static_cast<unsigned long long>(expect),
			static_cast<unsigned long long>(r.echoed), static_cast<unsigned long long>(echoes));
		check(what, r.sent == expect && r.echoed == echoes, detail);
	}
	// After the boot, both cores are running the program, not the loader.
	for(int c = 0; c < 2; ++c)
	{
		char what[96], detail[96];
		std::snprintf(what, sizeof what, "core %d: left the bootstrap and is running the payload", c);
		std::snprintf(detail, sizeof detail, "pc %#x, %s", pair.pc(c), pair.faulted(c) ? "FAULTED" : "no fault");
		check(what, !pair.faulted(c) && pair.pc(c) != 0x31000 + 4 && pair.pc(c) != 0x32000 + 4 && pair.bootFinished(c), detail);
	}

	std::printf("dsp gate: %d failure(s)\n", g_failures);
	return g_failures ? 1 : 0;
}
