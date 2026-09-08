// The two DSP56300 cores behind the ColdFire's host port -- milestone O8.
//
// WHAT THE WINDOW IS. `0x20000000`-`0x20000fff` is the HI08 HOST-SIDE
// register file of whichever core the GPIO byte at `0xfc0a400c` selects,
// one byte register per 4-byte stride, in the LOW byte of a 16-bit access:
//
//   +0x00  ICR   interrupt control   (RREQ 0, TREQ 1, HF0 3, HF1 4, INIT 7)
//   +0x04  CVR   command vector      (HV 6:0, HC 7)
//   +0x08  ISR   interrupt status    (RXDF 0, TXDE 1, TRDY 2, HF2 3, HF3 4, HREQ 7)
//   +0x0c  IVR   interrupt vector
//   +0x14  TXH / RXH   bits 23:16 of the 24-bit word
//   +0x18  TXM / RXM   bits 15:8
//   +0x1c  TXL / RXL   bits 7:0 -- the write that SENDS, the read that TAKES
//
// ✅ Every one of those comes from the firmware's own code, not the manual
// (docs/COLDFIRE_PORT.md, O8): the loader at `0x40001d4c` writes 0 to +0x04,
// spins on `+0x08 & 6` (TXDE|TRDY) before every word, writes the three lanes
// high-mid-low, and the payload uploader at `0x40001b18` spins on `+0x08 & 1`
// (RXDF) and reads +0x14/+0x18/+0x1c back for the DSP's echo. The frame
// handler at `0x4000aad0` writes `0x8c` to +0x04 (HC | vector 0x0c) and polls
// bit 7 until the DSP takes the host command. And `0x81` to +0x00 -- read for
// months as "start the DSP" -- is ICR INIT|RREQ: an interface reset.
//
// THE DSP SIDE is the vendored dsp56kEmu, exactly as `tools/dsp_host` builds
// it (two cores, X/Y 0x30000-0x3ffff of core 1 aliased onto core 0's arrays),
// plus its `DspBoot`: the emulation of the chip's HI08 bootstrap ROM (count,
// address, words, jump) that the firmware's 50- and 58-word uploads are
// written for. Once the ROM has jumped, host words go to the real HDI08 and
// the firmware's own bootstrap code echoes them back -- the far side of the
// handshake O6 had to fake.
//
// TIMING. The cores are stepped in lockstep with the ColdFire: `ratio` DSP
// instructions per ColdFire instruction during the boot (which has no sample
// clock), `ips` instructions per sample once the RTOS runs. Both are knobs;
// neither is measured. ⚠️ A core whose bootstrap ROM has not finished is HELD
// (the ROM jumps only after the last word), and a core is never run past the
// due count, so the ColdFire's polls see the DSP make progress between them
// and not before.
#pragma once

#include <cstdint>
#include <functional>
#include <memory>
#include <string>
#include <vector>

#include "machine.h"

namespace dsp56k
{
	class Memory;
	class Peripherals56362;
	class Peripherals56367;
	class DSP;
	class DspBoot;
	class HDI08;
	class IMemoryValidator;
}

namespace ot
{
	class DspPair final : public Coprocessor
	{
	public:
		static constexpr uint32_t g_window = 0x20000000, g_windowEnd = 0x20001000;
		static constexpr uint32_t g_select = 0xfc0a400c;
		static constexpr uint32_t g_shareLo = 0x30000, g_shareHi = 0x40000;
		static constexpr uint32_t g_pSize = 0x80000;			// the P memory each core is built with
		bool faulted(int _core) const;

		// `_ratio`: DSP instructions per ColdFire instruction (boot clock);
		// `_ips`: DSP instructions per sample (RTOS clock). 200 MIPS against
		// the port's 3990 ColdFire instructions per sample at 44.1 kHz gives
		// 4535 and 1.14 -- docs/CHIP.md's clocks, not a measurement of either
		// emulator's cadence.
		DspPair(double _ratio = 1.14, double _ips = 4535.0);
		~DspPair() override;

		bool read(uint32_t _addr, uint8_t _size, uint32_t& _out) override;
		bool write(uint32_t _addr, uint8_t _size, uint32_t _val) override;
		void tickInstructions(uint64_t _n) override;
		void tickSamples(double _n) override;
		int selected() const override { return m_sel; }
		bool hostRingEmpty(int _core) const override;
		void pushHalfwords(uint32_t _addr, const std::vector<uint16_t>& _hw) override;
		size_t pullHalfwords(uint32_t _addr, int _core, std::vector<uint16_t>& _out, size_t _n) override;
		uint64_t pulled(int _core) const;
		uint64_t pullShort(int _core) const;

		// -- probes ----------------------------------------------------------
		uint32_t peekP(int _core, uint32_t _addr) const;
		uint32_t peekX(int _core, uint32_t _addr) const;
		uint32_t peekY(int _core, uint32_t _addr) const;
		uint32_t pc(int _core) const;
		bool bootFinished(int _core) const;
		uint64_t executed(int _core) const;
		uint64_t hostWordsIn(int _core) const;		// words the host sent (ROM + HDI08)
		uint64_t hostWordsOut(int _core) const;		// words the host took back
		uint64_t hostCommands(int _core) const;
		uint32_t bootLength(int _core) const;		// what the ROM was told
		uint32_t bootAddress(int _core) const;
		// Every host-side event, in order, when enabled: "sel", "icr", "cvr",
		// "tx", "rx", "hc-taken". Cheap enough to leave on for a boot.
		struct Event { uint64_t due; int core; char kind[8]; uint32_t val; };
		void setLog(bool _on) { m_logOn = _on; }
		const std::vector<Event>& log() const { return m_log; }
		std::string report() const;
		// A line per core every `_every` executed instructions: the PC, the
		// DSP's own instruction counter, the ESAI frame counters and the ESAI /
		// HDI08 status registers -- what to read when a core stops making
		// progress and the question is when it stopped.
		void setTrace(uint64_t _every) { m_traceEvery = _every; }
		// The idle fast-forward: a core found in a poll loop (the last PCs in
		// a window of three words, outside any hardware DO loop) is advanced
		// to its next peripheral event instead of executing the polls. What it
		// polls -- the host port, the mailbox, memory -- can only change when
		// the ColdFire or the other core runs, and both keep running. Default
		// on; `setIdleSkip(false)` for a fidelity check.
		void setIdleSkip(bool _on) { m_idleSkip = _on; }
		// The vendored library's own log lines (ESAI register writes, underruns).
		static void setVerbose(bool _on);
		uint64_t idleSkipped(int _core) const;
		// The inter-core mailbox: words core 0 sent core 1 and back.
		uint64_t mailboxWords(int _from) const;
		const std::vector<std::string>& trace() const { return m_trace; }

		// Run both cores up to the due count now (the ticks only book it).
		void runDue();
		// Run ONE core until `_ready` or `_budget` instructions (the read-back
		// needs the DSP to produce each word). Returns whether it became ready.
		bool runCoreUntil(int _core, const std::function<bool()>& _ready, uint64_t _budget);

	private:
		struct Core;
		Core& cur() { return *m_cores[m_sel & 1]; }
		void note(const char* _kind, uint32_t _val);
		void icrWrite(uint32_t _v);
		void cvrWrite(uint32_t _v);
		uint32_t isrRead();
		void sendWord(uint32_t _word);
		uint32_t rxPeek();
		uint32_t rxTake();

		std::vector<std::unique_ptr<Core>> m_cores;
		// THE SHARED WINDOW, ONE MEMORY: P, X and Y of both cores at
		// 0x30000-0x3ffff (CHIP.md: measured on hardware; and the firmware
		// needs it -- core 1's entry P:0x38000 is written by core 0's upload).
		std::vector<uint32_t> m_shared;
		int m_sel = 0;
		double m_ratio, m_ips;
		double m_due = 0.0;
		bool m_logOn = false;
		uint64_t m_traceEvery = 0;
		bool m_idleSkip = true;
		// THE INTER-CORE MAILBOX, one register each way. 🟡 Inferred from the
		// firmware's use, not from a datasheet: core A writes Y:$FFFFD7 and
		// waits while bit 1 of Y:$FFFFD6 is set; core B waits for bit 1 of
		// Y:$FFFFD3 and reads Y:$FFFFD4 (docs/COLDFIRE_PORT.md, O8). Modelled
		// symmetrically: $D7 = my transmit data, $D6 bit 1 = it is still
		// unread; $D4 = my receive data, $D3 bit 1 = one is waiting.
		struct Mailbox { uint32_t data = 0; bool full = false; uint64_t words = 0; };
		Mailbox m_mail[2];		// m_mail[k]: written by core k, read by core k^1
		std::vector<std::string> m_trace;
		std::vector<Event> m_log;
	};
}
