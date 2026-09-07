#include "card.h"

#include <algorithm>
#include <cstdio>

namespace ot
{
	AtaCard::AtaCard(std::vector<uint8_t> _image)
		: m_img(std::move(_image))
	{
		m_nsect = static_cast<uint32_t>(m_img.size() / g_sector);
	}

	std::vector<uint16_t> AtaCard::identifyWords(const uint32_t _totalSectors)
	{
		std::vector<uint16_t> w(256, 0);
		constexpr uint16_t cyl = 1024, heads = 16, spt = 63;
		w[0] = 0x848a;								// CF signature
		w[1] = cyl; w[3] = heads; w[6] = spt;
		w[7] = static_cast<uint16_t>(_totalSectors >> 16);
		w[8] = static_cast<uint16_t>(_totalSectors);
		const auto str = [&w](const size_t _idx, const size_t _n, const char* _text)
		{
			std::string b(_text);
			b.resize(_n * 2, ' ');
			for(size_t i = 0; i < _n; ++i)
				w[_idx + i] = static_cast<uint16_t>((static_cast<uint8_t>(b[2 * i]) << 8)
					| static_cast<uint8_t>(b[2 * i + 1]));
		};
		str(10, 10, "OCTABAM0001");
		str(23, 4, "1.0");
		str(27, 20, "OCTABAM EMULATED CF");
		w[47] = 0x8001;
		w[49] = 0x0200;		// LBA supported, NO DMA (bit 8 clear)
		w[51] = 0x0200;		// PIO mode 2
		w[53] = 0x0000;		// words 54-58 / 64-70 not valid -> the PIO path
		w[54] = cyl; w[55] = heads; w[56] = spt;
		w[57] = static_cast<uint16_t>(_totalSectors);
		w[58] = static_cast<uint16_t>(_totalSectors >> 16);
		w[60] = static_cast<uint16_t>(_totalSectors);
		w[61] = static_cast<uint16_t>(_totalSectors >> 16);
		return w;
	}

	uint32_t AtaCard::lba() const
	{
		return m_lba0 | (m_lba1 << 8) | (m_lba2 << 16) | ((m_dev & 0x0f) << 24);
	}

	// ⚠️ A COUNT OF ZERO MEANS 256, which is the ATA rule -- but only in the
	// task file. The FIRMWARE's own count byte means SECTORS REMAINING, where
	// zero means none: reading that one as 256 wiped a whole card (5 Sep 2026).
	uint32_t AtaCard::count() const
	{
		return m_count ? m_count : 256;
	}

	uint32_t AtaCard::read(const uint32_t _off, uint32_t)
	{
		if(_off == R_DATA)
		{
			if(m_dpos + 1 < m_data.size())
			{
				const uint32_t v = (m_data[m_dpos] << 8) | m_data[m_dpos + 1];
				m_dpos += 2;
				if(m_dpos >= m_data.size())
					m_status &= ~ST_DRQ;
				return v;
			}
			return 0;
		}
		if(_off == R_CMD || _off == R_ALT)
			return m_status;
		if(_off == R_FEAT)
			return m_error;
		switch(_off)
		{
		case R_COUNT: return m_count;
		case R_LBA0:  return m_lba0;
		case R_LBA1:  return m_lba1;
		case R_LBA2:  return m_lba2;
		case R_DEV:   return m_dev;
		default:      return 0;
		}
	}

	void AtaCard::write(const uint32_t _off, uint32_t, const uint32_t _val)
	{
		if(_off == R_DATA)
		{
			if(m_wremaining)
			{
				m_wbuf.push_back(static_cast<uint8_t>(_val >> 8));
				m_wbuf.push_back(static_cast<uint8_t>(_val));
				if(m_wbuf.size() >= g_sector)
				{
					commitSector(m_wbuf.data());
					m_wbuf.erase(m_wbuf.begin(), m_wbuf.begin() + g_sector);
				}
			}
			return;
		}
		if(_off == R_CMD)
		{
			command(static_cast<uint8_t>(_val));
			return;
		}
		switch(_off)
		{
		case R_FEAT:  m_feat  = _val & 0xff; break;
		case R_COUNT: m_count = _val & 0xff; break;
		case R_LBA0:  m_lba0  = _val & 0xff; break;
		case R_LBA1:  m_lba1  = _val & 0xff; break;
		case R_LBA2:  m_lba2  = _val & 0xff; break;
		case R_DEV:   m_dev   = _val & 0xff; break;
		default: break;
		}
	}

	void AtaCard::command(const uint8_t _c)
	{
		m_cmd = _c;
		m_error = 0;
		m_status = ST_DRDY | ST_DSC;
		char name[32];
		switch(_c)
		{
		case 0xec:					// IDENTIFY DEVICE
		{
			const auto w = identifyWords(m_nsect);
			m_data.assign(w.size() * 2, 0);
			// LITTLE-endian in the buffer, as route A packs it ("<256H"):
			// the firmware byte-swaps what it reads off the bus.
			for(size_t i = 0; i < w.size(); ++i)
			{
				m_data[2 * i]     = static_cast<uint8_t>(w[i]);
				m_data[2 * i + 1] = static_cast<uint8_t>(w[i] >> 8);
			}
			m_dpos = 0;
			m_status |= ST_DRQ;
			m_log.push_back({"IDENTIFY", 0, 0});
			return;
		}
		case 0x20:					// READ SECTORS
		{
			const auto l = lba(), n = count();
			const size_t lo = static_cast<size_t>(l) * g_sector;
			const size_t hi = lo + static_cast<size_t>(n) * g_sector;
			m_data.assign(m_img.begin() + std::min(lo, m_img.size()),
				m_img.begin() + std::min(hi, m_img.size()));
			m_dpos = 0;
			m_status |= ST_DRQ;
			m_reads += n;
			m_log.push_back({"READ", l, n});
			return;
		}
		case 0x30:					// WRITE SECTORS
		{
			const auto l = lba(), n = count();
			m_wbuf.clear();
			m_wlba = l;
			m_wremaining = n;
			m_status |= ST_DRQ;
			m_log.push_back({"WRITE", l, n});
			return;
		}
		case 0x87:					// CFA TRANSLATE SECTOR
			m_data.assign(g_sector, 0);
			m_dpos = 0;
			m_status |= ST_DRQ;
			m_log.push_back({"CFA-TRANSLATE", lba(), 0});
			return;
		case 0xe5:					// CHECK POWER MODE
			m_count = 0xff;
			m_log.push_back({"CHECK-POWER", 0, 0});
			return;
		case 0xe0: case 0xe1: case 0xe2: case 0xe3: case 0xe6:
		case 0xef: case 0xc0: case 0x03: case 0x91: case 0xc6:
			std::snprintf(name, sizeof name, "CMD-%02x", _c);
			m_log.push_back({name, 0, 0});
			return;
		default:
			m_error = 0x04;			// ABRT
			m_status |= 0x01;
			std::snprintf(name, sizeof name, "UNSUPPORTED-%02x", _c);
			m_log.push_back({name, 0, 0});
			return;
		}
	}

	// One sector of a WRITE, in order: the handler streams the first sector
	// through the data register itself (0x40014c48 after the command), the
	// interrupt handler streams the rest.
	void AtaCard::commitSector(const uint8_t* _data)
	{
		const size_t off = static_cast<size_t>(m_wlba) * g_sector;
		if(m_wlba < m_nsect)
			std::copy(_data, _data + g_sector, m_img.begin() + off);
		++m_writes;
		++m_wlba;
		if(--m_wremaining <= 0)
		{
			m_wremaining = 0;
			m_status &= ~ST_DRQ;
		}
	}
}
