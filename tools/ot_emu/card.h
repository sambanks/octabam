// The CompactFlash card behind the FlexBus task-file window at 0x90000000.
//
// Translated from `tools/emu_card.py`'s `AtaCard`, which is the specification.
// ⚠️ THE FAT16 IMAGE BUILDER IS DELIBERATELY NOT HERE. Route A builds the card
// image from a directory tree in Python (`emu_card.build_image`), and that is
// a BUILD-TIME tool producing bytes, not machine behaviour: this port reads
// the same image file, so the two emulators are guaranteed to be looking at
// identical media and any difference between them is in the machine. Build one
// with `emu_rtos.stage_project(...)`.
//
// The register map is docs/ARCHITECTURE.md §5: data 0xa0, features/error 0xa4,
// count 0xa8, LBA 0xac/b0/b4, device 0xb8, command/status 0xbc, alt status
// 0xd8. IDENTIFY advertises PIO only (word 49 bit 8 clear, word 53 zero), so
// the driver's variant detection at 0x40015e28 never programs the on-chip DMA
// channel -- which is why this model never has to.
#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace ot
{
	class AtaCard
	{
	public:
		static constexpr uint32_t g_base = 0x90000000, g_window = 0x1000;
		static constexpr uint32_t g_sector = 512;
		enum : uint32_t
		{
			R_DATA = 0xa0, R_FEAT = 0xa4, R_COUNT = 0xa8, R_LBA0 = 0xac,
			R_LBA1 = 0xb0, R_LBA2 = 0xb4, R_DEV = 0xb8, R_CMD = 0xbc, R_ALT = 0xd8
		};
		enum : uint32_t { ST_DRDY = 0x40, ST_DSC = 0x10, ST_DRQ = 0x08 };

		explicit AtaCard(std::vector<uint8_t> _image);

		uint32_t read(uint32_t _off, uint32_t _size);
		void write(uint32_t _off, uint32_t _size, uint32_t _val);

		// What the run did, in the shape route A's log has it: the gate for
		// the project load is a COUNT of commands and sectors.
		struct Entry { std::string what; uint32_t lba = 0, count = 0; };
		const std::vector<Entry>& log() const { return m_log; }
		uint64_t sectorsRead() const { return m_reads; }
		uint64_t sectorsWritten() const { return m_writes; }

		// The INTRQ rules live in `Rtos::attachCard` and need these three.
		uint32_t status() const { return m_status; }
		size_t dataPos() const { return m_dpos; }
		size_t dataSize() const { return m_data.size(); }

		uint32_t totalSectors() const { return m_nsect; }
		static std::vector<uint16_t> identifyWords(uint32_t _totalSectors);

	private:
		uint32_t lba() const;
		uint32_t count() const;
		void command(uint8_t _c);
		void commitSector(const uint8_t* _data);

		std::vector<uint8_t> m_img;
		uint32_t m_nsect = 0;
		uint32_t m_feat = 0, m_count = 0, m_lba0 = 0, m_lba1 = 0, m_lba2 = 0, m_dev = 0xe0;
		uint32_t m_status = ST_DRDY | ST_DSC;
		uint32_t m_error = 0;
		std::vector<uint8_t> m_data;
		size_t m_dpos = 0;
		std::vector<uint8_t> m_wbuf;
		uint32_t m_wlba = 0;
		int64_t m_wremaining = 0;
		uint8_t m_cmd = 0;
		std::vector<Entry> m_log;
		uint64_t m_reads = 0, m_writes = 0;
	};
}
