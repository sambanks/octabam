// A WAV file, the minimum of it: N channels of 24-bit PCM out, 16- or 24-bit
// PCM in. Samples are 24-bit two's complement in an int32 -- the DSP's own
// word -- so a slot of an ESAI frame goes to disk untouched (O9).
#pragma once

#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

namespace ot
{
	inline bool writeWav24(const std::string& _path, const std::vector<int32_t>& _interleaved, const uint32_t _channels, const uint32_t _rate = 44100)
	{
		if(!_channels)
			return false;
		std::FILE* f = std::fopen(_path.c_str(), "wb");
		if(!f)
			return false;
		const uint32_t frames = static_cast<uint32_t>(_interleaved.size() / _channels);
		const uint32_t dataBytes = frames * _channels * 3;
		auto put16 = [f](const uint32_t _v){ const uint8_t b[2] = {uint8_t(_v), uint8_t(_v >> 8)}; std::fwrite(b, 1, 2, f); };
		auto put32 = [f](const uint32_t _v){ const uint8_t b[4] = {uint8_t(_v), uint8_t(_v >> 8), uint8_t(_v >> 16), uint8_t(_v >> 24)}; std::fwrite(b, 1, 4, f); };
		std::fwrite("RIFF", 1, 4, f); put32(36 + dataBytes); std::fwrite("WAVE", 1, 4, f);
		std::fwrite("fmt ", 1, 4, f); put32(16); put16(1); put16(_channels); put32(_rate);
		put32(_rate * _channels * 3); put16(_channels * 3); put16(24);
		std::fwrite("data", 1, 4, f); put32(dataBytes);
		std::vector<uint8_t> buf;
		buf.reserve(dataBytes);
		for(uint32_t i = 0; i < frames * _channels; ++i)
		{
			const uint32_t v = static_cast<uint32_t>(_interleaved[i]) & 0xffffff;
			buf.push_back(uint8_t(v)); buf.push_back(uint8_t(v >> 8)); buf.push_back(uint8_t(v >> 16));
		}
		std::fwrite(buf.data(), 1, buf.size(), f);
		std::fclose(f);
		return true;
	}

	// Returns false if the file is not PCM 16/24-bit. `_out` is interleaved,
	// every sample sign-extended into an int32 holding a 24-bit word (a 16-bit
	// file is shifted up eight).
	inline bool readWavPcm(const std::string& _path, std::vector<int32_t>& _out, uint32_t& _channels, uint32_t& _rate)
	{
		std::FILE* f = std::fopen(_path.c_str(), "rb");
		if(!f)
			return false;
		std::vector<uint8_t> d;
		{
			uint8_t buf[65536];
			size_t n;
			while((n = std::fread(buf, 1, sizeof buf, f)) > 0)
				d.insert(d.end(), buf, buf + n);
		}
		std::fclose(f);
		auto u16 = [&d](const size_t _o){ return uint32_t(d[_o]) | (uint32_t(d[_o + 1]) << 8); };
		auto u32 = [&d](const size_t _o){ return uint32_t(d[_o]) | (uint32_t(d[_o + 1]) << 8) | (uint32_t(d[_o + 2]) << 16) | (uint32_t(d[_o + 3]) << 24); };
		if(d.size() < 12 || std::string(d.begin(), d.begin() + 4) != "RIFF" || std::string(d.begin() + 8, d.begin() + 12) != "WAVE")
			return false;
		uint32_t bits = 0, fmt = 0;
		_channels = 0; _rate = 0;
		size_t o = 12;
		while(o + 8 <= d.size())
		{
			const std::string id(d.begin() + o, d.begin() + o + 4);
			const uint32_t len = u32(o + 4);
			const size_t body = o + 8;
			if(id == "fmt " && len >= 16)
			{
				fmt = u16(body); _channels = u16(body + 2); _rate = u32(body + 4); bits = u16(body + 14);
			}
			else if(id == "data")
			{
				if((fmt != 1 && fmt != 0xfffe) || (bits != 16 && bits != 24) || !_channels)
					return false;
				const uint32_t bytes = bits / 8;
				const size_t n = std::min<size_t>(len, d.size() - body) / bytes;
				_out.clear();
				_out.reserve(n);
				for(size_t i = 0; i < n; ++i)
				{
					const size_t p = body + i * bytes;
					int32_t v = bits == 16 ? int32_t(int16_t(u16(p))) << 8
						: int32_t((uint32_t(d[p]) | (uint32_t(d[p + 1]) << 8) | (uint32_t(d[p + 2]) << 16)) << 8) >> 8;
					_out.push_back(v);
				}
				return true;
			}
			o = body + len + (len & 1);
		}
		return false;
	}
}
