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
