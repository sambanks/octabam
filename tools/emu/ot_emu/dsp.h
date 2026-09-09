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
// (docs/firmware/COLDFIRE_PORT.md, O8): the loader at `0x40001d4c` writes 0 to +0x04,
// spins on `+0x08 & 6` (TXDE|TRDY) before every word, writes the three lanes
// high-mid-low, and the payload uploader at `0x40001b18` spins on `+0x08 & 1`
// (RXDF) and reads +0x14/+0x18/+0x1c back for the DSP's echo. The frame
// handler at `0x4000aad0` writes `0x8c` to +0x04 (HC | vector 0x0c) and polls
// bit 7 until the DSP takes the host command. And `0x81` to +0x00 -- read for
// months as "start the DSP" -- is ICR INIT|RREQ: an interface reset.
//
// THE DSP SIDE is the vendored dsp56kEmu, exactly as `tools/harness/dsp_host` builds
// it (two cores, X/Y 0x30000-0x3ffff of core 1 aliased onto core 0's arrays),
// plus its `DspBoot`: the emulation of the chip's HI08 bootstrap ROM (count,
// address, words, jump) that the firmware's 50- and 58-word uploads are
// written for. Once the ROM has jumped, host words go to the real HDI08 and
// the firmware's own bootstrap code echoes them back -- the far side of the
// handshake O6 had to fake.
//
// TIMING. The cores are stepped in lockstep with the ColdFire: `ratio` DSP
// instructions per ColdFire instruction during the boot (which has no sample
// clock), `ips` instructions per sample once the RTOS runs. Both are knobs.
// `ips` defaults to 4160 = 512 x 8.125: the payload never writes PCTL, so the
// core runs at the DSP56720's reset PLL (0x2B60C2: NF/(NR*NO) = 195/24) from
// an EXTAL the payload itself makes the audio clock (P:0x30024 routes EXTAL
// into both ESAI chains, TPSR=1/TPM=0/TFP=0, 8 slots x 32 bits), so
// Fsys/fs = 512 x 8.125 whatever the crystal is (COLDFIRE_PORT.md, O8:
// "the ESAI rate"). The ESAI fires ONE SLOT per `ips / 8` instructions -- the
// vendored clock's "cycles per sample" is per slot (its "2 samples = 1
// frame" comment). ⚠️ A core whose bootstrap ROM has not finished is HELD
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
		// `_ips`: DSP instructions per sample (RTOS clock). 4160 is the
		// firmware's own arithmetic (see the file comment; ❌ 4535 was the
		// datasheet's 200 MIPS ceiling, not this board's clock); the ratio is
		// that against the port's 3990 ColdFire instructions per sample.
		// Neither is a measurement of either emulator's cadence.
		static constexpr double g_dspIps = 4160.0;
		static constexpr double g_cfIps = 3990.0;
		static constexpr uint32_t g_esaiSlots = 8;		// TDC = 7 in both payload TCCRs
		DspPair(double _ratio = g_dspIps / g_cfIps, double _ips = g_dspIps);
		~DspPair() override;

		bool read(uint32_t _addr, uint8_t _size, uint32_t& _out) override;
		bool write(uint32_t _addr, uint8_t _size, uint32_t _val) override;
		void tickInstructions(uint64_t _n) override;
		double tickSamples(double _n) override;
		void setHostWordHook(std::function<bool(int)> _f) override { m_hostWordHook = std::move(_f); }
		int selected() const override { return m_sel; }
		bool hostRingEmpty(int _core) const override;
		void pushHalfwords(uint32_t _addr, const std::vector<uint16_t>& _hw) override;
		size_t pullHalfwords(uint32_t _addr, int _core, std::vector<uint16_t>& _out, size_t _n) override;
		std::string blockNote(int _core) override;
		uint32_t peekWord(int _core, char _space, uint32_t _addr) const override;
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
		// ESAI frames put out between consecutive host commands (0x8c): the
		// falsifier for the pacing. Sixteen per frame is what the ring's
		// double buffer needs; anything else and one bank is never taken.
		uint64_t framesPerCommandMin(int _core) const;
		uint64_t framesPerCommandMax(int _core) const;
		uint64_t framesPerCommandSixteen(int _core) const;
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
		void setTraceFrom(uint64_t _executed) { m_traceFrom = _executed; }	// O9b: a window, so the cap holds the END of a run
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

		// -- audio (O9) -------------------------------------------------------
		// The X-side ESAI's eight slots, TX0 out and RX0 in: the only audio
		// port either payload sets up (payload A, P:0x30024, DMA2 out of the
		// X:0x8000 ring and DMA3 into X:0x8100; payload B configures none, and
		// core 1 reports 0 ESAI frames). ESAI_1 is configured alongside but
		// no DMA feeds it. Which physical input or output each slot is has
		// NOT been measured -- see docs/firmware/COLDFIRE_PORT.md O9.
		static constexpr uint32_t g_audioSlots = 8;
		// Keep every transmitted frame (8 words, slot order) for a WAV.
		void setAudioCapture(const bool _on) { m_capture = _on; }
		const std::vector<int32_t>& audioOut(int _core) const;
		// Feed RX0 from the transport start (the first 0x8c) on: `_channels`
		// interleaved channels onto slots 0..channels-1, silence past the end
		// -- or the built-in tones (slot k = a sine at 500 x (k+1) Hz, -20 dBFS).
		void setAudioInput(std::vector<int32_t> _interleaved, uint32_t _channels);
		void setAudioTones(const bool _on) { m_tones = _on; }
		uint64_t txAtFirstCommand(int _core) const;
		uint64_t rxAtFirstCommand(int _core) const;
		uint64_t txSlotNonZero(int _core, uint32_t _slot) const;
		uint64_t rxSlotNonZero(int _core, uint32_t _slot) const;
		// The DSP's own instruction counter (which clocks its ESAI) minus the
		// interpreter calls the budget used to count -- `rep` iterations, mostly.
		uint64_t counterSurplus(int _core) const;
		uint64_t zeroDeltaCalls(int _core) const;
		// The activity map: at every frame command (0x8c) on core 0, the count
		// of non-zero words in each 4K chunk of X and Y of BOTH cores (the
		// shared window included) -- one line per command. Where audio (or
		// anything) lives on the DSP, frame by frame, without knowing where
		// to look first.
		void setActivityMap(const bool _on) { m_mapOn = _on; }
		const std::vector<std::string>& activityMap() const { return m_map; }
		// The write map: every NON-ZERO data write either core makes, binned
		// by 256-word region of X and Y, flushed as one line per frame
		// command. A region written with content is where audio (or state)
		// passes through, whatever the buffer is called.
		void setWriteMap(const bool _on) { m_writesOn = _on; }
		// A write watch on one DSP word: the last 16 (pc, value, executed) that wrote it (O9b).
		void setWriteWatch(const int _core, const char _space, const uint32_t _addr) { m_watchCore = _core; m_watchSpace = _space; m_watchAddr = _addr; m_watchOn = true; }
		struct WatchHit { uint32_t pc, val; uint64_t executed; uint32_t last[4]; uint32_t ddr0, dco0, dsr1, dco1, r4, r6, area, r0; };
		const std::vector<WatchHit>& writeWatchHits() const { return m_watchHits; }
		// A PC watch on one core: registers at every arrival (last 24), the DSP side of route A's --watch-pc (O9b).
		struct PcWatchHit { uint64_t executed; uint32_t a1, a0, b1, b0, x0, x1, y0, y1, r0, r4, r6, n4, sp, r2, m2, r1, n1, r7; };
		void setPcWatch(const int _core, const uint32_t _pc, const uint64_t _from = 0) { m_pcWatchCore = _core; m_pcWatchPc = _pc; m_pcWatchFrom = _from; m_pcWatchOn = true; }
		// O12 cycle meter: instructions executed between two PCs on one core, per
		// arrival pair (the dispatcher's head to its exit = one frame's DSP work,
		// in the same unit as dsp_host's meter). Spins outside the pair (the host
		// wait, the bank wait) are not counted, which is what "busy" failed to do.
		struct Stopwatch { int core = -1; uint32_t start = 0, stop = 0; uint64_t t0 = 0; bool armed = false; uint64_t n = 0, sum = 0, max = 0, min = ~0ull; std::vector<uint32_t> last; };
		void setStopwatch(const int _core, const uint32_t _start, const uint32_t _stop) { m_sw.core = _core; m_sw.start = _start; m_sw.stop = _stop; }
		const Stopwatch& stopwatch() const { return m_sw; }
		const std::vector<PcWatchHit>& pcWatchHits() const { return m_pcWatchHits; }
		const std::vector<std::string>& writeMap() const { return m_writeMap; }

		// Run both cores up to the due count now (the ticks only book it),
		// interleaved in quanta of g_quantum instructions (O9b).
		static double g_quantum;		// O12: --dsp-quantum N (default 64); huge = each core runs its whole due span in turn
		void runDue();
		bool stepCore(int _i, double _limit);
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
		uint64_t m_traceEvery = 0, m_traceFrom = 0;
		bool m_idleSkip = true;
		bool m_capture = false, m_tones = false, m_mapOn = false, m_writesOn = false;
		bool m_pulling = false;
		bool m_pcWatchOn = false; int m_pcWatchCore = 0; uint32_t m_pcWatchPc = 0; uint64_t m_pcWatchFrom = 0;	// with a `from`, the FIRST 24 arrivals after it are kept
		std::vector<PcWatchHit> m_pcWatchHits;
		Stopwatch m_sw;
		bool m_watchOn = false; int m_watchCore = 0; char m_watchSpace = 'X'; uint32_t m_watchAddr = 0;
		std::vector<WatchHit> m_watchHits;			// inside pullHalfwords: host-port words are the read-back, not the bank id
		bool m_hostWordFired = false;	// set by runDue when the hook fired; tickSamples stops its slice on it
		std::function<bool(int)> m_hostWordHook;
		std::vector<std::string> m_map, m_writeMap;
		std::vector<int32_t> m_input;
		uint32_t m_inputChannels = 0;
		// THE INTER-CORE MAILBOX, one register each way. 🟡 Inferred from the
		// firmware's use, not from a datasheet: core A writes Y:$FFFFD7 and
		// waits while bit 1 of Y:$FFFFD6 is set; core B waits for bit 1 of
		// Y:$FFFFD3 and reads Y:$FFFFD4 (docs/firmware/COLDFIRE_PORT.md, O8). Modelled
		// symmetrically: $D7 = my transmit data, $D6 bit 1 = it is still
		// unread; $D4 = my receive data, $D3 bit 1 = one is waiting.
		struct Mailbox { uint32_t data = 0; bool full = false; uint64_t words = 0; };
		Mailbox m_mail[2];		// m_mail[k]: written by core k, read by core k^1
		std::vector<std::string> m_trace;
		std::vector<Event> m_log;
	};
}
