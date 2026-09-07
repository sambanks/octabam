// The peripheral gate: every rule these models carry, checked against the
// value route A's own model produces.
//
// The rules here are not obvious and several are counter-intuitive; each one
// below exists because getting it wrong produced a specific, silent failure in
// route A first (`docs/RTOS_FORK.md` §8.2, §4). Testing them is how a
// translation stays a translation rather than a rewrite.
#include <cstdio>
#include <cmath>

#include "card.h"
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

	// ---- eDMA ------------------------------------------------------------
	// The three completion rules. Each wrong version below is one route A
	// actually shipped, with the symptom it produced (RTOS_FORK.md §8.1), so
	// these are negative controls and not decoration.
	{
		const uint32_t tcd = ot::Edma::g_tcd;
		const auto csrAddr = [tcd](uint32_t ch) { return tcd + ch * 32 + 0x1e; };
		const auto saddr   = [tcd](uint32_t ch) { return tcd + ch * 32 + 0x00; };
		const auto daddr   = [tcd](uint32_t ch) { return tcd + ch * 32 + 0x10; };

		// RULE 1: a CSR.START of a HOST-PORT channel completes at the DSP's
		// NEXT 16-sample boundary, not instantly and not at kick + 16.
		{
			ot::Edma e;
			e.write(daddr(1), 4, 0x2000001c, false);		// ch1: host port -> RAM
			e.setBoundary(16.0);
			e.write(csrAddr(1), 2, ot::Edma::START | ot::Edma::INTMAJOR, false);
			check("a host-port START does NOT complete at once",
				!(e.read(csrAddr(1), 2) & ot::Edma::DONE) && !e.irq(1));
			e.advance(5.0);
			check("... nor part-way through the frame", !e.irq(1));
			// ❌ "kick + 16": kicked at 5, that version completed at 21 and
			// the period came out 18.5 samples, dropping every sixth frame.
			e.advance(15.9);
			check("... nor at kick + 16 (that gave an 18.5-sample period)", !e.irq(1));
			e.advance(16.0);
			check("... it completes AT the boundary", e.irq(1));
			checkEq("... and DONE is set", e.read(csrAddr(1), 2) & ot::Edma::DONE, ot::Edma::DONE);
		}

		// RULE 2: an SSRT is a control transfer over the same host port and
		// completes AT ONCE, even though the channel looks paced.
		{
			ot::Edma e;
			e.write(saddr(0), 4, 0x2000001c, false);
			e.write(csrAddr(0), 2, ot::Edma::INTMAJOR, false);	// no START bit
			e.setBoundary(16.0);
			e.write(ot::Edma::g_base + ot::Edma::SSRT, 1, 0, false);
			check("an SSRT completes at once, host port or not", e.irq(0));
		}

		// RULE 3: a memory-to-memory START completes at once -- the caller
		// busy-waits on it at 0x400035a8 and holding it for a frame spun
		// forever.
		{
			ot::Edma e;
			e.write(saddr(2), 4, 0x4f502c10, false);			// the delay ring
			e.write(daddr(2), 4, 0x46000000, false);
			e.setBoundary(16.0);
			e.write(csrAddr(2), 2, ot::Edma::START | ot::Edma::INTMAJOR, false);
			check("a memory-to-memory START completes at once", e.irq(2));
		}

		// THE CHAIN, which is the audio path: ch1 (0x621) links to ch6, ch6
		// (0x720) links to ch7, ch7 (0x0002) raises source 15. It is ONE
		// event at the boundary, not three -- a linked channel is a burst and
		// completes with its parent.
		{
			ot::Edma e;
			e.write(daddr(1), 4, 0x2000001c, false);
			e.write(csrAddr(6), 2, 0x0720, false);				// link to ch7
			e.write(csrAddr(7), 2, 0x0002, false);				// INTMAJOR, no link
			e.setBoundary(16.0);
			e.write(csrAddr(1), 2, 0x0621, false);				// START|MAJORELINK|link ch6
			check("the chain has not fired before the boundary", !e.irq(7));
			e.advance(16.0);
			// ✅ Only ch7 raises a line: 0x621 and 0x720 have no INTMAJOR, and
			// channel 7 is INTC0 source 8 + 7 = 15, which is exactly the
			// source route A names for the end of this chain.
			check("ch1 -> ch6 -> ch7 complete together, and only ch7 raises a line",
				e.irq(7) && !e.irq(1) && !e.irq(6));
			checkEq("the whole chain is one boundary event, 3 starts", e.started(), 3);
		}

		// CINT and CDNE, the acks.
		{
			ot::Edma e;
			e.write(saddr(3), 4, 0x46000000, false);
			e.write(daddr(3), 4, 0x46100000, false);
			e.write(csrAddr(3), 2, ot::Edma::START | ot::Edma::INTMAJOR, false);
			check("INTMAJOR holds the line until CINT", e.irq(3));
			e.write(ot::Edma::g_base + ot::Edma::CINT, 1, 3, false);
			check("CINT drops it", !e.irq(3));
			checkEq("DONE survives CINT", e.read(csrAddr(3), 2) & ot::Edma::DONE, ot::Edma::DONE);
			e.write(ot::Edma::g_base + ot::Edma::CDNE, 1, 3, false);
			checkEq("CDNE clears DONE", e.read(csrAddr(3), 2) & ot::Edma::DONE, 0);
		}
		{
			ot::Edma e;
			for(uint32_t ch : {4u, 5u})
			{
				e.write(saddr(ch), 4, 0x46000000, false);
				e.write(csrAddr(ch), 2, ot::Edma::START | ot::Edma::INTMAJOR, false);
			}
			check("two lines up", e.irq(4) && e.irq(5));
			e.write(ot::Edma::g_base + ot::Edma::CINT, 1, 0x40, false);
			check("CINT 0x40 clears them all", !e.irq(4) && !e.irq(5));
		}

		// A REPLAYED write is the boot's, not the firmware's: it must set the
		// register state and start NOTHING. Same rule the UART and the PIT
		// carry, and the reason `install` can seed from the boot's log.
		{
			ot::Edma e;
			e.write(saddr(8), 4, 0x46000000, true);
			e.write(csrAddr(8), 2, ot::Edma::START | ot::Edma::INTMAJOR, true);
			check("a replayed START does not run the channel", !e.irq(8));
			checkEq("... but the CSR is stored", e.read(csrAddr(8), 2) & ot::Edma::START, ot::Edma::START);
		}

		// A channel whose TCD does not ask for an interrupt must not raise
		// one: ch0 and ch1 carry INTMAJOR from the boot, and route A's note
		// is that nothing in the model asserts a source the TCD did not ask
		// for.
		{
			ot::Edma e;
			e.write(saddr(9), 4, 0x46000000, false);
			e.write(csrAddr(9), 2, ot::Edma::START, false);		// no INTMAJOR
			check("no INTMAJOR, no line", !e.irq(9));
		}
	}

	// ---- the ATA card ----------------------------------------------------
	// The task-file model. The image here is synthetic -- a real card image is
	// built by route A's own Python (`emu_rtos.stage_project`) and read from
	// disk, so the two emulators are looking at identical media.
	{
		std::vector<uint8_t> img(64 * ot::AtaCard::g_sector);
		for(size_t i = 0; i < img.size(); ++i)
			img[i] = static_cast<uint8_t>(i * 7 + (i >> 9));
		ot::AtaCard c(img);
		const uint32_t b = ot::AtaCard::g_base;	// offsets are window-relative
		(void)b;

		checkEq("the image is 64 sectors", c.totalSectors(), 64);

		// IDENTIFY: the words the driver's variant detection reads. Word 49
		// bit 8 CLEAR and word 53 zero are what keep it on the PIO path and
		// stop it programming the on-chip DMA channel.
		c.write(ot::AtaCard::R_CMD, 1, 0xec);
		check("IDENTIFY raises DRQ", (c.status() & ot::AtaCard::ST_DRQ) != 0);
		{
			const auto w = ot::AtaCard::identifyWords(64);
			checkEq("word 0 is the CF signature", w[0], 0x848a);
			checkEq("word 49: LBA supported, DMA bit CLEAR", w[49] & 0x0100, 0);
			checkEq("word 53 is zero, so words 54-58/64-70 are 'not valid'", w[53], 0);
			checkEq("words 60/61 carry the sector count", (w[61] << 16) | w[60], 64);
		}
		// The data register streams the buffer and drops DRQ at the end.
		size_t n = 0;
		while(c.status() & ot::AtaCard::ST_DRQ)
		{
			c.read(ot::AtaCard::R_DATA, 2);
			if(++n > 512)
				break;
		}
		checkEq("IDENTIFY streams exactly 256 words", n, 256);

		// READ SECTORS: count 0 means 256 in the TASK FILE.
		c.write(ot::AtaCard::R_LBA0, 1, 2);
		c.write(ot::AtaCard::R_COUNT, 1, 3);
		c.write(ot::AtaCard::R_CMD, 1, 0x20);
		checkEq("READ logs its LBA and count", c.log().back().lba, 2);
		checkEq("... and its count", c.log().back().count, 3);
		checkEq("... and the sector tally follows it", c.sectorsRead(), 3);
		{
			const auto first = c.read(ot::AtaCard::R_DATA, 2);
			const size_t o = 2 * ot::AtaCard::g_sector;
			checkEq("the data register returns the image, big-endian on the bus",
				first, static_cast<uint32_t>((img[o] << 8) | img[o + 1]));
		}

		// WRITE SECTORS: one sector streamed through the data register lands
		// in the image, and DRQ drops when the last one is absorbed.
		{
			ot::AtaCard w(img);
			w.write(ot::AtaCard::R_LBA0, 1, 5);
			w.write(ot::AtaCard::R_COUNT, 1, 1);
			w.write(ot::AtaCard::R_CMD, 1, 0x30);
			check("WRITE raises DRQ", (w.status() & ot::AtaCard::ST_DRQ) != 0);
			for(size_t i = 0; i < ot::AtaCard::g_sector / 2; ++i)
				w.write(ot::AtaCard::R_DATA, 2, 0xbeef);
			checkEq("one sector absorbed", w.sectorsWritten(), 1);
			check("DRQ drops when the count is exhausted",
				(w.status() & ot::AtaCard::ST_DRQ) == 0);
			// and it is readable back
			w.write(ot::AtaCard::R_LBA0, 1, 5);
			w.write(ot::AtaCard::R_COUNT, 1, 1);
			w.write(ot::AtaCard::R_CMD, 1, 0x20);
			checkEq("the written sector reads back", w.read(ot::AtaCard::R_DATA, 2), 0xbeef);
		}

		// An unsupported command ABORTs rather than being ignored: the
		// firmware checks the error register, and a silent success here would
		// send the storage stack down a path that never happened.
		c.write(ot::AtaCard::R_CMD, 1, 0x99);
		check("an unknown command sets ABRT and the error bit",
			(c.status() & 1) != 0 && c.log().back().what.rfind("UNSUPPORTED", 0) == 0);
	}

	std::printf("%s\n", g_failures ? "PERIPHERAL GATE FAILED" : "peripheral gate passed.");
	return g_failures ? 1 : 0;
}
