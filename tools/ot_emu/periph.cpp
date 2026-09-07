#include "periph.h"

#include <algorithm>
#include <cmath>

namespace ot
{
	// ---- PIT ---------------------------------------------------------------
	double Pit::periodSamples() const
	{
		const uint32_t pre = (m_pcsr >> 8) & 0xf;
		return static_cast<double>(m_pmr + 1) * static_cast<double>(1u << pre) / m_clockHz * g_sampleHz;
	}

	void Pit::arm(const double _now)
	{
		if(m_pcsr & EN)
		{
			m_expiry = _now + periodSamples();
			m_armed = true;
		}
		else
			m_armed = false;
	}

	uint32_t Pit::read(const uint32_t _off, const uint32_t _size, const double _now) const
	{
		if(_off == 0)
			return m_pcsr;
		if(_off == 2)
			return m_pmr;
		if(_off == 4)
		{
			// PCNTR: what is left of the current period, scaled into the
			// counter's own units. Route A's shape exactly -- the firmware
			// only ever compares it against zero and against PMR.
			if(!m_armed)
				return m_pmr;
			const double period = std::max(periodSamples(), 1e-9);
			const double frac = std::max(0.0, m_expiry - _now) / period;
			return static_cast<uint32_t>(frac * static_cast<double>(m_pmr)) & 0xffff;
		}
		return (1u << (8 * _size)) - 1;
	}

	void Pit::write(const uint32_t _off, uint32_t, const uint32_t _val, const double _now)
	{
		if(_off == 0)
		{
			// PIF is WRITE-1-TO-CLEAR: the incoming bit clears the flag, it
			// never sets it.
			const bool wasEnabled = (m_pcsr & EN) != 0;
			const bool clearPif = (_val & PIF) != 0;
			m_pcsr = (_val & ~PIF) | (m_pcsr & PIF);
			if(clearPif)
				m_pcsr &= ~PIF;
			if((m_pcsr & EN) && !wasEnabled)
				arm(_now);
			else if(!(m_pcsr & EN))
				m_armed = false;
		}
		else if(_off == 2)
		{
			m_pmr = _val & 0xffff;
			// OVW: overwrite the running count immediately. Without it a new
			// period only takes effect at the next expiry.
			if((m_pcsr & OVW) || !m_armed)
				arm(_now);
		}
	}

	uint32_t Pit::advance(const double _now)
	{
		uint32_t n = 0;
		while(m_armed && _now >= m_expiry)
		{
			m_pcsr |= PIF;
			++m_fired;
			++n;
			if(m_pcsr & RLD)
				m_expiry += periodSamples();
			else
				m_armed = false;
		}
		return n;
	}

	void Pit::seed(const uint32_t _pcsr, const uint32_t _pmr, const double _now)
	{
		m_pcsr = _pcsr;
		m_pmr = _pmr;
		arm(_now);
	}

	// ---- INTC --------------------------------------------------------------
	uint64_t Intc::asserted() const
	{
		uint64_t a = m_intfrc;
		for(const auto& l : m_lines)
			if(l.second())
				a |= 1ull << l.first;
		return a;
	}

	std::vector<std::pair<uint32_t, uint32_t>> Intc::pending() const
	{
		uint64_t a = asserted() & ~m_imr;
		if(m_imr & 1)			// MASKALL
			a = 0;
		a |= m_intfrc;			// ... but a forced source is delivered anyway

		std::vector<std::pair<uint32_t, uint32_t>> out;
		for(uint32_t s = 1; s < 64; ++s)
			if((a >> s) & 1)
				if(const auto level = m_icr[s])		// ICR 0 is never delivered
					out.emplace_back(level, s);
		std::sort(out.begin(), out.end(), std::greater<>());
		return out;
	}

	uint32_t Intc::read(const uint32_t _off, const uint32_t _size) const
	{
		if(_off < 0x18 && _size == 4)
		{
			const auto a = asserted();
			switch(_off)
			{
			case 0x00: return static_cast<uint32_t>(a >> 32);
			case 0x04: return static_cast<uint32_t>(a);
			case 0x08: return static_cast<uint32_t>(m_imr >> 32);
			case 0x0c: return static_cast<uint32_t>(m_imr);
			case 0x10: return static_cast<uint32_t>(m_intfrc >> 32);
			case 0x14: return static_cast<uint32_t>(m_intfrc);
			default:   return 0;
			}
		}
		if(_off >= 0x40 && _off < 0x80 && _size == 1)
			return m_icr[_off - 0x40];
		return (1u << (8 * _size)) - 1;
	}

	void Intc::write(const uint32_t _off, const uint32_t _size, const uint32_t _val)
	{
		if(_off == 0x08 && _size == 4)
			m_imr = (static_cast<uint64_t>(_val) << 32) | (m_imr & 0xffffffffull);
		else if(_off == 0x0c && _size == 4)
			m_imr = (m_imr & ~0xffffffffull) | _val;
		else if((_off == 0x10 || _off == 0x14) && _size == 4)
		{
			const auto before = m_intfrc;
			if(_off == 0x10)
				m_intfrc = (static_cast<uint64_t>(_val) << 32) | (m_intfrc & 0xffffffffull);
			else
				m_intfrc = (m_intfrc & ~0xffffffffull) | _val;
			// A force is a RESCHEDULE REQUEST: the run loop has to see it
			// inside the instruction that made it, not at the end of a burst.
			if((m_intfrc & ~before) && m_onForce)
				m_onForce(m_intfrc & ~before);
		}
		else if(_off == 0x1c && _size == 1)			// SIMR: set mask
			m_imr = (_val & 0x40) ? ~0ull : (m_imr | (1ull << (_val & 0x3f)));
		else if(_off == 0x1d && _size == 1)			// CIMR: clear mask
		{
			// ...and MASKALL (IMRL bit 0) with it. 🟡 INFERRED, and route A
			// says why: nothing in the image ever writes IMRH/IMRL (a literal
			// scan found no site), the firmware unmasks only through CIMR, and
			// the unit plainly takes interrupts -- so CIMR must clear MASKALL
			// too or nothing would ever be delivered.
			m_imr = (_val & 0x40) ? 0ull : (m_imr & ~((1ull << (_val & 0x3f)) | 1ull));
		}
		else if(_off >= 0x40 && _off < 0x80 && _size == 1)
			m_icr[_off - 0x40] = _val & 7;
	}
}
