// The Octatrack as a machine, headless: one ColdFire MCF54454 and (later) two
// DSP56300 cores, driven from a script and open to interception.
//
// WHY THIS EXISTS. `tools/emu_rtos.py` (route A) already runs the firmware's
// own scheduler on Unicorn + Python, and it is the ORACLE this port is
// measured against -- but it costs ~120x real time, models no audio, and
// stops at the DSP host port. `tools/dsp_host` runs both DSP cores at about
// real time but knows nothing of the ColdFire. This is the join: the same
// machine, in one process, fast enough to play with.
//
// It is deliberately NOT a plugin. No JUCE, no UI, no audio device. The
// deliverable is a library plus a CLI you can drive and intercept -- the
// C++ counterpart of route A's Python API.
//
// MILESTONE O1 (this file's only job so far): boot the OS image to the RTOS
// handoff -- the `trap #0` at 0x4000ff9a that hands control to the kernel --
// with the same registers route A reaches. Everything below is the minimum
// that boot touches, taken FIELD FOR FIELD from `tools/emu_bringup.py` so the
// two can be diffed rather than argued about:
//
//   * the RAM map (six regions, `emu_bringup.boot`)
//   * SR = 0x2700 and A7 = 0x48000000 before the first instruction, SR FIRST
//     (the supervisor/user stack banks swap on the SR write, so writing A7
//     first lands it in the wrong bank -- route A's comment, kept because the
//     failure is silent)
//   * peripheral reads default to ALL-ONES, which satisfies every
//     wait-until-set spin in the boot path
//   * the PLL at 0xfc0c4000 must read (reg >> 24) * 12 MHz == 264 MHz or the
//     firmware halts at 0x4000fa8c -- so the top byte is 22
//
// ⚠️ WHAT IS KNOWN MISSING, and why it is fine for O1: the vendored Musashi
// implements ColdFire V2 (MCF5206E, ISA_A) and this chip is V4e. Every
// `mvs`/`mvz`/`mov3q`/`byterev`/`ff1` and the whole EMAC are absent, so the
// boot will stop at the first one. That is the point: the illegal-instruction
// report below names the opcode and the PC, which is a work list, not a bug.
#pragma once

#include <array>
#include <cstdint>
#include <functional>
#include <string>
#include <unordered_map>
#include <vector>

#include "mc68k/mc68k.h"

namespace ot
{
	// One mapped span of plain read/write memory.
	struct Region
	{
		uint32_t base = 0;
		std::vector<uint8_t> data;

		bool contains(const uint32_t _a, const uint32_t _size) const
		{
			// ⚠️ `(_a - base) + _size <= data.size()` OVERFLOWS. With the
			// region at 0x00000000, an access at 0xffffffff gives offset
			// 0xffffffff and 0xffffffff + 1 == 0, so the region claimed the
			// address and the write went 4 GB past its buffer. ✅ Measured
			// 8 Sep 2026 (O6): the frame handler's `moveb %d0,%a0@-` with a0
			// = 0 writes 0xffffffff, and the emulator died there with a bare
			// SIGSEGV inside Musashi. Subtract instead of add.
			if(_a < base)
				return false;
			const auto off = _a - base;
			return off < data.size() && data.size() - off >= _size;
		}
	};

	// A co-processor behind a peripheral window: the two DSP cores (O8). It is
	// asked FIRST, before the models and the boot's override table, so the
	// stand-in replies for the host port (below) are bypassed the moment a
	// real one is attached -- and stay in force when none is, which keeps
	// every gate that was measured against them bit-identical. It is also
	// clocked from both run loops: per ColdFire instruction during the boot
	// (no sample clock exists yet) and per sample once the RTOS runs.
	class Coprocessor
	{
	public:
		virtual ~Coprocessor() = default;
		virtual bool read(uint32_t _addr, uint8_t _size, uint32_t& _out) = 0;
		virtual bool write(uint32_t _addr, uint8_t _size, uint32_t _val) = 0;
		virtual void tickInstructions(uint64_t _n) = 0;
		// Returns the samples actually advanced: fewer than `_n` when the
		// co-processor raised a host word the machine should take NOW (O9b).
		virtual double tickSamples(double _n) = 0;
		// O9b: called when core `_core` puts a word in its host port OUTSIDE a
		// read-back pull -- the DSP's bank id, which on hardware is what the
		// frame interrupt announces (the frame handler reads it with no ready
		// check). Default: nobody listens.
		virtual void setHostWordHook(std::function<bool(int)>) {}		// returns whether the edge was taken; if not, it is offered again
		// The eDMA's side of the host port (O8 step 4). A block going TO the
		// co-processor is pushed whole at the kick, halfword by halfword, as
		// the bus cycles the eDMA would make; a block coming FROM it is pulled
		// at completion from the core the kick was made against, running that
		// core until each word is there. Returns the words it could not get.
		virtual int selected() const = 0;
		virtual bool hostRingEmpty(int _core) const = 0;	// the DSP has taken every word pushed so far
		virtual void pushHalfwords(uint32_t _addr, const std::vector<uint16_t>& _hw) = 0;
		virtual size_t pullHalfwords(uint32_t _addr, int _core, std::vector<uint16_t>& _out, size_t _n) = 0;
		// What the co-processor was told about the block just moved, for the
		// block log: where its own DMA is putting it and how much is left.
		virtual std::string blockNote(int _core) = 0;
		virtual uint32_t peekWord(int _core, char _space, uint32_t _addr) const = 0;
	};

	// A peripheral window: reads answer from `overrides` if the address has
	// one, else all-ones; writes are logged. This is route A's model, and the
	// boot never needs more than it (`emu_bringup.boot`).
	class Machine final : public mc68k::Mc68k
	{
	public:
		static constexpr uint32_t g_imageBase = 0x40000400;	// 0x40000000 + the 0x400 header
		static constexpr uint32_t g_resetSp   = 0x48000000;
		static constexpr uint16_t g_trap0     = 0x4e40;		// the RTOS handoff instruction

		explicit Machine(const std::vector<uint8_t>& _image);

		// -- the memory interface Musashi calls through ----------------------
		uint8_t  read8 (uint32_t _addr) override;
		uint16_t read16(uint32_t _addr) override;
		void     write8 (uint32_t _addr, uint8_t  _val) override;
		void     write16(uint32_t _addr, uint16_t _val) override;
		uint16_t readImm16(uint32_t _addr) override;

		// ⚠️ 32-BIT ACCESSES MUST ARRIVE WHOLE. Musashi's memoryOps compose a
		// longword from two 16-bit halves unless the machine provides these,
		// and a peripheral register is not two halves: the DSPI's status word
		// (0xfc05c02c) came back as 0x0000ffff instead of its real value, so
		// the firmware's `(SR >> 4) & 15 == 2` wait at 0x4001c504 could never
		// match and main parked there forever -- no task was ever created
		// (measured 7 Sep 2026, the second run of the O4 loop). The same class
		// as the PLL truncation that stalled the boot in O1.
		uint32_t read32(uint32_t _addr);
		void     write32(uint32_t _addr, uint32_t _val);

		uint32_t getResetPC() override { return g_imageBase; }
		uint32_t getResetSP() override { return g_resetSp; }

		uint32_t onIllegalInstruction(uint32_t _opcode) override;

		// The interrupt ACKNOWLEDGE: the core calls this when it actually
		// takes a queued vector. Offering a line and having it taken are
		// different events here, because Musashi dispatches the exception
		// itself, so anything that has to happen "when the interrupt is
		// delivered" hangs off this -- including the frame latch, which route A
		// clears as it pushes the frame (`_deliver` clears `frame_pending`), so
		// it must be cleared from the ack and not from the offer.
		uint32_t readIrqUserVector(uint8_t _level) override;
		using AckHook = std::function<void(uint8_t _vector, uint8_t _level)>;
		void setAckHook(AckHook _h) { m_ack = std::move(_h); }

		// -- driving it ------------------------------------------------------
		// Run until `trap #0` (the handoff), an illegal instruction, or the
		// budget. Returns why it stopped. This is the BOOT: it carries the
		// stall detector and the auto-poke, and it stops AT the handoff
		// without dispatching it, the way route A's `boot()` does.
		enum class Stop { Handoff, Illegal, Budget, Fault };
		Stop run(uint64_t _maxInstructions);

		// One instruction, with the V4e layer and the A-line dispatch, and
		// nothing else -- no stall detector, no handoff check. This is what
		// `Rtos` drives once the boot has handed over; it returns false if an
		// opcode was genuinely unknown (`why()` says which).
		bool step();

		// The vector base register. The firmware sets it itself with a
		// `movec %a0,%vbr` at 0x40000db6, so after a boot this reads
		// 0x40000000 -- ✅ checked rather than assumed, because Musashi's
		// ColdFire support for that register is what makes native exception
		// dispatch possible at all (route A had to hand-roll it: Unicorn's
		// CFV4E treats VBR as a no-op).
		uint32_t vbr() const;

		uint64_t instructions() const { return m_instructions; }
		uint64_t v4eExecuted() const { return m_v4e; }
		uint32_t pc() const;
		std::string why() const { return m_why; }

		// -- the peripheral window -------------------------------------------
		// A handler that answers reads and takes writes for 0xfc000000 and the
		// other windows. Returning false from the reader falls through to the
		// boot's override table (and to all-ones), which is how the models can
		// be installed for the addresses they own and no others.
		//
		// Route A's shape, deliberately: the BOOT runs against the all-ones
		// stub with no models at all, and the models are installed afterwards
		// and seeded by REPLAYING the writes the boot made. Modelling during
		// the boot would answer its wait-until-set spins differently and the
		// two emulators would stop being comparable.
		using PeriphRead  = std::function<bool(uint32_t _addr, uint8_t _size, uint32_t& _out)>;
		using PeriphWrite = std::function<void(uint32_t _addr, uint8_t _size, uint32_t _val)>;
		void setPeripheralHandlers(PeriphRead _r, PeriphWrite _w)
		{
			m_periphReadFn = std::move(_r);
			m_periphWriteFn = std::move(_w);
		}

		// Every write the run made into a peripheral window, in order: what
		// `Rtos` replays to seed its models (route A logs 7,886 of them on the
		// stock image).
		struct PeriphWriteRec { uint32_t addr; uint8_t size; uint32_t val; };
		const std::vector<PeriphWriteRec>& peripheralWrites() const { return m_periphWrites; }

		// A stateful peripheral reply, for the handful the boot needs that are
		// not constants (the DSP host port's ping index toggles 0/1).
		void setOverrideFn(uint32_t _addr, std::function<uint32_t()> _fn) { m_overrideFns[_addr] = std::move(_fn); }

		// A single peripheral BYTE that must not read all-ones. Route A keeps
		// these in `EXTRA_OVERRIDES`; the boot needs only the PLL, the card
		// needs one more (see `Rtos::attachCard`).
		void setOverride8(uint32_t _addr, uint8_t _val) { m_overrides[_addr] = _val; }

		void setCoprocessor(Coprocessor* _c) { m_coproc = _c; }
		Coprocessor* coprocessor() const { return m_coproc; }

		// Interception, the whole point of a headless build: a callback per
		// instruction (nullptr = off), and direct memory access for probes.
		void setStepHook(std::function<void(Machine&, uint32_t _pc)> _h) { m_step = std::move(_h); }

		// Sample the PC every `_every` instructions. A boot that does not
		// reach the handoff is almost always spinning on a flag no peripheral
		// model answers, and the hot address names it -- route A grew the same
		// thing (its stall detector) for the same reason.
		// ⚠️ THE PC WATCH LIVES HERE, NOT IN `Rtos`, AND THAT IS THE POINT.
		// It was in `Rtos::stepOnce` first, which runs only AFTER the handoff
		// -- so a watch on an address in the BOOT's own range reported "0
		// hits" whether it ran or not. That is the silent-instrument trap
		// again (RTOS_FORK §10.3b), and it nearly produced a wrong finding
		// about the DSP program loader on 8 Sep 2026 (O8): `0x4000050c`, the
		// only caller of the DSP start, is at a boot address. Consulted from
		// BOTH `run()` and `step()`, the answer covers the whole run.
		//
		// The timestamp is the INSTRUCTION COUNT rather than the sample clock,
		// because the boot has no sample clock -- `Rtos` prints its own sample
		// beside it for hits it saw.
		struct PcHit { uint64_t instruction; uint32_t pc, d0, d1, a0, a1, sp, stack[5]; uint32_t d[8], a[7]; };	// d/a: every register (O9b: a watch that showed four of them could not say which record a routine read)
		void watchPc(std::vector<uint32_t> _addrs) { m_watchPc = std::move(_addrs); }

		// ✅ THE DSP HOST PORT, RECORDED. The firmware programs the DSPs
		// ITSELF -- `0x40001e50` (called once, from the boot at `0x4000050c`)
		// uploads through `0x20000014/18/1c`, three halfwords per 24-bit word,
		// with a ready handshake on `0x20000008` (measured 8 Sep 2026, O8).
		// So the words it sends ARE the payload, and capturing them is how the
		// protocol decode gets checked against `out/dsp/mem_*.mem` before a
		// single line of DSP emulation exists.
		//
		// ⚠️ This is a SEPARATE log from `peripheralLog`, which is capped at
		// 4096 accesses and therefore full long before the DSP init runs at
		// instruction ~4.27M -- reading "0 host-port touches" out of it was a
		// false negative that cost a measurement.
		struct HostPortWrite { uint64_t instruction; uint32_t pc, addr, val; uint8_t size; };
		void setHostPortLog(bool _on) { m_hostPortLogOn = _on; }
		const std::vector<HostPortWrite>& hostPortLog() const { return m_hostPortLog; }
		const std::vector<PcHit>& pcHits() const { return m_pcHits; }
		void notePcWatch(uint32_t _pc);

		void setProfile(uint32_t _every) { m_profileEvery = _every; }
		const std::unordered_map<uint32_t, uint64_t>& profile() const { return m_profile; }
		// Registers a borrowed call needs: main's stack pointer to push the
		// frame onto, and D0 for the return value.
		uint32_t getA7() const;
		void     setA7(uint32_t _v);
		uint32_t getD0() const;
		uint32_t getD(int _n) const;
		uint32_t getA(int _n) const;

		uint32_t peek32(uint32_t _addr);
		void     poke32(uint32_t _addr, uint32_t _val);

		// Route A's `watch_mem`: every write into a small range, with the PC
		// of the instruction making it. Used by the M6c trig log (the
		// per-track live nibble at 0x46104d15) and by the load's own watch on
		// PART_PTR, which is how the engine's BANK= parse is told apart from
		// every other writer of that word.
		//
		// ⚠️ THE PC IS `M68K_REG_PPC`, NOT `pc()`. Musashi's PC is the fetch
		// pointer -- already past the instruction and its extension words by
		// the time the write executes -- so a watch that reported `pc()` would
		// name the NEXT instruction, and route A's site addresses would never
		// match. PPC is the address of the instruction being executed.
		using WriteWatch = std::function<void(uint32_t _addr, uint8_t _size, uint32_t _val, uint32_t _pc)>;
		void addWriteWatch(uint32_t _begin, uint32_t _end, WriteWatch _cb);
		uint32_t currentPc() const;

		// Map a span of plain memory after construction. Route A's `install`
		// adds two of these over the boot map (`Rtos::install`), and an
		// overlap with something already mapped is IGNORED, not an error --
		// route A wraps each `mem_map` in a bare `except UcError: pass`.
		void mapRegion(uint32_t _base, uint32_t _size);

		// ⚠️ THIS MACHINE NEVER FAULTS ON UNMAPPED MEMORY AND ROUTE A ALWAYS
		// DOES, so the two emulators are least comparable exactly where a
		// model is missing. Unicorn raises UC_ERR_READ_UNMAPPED, which is why
		// route A's own note says it "faults reading 0x100fff04 in main's
		// settings path" without a card attached; here the same read answers
		// all-ones and the firmware carries on down a path nobody chose. So
		// every access outside every region and every peripheral window is
		// COUNTED and the first few thousand are kept, because a silent
		// all-ones is the port's version of route A's crash and it has to be
		// visible to be compared at all.
		// ✅ WHAT ROUTE A ACTUALLY DOES, measured 8 Sep 2026 and NOT what its
		// source reads like: `_prime_menu` (emu_bringup) installs an
		// unmapped-access hook that maps a zero page and returns True -- a
		// workaround for a stale formatter pointer in the menu render -- and
		// it stays installed for the rest of the run. So in the golden
		// configuration route A does not fault on unmapped memory at all: it
		// GROWS. Its region list goes from 11 after `install` to 15 by the
		// M6a gate, and the four it adds are
		//     0x10000000-0x100affff  0x100c0000-0x100fffff
		//     0x42000000-0x45ffffff  0x48100000-0x4fffffff
		// which are, page for page, the four spans this port was answering
		// all-ones for (20,348,069 accesses: a 64 MB clear at 0x42000000 from
		// the bzero at 0x400209a4, a 10.8 MB clear at 0x4f502c10 from the
		// literal loop at 0x40002fb4, and main's settings window). So the
		// port grows the same way, at route A's own 4 KB granularity: a first
		// touch allocates a ZEROED page and the access proceeds.
		//
		// ⚠️ Without a project route A DOES fault (measured: "unmapped read
		// 0x100fff04 at pc 0x4001fa4e"), because nothing primed the menu. The
		// oracle is the golden configuration, so growing is the faithful
		// behaviour; `setAutoMap(false)` restores the all-ones stub for
		// diagnosis, and then this counter is the work list again.
		void setAutoMap(bool _on) { m_autoMap = _on; }
		// ⚠️ A RUNAWAY AUTO-MAP IS A BUG, AND WITHOUT A CEILING IT PRESENTS AS
		// A CRASH IN THE EMULATOR RATHER THAN AS A FINDING ABOUT THE FIRMWARE.
		// Measured 8 Sep 2026 (O6): a `moveb %d0,%a0@-` loop walking down
		// through unmapped memory grew a 4 KB page per 4 KB of address space
		// until the process died -- SIGSEGV bare, SIGBUS under ASan, no report
		// printed either way, because the port's own stdout never flushed. The
		// limit turns that into "stopped: auto-map limit, N pages, top pc X",
		// which names the loop. Route A's own growth on the golden path is 4
		// spans / ~200 MB before the card maps them explicitly, so the default
		// is well clear of anything faithful.
		void setAutoMapLimit(uint64_t _pages) { m_autoMapLimit = _pages; }
		uint64_t autoMappedPages() const { return m_autoPages.size(); }

		struct Unmapped { char kind; uint32_t pc, addr; uint8_t size; uint32_t val; };
		const std::vector<Unmapped>& unmapped() const { return m_unmapped; }
		uint64_t unmappedCount() const { return m_unmappedCount; }
		// A dropped WRITE and an all-ones READ are different problems: the
		// write is lost only if something reads it back, the read is a value
		// the firmware acts on. Counted apart for that reason.
		uint64_t unmappedReads() const { return m_unmappedReads; }
		uint64_t unmappedWrites() const { return m_unmappedCount - m_unmappedReads; }
		// The detail log is capped; these two are not. A page is 64 KB.
		const std::unordered_map<uint32_t, uint64_t>& unmappedPages() const { return m_unmappedPages; }
		const std::unordered_map<uint32_t, uint64_t>& unmappedPcs() const { return m_unmappedPcs; }
		// Reads only: the accesses that feed the firmware a value it acts on.
		const std::unordered_map<uint32_t, uint64_t>& unmappedReadPcs() const { return m_unmappedReadPcs; }

		// Every distinct peripheral address the run touched, in first-touch
		// order: route A logs the same thing (`BootResult.boot_map`), so the
		// two boots can be compared without a full instruction trace.
		struct Access { char kind; uint32_t pc, addr; uint8_t size; uint32_t val; };
		const std::vector<Access>& peripheralLog() const { return m_periphLog; }

		// EVERY peripheral access in order, not just first touches, while
		// switched on: for diffing a window of the run against route A's.
		void setPeriphTrace(bool _on) { m_periphTraceOn = _on; }
		const std::vector<Access>& periphTrace() const { return m_periphTrace; }

		// Every completion flag the stall detector had to satisfy, as
		// (loop pc, flag address, value): route A keeps the same list and it
		// is the honest record of where this emulator is standing in for
		// hardware nobody has modelled yet.
		struct AutoPoke { uint32_t pc, addr, value; };
		const std::vector<AutoPoke>& autoPokes() const { return m_autoPokes; }

	private:
		Region* find(uint32_t _addr, uint32_t _size);
		bool isPeripheral(uint32_t _addr) const;
		uint32_t peripheralRead(uint32_t _addr, uint8_t _size);
		void peripheralWrite(uint32_t _addr, uint8_t _size, uint32_t _val);

		std::vector<Region> m_regions;
		// BYTE-addressable, not word: Musashi composes a 32-bit peripheral read
		// from two 16-bit reads, so a value stored whole and returned per
		// access is truncated to the access width. That cost the first boot --
		// the PLL register read back 0x0000ffff instead of 0x16000000 and the
		// firmware spun forever in its clock check at 0x4000f9e8.
		std::unordered_map<uint32_t, uint8_t> m_overrides;
		std::unordered_map<uint32_t, std::function<uint32_t()>> m_overrideFns;
		void override32(uint32_t _addr, uint32_t _val);
		Coprocessor* m_coproc = nullptr;
		PeriphRead m_periphReadFn;
		PeriphWrite m_periphWriteFn;
		std::vector<PeriphWriteRec> m_periphWrites;
		std::vector<Access> m_periphLog;
		std::vector<Access> m_periphTrace;
		bool m_periphTraceOn = false;
		void noteUnmapped(char _kind, uint32_t _addr, uint8_t _size, uint32_t _val);
		struct Watch { uint32_t begin, end; WriteWatch cb; };
		std::vector<Watch> m_writeWatches;
		void noteWatchedWrite(uint32_t _addr, uint8_t _size, uint32_t _val);
		std::vector<Unmapped> m_unmapped;
		uint64_t m_unmappedCount = 0, m_unmappedReads = 0;
		std::unordered_map<uint32_t, uint64_t> m_unmappedPages, m_unmappedPcs, m_unmappedReadPcs;

		// Route A's granularity: `mem_map(addr & ~0xFFF, 0x1000)`.
		static constexpr uint32_t g_autoPageBits = 12;
		static constexpr uint32_t g_autoPageSize = 1u << g_autoPageBits;
		bool m_autoMap = true;
		std::unordered_map<uint32_t, std::vector<uint8_t>> m_autoPages;
		uint32_t m_lastAutoPage = ~0u;			// a one-entry cache: these loops are sequential
		std::vector<uint8_t>* m_lastAutoData = nullptr;
		uint8_t* autoByte(uint32_t _addr, bool _create);
		void badWrite(const char* _what, uint32_t _addr, uint8_t _size);
		uint64_t m_autoMapLimit = 65536;		// 4 KB pages: 256 MB
		std::vector<uint8_t> m_autoScrap;		// where a write goes once the limit is hit
		std::function<void(Machine&, uint32_t)> m_step;
		AckHook m_ack;
		uint64_t m_instructions = 0;
		uint64_t m_v4e = 0;			// instructions the V4e layer supplied
		bool m_hostPortLogOn = false;
		std::vector<HostPortWrite> m_hostPortLog;
		std::vector<uint32_t> m_watchPc;
		std::vector<PcHit> m_pcHits;
		uint32_t m_profileEvery = 0;
		std::unordered_map<uint32_t, uint64_t> m_profile;
		std::string m_why;
		bool m_illegal = false;

		// -- the stall detector, ported field for field from route A ---------
		// A PC confined to a 64-byte window across four 500k bursts with fewer
		// than 2,000 stores in between is a poll, not a memset. When one is
		// found, `tryAutoPoke` looks for the `move.w (abs),d0 ... cmpi #imm,d0`
		// pair around it and writes imm at the LOAD width -- two bytes, NOT the
		// compare's width, or the low word reads back wrong (route A's comment,
		// and it is a measured trap).
		static constexpr uint64_t g_burst = 500000;
		static constexpr uint32_t g_stallBursts = 4;
		bool tryAutoPoke(uint32_t _pcInLoop);
		std::vector<uint32_t> m_window;
		std::vector<uint64_t> m_windowWrites;
		std::vector<AutoPoke> m_autoPokes;
		uint64_t m_writes = 0;
	};
}
