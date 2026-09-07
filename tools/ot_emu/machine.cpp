#include "machine.h"

#include "v4e.h"

#include <cstdio>
#include <cstring>
#include <algorithm>

// Musashi reaches the machine through these free functions; the header wants
// MC68K_CLASS defined to the concrete class and must be included EXACTLY ONCE
// in the whole program (it defines them, it does not declare them).
#define MC68K_CLASS ot::Machine
#include "mc68k/musashiEntry.h"

#include "mc68k/Musashi/m68k.h"
#include "mc68k/cpuState.h"

namespace ot
{
	namespace
	{
		// The RAM map, verbatim from tools/emu_bringup.py's boot(). Sizes are
		// what route A maps, not what the hardware has: the point is that a
		// divergence between the two emulators can never be a map difference.
		constexpr struct { uint32_t base, size; } g_map[] = {
			{0x00000000, 0x00010000},	// the vector page / low scratch
			{0x40000000, 0x02000000},	// SDRAM: the OS image at +0x400
			{0x46000000, 0x02000000},	// SDRAM: data, BSS, app objects
			{0x48000000, 0x00100000},	// the reset stack lives at the base
			{0x80000000, 0x01000000},	// fast/shared RAM: voice state, TCBs, DSP frames
			{0x100b0000, 0x00010000},	// the settings/mirror page the boot touches
		};

		// Peripheral windows. Reads that have no override answer ALL-ONES,
		// which is what satisfies the boot's wait-until-set spins.
		constexpr struct { uint32_t base, size; } g_periph[] = {
			{0xfc000000, 0x00100000},	// the on-chip peripheral space
			{0x20000000, 0x00001000},	// the DSP host port
			{0x90000000, 0x00001000},	// the ATA task file (CompactFlash) over FlexBus
		};
	}

	Machine::Machine(const std::vector<uint8_t>& _image)
		: Mc68k(M68K_CPU_TYPE_MCF5206E)		// the closest type this Musashi has;
											// V4e is the port's first job
	{
		for(const auto& r : g_map)
		{
			Region reg;
			reg.base = r.base;
			reg.data.assign(r.size, 0);
			m_regions.push_back(std::move(reg));
		}
		if(auto* const r = find(g_imageBase, static_cast<uint32_t>(_image.size())))
			std::memcpy(r->data.data() + (g_imageBase - r->base), _image.data(), _image.size());

		// The PLL gate: the firmware halts at 0x4000fa8c unless the top byte
		// of 0xfc0c4000 times 12 MHz is 264 MHz, so the byte is 22 (0x16).
		// Measured by route A (emu_bringup), kept identical here.
		override32(0xfc0c4000, 0x16000000);

		// SR BEFORE A7: writing the status register swaps the supervisor and
		// user stack banks, so setting A7 first puts the reset stack in the
		// bank the machine is about to leave. Route A's lesson, and it fails
		// silently -- the boot simply wanders.
		m68k_set_reg(getCpuState(), M68K_REG_SR, 0x2700);
		m68k_set_reg(getCpuState(), M68K_REG_SP, g_resetSp);
		setPC(g_imageBase);
	}

	void Machine::override32(const uint32_t _addr, const uint32_t _val)
	{
		for(uint32_t i = 0; i < 4; ++i)
			m_overrides[_addr + i] = static_cast<uint8_t>(_val >> (8 * (3 - i)));
	}

	Region* Machine::find(const uint32_t _addr, const uint32_t _size)
	{
		for(auto& r : m_regions)
			if(r.contains(_addr, _size))
				return &r;
		return nullptr;
	}

	void Machine::mapRegion(const uint32_t _base, const uint32_t _size)
	{
		// Route A's `except UcError: pass`: a span that is already there is
		// left alone rather than remapped, so the boot map always wins.
		for(const auto& r : m_regions)
			if(_base >= r.base && _base - r.base < r.data.size())
				return;
		Region reg;
		reg.base = _base;
		reg.data.assign(_size, 0);
		// A real map WINS over pages this machine grew on its own: carry the
		// bytes across and drop them, so a later access cannot see stale ones.
		for(uint32_t a = _base; a < _base + _size; ++a)
			if(const uint8_t* const b = autoByte(a, false))
				reg.data[a - _base] = *b;
		for(uint32_t p = _base >> g_autoPageBits; p <= (_base + _size - 1) >> g_autoPageBits; ++p)
			m_autoPages.erase(p);
		m_lastAutoPage = ~0u;
		m_lastAutoData = nullptr;
		m_regions.push_back(std::move(reg));
	}

	// One byte of auto-mapped memory, allocating its page on first touch.
	// The one-entry cache matters: the loops that need this are `bzero` and
	// `memcpy` walking tens of megabytes in order, so the page almost never
	// changes between accesses.
	uint8_t* Machine::autoByte(const uint32_t _addr, const bool _create)
	{
		const uint32_t page = _addr >> g_autoPageBits;
		if(page != m_lastAutoPage || !m_lastAutoData)
		{
			auto it = m_autoPages.find(page);
			if(it == m_autoPages.end())
			{
				if(!_create)
					return nullptr;
				it = m_autoPages.emplace(page, std::vector<uint8_t>(g_autoPageSize, 0)).first;
			}
			m_lastAutoPage = page;
			m_lastAutoData = &it->second;
		}
		return m_lastAutoData->data() + (_addr & (g_autoPageSize - 1));
	}

	void Machine::noteUnmapped(const char _kind, const uint32_t _addr, const uint8_t _size,
		const uint32_t _val)
	{
		++m_unmappedCount;
		const auto p = pc();
		if(_kind == 'r')
		{
			++m_unmappedReads;
			++m_unmappedReadPcs[p];
		}
		++m_unmappedPages[_addr >> 16];
		++m_unmappedPcs[p];
		if(m_unmapped.size() < 4096)
			m_unmapped.push_back({_kind, p, _addr, _size, _val});
	}

	bool Machine::isPeripheral(const uint32_t _addr) const
	{
		for(const auto& p : g_periph)
			if(_addr >= p.base && _addr - p.base < p.size)
				return true;
		return false;
	}

	uint32_t Machine::peripheralRead(const uint32_t _addr, const uint8_t _size)
	{
		// The models first, once installed; anything they do not own falls
		// through to the boot's override table below.
		if(m_periphReadFn)
		{
			uint32_t v = 0;
			if(m_periphReadFn(_addr, _size, v))
			{
				if(m_periphLog.size() < 4096)
					m_periphLog.push_back({'R', pc(), _addr, _size, v});
				return v;
			}
		}
		if(const auto it = m_overrideFns.find(_addr); it != m_overrideFns.end())
		{
			const auto v = it->second();
			if(m_periphLog.size() < 4096)
				m_periphLog.push_back({'R', pc(), _addr, _size, v});
			return v;
		}
		// Byte by byte, big-endian, so an access of any width or alignment sees
		// the same bytes. Anything without an override reads ALL-ONES, which is
		// what satisfies the boot's wait-until-set spins (route A's default).
		uint32_t v = 0;
		for(uint32_t i = 0; i < _size; ++i)
		{
			const auto it = m_overrides.find(_addr + i);
			v = (v << 8) | (it != m_overrides.end() ? it->second : 0xff);
		}
		if(m_periphLog.size() < 4096)
			m_periphLog.push_back({'R', pc(), _addr, _size, v});
		return v;
	}

	void Machine::peripheralWrite(const uint32_t _addr, const uint8_t _size, const uint32_t _val)
	{
		m_periphWrites.push_back({_addr, _size, _val});
		if(m_periphLog.size() < 4096)
			m_periphLog.push_back({'W', pc(), _addr, _size, _val});
		if(m_periphWriteFn)
			m_periphWriteFn(_addr, _size, _val);
	}

	uint32_t Machine::vbr() const
	{
		return m68k_get_reg(const_cast<mc68k::CpuState*>(getCpuState()), M68K_REG_VBR);
	}

	bool Machine::step()
	{
		const auto p = pc();
		const auto op = read16(p);
		// The EMAC and mov3q are A-line: Musashi routes 0xAxxx to the A-line
		// EXCEPTION, not to the illegal-instruction callback the V4e layer
		// hooks, so they are dispatched here (see run(), same rule).
		if((op & 0xf000) == 0xa000)
		{
			setPC(p + 2);
			if(v4e::execute(*this, op) == v4e::Result::Handled)
			{
				++m_v4e;
				return true;
			}
			setPC(p);
		}
		exec();
		return !m_illegal;
	}

	uint8_t Machine::read8(const uint32_t _addr)
	{
		if(isPeripheral(_addr))
			return static_cast<uint8_t>(peripheralRead(_addr, 1));
		if(auto* const r = find(_addr, 1))
			return r->data[_addr - r->base];
		noteUnmapped('r', _addr, 1, 0xff);
		if(m_autoMap)
			return *autoByte(_addr, true);
		return 0xff;
	}

	uint16_t Machine::read16(const uint32_t _addr)
	{
		if(isPeripheral(_addr))
			return static_cast<uint16_t>(peripheralRead(_addr, 2));
		if(auto* const r = find(_addr, 2))
		{
			const auto o = _addr - r->base;
			return static_cast<uint16_t>((r->data[o] << 8) | r->data[o + 1]);
		}
		noteUnmapped('r', _addr, 2, 0xffff);
		if(m_autoMap)
			return static_cast<uint16_t>((*autoByte(_addr, true) << 8) | *autoByte(_addr + 1, true));
		return 0xffff;
	}

	void Machine::write8(const uint32_t _addr, const uint8_t _val)
	{
		++m_writes;
		if(isPeripheral(_addr))
			return peripheralWrite(_addr, 1, _val);
		if(auto* const r = find(_addr, 1))
			r->data[_addr - r->base] = _val;
		else
		{
			noteUnmapped('w', _addr, 1, _val);
			if(m_autoMap)
				*autoByte(_addr, true) = _val;
		}
	}

	void Machine::write16(const uint32_t _addr, const uint16_t _val)
	{
		++m_writes;
		if(isPeripheral(_addr))
			return peripheralWrite(_addr, 2, _val);
		if(auto* const r = find(_addr, 2))
		{
			const auto o = _addr - r->base;
			r->data[o]     = static_cast<uint8_t>(_val >> 8);
			r->data[o + 1] = static_cast<uint8_t>(_val);
		}
		else
		{
			noteUnmapped('w', _addr, 2, _val);
			if(m_autoMap)
			{
				*autoByte(_addr, true)     = static_cast<uint8_t>(_val >> 8);
				*autoByte(_addr + 1, true) = static_cast<uint8_t>(_val);
			}
		}
	}

	uint16_t Machine::readImm16(const uint32_t _addr)
	{
		return read16(_addr);
	}

	uint32_t Machine::read32(const uint32_t _addr)
	{
		if(isPeripheral(_addr))
			return peripheralRead(_addr, 4);
		if(auto* const r = find(_addr, 4))
		{
			const auto o = _addr - r->base;
			return (static_cast<uint32_t>(r->data[o]) << 24) | (static_cast<uint32_t>(r->data[o + 1]) << 16)
				 | (static_cast<uint32_t>(r->data[o + 2]) << 8) | r->data[o + 3];
		}
		noteUnmapped('r', _addr, 4, 0xffffffff);
		if(m_autoMap)
			return (static_cast<uint32_t>(*autoByte(_addr, true)) << 24)
				 | (static_cast<uint32_t>(*autoByte(_addr + 1, true)) << 16)
				 | (static_cast<uint32_t>(*autoByte(_addr + 2, true)) << 8)
				 | *autoByte(_addr + 3, true);
		return 0xffffffff;
	}

	void Machine::write32(const uint32_t _addr, const uint32_t _val)
	{
		++m_writes;
		if(isPeripheral(_addr))
			return peripheralWrite(_addr, 4, _val);
		if(auto* const r = find(_addr, 4))
		{
			const auto o = _addr - r->base;
			r->data[o]     = static_cast<uint8_t>(_val >> 24);
			r->data[o + 1] = static_cast<uint8_t>(_val >> 16);
			r->data[o + 2] = static_cast<uint8_t>(_val >> 8);
			r->data[o + 3] = static_cast<uint8_t>(_val);
		}
		else
		{
			noteUnmapped('w', _addr, 4, _val);
			if(m_autoMap)
			{
				*autoByte(_addr, true)     = static_cast<uint8_t>(_val >> 24);
				*autoByte(_addr + 1, true) = static_cast<uint8_t>(_val >> 16);
				*autoByte(_addr + 2, true) = static_cast<uint8_t>(_val >> 8);
				*autoByte(_addr + 3, true) = static_cast<uint8_t>(_val);
			}
		}
	}

	uint32_t Machine::readIrqUserVector(const uint8_t _level)
	{
		const auto vec = Mc68k::readIrqUserVector(_level);
		if(m_ack && vec != 0xffffffffu)
			m_ack(static_cast<uint8_t>(vec), _level);
		return vec;
	}

	uint32_t Machine::peek32(const uint32_t _addr)
	{
		return read32(_addr);
	}

	void Machine::poke32(const uint32_t _addr, const uint32_t _val)
	{
		write16(_addr, static_cast<uint16_t>(_val >> 16));
		write16(_addr + 2, static_cast<uint16_t>(_val));
	}

	uint32_t Machine::pc() const
	{
		return getPC();
	}

	uint32_t Machine::onIllegalInstruction(const uint32_t _opcode)
	{
		// FIRST the V4e layer: this Musashi is ColdFire V2 and the firmware is
		// V4e, so most of what lands here is not illegal at all, merely absent
		// (v4e.cpp). A nonzero return tells Musashi to take no exception.
		if(v4e::execute(*this, _opcode) == v4e::Result::Handled)
		{
			++m_v4e;
			return 1;
		}

		// Genuinely unknown: report the opcode and the instruction's OWN
		// address -- REG_PPC, not the PC, which Musashi has already advanced
		// past the opcode word -- and stop. Letting the exception run would
		// send the boot somewhere meaningless and hide the cause.
		const auto at = m68k_get_reg(getCpuState(), M68K_REG_PPC);
		char buf[256] = {};
		disassemble(at, buf);
		char msg[512];
		std::snprintf(msg, sizeof msg,
			"unimplemented opcode %04x at %06x after %llu instructions (%s)",
			_opcode & 0xffff, at, static_cast<unsigned long long>(m_instructions), buf);
		m_why = msg;
		m_illegal = true;
		return 0;
	}

	// Route A's `try_auto_poke`, instruction for instruction. Scan 48 bytes
	// around the loop for `move.w (abs).w,d0` (3038) or `move.w (abs).l,d0`
	// (3039), then within the next 20 bytes for `cmpi.l #imm,d0` (0c80) or
	// `cmpi.w #imm,d0` (0c40); write the immediate to the flag as a WORD.
	bool Machine::tryAutoPoke(const uint32_t _pcInLoop)
	{
		const uint32_t lo = _pcInLoop - 16;
		uint8_t blk[48];
		for(uint32_t i = 0; i < sizeof blk; ++i)
			blk[i] = read8(lo + i);

		const auto be16 = [&](const uint32_t _i)
		{
			return static_cast<uint32_t>((blk[_i] << 8) | blk[_i + 1]);
		};
		const auto be32 = [&](const uint32_t _i)
		{
			return (be16(_i) << 16) | be16(_i + 2);
		};

		for(uint32_t i = 0; i + 6 < sizeof blk; i += 2)
		{
			uint32_t addr, k;
			if(be16(i) == 0x3038)						// (abs).w -- sign-extended
			{
				addr = static_cast<uint32_t>(static_cast<int32_t>(static_cast<int16_t>(be16(i + 2))));
				k = i + 4;
			}
			else if(be16(i) == 0x3039)					// (abs).l
			{
				addr = be32(i + 2);
				k = i + 6;
			}
			else
				continue;

			bool found = false;
			uint32_t imm = 0;
			for(uint32_t j = k; j < std::min<uint32_t>(i + 20, sizeof blk - 2); j += 2)
			{
				if(be16(j) == 0x0c80) { imm = be32(j + 2); found = true; break; }	// cmpi.l
				if(be16(j) == 0x0c40) { imm = be16(j + 2); found = true; break; }	// cmpi.w
			}
			if(!found)
				continue;

			write16(addr, static_cast<uint16_t>(imm));
			m_autoPokes.push_back({lo + i, addr, imm});
			return true;
		}
		return false;
	}

	Machine::Stop Machine::run(const uint64_t _maxInstructions)
	{
		for(m_instructions = 0; m_instructions < _maxInstructions; ++m_instructions)
		{
			const auto p = pc();
			const auto op = read16(p);

			// THE EMAC IS A-LINE, and Musashi routes 0xAxxx to the A-line
			// EXCEPTION, not to the illegal-instruction callback the V4e layer
			// hooks (`m68ki_exception_1010`, no callback of its own). So the
			// EMAC is dispatched here instead, from the fetch this loop already
			// does for the handoff check -- which keeps the vendored Musashi
			// unpatched and costs nothing extra.
			//
			// ⚠️ The V4e layer expects the PC PAST the opcode word, the way
			// Musashi leaves it on the illegal path, so advance it first.
			if((op & 0xf000) == 0xa000)
			{
				setPC(p + 2);
				if(v4e::execute(*this, op) == v4e::Result::Handled)
				{
					++m_v4e;
					continue;
				}
				setPC(p);				// not ours: let Musashi take its exception
			}

			if(op == g_trap0)
			{
				char msg[128];
				std::snprintf(msg, sizeof msg, "reached the RTOS handoff (trap #0) at pc %06x", p);
				m_why = msg;
				return Stop::Handoff;
			}
			if(m_profileEvery && (m_instructions % m_profileEvery) == 0)
				++m_profile[p];
			if(m_step)
				m_step(*this, p);
			exec();
			if(m_illegal)
				return Stop::Illegal;

			// The stall check, once per burst.
			if((m_instructions % g_burst) == g_burst - 1)
			{
				m_window.push_back(pc());
				m_windowWrites.push_back(m_writes);
				if(m_window.size() > g_stallBursts)
				{
					m_window.erase(m_window.begin());
					m_windowWrites.erase(m_windowWrites.begin());
				}
				if(m_window.size() == g_stallBursts)
				{
					const auto lo = *std::min_element(m_window.begin(), m_window.end());
					const auto hi = *std::max_element(m_window.begin(), m_window.end());
					if(hi - lo <= 64)
					{
						// A memset makes progress; a poll does not.
						if(m_windowWrites.back() - m_windowWrites.front() > 2000)
							m_window.clear(), m_windowWrites.clear();
						else if(tryAutoPoke(pc()))
							m_window.clear(), m_windowWrites.clear();
						else
						{
							char msg[160];
							std::snprintf(msg, sizeof msg,
								"unrecognised spin at %06x after %llu instructions",
								pc(), static_cast<unsigned long long>(m_instructions));
							m_why = msg;
							return Stop::Fault;
						}
					}
				}
			}
		}
		m_why = "instruction budget exhausted";
		return Stop::Budget;
	}
}
