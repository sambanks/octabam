// The MCF5445x peripherals the RTOS needs, translated from route A.
//
// `tools/emu_rtos.py` is the specification for every rule in here, and each
// one carries the measurement or the failure that established it. Where route
// A says "measured", this says measured; where it says "inferred", so does
// this. Nothing is tightened on the way across -- a rule that reads as
// arbitrary is arbitrary in the firmware too, and the comment says so.
//
// Time is counted in SAMPLES, as route A counts it: the two clocks the
// firmware cares about are fixed ratios of the sample clock (a DSP frame every
// 16 samples, PIT0 every 220.5), so samples make the ratios exact and the
// instruction budget a separate, honest knob.
#pragma once

#include <array>
#include <cstdint>
#include <functional>
#include <unordered_map>
#include <vector>

namespace ot
{
	inline constexpr double g_sampleHz = 44100.0;
	inline constexpr double g_framePeriod = 16.0;		// samples per DSP frame interrupt

	// ---- PIT ---------------------------------------------------------------
	// MCF5445x programmable interval timer. PCSR +0, PMR +2, PCNTR +4.
	//
	// ⚠️ The prescaler input is a KNOB, not a fact: route A defaults it to
	// 264 MHz and notes that off the 132 MHz bus clock every period is 2x
	// longer. The sequencer's own tick rate is what pins it, and M6c's gate is
	// what checks it.
	class Pit
	{
	public:
		enum : uint32_t { EN = 1, RLD = 2, PIF = 4, PIE = 8, OVW = 16 };

		Pit(const char* _name, double _clockHz) : m_name(_name), m_clockHz(_clockHz) {}

		double periodSamples() const;
		bool irq() const { return (m_pcsr & PIF) && (m_pcsr & PIE); }
		uint64_t fired() const { return m_fired; }

		uint32_t read(uint32_t _off, uint32_t _size, double _now) const;
		void write(uint32_t _off, uint32_t _size, uint32_t _val, double _now);

		// Fire every expiry up to `_now`; returns how many fired.
		uint32_t advance(double _now);

		// When this timer next expires, if it is armed at all: what the run
		// loop's idle skip jumps to.
		bool nextExpiry(double& _out) const { _out = m_expiry; return m_armed; }

		// The state the boot left behind the generic peripheral stub
		// (0x400005a8..0x400005f6), replayed rather than guessed.
		void seed(uint32_t _pcsr, uint32_t _pmr, double _now);

	private:
		void arm(double _now);

		const char* m_name;
		double m_clockHz;
		uint32_t m_pcsr = 0, m_pmr = 0xffff;
		bool m_armed = false;
		double m_expiry = 0;
		uint64_t m_fired = 0;
	};

	// ---- UART --------------------------------------------------------------
	// One of the serial blocks at 0xfc064000 / 0xfc068000, modelled from the
	// firmware's own use of it (route A: handler 0x400109bc, ring writer
	// 0x40010b1c, polled sender 0x40010a4c):
	//   +0x04 status: bit 0 = receive ready (must read 0 with nothing queued,
	//         or the handler's receive loop never ends), bit 2 = transmit ready
	//   +0x0c data: read = the next received byte, write = one byte sent
	//   +0x14 mask: 3 = transmit + receive, 2 = receive only
	// Transmit is always ready, so the line is asserted exactly while the
	// transmit interrupt is enabled -- the handler drains the ring and drops
	// the mask to 2 itself.
	class Uart
	{
	public:
		enum : uint32_t { RXRDY = 1, TXRDY = 4 };

		Uart(const char* _name, uint32_t _base) : m_name(_name), m_base(_base) {}

		uint32_t base() const { return m_base; }
		bool irq() const { return (m_imr & 1) || ((m_imr & 2) && !m_rx.empty()); }
		const std::vector<uint8_t>& tx() const { return m_tx; }

		// ⚠️ The boot leaves the transmit interrupt ARMED with the kernel's
		// trampoline still in the vector slot: on hardware the driver's own
		// handler drains the ring during the boot, but a cold emulated boot
		// takes no interrupts at all, so the mask arrives at the handoff armed
		// and storms. Main re-installs the handler and re-arms transmit on its
		// first write. Route A clears bit 0 after seeding for exactly this;
		// 🟡 inferred from the storm, not measured.
		void clearTransmitInterrupt() { m_imr &= ~1u; }

		uint32_t read(uint32_t _off, uint32_t _size);
		void write(uint32_t _off, uint32_t _size, uint32_t _val, bool _replay);

	private:
		const char* m_name;
		uint32_t m_base;
		uint32_t m_imr = 0;
		std::vector<uint8_t> m_tx;
		std::vector<uint8_t> m_rx;
		std::unordered_map<uint32_t, uint32_t> m_regs;
	};

	// ---- DSPI --------------------------------------------------------------
	// The DSPI at 0xfc05c000 as a LOOPBACK: every frame pushed (PUSHR +0x34)
	// yields one received frame (POPR +0x38, value 0), and the status register
	// (+0x2c) reports the receive count in bits 4-7 with TCF (31) and TFFF (25)
	// set. Route A's sites: 0x4001c398 pushes three and waits for three;
	// 0x40040b94 waits for two. What sits on the far end is not modelled.
	//
	// ✅ This is why it is here and not in a later milestone: without it main
	// parks in that wait at 0x4001c50e and never reaches its init list, so no
	// task is ever created and the M6a gate cannot pass (measured 7 Sep 2026,
	// the first run of the O4 loop -- 401 dispatches, 0 creates, main pinned).
	class Dspi
	{
	public:
		enum : uint32_t { SR = 0x2c, PUSHR = 0x34, POPR = 0x38 };

		uint32_t read(uint32_t _off, uint32_t _size);
		void write(uint32_t _off, uint32_t _size, uint32_t _val, bool _replay);

	private:
		std::vector<uint32_t> m_rx;
		std::unordered_map<uint32_t, uint32_t> m_regs;
		uint64_t m_pushed = 0;
	};

	// ---- INTC --------------------------------------------------------------
	// MCF54455RM rev 5 chapter 17. IPRH/L +0x00/+0x04 (read back what is
	// asserted), IMRH/L +0x08/+0x0c, INTFRCH/L +0x10/+0x14, SIMR/CIMR bytes at
	// +0x1c/+0x1d (value = source, 0x40 = all), ICRn at +0x40+n. The vector of
	// a source is `vectorBase + source`.
	class Intc
	{
	public:
		Intc(const char* _name, uint32_t _vectorBase) : m_name(_name), m_vectorBase(_vectorBase) {}

		// A source whose assertion is a live wire rather than a register bit
		// (a timer's IRQ, a DMA completion): asked every time.
		void addLine(uint32_t _source, std::function<bool()> _fn) { m_lines.emplace_back(_source, std::move(_fn)); }
		void setForceHook(std::function<void(uint64_t)> _fn) { m_onForce = std::move(_fn); }

		uint64_t asserted() const;

		// (level, source) pairs, asserted and deliverable, highest level first.
		//
		// ⚠️ A FORCED request IGNORES THE MASK -- "The assertion of an
		// interrupt request via the interrupt force register is not affected by
		// the interrupt mask register" (MCF54455RM rev 5, §17.2.3). The
		// firmware depends on it: the sequencer tick is source 32, installed
		// with ICR 3 and never unmasked anywhere in the image, and masking it
		// leaves the sequencer silent -- route A measured 400 frames and zero
		// ticks before this rule went in. A source with ICR 0 is still never
		// delivered.
		std::vector<std::pair<uint32_t, uint32_t>> pending() const;

		// The highest-priority deliverable source, without allocating: the run
		// loop asks this after every instruction, so `pending()`'s vector
		// would dominate the whole emulator (measured: it did -- the first
		// version of the O4 loop ran so slowly it looked like a hang).
		bool top(uint32_t& _level, uint32_t& _source) const;

		uint32_t vectorBase() const { return m_vectorBase; }

		uint32_t read(uint32_t _off, uint32_t _size) const;
		void write(uint32_t _off, uint32_t _size, uint32_t _val);

	private:
		const char* m_name;
		uint32_t m_vectorBase;
		uint64_t m_imr = ~0ull;			// bit n = source n masked; bit 0 = mask all
		uint64_t m_intfrc = 0;
		std::array<uint8_t, 64> m_icr = {};
		std::vector<std::pair<uint32_t, std::function<bool()>>> m_lines;
		std::function<void(uint64_t)> m_onForce;
	};
}
