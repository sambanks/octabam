#include "rtos.h"

#include <utility>

#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <fstream>

namespace ot
{
	const TaskSpec g_expectedTasks[10] = {
		{0x46c7fb0c, 0x40005540, 6, 0x46c7ea20, 0x1000, g_mainTcb},		// voice / DSP mailbox
		{0x460fab80, 0x40091d18, 2, 0x460fabd4, 0x2000, g_mainTcb},		// p2a
		{0x460ffd44, 0x400921c4, 2, 0x460fdd44, 0x2000, g_mainTcb},		// p2b
		{0x460e0e38, 0x4009203c, 2, 0x460dee38, 0x2000, g_mainTcb},		// p2c
		{0x460ddde4, 0x4008445c, 1, 0x460d9de4, 0x4000, g_mainTcb},		// engine
		{0x46105508, 0x40098a5c, 1, 0x4610555c, 0x2000, g_mainTcb},		// p1b
		{0x46c7bed8, 0x40061a94, 1, 0x460d6de4, 0x2000, g_mainTcb},		// sys: creates the three below
		{0x460bcc2c, 0x4001ee30, 5, 0x460bc42c, 0x0800, 0x46c7bed8},	// storage
		{0x460d4f80, 0x4005593c, 4, 0x460d4780, 0x0800, 0x46c7bed8},	// keyrepeat (NOT ui -- M6d)
		{0x460d59d4, 0x40056c40, 3, 0x460d51d4, 0x0800, 0x46c7bed8},	// ui: the real UI_QUEUE receiver
	};

	const char* taskName(const uint32_t _tcb)
	{
		switch(_tcb)
		{
		case 0x46c7fb0c: return "voice";
		case 0x460bcc2c: return "storage";
		case 0x460d4f80: return "keyrepeat";
		case 0x460fab80: return "p2a";
		case 0x460ffd44: return "p2b";
		case 0x460e0e38: return "p2c";
		case 0x460ddde4: return "engine";
		case 0x46105508: return "p1b";
		case 0x46c7bed8: return "sys";
		case 0x460d59d4: return "ui";
		case g_mainTcb:  return "main";
		case g_bootTcb:  return "boot";
		default:         return "?";
		}
	}

	Rtos::Rtos(Machine& _m, const double _ips, const double _pitClockHz, const bool _frame)
		: m_machine(_m)
		, m_ips(_ips)
		, m_pit0("PIT0", _pitClockHz)
		, m_pit1("PIT1", _pitClockHz)
		, m_intc0("INTC0", 64)
		, m_intc1("INTC1", 128)
	{
		if(const char* const e = std::getenv("OT_FENCE_TRACE"); e && std::atoi(e) != 0)
			m_fenceTrace = true;
		// INTC1 source 43 = PIT0 (vector 171, the scheduler); 44 = PIT1 (the
		// storage layer's delay timer). INTC0 source 1 is the DSP frame clock
		// and 27/28 the serial blocks -- both are later milestones, and their
		// lines are simply absent here rather than stubbed true, which is what
		// route A's own defaults amount to (`frame=False`, and the UARTs'
		// transmit interrupt cleared at seeding with nothing queued to
		// receive).
		// INTC0 source 1 = the DSP frame clock (vector 0x41), sources 8..23
		// are eDMA channels 0..15 (MCF5445x; 8, 9 and 15 are the ones the
		// frame exchange raises), 26..28 the three UARTs. INTC1: 43/44 the
		// PITs.
		m_frame = _frame;
		m_intc0.setWires([this]
		{
			uint64_t a = static_cast<uint64_t>(m_edma.irqMask()) << 8;
			if(m_frame && m_framePending) a |= 1ull << 1;
			if(m_uart60.irq()) a |= 1ull << 26;
			if(m_uart64.irq()) a |= 1ull << 27;
			if(m_uart68.irq()) a |= 1ull << 28;
			// INTC0 sources 32..35 = DTIM0..3. Source 32 is also the forced
			// sequencer tick (INTFRC); DTIM0 never asserts it -- the firmware
			// runs DTIM0 without ORRI (DTMR 7). DTIM1 is the UI tick and the
			// LED countdown's clock, DTIM2 the soft-timer dispatcher's (periph.h).
			for(uint32_t n = 0; n < 4; ++n)
				if(m_dtim[n].irq()) a |= 1ull << (32 + n);
			return a;
		});
		m_intc1.setWires([this]
		{
			uint64_t a = 0;
			if(m_pit0.irq()) a |= 1ull << 43;
			if(m_pit1.irq()) a |= 1ull << 44;
			if(m_usb && m_usb->irq()) a |= 1ull << 47;	// the USB device controller (vector 0xaf, the firmware installs it at level 4)
			return a;
		});
	}

	// O15a: the burst knobs, read once. Diagnosis only -- the shipped default
	// is bursts of 4096 through stepFast; OT_BURST=0 is the pre-O15a loop.
	int Rtos::burstQuantum()
	{
		static const int q = []
		{
			const char* const e = std::getenv("OT_BURST");
			return e ? std::atoi(e) : 4096;
		}();
		return q;
	}

	bool Rtos::burstStepFast()
	{
		static const bool f = []
		{
			const char* const e = std::getenv("OT_STEPFAST");
			return !e || std::atoi(e) != 0;
		}();
		return f;
	}

	// O16c: OT_DSP_SYNC=0 drops the run loop's sync of a lazy pair at burst
	// ends and exact steps, leaving only the host-port touch points and the
	// `--dsp-lazy N` backlog cap -- the frame edge is then seen up to N DSP
	// instructions late instead of one burst. A measurement knob (how much
	// the per-burst sync costs), not a mode: nothing prints, nothing else moves.
	bool Rtos::dspSyncAtTick()
	{
		static const bool s = []
		{
			const char* const e = std::getenv("OT_DSP_SYNC");
			return !e || std::atoi(e) != 0;
		}();
		return s;
	}

	Rtos::~Rtos()
	{
		// stderr only, opt-in: stdout is diffed byte for byte by the oracles.
		if(memStatOn())
			std::fprintf(stderr, "memstat %.0f ms (end): %s\n", ms(), memStat().c_str());
		if(const char* const e = std::getenv("OT_BURST_STATS"); e && std::atoi(e) != 0)
		{
			const auto& s = m_burstStats;
			std::fprintf(stderr, "burst stats: bursts=%llu burstInstr=%llu exactInstr=%llu "
				"endPeriph=%llu endWake=%llu endHorizon=%llu endSpin=%llu endGate=%llu endPc=%llu idleSkips=%llu instructions=%llu quantum=%d stepfast=%d"
				" exactWake=%llu exactHorizon frame=%llu ata=%llu pit=%llu dtim=%llu edma=%llu\n",
				static_cast<unsigned long long>(s.bursts), static_cast<unsigned long long>(s.burstInstr),
				static_cast<unsigned long long>(s.exactInstr), static_cast<unsigned long long>(s.endPeriph),
				static_cast<unsigned long long>(s.endWake), static_cast<unsigned long long>(s.endHorizon),
				static_cast<unsigned long long>(s.endSpin), static_cast<unsigned long long>(s.endGate),
				static_cast<unsigned long long>(s.endPc), static_cast<unsigned long long>(m_idleSkips),
				static_cast<unsigned long long>(m_machine.instructions()), burstQuantum(), burstStepFast() ? 1 : 0,
				static_cast<unsigned long long>(s.exactWake), static_cast<unsigned long long>(s.exactBySrc[0]), static_cast<unsigned long long>(s.exactBySrc[1]),
				static_cast<unsigned long long>(s.exactBySrc[2]), static_cast<unsigned long long>(s.exactBySrc[3]), static_cast<unsigned long long>(s.exactBySrc[4]));
		}
	}

	uint32_t Rtos::curTcb()
	{
		return m_machine.peek32(g_curTcb);
	}

	bool Rtos::peripheralRead(const uint32_t _addr, const uint8_t _size, uint32_t& _out)
	{
		if(_addr >= g_intc0 && _addr < g_intc0 + 0x100) { _out = m_intc0.read(_addr - g_intc0, _size); return true; }
		if(_addr >= g_intc1 && _addr < g_intc1 + 0x100) { _out = m_intc1.read(_addr - g_intc1, _size); return true; }
		if(_addr >= g_pit0 && _addr < g_pit0 + 0x10)    { _out = m_pit0.read(_addr - g_pit0, _size, m_sample); return true; }
		if(_addr >= g_pit1 && _addr < g_pit1 + 0x10)    { _out = m_pit1.read(_addr - g_pit1, _size, m_sample); return true; }
		if(_addr >= g_dtim && _addr < g_dtim + 4 * 0x4000 && ((_addr - g_dtim) & 0x3fff) < 0x10)
		{
			_out = m_dtim[(_addr - g_dtim) >> 14].read((_addr - g_dtim) & 0xf, _size, m_sample);
			return true;
		}
		if(_addr >= g_dspi && _addr < g_dspi + 0x100)   { _out = m_dspi.read(_addr - g_dspi, _size); return true; }
		if(_addr >= Edma::g_base && _addr < Edma::g_tcd + 16 * 32)
		{
			// O15a: inside a burst tickTimers() has not run since the burst
			// began, so the eDMA's `now` and boundary are refreshed HERE, on
			// every access, read or write. The value is the one the exact path
			// had: tickTimers() set them from m_sample after the previous
			// instruction, and m_sample has not moved since (the increment
			// follows the instruction). A read needs neither; it is done on
			// both so the rule has no exception to forget.
			m_edma.setBoundary(m_nextFrame);
			m_edma.setNow(m_sample);
			_out = m_edma.read(_addr, _size);
			return true;
		}
		if(m_usb && _addr >= UsbDevice::g_base && _addr < UsbDevice::g_base + UsbDevice::g_size) { _out = m_usb->read(_addr - UsbDevice::g_base, _size); return true; }
		if(m_card && _addr >= AtaCard::g_base && _addr < AtaCard::g_base + AtaCard::g_window)
		{
			const auto off = _addr - AtaCard::g_base;
			_out = m_card->read(off, _size);
			if(m_ataTraceOn && m_ataTrace.size() < 200000)
			{
				char line[64];
				std::snprintf(line, sizeof line, "R %02x %u %04x %08x", off, _size, _out & 0xffff, m_machine.pc());
				m_ataTrace.emplace_back(line);
			}
			// INTRQ is cleared by a read of the STATUS register (not the
			// alternate status), and raised again when the next sector is
			// ready: one interrupt per sector.
			if(off == AtaCard::R_CMD)
				m_ataIrq = false;
			else if(off == AtaCard::R_DATA && m_card->dataPos() % AtaCard::g_sector == 0
				&& m_card->dataPos() < m_card->dataSize())
				m_ataIrqDue = m_sample + m_ataLatency;
			return true;
		}
		for(auto* u : {&m_uart60, &m_uart64, &m_uart68})
			if(_addr >= u->base() && _addr < u->base() + 0x20)
			{
				_out = u->read(_addr - u->base(), _size);
				return true;
			}
		return false;
	}

	void Rtos::peripheralWrite(const uint32_t _addr, const uint8_t _size, const uint32_t _val, const bool _replay)
	{
		if(_addr >= g_intc0 && _addr < g_intc0 + 0x100)
		{
			// O17b: the frame handler masks its own source (INTC0 source 1)
			// for the whole host-port exchange and unmasks it at the end --
			// that unmask is "frame handled", the protocol's own end-of-frame
			// mark, and the real-time DSP mode's fence opens on it.
			const bool was = m_intc0.masked(1);
			m_intc0.write(_addr - g_intc0, _size, _val);
			const bool now = m_intc0.masked(1);
			if(was != now)
			{
				if(m_fenceTrace)
					std::fprintf(stderr, "ftrace %.3f cf src1 %s pc=%08x\n", m_sample, now ? "MASK" : "UNMASK", m_machine.pc());
				if(auto* co = m_machine.coprocessor())
				{
					if(now)
						co->frameHandling();
					else
						co->frameHandled();
				}
			}
		}
		else if(_addr >= g_intc1 && _addr < g_intc1 + 0x100) m_intc1.write(_addr - g_intc1, _size, _val);
		else if(_addr >= g_pit0 && _addr < g_pit0 + 0x10) m_pit0.write(_addr - g_pit0, _size, _val, m_sample);
		else if(_addr >= g_pit1 && _addr < g_pit1 + 0x10) m_pit1.write(_addr - g_pit1, _size, _val, m_sample);
		else if(_addr >= g_dtim && _addr < g_dtim + 4 * 0x4000 && ((_addr - g_dtim) & 0x3fff) < 0x10)
			m_dtim[(_addr - g_dtim) >> 14].write((_addr - g_dtim) & 0xf, _size, _val, m_sample);
		else if(_addr >= g_dspi && _addr < g_dspi + 0x100) m_dspi.write(_addr - g_dspi, _size, _val, _replay);
		else if(_addr >= Edma::g_base && _addr < Edma::g_tcd + 16 * 32)
		{
			// ⚠️ THE WRITE SIDE IS THE ONE THAT MATTERS, and the prototype
			// refreshed only the read side (12 Sep 2026, the architect's
			// bisect): a CSR.START kick books a bus-paced completion from
			// `m_now` (Edma::start), and with `m_now` stale by up to a burst the
			// completion came early, the DSP took its block early, and the
			// `--dsp` pipe PCM drifted by +-1 LSB in 280 samples. Same rule as
			// the read above; see there for why the value is the exact one.
			m_edma.setBoundary(m_nextFrame);
			m_edma.setNow(m_sample);
			m_edma.write(_addr, _size, _val, _replay);
		}
		else if(m_usb && _addr >= UsbDevice::g_base && _addr < UsbDevice::g_base + UsbDevice::g_size) m_usb->write(_addr - UsbDevice::g_base, _size, _val, _replay);
		else if(m_card && _addr >= AtaCard::g_base && _addr < AtaCard::g_base + AtaCard::g_window)
		{
			const auto off = _addr - AtaCard::g_base;
			if(m_ataTraceOn && m_ataTrace.size() < 200000)
			{
				char line[64];
				std::snprintf(line, sizeof line, "W %02x %u %04x %08x", off, _size, _val & 0xffff, m_machine.pc());
				m_ataTrace.emplace_back(line);
			}
			const auto before = m_card->sectorsWritten();
			m_card->write(off, _size, _val);
			// A command asserts INTRQ at once -- except a WRITE, which
			// asserts only once the drive has absorbed a sector.
			if(off == AtaCard::R_CMD)
			{
				// Who issued it. The command register write is the moment the
				// command exists, and `currentPc()` is the instruction making
				// it (not the fetch pointer) -- see Machine::currentPc.
				m_card->stampLastCommand(m_machine.currentPc(), curTcb());
				if((_val & 0xff) != 0x30)
					m_ataIrqDue = m_sample + m_ataLatency;
				if(!m_pcRing.empty() && !m_pcRingArmed)
					m_pcRingArmed = true;
			}
			else if(off == AtaCard::R_DATA && m_card->sectorsWritten() > before)
				m_ataIrqDue = m_sample + m_ataLatency;
		}
		else
		{
			for(auto* u : {&m_uart60, &m_uart64, &m_uart68})
				if(_addr >= u->base() && _addr < u->base() + 0x20)
					u->write(_addr - u->base(), _size, _val, _replay);
		}
	}

	void Rtos::install()
	{
		// ✅ Check the vectors before trusting any of this: vector 32 (trap #0)
		// and vector 171 (PIT0) must both point at the one scheduler entry.
		// Route A raises here rather than run a machine whose kernel is not
		// where it thinks.
		const auto v32 = m_machine.peek32(g_vbr + 0x80);
		const auto v171 = m_machine.peek32(g_vbr + 4 * 171);
		if(v32 != g_sched || v171 != g_sched)
		{
			char msg[192];
			std::snprintf(msg, sizeof msg,
				"vector 32 -> %#x and vector 171 -> %#x; both should be the scheduler %#x",
				v32, v171, g_sched);
			m_why = msg;
			return;
		}

		// Two spans the BOOT does not map and main's init needs, added here
		// because route A adds them here (`install`), with its reasons:
		//
		//   * Main's init reads a magic word at 0x1ffffe (0x4003232c: equal to
		//     0xdcba means a test-mode flash) and the boot maps only the first
		//     64 KB. Zero = no magic. ⚠️ THE PORT WAS ANSWERING ALL-ONES HERE
		//     and route A answers zero -- both fail the 0xdcba test, so the
		//     behaviour matched by luck rather than by model, and a machine
		//     that never faults on unmapped memory gets no warning about that.
		//   * The settings reset (0x4001f298) clears up to 0x10100004, four
		//     bytes past the SRAM window -- a firmware off-by-four that
		//     hardware absorbs. ✅ Reproduced here: the port's own unmapped
		//     log shows exactly four byte-accesses at 0x10100000.
		for(const auto& [base, size] : {std::pair<uint32_t, uint32_t>{0x00010000, 0x001f0000},
			std::pair<uint32_t, uint32_t>{0x10100000, 0x1000}})
			m_machine.mapRegion(base, size);

		// SEED the models by replaying what the boot wrote into the all-ones
		// stub before they existed. Route A's rule, including its exclusion:
		//
		// ⚠️ An all-ones value is a READ-MODIFY-WRITE of the stub's own
		// all-ones reply (PIT0's `PCSR |= 9` arrives as 0xffff), not a value
		// the firmware chose -- skip it. Nothing in the boot writes all-ones
		// on purpose (7,886 writes on the stock image, measured 6 Sep 2026).
		for(const auto& w : m_machine.peripheralWrites())
		{
			const uint32_t mask = w.size >= 4 ? 0xffffffffu : (1u << (8 * w.size)) - 1;
			const uint32_t val = w.val & mask;
			if(val == mask)
				continue;
			peripheralWrite(w.addr, w.size, val, true);
		}
		m_seeded = m_machine.peripheralWrites().size();
		m_machine.endPeripheralWriteLog();		// O18: the record has no reader past this line
		if(m_quirks.clearTransmitInterrupt)
			for(auto* u : {&m_uart60, &m_uart64, &m_uart68})
				u->clearTransmitInterrupt();
		m_dtim[3].setBias(m_quirks.skipBootLogo ? g_bootLogoCounts : 0);

		installHostPortMover();

		m_machine.setPeripheralHandlers(
			[this](uint32_t a, uint8_t s, uint32_t& o) { return peripheralRead(a, s, o); },
			[this](uint32_t a, uint8_t s, uint32_t v) { peripheralWrite(a, s, v, false); });

		// An INTFRC write is a RESCHEDULE REQUEST and has to be seen inside
		// the instruction that made it. This loop steps one instruction at a
		// time and re-evaluates interrupts after every one, so the hook only
		// has to count them -- route A needed it to break its burst.
		// The frame latch is cleared when the CPU TAKES vector 0x41 (INTC0
		// base 64 + source 1), which is where route A clears it.
		m_machine.setAckHook([this](const uint8_t _vec, const uint8_t _level)
		{
			m_wake = true;		// O15a: the core consumed the injected vector; deliver() must re-offer or withdraw
			if(_vec == m_intc0.vectorBase() + 1)
			{
				m_framePending = false;
				++m_frameCount;
			}
			if(_vec >= m_intc0.vectorBase() && _vec < m_intc0.vectorBase() + 64)
			{
				if(m_fenceTrace)
					std::fprintf(stderr, "ftrace %.3f cf ack vec=%02x src=%u\n", m_sample, _vec, _vec - m_intc0.vectorBase());
				if(auto* co = m_machine.coprocessor(); co && (_vec == m_intc0.vectorBase() + 1 || (_vec >= m_intc0.vectorBase() + 8 && _vec < m_intc0.vectorBase() + 24)))
					co->cpuNote('a', _vec);		// the frame and the eDMA channels only (the timers would flood the record)
			}
			if(m_card && _vec == m_intc1.vectorBase() + g_ataSource)
				++m_ataInterrupts;
			if(m_acks.size() < 100000)
				m_acks.push_back({m_sample, _vec, _level, curTcb(), m_machine.pc(),
					m_machine.peek32(g_vbr + 4u * _vec)});
		});

		m_intc0.setForceHook([this](uint64_t) { ++m_forces; });
		m_intc1.setForceHook([this](uint64_t) { ++m_forces; });
		m_installed = true;
		if(m_machine.read16(g_mainSpin - 6) == 0x4ef9)		// jmp abs.l: the park is detoured
		{
			m_spinLo = m_machine.peek32(g_mainSpin - 4);
			m_spinHi = m_spinLo + 0x80;
		}
	}

	// O8 step 4 -- THE DATA. Decoded from route A's tape (8 Sep 2026): every
	// block is a 32-bit eDMA stream at 0x2000001c, and the DSP's count word for
	// each is exactly half its byte count -- 672 words for 4 x 336 bytes, 64
	// for 128, 128 for 256, 512 for 1024, and the read-back chain ch1+ch6+ch7
	// of 512+256+256 bytes is the DSP's 512-word block. So one DSP word rides
	// each 16-BIT BUS CYCLE (a longword is two, high halfword first), which is
	// what the DspPair's lane model does with a halfword at +0x1c. The RAM
	// side is contiguous (SOFF/DOFF equal the burst size), the port side is a
	// fixed address, and a block is NBYTES x the minor-loop count.
	uint32_t Rtos::tcdWords(const uint32_t _ch) const
	{
		return static_cast<uint32_t>(m_edma.tcdField(_ch, 8, 4) * m_edma.minorLoops(_ch) / 4);	// bytes -> DSP words (one per 16-bit cycle pair... a 32-bit write is two halfwords on TXM:TXL = one word)
	}

	void Rtos::copyMemToMem(const uint32_t _ch, const uint32_t _saddr, const uint32_t _daddr)
	{
		// The MCF5445x eDMA TCD (RM ch. 18): ATTR = SMOD[15:11] SSIZE[10:8]
		// DMOD[7:3] DSIZE[2:0], sizes 0..5 = 1/2/4/8/16/32 bytes; NBYTES per
		// minor loop; CITER minor loops (bit 15 = a link, count in bits 8-0);
		// SOFF/DOFF signed 16-bit strides per transfer. SLAST/DLAST_SGA (the
		// pointer adjustments after the major loop) and the TCD's running
		// SADDR/DADDR are not written back: the firmware reprograms both
		// addresses before every kick and never reads them.
		// ⚠️ O21 (13 Sep 2026): THE WORD AT +4 IS ATTR AND THE WORD AT +6 IS
		// SOFF (MCF5445x RM ch. 18, the TCD memory map: TCDn_ATTR 0x04,
		// TCDn_SOFF 0x06 -- the big-endian halves of the 32-bit word at +4),
		// and the firmware's own values say so: the delay routine writes
		// 0x0402 / 0x0404 there (SSIZE 4 = 16-byte bursts with a 32-bit or
		// 16-byte destination -- attribute words) and 0x0010 at +6 (the
		// 16-byte stride). O20 read them the other way round, so every
		// delay copy ran with SSIZE = DSIZE = 1 byte, DMOD = 2 (a 4-byte
		// destination window) and a source stride of 1026/1028: the taps
		// were 144 single bytes from every 1026th address folded into the
		// staging block's first longword, and the ring received four bytes
		// per frame -- measured 13 Sep 2026 on a track that sounds (T7): the
		// ring all zero at the write pointer, no repeat at 367 ms, while
		// the mix loop's ring-input stores were non-zero. The label swap
		// hid in plain sight because nothing else reads +4/+6 (the
		// host-port mover uses NBYTES/CITER/SADDR/DADDR only).
		const auto attr = m_edma.tcdField(_ch, 4, 2);
		const auto nbytes = m_edma.tcdField(_ch, 8, 4);
		const auto loops = m_edma.minorLoops(_ch);
		const auto soff = static_cast<int32_t>(static_cast<int16_t>(m_edma.tcdField(_ch, 6, 2)));
		const auto doff = static_cast<int32_t>(static_cast<int16_t>(m_edma.tcdField(_ch, 0x16, 2)));
		const uint32_t ssize = 1u << ((attr >> 8) & 7), dsize = 1u << (attr & 7);
		const uint32_t smod = (attr >> 11) & 0x1f, dmod = (attr >> 3) & 0x1f;
		if(!nbytes || !loops || nbytes > 0x100000)
			return;
		auto step = [](uint32_t& _a, const int32_t _off, const uint32_t _mod)
		{
			if(_mod)
			{
				const uint32_t mask = (1u << _mod) - 1;
				_a = (_a & ~mask) | ((_a + static_cast<uint32_t>(_off)) & mask);
			}
			else
				_a += static_cast<uint32_t>(_off);
		};
		std::vector<uint8_t> buf(nbytes);
		uint32_t s = _saddr, d = _daddr;
		for(uint32_t loop = 0; loop < loops; ++loop)
		{
			for(uint32_t i = 0; i < nbytes; i += ssize)
			{
				const auto n = std::min(ssize, nbytes - i);
				for(uint32_t k = 0; k < n; ++k)
					buf[i + k] = m_machine.read8(s + k);
				step(s, soff, smod);
			}
			for(uint32_t i = 0; i < nbytes; i += dsize)
			{
				const auto n = std::min(dsize, nbytes - i);
				for(uint32_t k = 0; k < n; ++k)
					m_machine.write8(d + k, buf[i + k]);
				step(d, doff, dmod);
			}
			m_m2mBytes += nbytes;
		}
		++m_m2mBlocks;
	}

	void Rtos::installHostPortMover()
	{
		auto* co = m_machine.coprocessor();
		if(!co)
			return;
		m_edma.setDataHooks(
			[this, co](const uint32_t _ch)
			{
				co->cpuNote('k', _ch);		// O17b: the kick, in the protocol record
				const auto daddr = m_edma.tcdField(_ch, 0x10, 4);
				const auto saddr = m_edma.tcdField(_ch, 0, 4);
				m_kickSel[_ch & 15] = co->selected();
				if(daddr < Edma::g_hostPortLo || daddr >= Edma::g_hostPortHi)
				{
					// O20 (13 Sep 2026): A MEMORY-TO-MEMORY CHANNEL MOVES ITS BYTES.
					// Route A's model moved no data on any channel, and the host-port
					// mover only ever carried the DSP blocks -- so the ECHO FREEZE
					// DELAY, which is not on the DSP at all (EXTERNAL.md §1: the
					// ColdFire's frame routine at 0x400031a0 points the eDMA at its
					// per-track rings in SDRAM at 0x4f502c10), never got its taps:
					// channels 2/3 fetch this frame's and last frame's delay positions
					// from the ring into the staging buffers 0x800039a0/0x80003a40
					// (TCD: ATTR 0x0402 = 16-byte source bursts, 32-bit destination,
					// SOFF 16, DOFF 4, NBYTES 144, CITER 1, no modulo), channels 4/5
					// write the frame's block from 0x800000e8 into the ring (ATTR
					// 0x0404, NBYTES 128) with a mirror at ring + 1,411,200 when the
					// write lands at the base. The routine busy-waits DONE at
					// 0x400035a8 / 0x40003780 and then mixes the staging buffers: with
					// nothing moved the repeats were silence on every card (measured
					// 13 Sep 2026: SEND 100 / FB 70 / TIME 47, no energy between the
					// hits, lockstep and rt alike). The copy is the TCD's: every minor
					// loop moves NBYTES as SSIZE reads at SOFF and DSIZE writes at
					// DOFF (SMOD/DMOD honoured if ever set), CITER minor loops; the
					// TCD's own words are left as the firmware wrote them (it
					// reprograms the addresses every frame). The host-port lanes are
					// untouched: a channel with either end in the window keeps the
					// mover's rules below.
					if(saddr < Edma::g_hostPortLo || saddr >= Edma::g_hostPortHi)
						copyMemToMem(_ch, saddr, daddr);
					return;
				}
				const auto bytes = m_edma.tcdField(_ch, 8, 4) * m_edma.minorLoops(_ch);
				std::vector<uint16_t> hw;
				hw.reserve(bytes / 2);
				for(uint32_t i = 0; i + 1 < bytes; i += 2)
					hw.push_back(m_machine.read16(saddr + i));
				co->pushHalfwords(daddr, hw);
				uint64_t nz = 0;
				for(const auto w : hw)
					if(w)
						++nz;
				++m_hostBlocksOut;
				m_hostWordsOut += hw.size();
				m_hostNonZeroOut += nz;
				m_pendingOut[_ch & 15] = {saddr, hw, nz, m_sample};
			},
			[this, co](const uint32_t _ch)
			{
				co->cpuNote('d', _ch);		// O17b: the completion, in the protocol record
				const auto saddr = m_edma.tcdField(_ch, 0, 4);
				const auto daddr = m_edma.tcdField(_ch, 0x10, 4);
				// ⚠️ An OUTBOUND block's DSP-side state is only meaningful HERE,
				// at the completion the drain gate holds until the ring is
				// empty. Noted at the kick it lagged by a whole block (DCO0
				// still held the PREVIOUS block's count) and read as if the
				// host's destination word were being ignored.
				if(daddr >= Edma::g_hostPortLo && daddr < Edma::g_hostPortHi)
				{
					const auto& p = m_pendingOut[_ch & 15];
					if(!p.hw.empty())
					{
						const int core = m_kickSel[_ch & 15];
						std::string tail;
						// The note is the block log's / the block dump's; its
						// reads of DMA0's pointer and the landed words are the
						// DSP's own registers and memory, which under --dsp-rt
						// belong to the core's thread (TSan, 13 Sep 2026: seven
						// reports, all this read against the DMA's write), so
						// they are made only when a log wants them.
						if((m_blockLogOn || m_blockDump.is_open()) && !co->realtime())
						{
							// (O17c: not under --dsp-rt -- the peeks below stalled the
							// frame protocol, measured 13 Sep 2026: the dump's words are
							// the ColdFire's own RAM and need none of them)
							// Where DMA0 has just left off, and the tail of what
							// landed there: the direct test of whether the words
							// the port sent reached DSP memory.
							const auto ddr = co->peekWord(core, 'R', 0);	// 'R' = DMA0's DDR, see DspPair
							char t[160];
							// The burst's own timeline in SAMPLES: kicked, and the
							// completion the drain gate released -- the frame
							// period is read off consecutive frames' stamps.
							std::snprintf(t, sizeof t, " kicked@%.1f done@%.1f landed@", p.kicked, m_sample);
							tail += t;
							std::snprintf(t, sizeof t, "%04x:", ddr >= 8 ? ddr - 8 : 0);
							tail += t;
							for(uint32_t k = 0; k < 8 && ddr >= 8; ++k)
							{
								std::snprintf(t, sizeof t, " %06x", co->peekWord(core, 'X', ddr - 8 + k));
								tail += t;
							}
							tail = co->blockNote(core) + tail;
						}
						noteBlock('>', _ch, p.saddr, p.hw, p.nonZero, tail);
						m_pendingOut[_ch & 15] = {};
					}
				}
				if(saddr < Edma::g_hostPortLo || saddr >= Edma::g_hostPortHi)
					return;
				const auto bytes = m_edma.tcdField(_ch, 8, 4) * m_edma.minorLoops(_ch);
				std::vector<uint16_t> hw;
				hw.reserve(bytes / 2);
				m_hostWordsShort += co->pullHalfwords(saddr, m_kickSel[_ch & 15], hw, bytes / 2);
				for(size_t i = 0; i < hw.size(); ++i)
					m_machine.write16(daddr + 2 * static_cast<uint32_t>(i), hw[i]);
				uint64_t nz = 0;
				for(const auto w : hw)
					if(w)
						++nz;
				++m_hostBlocksIn;
				m_hostWordsIn += hw.size();
				m_hostNonZeroIn += nz;
				std::string at;
				if((m_blockLogOn || m_blockDump.is_open()) && !co->realtime())
				{
					char t[48];
					std::snprintf(t, sizeof t, " at@%.1f", m_sample);
					at = co->blockNote(m_kickSel[_ch & 15]) + t;
				}
				noteBlock('<', _ch, daddr, hw, nz, at);
			});
		// With the cores attached the bus's own time paces a burst (periph.h).
		m_edma.setBusPaced(true);
		if(co->realtime() && !(std::getenv("OT_RT_DRAINPACE") && *std::getenv("OT_RT_DRAINPACE") == '0'))
		{
			// O17c: THE DRAIN TIMES. Under the lockstep interpreter a pushed block
			// is drained by the DSP's DMA0 one word per service, and the firmware
			// handler's six block shapes each take a fixed time to drain (the
			// DSP's code path at that point of the frame is the same every frame):
			// measured 13 Sep 2026 over 12,360 frames of the OTLIVE fixture
			// (`pushlat.py` on the OT_FENCE_TRACE of a --dsp run, ack 0x48 minus
			// the push, at most 10 distinct values per shape within 0.005 sample).
			// The JIT workers drain a block in one service, so without this the
			// ISR chain ran ~0.5 samples shorter and its length followed the wall;
			// the sequencer's bookkeeping inside that chain (a voice's 8-sample
			// position bucket) then differed from the reference run to run. Words
			// = DSP words (halfword pairs); a shape not in the table gets the
			// interpreter's base rate, two instructions a word.
			m_edma.setHostDrainTime([this, co](const uint32_t _ch) -> double
			{
				const auto words = tcdWords(_ch);
				const int core = co->selected();
				struct Shape { int core; uint32_t words; double samples; };
				static constexpr Shape g_shapes[] = {
					{0, 336, 0.3400}, {1, 336, 0.1650}, {0, 256, 0.1260}, {0, 64, 0.0320}, {1, 64, 0.0320}, {0, 32, 0.0170}};
				for(const auto& sh : g_shapes)
					if(sh.core == core && sh.words == words)
						return sh.samples;
				return (2.04 * static_cast<double>(words) + 2.0) / 4160.0;	// DSP instructions per sample (dsp.h g_dspIps)
			});
		}
		m_edma.setCompletionGate([this, co](const uint32_t _ch)
		{
			const auto daddr = m_edma.tcdField(_ch, 0x10, 4);
			if(daddr < Edma::g_hostPortLo || daddr >= Edma::g_hostPortHi)
				return true;
			return co->hostRingEmpty(m_kickSel[_ch & 15]);
		});
	}

	void Rtos::noteBlock(const char _dir, const uint32_t _ch, const uint32_t _ramAddr,
		const std::vector<uint16_t>& _hw, const uint64_t _nonZero, const std::string& _note)
	{
		if(m_blockDump.is_open())
		{
			const uint8_t dir = static_cast<uint8_t>(_dir);
			const uint32_t frame = static_cast<uint32_t>(m_frameCount);
			const uint16_t ch = static_cast<uint16_t>(_ch);
			const uint8_t core = static_cast<uint8_t>(m_kickSel[_ch & 15]);
			const uint32_t ram = _ramAddr;
			const uint32_t n = static_cast<uint32_t>(_hw.size());
			m_blockDump.write(reinterpret_cast<const char*>(&dir), 1);
			m_blockDump.write(reinterpret_cast<const char*>(&frame), 4);
			m_blockDump.write(reinterpret_cast<const char*>(&ch), 2);
			m_blockDump.write(reinterpret_cast<const char*>(&core), 1);
			m_blockDump.write(reinterpret_cast<const char*>(&ram), 4);
			m_blockDump.write(reinterpret_cast<const char*>(&n), 4);
			if(n)
				m_blockDump.write(reinterpret_cast<const char*>(_hw.data()), n * 2);
		}
		if(!m_blockLogOn || m_blockLog.size() >= 200000)
			return;
		char line[512];
		std::snprintf(line, sizeof line, "%c frame %6llu ch %2u core %d ram %08x %5zu words, %5llu non-zero  first",
			_dir, static_cast<unsigned long long>(m_frameCount), _ch, m_kickSel[_ch & 15], _ramAddr,
			_hw.size(), static_cast<unsigned long long>(_nonZero));
		std::string s = line;
		for(size_t i = 0; i < _hw.size() && i < 8; ++i)
		{
			std::snprintf(line, sizeof line, " %04x", _hw[i]);
			s += line;
		}
		m_blockLog.push_back(s + "  " + _note);
	}

	void Rtos::tickTimers()
	{
		m_pit0.advance(m_sample);
		m_pit1.advance(m_sample);
		for(auto& t : m_dtim)
			t.advance(m_sample);
		if(m_frame && !m_frameFromDsp)
			while(m_sample >= m_nextFrame)
			{
				m_framePending = true;			// a latch, not a count: a masked
				m_nextFrame += g_framePeriod;	// edge source remembers ONE edge
			}
		else if(m_frameFromDsp)
		{
			// The DSP's first bank id has been waiting since the load (it
			// blocks at P:0x97 until the host takes it). Deliver it where
			// route A fires ITS first frame -- one period after the frame
			// clock came on -- so the transport start keeps the oracle's
			// phase; from then on the DSP's own writes are the edges.
			if(m_frame && m_dspEdgeLatched && m_sample >= m_nextFrame)
			{
				m_framePending = true;
				m_dspEdgeLatched = false;
			}
			while(m_sample >= m_nextFrame)
				m_nextFrame += g_framePeriod;	// only the idle skip's horizon; the edge itself is the DSP's
		}
		// The eDMA is told the boundary even when the frame clock is off:
		// its paced completions are the DSP's clock, not the interrupt's, and
		// the TCD state is real in every run.
		m_edma.setBoundary(m_nextFrame);
		m_edma.setNow(m_sample);
		m_edma.advance(m_sample);
		if(m_ataIrqDue != 0.0 && m_sample >= m_ataIrqDue)
		{
			m_ataIrqDue = 0.0;
			m_ataIrq = true;
		}
		// The host's start-of-frame, once per audio block (octemu raises it
		// from the DSP block close as well; the payload's packet builder is
		// paced by the host's IN polls, not by this edge).
		if(m_usb)
		{
			while(m_sample >= m_usbNextSof)
			{
				m_usb->sof();
				m_usbNextSof += g_framePeriod;
			}
			// The host's isochronous poll, on the schedule the audio
			// endpoint is described with: every 250 us of device time at
			// high speed (11.025 samples), every 1 ms at full speed.
			while(m_sample >= m_usbNextIso)
			{
				// A run of polls the bench host did not answer is device
				// time with nothing drained: logged, so a ring overrun it
				// causes is told apart from the guest's own.
				if(m_usb->isoPoll())
					++m_usbMissRun;
				else
				{
					if(m_usbMissRun >= 16)
						std::printf("usb        : %u isochronous poll(s) in a row with no IN from the bench host, ending at %.4f s\n",
							m_usbMissRun, m_sample / 44100.0);
					m_usbMissRun = 0;
				}
				m_usbNextIso += 44100.0 / m_usb->isoPollHz();
			}
		}
	}

	// O15a: THE HORIZON. The earliest sample at which tickTimers()/deliver()
	// could do anything that a peripheral access (m_periphTouched), an
	// acknowledgement or the DSP's host-word hook (m_wake) would not already
	// have ended the burst for. Everything that can change deliverable state
	// -- the list beside Intc::addLine in the constructor, plus the
	// registers the firmware reads back -- is one of:
	//   * a peripheral WRITE (INTC masks/forces/ICRs, PIT/DTIM control and
	//     acks, eDMA kicks/CINT/CDNE, UART masks, the card's command and data
	//     registers, the DSPI, the host port): m_periphTouched;
	//   * a peripheral READ with a side effect (UART +0x0c pops the receive
	//     queue and its line, the card's STATUS clears INTRQ and a DATA read
	//     re-arms it, DSPI POPR, the host port): m_periphTouched;
	//   * the CPU acknowledging a vector (the injected interrupt is consumed;
	//     the ack hook counts frames/ATA and deliver() must re-offer or
	//     withdraw): m_wake;
	//   * the DSP raising its bank word (setFrameFromDsp's hook: the frame
	//     edge and m_nextFrame): m_wake;
	//   * the outside world between runs (rxPush from the panel, pokes,
	//     setFrame, setNames): m_wake at runLoop entry;
	//   * TIME: an armed PIT expiring (PIF; PIE or not -- PCSR reads back),
	//     an armed DTIM reaching its reference (DTER.REF; ORRI or not), the
	//     frame timer's edge and the latched DSP edge (both at m_nextFrame,
	//     only while a frame source is on -- otherwise tickTimers() never
	//     touches it and the boundary it publishes is a constant), the ATA
	//     INTRQ latency, a booked eDMA completion (a gated one answers a
	//     sample already past: exact stepping until it clears, because the
	//     gate is the DSP's ring, re-asked after every instruction): HERE.
	// Nothing else writes the models. The DSP cores' own state reaches the
	// ColdFire only through the host port (a read: touched), the eDMA gate
	// (a due entry: here) and the host-word hook (wake); the co-processor's
	// per-instruction tick is unchanged inside a burst, so its interleave
	// with the ColdFire -- the O12 contract -- does not move.
	double Rtos::nextEvent() const
	{
		double best = (m_frame || m_frameFromDsp) ? m_nextFrame : 1e300;
		m_horizonSrc = 0;
		if(m_ataIrqDue != 0.0 && m_ataIrqDue < best)
		{
			best = m_ataIrqDue;
			m_horizonSrc = 1;
		}
		double e;
		for(const auto* p : {&m_pit0, &m_pit1})
			if(p->nextExpiry(e) && e < best)
			{
				best = e;
				m_horizonSrc = 2;
			}
		for(const auto& t : m_dtim)
			if(t.nextMatch(e) && e < best)
			{
				best = e;
				m_horizonSrc = 3;
			}
		if(m_edma.nextDue(e) && e < best)
		{
			best = e;
			m_horizonSrc = 4;
		}
		// The USB host's start-of-frame and isochronous polls (tickTimers):
		// each can raise the device controller's line.
		if(m_usb)
		{
			const double u = std::min(m_usbNextSof, m_usbNextIso);
			if(u < best)
			{
				best = u;
				m_horizonSrc = 5;
			}
		}
		return best;
	}

	bool Rtos::anyPending() const
	{
		uint32_t l, s;
		return m_intc0.top(l, s) || m_intc1.top(l, s);
	}

	bool Rtos::nextExpiry(double& _out) const
	{
		bool any = false;
		double best = 0.0;
		if(m_frame)
		{
			best = m_nextFrame;
			any = true;
		}
		if(m_ataIrqDue != 0.0 && (!any || m_ataIrqDue < best))
		{
			best = m_ataIrqDue;
			any = true;
		}
		for(const auto* p : {&m_pit0, &m_pit1})
		{
			double e;
			if(p->nextExpiry(e) && (!any || e < best))
			{
				best = e;
				any = true;
			}
		}
		for(const auto& t : m_dtim)
		{
			double e;
			if(t.nextExpiry(e) && (!any || e < best))
			{
				best = e;
				any = true;
			}
		}
		_out = best;
		return any;
	}

	// Offer the highest-priority asserted source to the CPU and let IT decide
	// whether to take it: Musashi compares the level against the SR mask and
	// acknowledges through the vendored core's own vector callback. That is
	// route A's `level <= ipl -> don't deliver` rule, done by the machine
	// rather than modelled beside it.
	//
	// ⚠️ AN INTERRUPT LINE IS LEVEL-SENSITIVE, AND A QUEUED VECTOR IS NOT.
	// The core holds an injected vector until it is acknowledged, so a source
	// that asserts and then DEASSERTS before the CPU can take it (the PIT's
	// PIF, cleared by the scheduler at 0x40000588 while it runs at mask 7)
	// would still be delivered afterwards -- firing the handler a second time
	// for an expiry that no longer exists. Measured 7 Sep 2026: that is
	// exactly what happened, and it showed up as TWICE the oracle's
	// dispatches, every other one resuming at the scheduler's own entry
	// (0x40000550) because the stale interrupt landed in the one-instruction
	// window before `movew #0x2700,%sr` raises the mask. So a line that has
	// gone away is WITHDRAWN, which is what the vendored core's
	// `removePendingInterrupt` is for.
	bool Rtos::deliver()
	{
		uint32_t bestLevel = 0, bestVector = 0;
		for(const auto* intc : {&m_intc0, &m_intc1})
		{
			uint32_t level, source;
			if(intc->top(level, source) && level > bestLevel)
			{
				bestLevel = level;
				bestVector = intc->vectorBase() + source;
			}
		}

		if(m_injectedLevel && (m_injectedLevel != bestLevel || m_injectedVector != bestVector))
		{
			m_machine.removePendingInterrupt(static_cast<uint8_t>(m_injectedVector),
				static_cast<uint8_t>(m_injectedLevel));
			m_injectedLevel = m_injectedVector = 0;
		}
		if(!bestLevel)
			return false;
		if(!m_machine.hasPendingInterrupt(static_cast<uint8_t>(bestVector), static_cast<uint8_t>(bestLevel)))
		{
			m_machine.injectInterrupt(static_cast<uint8_t>(bestVector), static_cast<uint8_t>(bestLevel));
			m_injectedLevel = bestLevel;
			m_injectedVector = bestVector;
		}
		return true;
	}

	void Rtos::recordCreate()
	{
		// create(tcb, entry, prio, stack, size), arguments on the stack above
		// the return address.
		const auto sp = m_machine.getAReg(7);
		Created c{};
		c.sample = m_sample;
		c.tcb     = m_machine.peek32(sp + 4);
		c.entry   = m_machine.peek32(sp + 8);
		c.prio    = m_machine.peek32(sp + 12);
		c.stack   = m_machine.peek32(sp + 16);
		c.size    = m_machine.peek32(sp + 20);
		c.creator = curTcb();
		m_created.push_back(c);
		m_gateDirty = true;
	}

	Rtos::Stop Rtos::run(const double _ms, const bool _untilGate)
	{
		RunSpec s;
		s.ms = _ms;
		s.untilGate = _untilGate;
		s.whyGate = "the M6a gate passed";
		s.whyTime = "time";
		const auto r = runLoop(s);
		if(memStatOn())
			std::fprintf(stderr, "memstat %.0f ms: %s\n", ms(), memStat().c_str());
		return r;
	}

	bool Rtos::memStatOn()
	{
		static const bool s_on = [] { const char* const e = std::getenv("OT_MEMSTAT"); return e && std::atoi(e) != 0; }();
		return s_on;
	}

	std::string Rtos::memStat() const
	{
		char b[640];
		std::snprintf(b, sizeof b, "dispatches=%zu(kept %zu) created=%zu acks=%zu pcRing=%zu blockLog=%zu ataTrace=%zu memWrites=%zu"
			" liveNibble=%zu trigWords=%zu uartA.tx=%zu uartA.rx=%zu uartB.tx=%zu cardLog=%zu(dropped %llu) edmaDue=%zu | ",
			m_dispatches.size(), m_dispatches.kept(), m_created.size(), m_acks.size(), m_pcRing.size(), m_blockLog.size(),
			m_ataTrace.size(), m_memWrites.size(), m_liveNibble.size(), m_trigWords.size(), m_uart64.tx().size(),
			m_uart64.rxPending(), m_uart68.tx().size(), m_card ? m_card->log().size() : 0,
			static_cast<unsigned long long>(m_card ? m_card->logDropped() : 0), m_edma.outstanding());
		std::string out = b;
		out += m_machine.memStat();
		if(const auto* co = m_machine.coprocessor())
		{
			out += " | ";
			out += co->memStat();
		}
		return out;
	}

	Rtos::Stop Rtos::runUntil(const double _ms, const std::function<bool()>& _stop, const Changes _changes)
	{
		RunSpec s;
		s.ms = _ms;
		s.stop = &_stop;
		s.stopOnEvent = _changes == Changes::OnEvent;
		s.whyGate = "the caller's condition came true";
		s.whyTime = "time";
		return runLoop(s);
	}

	Rtos::Stop Rtos::runToPc(const uint32_t _pc, const double _ms)
	{
		// O15e: a PC condition is compared inside the burst, before each
		// instruction, where the old predicate was asked -- same instruction,
		// same sample, and the pair has run for the instruction before it.
		RunSpec s;
		s.ms = _ms;
		s.pc = _pc;
		s.pcArmed = true;
		s.whyGate = "the caller's condition came true";
		s.whyTime = "time";
		return runLoop(s);
	}

	void Rtos::wakeOnWrite(const uint32_t _addr, const uint32_t _len, bool& _armed)
	{
		if(_armed)
			return;
		_armed = true;
		m_machine.addWriteWatch(_addr, _addr + _len - 1,
			[this](uint32_t, uint8_t, uint32_t, uint32_t) { m_wake = true; });
	}

	Rtos::Stop Rtos::runLoop(const RunSpec& _s)
	{
		if(_s.needInstall && !m_installed)
		{
			if(m_why.empty())
				m_why = "install() was not called";
			return Stop::Fault;
		}
		const double end = _s.hasEnd ? m_sample + _s.ms * g_sampleHz / 1000.0 : 1e300;
		uint64_t idleRuns = 0, executed = 0;
		// O15a: bursts on the plain run. O15e: on the gated run too (a burst
		// ends the instruction the gate goes dirty), on a PC condition (the
		// compare is inside the burst) and on a condition that changes only
		// on an event; a condition on anything else keeps the pre-O15a loop.
		// The pre-O15a loop for all of them is OT_BURST=0.
		const int quantum = burstQuantum();
		const bool bursts = quantum > 0 && (!_s.stop || _s.stopOnEvent);
		const bool fast = burstStepFast();
		// The three per-instruction compares the spec adds to the burst loop,
		// hoisted: a PC that never matches (odd) when none is armed; the gate
		// only under the gated run; the spin only while the idle skip wants
		// its look (without the skip, main's park is stepped through like
		// the old stepOnce loops stepped it, and breaking on it would make a
		// burst of one instruction).
		const uint32_t pcStop = _s.pcArmed ? _s.pc : 1u;
		const uint32_t pcLo = _s.pcArmed ? _s.pcLo : 0u, pcHi = _s.pcArmed ? _s.pcHi : 0u;
		const uint32_t spinLo = m_spinLo, spinHi = m_spinHi;
		const bool gateEnds = _s.untilGate;
		const bool spinEnds = _s.idleSkip;
		Coprocessor* const co = m_machine.coprocessor();
		const bool coRt = co && co->realtime();		// O17: its bank-word edge (an atomic count) ends a burst; sync() applies it
		const bool syncCo = dspSyncAtTick() || coRt;	// the rt mode needs the sync (its edges and its posts live there)
		m_wake = true;

		while(m_sample < end)
		{
			// ⚠️ ONLY when something could have changed it. `gate()` walks the
			// created list and rebuilds the ran() set, so evaluating it per
			// instruction costs more than the emulator itself -- the first
			// version of this loop did exactly that and looked like a hang.
			// A create or a dispatch is the only thing that can move it.
			if(_s.untilGate && m_gateDirty)
			{
				m_gateDirty = false;
				if(gate())
				{
					if(_s.whyGate)
						m_why = _s.whyGate;
					return Stop::Gate;
				}
			}
			// callAsMain's budget: the old loop checked it before the PC, so
			// a call that returns on its very last permitted instruction is
			// still "did not return" -- kept, for the stamps' sake.
			if(_s.budget && executed >= _s.budget)
				return Stop::Time;
			if(_s.pcArmed && (m_machine.pcFast() == _s.pc || (m_machine.pcFast() >= pcLo && m_machine.pcFast() < pcHi)))
			{
				if(_s.whyGate)
					m_why = _s.whyGate;
				return Stop::Gate;
			}
			if(_s.stop && (*_s.stop)())
			{
				if(_s.whyGate)
					m_why = _s.whyGate;
				return Stop::Gate;
			}
			// The outside world's inputs (setPoll: the --live FIFO, --midi)
			// and the USB host's I/O, on an instruction schedule: the burst
			// below stops at the next one, and whatever they change is
			// delivered through an exact step (m_wake).
			if(m_poll && m_machine.instructions() >= m_nextPoll)
			{
				m_nextPoll = m_machine.instructions() + m_pollEvery;
				m_poll();
				m_wake = true;
			}
			if(m_usb && m_machine.instructions() >= m_nextUsbPoll)
			{
				m_nextUsbPoll = m_machine.instructions() + 256;
				m_usb->pollIo();
				m_wake = true;
				if(!m_usbNotify.empty())
				{
					const bool active = m_machine.peek32(0x460e76a0) != 0;
					if(active != m_usbActive)
					{
						m_usbActive = active;
						std::ofstream f(m_usbNotify, std::ios::app);
						f << (active ? "attach" : "detach") << " " << m_sample << "\n";
					}
				}
			}

			const auto pc = m_machine.pcFast();

			// IDLE. Main parks in `bras .` and never blocks, so level 0 is
			// never empty and there is no idle path in the kernel to model:
			// a PC sitting there with nothing deliverable means the machine
			// is waiting for a timer, and the clock can simply be advanced to
			// it (route A's "idle skips"). ⚠️ Not in the borrowed-call and
			// wait loops (`idleSkip` false): they never skipped, and a skip
			// lands the clock ON the expiry where stepping lands it a
			// fraction of a sample past -- every later stamp would move.
			if(_s.idleSkip && atSpin(pc) && !anyPending())
			{
				double ex;
				if(!nextExpiry(ex))
				{
					m_why = "idle at main's spin with no timer armed: deadlock";
					return Stop::Fault;
				}
				// The DSPs keep running through a skipped idle: book them the
				// samples the clock jumps (O8).
				if(auto* c = m_machine.coprocessor(); c && ex > m_sample)
					ex = m_sample + c->tickSamples(ex - m_sample);	// a DSP frame edge ends the skip there
				m_sample = std::max(m_sample, ex);
				++m_idleSkips;
				tickTimers();
				deliver();
				if(++idleRuns > 1000000)
				{
					m_why = "idle skip made no progress";
					return Stop::Fault;
				}
				continue;
			}
			idleRuns = 0;

			if(bursts)
			{
				// EVENT-HORIZON BURSTS (O15a, 12 Sep 2026). tickTimers() and
				// deliver() are pure functions of the models' state and the
				// sample clock, so between two instructions that change
				// neither they are no-ops -- and every way the state CAN change
				// is either flagged (m_periphTouched, m_wake) or timed
				// (nextEvent). So run up to `quantum` instructions with only
				// the per-instruction port work, stopping two instructions
				// short of the earliest timed event (and of the run's end), and
				// call the pair once. The exact tail then steps instruction by
				// instruction across the event, so every timer fires on the
				// same instruction as before and every stamp -- the same
				// `m_sample += 1/ips` in the same order -- stays bit-identical.
				// A burst that ends early is always exact (it only calls the
				// pair where the old loop called it too); one that ran too
				// long would not be, which is what the horizon prevents.
				const double lim = std::min(nextEvent(), end);
				double nd = (lim - m_sample) * m_ips - 2.0;
				// O17: behind the eDMA's drain gate (a completion due in the past,
				// granted when the DSP has taken the block) the exact loop steps
				// one instruction at a time until the gate clears, ~100 ns each --
				// bit-exact completion timing for the lockstep modes, 18 M steps
				// in 4 s of play. The rt mode's contract is functional: it steps
				// the gate in bursts of 32 (the completion then lands at most 32
				// instructions late, and any peripheral access still ends the
				// burst), except within 32 instructions of the run's end.
				// O17c: only for a completion HELD by the gate (its due time behind
				// the clock); one due at the horizon lands on its instruction, as
				// under lockstep (the drain-booked pushes, periph.h setHostDrainTime)
				if(coRt && nd < -4.0 && m_horizonSrc == 4 && !m_wake && (end - m_sample) * m_ips > 34.0)
					nd = 32.0;
				if(nd > static_cast<double>(quantum))
					nd = static_cast<double>(quantum);
				if(_s.budget && nd > static_cast<double>(_s.budget - executed))
					nd = static_cast<double>(_s.budget - executed);
				if(m_poll && nd > static_cast<double>(m_nextPoll - m_machine.instructions()))
					nd = static_cast<double>(m_nextPoll - m_machine.instructions());
				if(m_usb && nd > static_cast<double>(m_nextUsbPoll - m_machine.instructions()))
					nd = static_cast<double>(m_nextUsbPoll - m_machine.instructions());
				if(m_wake || nd < 2.0)
				{
					// The exact step: the run's first instruction (whatever
					// changed between runs is delivered after it, as before),
					// and the tail across an event. m_wake is cleared BEFORE
					// the step so a wake raised inside it is never lost.
					++m_burstStats.exactInstr;
					if(m_wake) ++m_burstStats.exactWake; else ++m_burstStats.exactBySrc[m_horizonSrc & 7];	// O17 diagnostic: what forced it
					m_wake = false;
					if(!stepOnce())
						return Stop::Illegal;
					++executed;
					m_machine.takePeriphTouched();		// stepOnce handled that instruction in full
					continue;
				}
				const int n = static_cast<int>(nd);
				++m_burstStats.bursts;
				// The ring's state can only change through the card's command
				// register (a peripheral write: the burst ends there) or between
				// runs, so it is asked once per burst.
				const bool ring = m_pcRingArmed && !m_pcRing.empty();
				int i = 0;
				for(;;)
				{
					// stepOnce's per-instruction work, verbatim, minus the pair.
					const uint32_t ipc = m_machine.pcFast();
					// O15e: the caller's address, BEFORE the instruction -- the
					// old loop asked its predicate at the top, after the
					// previous instruction's pair; the pair runs at the break.
					if(ipc == pcStop || (ipc >= pcLo && ipc < pcHi)) { ++m_burstStats.endPc; break; }
					// Main's park: the idle skip must get its look at it before
					// the spin is executed (the old loop checked before every
					// instruction) -- after at least one instruction, so a park
					// with something pending but masked still makes progress.
					if(spinEnds && i > 0 && (ipc == g_mainSpin || (ipc >= spinLo && ipc < spinHi))) { ++m_burstStats.endSpin; break; }
					if(ring)
					{
						m_pcRing[m_pcRingPos % m_pcRing.size()] = ipc;
						++m_pcRingPos;
					}
					if(ipc == g_create)
						recordCreate();
					const bool atSchedRte = ipc == g_schedRte;
					if(!(fast ? m_machine.stepFast() : m_machine.step()))
					{
						m_why = m_machine.why();
						return Stop::Illegal;
					}
					m_sample += 1.0 / m_ips;
					if(atSchedRte)
					{
						const auto cur = curTcb();
						m_dispatches.push(Dispatch{m_sample, cur, m_machine.pc()});
						m_gateDirty = true;
						if(m_firstSwitch.first && !m_firstSwitch.second)
							m_firstSwitch.second = cur;
					}
					if(!m_firstSwitch.first && ipc == g_handoff)
						m_firstSwitch.first = curTcb();
					++i;		// once per instruction (the prototype counted twice)
					if(m_machine.takePeriphTouched()) { ++m_burstStats.endPeriph; break; }
					if(m_wake) { ++m_burstStats.endWake; break; }
					if(coRt && (i & 63) == 0 && co->edgePending()) { ++m_burstStats.endWake; break; }	// O17: the DSP's edge, applied by sync() below (asked every 64 instructions: an atomic load in the hot loop, and the lateness is the lag's)
					// O15e: the gate went dirty on this instruction (a create
					// or a dispatch): the pair, then the loop's top asks it.
					if(gateEnds && m_gateDirty) { ++m_burstStats.endGate; break; }
					if(i >= n) { ++m_burstStats.endHorizon; break; }
				}
				m_burstStats.burstInstr += static_cast<uint64_t>(i);
				executed += static_cast<uint64_t>(i);
				// O16c: a lazy pair runs its backlog HERE, where the old loop
				// had already run it (inside each instruction's tick): before
				// the timers and the delivery, so an edge or a drained ring
				// due inside the burst is seen at the burst's end -- and
				// before the clear below, as a wake the pair raised inside the
				// burst was cleared here too (deliver() reads the latch itself).
				if(co && syncCo)
					co->sync();
				m_wake = false;		// before the timers: a wake raised inside them forces an exact step next
				tickTimers();
				deliver();
				continue;
			}

			if(!stepOnce())
				return Stop::Illegal;
			++executed;
		}
		if(_s.whyTime)
			m_why = _s.whyTime;
		return Stop::Time;
	}

	// One instruction and everything the loop does around it: the exact step
	// (a run's first instruction, the tail across an event, OT_BURST=0). Until
	// O15e it was also the whole of the borrowed-call and wait loops; those
	// now go through runLoop, whose burst body is this work minus the pair.
	bool Rtos::stepOnce()
	{
		const auto pc = m_machine.pc();
		// A TRUE RING: it keeps the LAST N instructions, not the first N.
		// The first-N version answered "what does the ISR do" (O7's INTRQ
		// race); a STALL asks the opposite question -- what was running when
		// the work stopped -- and the printer already reads it as a ring.
		if(m_pcRingArmed && !m_pcRing.empty())
		{
			m_pcRing[m_pcRingPos % m_pcRing.size()] = pc;
			++m_pcRingPos;
		}
		if(pc == g_create)
			recordCreate();

		// The scheduler's `rte` is the moment a task is (re)entered: the TCB
		// it is entering is already current, and the PC it resumes at is the
		// one the frame pops. So the record is taken AFTER the instruction,
		// from the new PC -- route A records exactly the popped PC, not the
		// address of the rte.
		const bool atSchedRte = pc == g_schedRte;

		if(!m_machine.step())
		{
			m_why = m_machine.why();
			return false;
		}
		m_sample += 1.0 / m_ips;

		if(atSchedRte)
		{
			const auto cur = curTcb();
			m_dispatches.push(Dispatch{m_sample, cur, m_machine.pc()});
			m_gateDirty = true;
			if(m_firstSwitch.first && !m_firstSwitch.second)
				m_firstSwitch.second = cur;
		}
		// The first trap #0 is the boot handing over: whatever context it
		// saves is the "from" half of the first switch.
		if(!m_firstSwitch.first && pc == g_handoff)
			m_firstSwitch.first = curTcb();

		// O16c: the exact step syncs a lazy pair after every instruction --
		// the pre-O16c schedule, instruction for instruction.
		if(auto* co = m_machine.coprocessor(); co && dspSyncAtTick())
			co->sync();
		tickTimers();
		deliver();
		return true;
	}

	Rtos::Stop Rtos::runToMainSpin(const double _ms)
	{
		// ⚠️ THE PC ALONE, as route A's `until=lambda r: r.pc == MAIN_SPIN`.
		// Requiring nothing to be pending as well never comes true once
		// the card is live: the ATA and serial lines assert constantly,
		// so the park never returned and the load never started.
		// O15e: the same loop, in bursts, no idle skip (it never had one:
		// the PC at the park IS the condition), no install check (as before).
		RunSpec s;
		s.ms = _ms;
		s.pc = g_mainSpin;
		s.pcArmed = true;
		s.pcLo = m_spinLo; s.pcHi = m_spinHi;
		s.idleSkip = false;
		s.needInstall = false;
		s.whyTime = "never reached main's spin";
		return runLoop(s);
	}

	void Rtos::mapCardMemory()
	{
		// ✅ MEASURED, and it CORRECTS THE O5 RECORD. These four spans are
		// mapped EXPLICITLY by route A's `emu_card.attach`, with its own
		// comment: the boot maps 32 MB at 0x40000000, 32 MB at 0x46000000,
		// 1 MB at 0x48000000 and 64 KB at 0x100b0000, and the storage stack
		// and the project loader use the REST of the 256 MB -- the PCM pool,
		// the sector buffers at 0x4ece3000/0x4eceb200, the delay rings at
		// 0x4f502c10 -- plus the on-chip SRAM around the boot's window, where
		// the names (0x100f8480) and the object tables
		// (0x100b14f0..0x100f7f30) live.
		//
		// ❌ O5 concluded that route A GROWS these through `_prime_menu`'s
		// auto-mapping hook. It does not. `_prime_menu` is called only from
		// the menu RENDER helpers, none of which run on the golden path, so
		// that hook is never installed there and route A really does fault on
		// anything outside its maps. The spans O5 identified were right; the
		// mechanism was wrong, and the difference matters: an explicit map has
		// KNOWN BOUNDS, so a wild pointer outside them is still a fault in
		// route A while this port's auto-map would absorb it silently.
		for(const auto& [base, size] : {std::pair<uint32_t, uint32_t>{0x42000000, 0x04000000},
			std::pair<uint32_t, uint32_t>{0x48100000, 0x07f00000},
			std::pair<uint32_t, uint32_t>{0x10000000, 0x000b0000},
			std::pair<uint32_t, uint32_t>{0x100c0000, 0x00040000}})
			m_machine.mapRegion(base, size);
	}

	void Rtos::attachCard(AtaCard& _card)
	{
		m_card = &_card;
		mapCardMemory();
		// ⚠️ THE ATA HOST STATUS BYTE, and without it nothing happens at all.
		// 0xfc0a4039 bit 3 must read CLEAR (`movew` into the CCR, then `bpl`);
		// an unmodelled peripheral answers all-ones, the bit is set, and the
		// driver concludes there is no card -- the request posts, SYS runs the
		// card case, and ZERO ATA commands are issued, with no error anywhere.
		// Measured on the first run of this milestone. Route A carries it in
		// `EXTRA_OVERRIDES` from the boot; here it belongs with the card.
		m_machine.setOverride8(0xfc0a4039, 0x00);
		m_intc1.addLine(g_ataSource, [this] { return m_ataIrq; });
	}

	bool Rtos::callAsMain(const uint32_t _addr, const std::vector<uint32_t>& _args, uint32_t& _d0,
		const uint64_t _budget)
	{
		if(!atSpin(m_machine.pc()))
		{
			char msg[160];
			std::snprintf(msg, sizeof msg, "callAsMain(%#x): pc is %#x, not main's spin %#x",
				_addr, m_machine.pc(), g_mainSpin);
			m_why = msg;
			return false;
		}
		// retaddr at [sp], then the args in the order given -- the convention
		// the firmware's own call sites use (`pea a1; pea a0; jsr addr`).
		const auto sp = m_machine.getA7() - 4 * static_cast<uint32_t>(1 + _args.size());
		m_machine.poke32(sp, g_mainSpin);
		for(size_t i = 0; i < _args.size(); ++i)
			m_machine.poke32(sp + 4 * static_cast<uint32_t>(i + 1), _args[i]);
		m_machine.setA7(sp);
		m_machine.setPC(_addr);

		// O15e: the return is the PC condition (the return address IS the
		// park), the budget counts instructions as the old loop's `n` did,
		// no idle skip, no sample end. With the card live the call is
		// preempted constantly and the bursts run the other tasks' code
		// underneath it exactly as the plain run would.
		RunSpec s;
		s.hasEnd = false;
		s.budget = _budget;
		s.pc = g_mainSpin;
		s.pcArmed = true;
		s.idleSkip = false;
		s.needInstall = false;
		const auto st = runLoop(s);
		if(st == Stop::Gate)
		{
			_d0 = m_machine.getD0();
			return true;
		}
		if(st != Stop::Time)
			return false;		// Illegal: m_why is the machine's, as stepOnce left it
		char msg[160];
		std::snprintf(msg, sizeof msg, "callAsMain(%#x) did not return in %llu steps",
			_addr, static_cast<unsigned long long>(_budget));
		m_why = msg;
		return false;
	}

	bool Rtos::postMessage(const uint32_t _queue, const uint32_t _msg, uint32_t& _d0)
	{
		return callAsMain(g_kernelPost, {_queue, _msg}, _d0);
	}

	void Rtos::setNames(const std::string& _set, const std::string& _project)
	{
		const auto write = [this](uint32_t _addr, const std::string& _s)
		{
			for(size_t i = 0; i < _s.size() && i < 0x100; ++i)
				m_machine.write8(_addr + static_cast<uint32_t>(i), static_cast<uint8_t>(_s[i]));
			m_machine.write8(_addr + static_cast<uint32_t>(std::min<size_t>(_s.size(), 0x100)), 0);
		};
		write(g_setName, _set.empty() || _set[0] == '/' ? _set : "/" + _set);
		write(g_projectName, _project);
	}

	Rtos::LoadResult Rtos::loadProjectLive(const std::string& _set, const std::string& _project,
		const double _runMs, const double _mountMs, const bool _namesEarly, const bool _bootLoad)
	{
		LoadResult out;
		const double start = m_sample;

		if(runToMainSpin() != Stop::Gate)
			return out;
		if(_namesEarly || _bootLoad)
			setNames(_set, _project);
		if(_bootLoad)
			m_machine.countPc(g_loadHandler);
		if(!requestCardMount())
			return out;

		// Wait for the card to come READY rather than for a fixed time: the
		// mount runs in the SYS task against real ATA commands completed
		// through vector 0xb6.
		// O15e: a memory condition, so the word is watched -- the store that
		// sets it wakes the burst loop on that instruction, and the condition
		// is asked there, as it was before every instruction. No idle skip
		// (the old loop had none: main parks between the ATA interrupts and
		// was stepped through), no sample stamp moves.
		{
			wakeOnWrite(g_cardReady, 4, m_cardReadyWatched);
			const std::function<bool()> ready = [this] { return m_machine.peek32(g_cardReady) != 0; };
			RunSpec s;
			s.ms = _mountMs;
			s.stop = &ready;
			s.stopOnEvent = true;
			s.idleSkip = false;
			s.needInstall = false;
			if(runLoop(s) == Stop::Illegal)
				return out;
		}
		out.ready = m_machine.peek32(g_cardReady);

		// ⚠️ WAIT FOR `sys`'S MEDIA CASE TO PASS BEFORE NAMING THE PROJECT,
		// or the name is a RACE. ✅ Measured 8 Sep 2026 (O7b): the case at
		// `0x4006203a` reloads whatever project is named, and the two
		// emulators disagreed by 6,184 ATA commands for no other reason than
		// that route A's mount tail runs ~200 samples longer, so its case
		// fired BEFORE its harness wrote the name and this port's fired after.
		// Route A reproduces the port's 12,373 exactly when told to write the
		// name first (`--names-early`), which is what turns this from a story
		// into a measurement. Waiting for the join point makes the order a
		// choice; `_namesEarly` takes the other one deliberately.
		if(!_namesEarly && !_bootLoad)
		{
			out.mediaCaseSeen = runToPc(g_mediaCaseJoin, 2000.0) == Stop::Gate;
			// ⚠️ 12 Sep 2026, with the DMA timers modelled: the names go in AT
			// the join, not after main's next spin. The sys tick (DTIM1's
			// handler posts sys command 5 at 60 Hz) is already queued behind
			// the media case, and its startup step (0x40052200 .. `jmp
			// 0x400256b8` at 0x4007ec5a) is the firmware's own "mount the
			// last set": it reads g_setName ~7,500 instructions after the
			// case ends. Empty, it opens "NO SET IS MOUNTED! PLEASE MOUNT
			// ONE." and the CHOOSE A SET browser (measured: 0x400256ce, then
			// 0x400116aa with a 75x41 box); named, it mounts the set
			// (0x400255ec) and nothing pops. The media case's own reload
			// check has passed by then, so the load is still the one posted
			// below (1 pass of 0x400907da); the set mount itself now reads the
			// card as the firmware does: 10285 ATA commands / 42926 sectors per
			// boot where the old order read 5395 / 22714, ~16 s more wall.
			// Before the timers that tick never came and the order did not
			// matter; `setNames` is plain memory writes and needs no spin.
			setNames(_set, _project);
		}

		if(runToMainSpin() != Stop::Gate)
			return out;
		// Route A's own watch: the engine's BANK= parse is the write to
		// PART_PTR made at 0x40087d44, and it is the ONLY thing that tells
		// the saved bank apart from every other writer of that word (`sys`'s
		// select-bank case writes it too, from a different PC).
		if(!m_partPtrWatched)
		{
			m_partPtrWatched = true;
			// A mod may DETOUR the site (midisc's bank_publish replaces the
			// 6-byte store with `jsr (cave).l` and makes the store from the
			// cave). Keyed on the stock PC alone, this watch never fired on
			// such an image, savedBank stayed -1, the transport start below
			// re-selected bank 0, and three sessions (10-12 Sep 2026) read
			// the resulting 3-tracks-armed signature as a firmware defect at
			// that one site -- bisected, "narrowed to unpack", reported and
			// PR'd upstream. It was this watch. Follow a jsr at the site and
			// accept the store from the detour's own code as well.
			uint32_t detourLo = 0, detourHi = 0;
			if(m_machine.read16(g_engineBankWrite) == 0x4eb9)	// jsr (abs).l
			{
				detourLo = m_machine.peek32(g_engineBankWrite + 2);
				detourHi = detourLo + 0x80;
			}
			m_machine.addWriteWatch(g_partPtr, g_partPtr + 3,
				[this, detourLo, detourHi](uint32_t, uint8_t, const uint32_t _val, const uint32_t _pc)
				{
					if(_pc == g_engineBankWrite || (detourLo && _pc >= detourLo && _pc < detourHi))
						m_savedBank = static_cast<int>((_val - g_bankBlob) / g_bankStride);
				});
		}
		uint32_t d0 = 0;
		// A generous budget: with the card live the borrowed call is preempted
		// constantly, so the step count is dominated by the OTHER tasks
		// running underneath it, not by the call itself.
		if(_bootLoad)
		{
			out.posted = true;	// the firmware's own post, not ours
			out.postWhy = "the firmware's (--boot-load)";
		}
		else
		{
			m_machine.countPc(g_loadHandler);
			out.posted = callAsMain(g_postLoad, {g_projectName}, d0, 200000000);
			if(!out.posted)
				out.postWhy = m_why;
		}
		// Run until the engine has taken LOAD PROJECT and is next at its
		// queue receive with nothing queued (g_engineQueue), within the
		// budget. The handler
		// is usually entered while the borrowed post call is still stepping
		// (the scheduler runs every task underneath it), so its entry is
		// counted from before the post rather than waited for.
		const double postSample = m_sample;
		double left = _runMs;
		for(;;)
		{
			out.stop = runToPc(g_engineReceive, left);
			if(out.stop != Stop::Gate)
				break;
			if(m_machine.pcCount() > 0 && m_machine.peek32(g_engineQueue + 4) == 0)
			{
				out.handledMs = (m_sample - postSample) / g_sampleHz * 1000.0;
				out.handledInstr = m_machine.instructions();
				break;
			}
			// Another command is queued (or this pass was not the load's): step
			// off the receive and wait for the next pass.
			if(!stepOnce())
			{
				out.stop = Stop::Illegal;
				break;
			}
			left = _runMs - (m_sample - postSample) / g_sampleHz * 1000.0;
			if(left <= 0.0)
			{
				out.stop = Stop::Time;
				break;
			}
		}
		out.handlerEntered = m_machine.pcCount() > 0;
		m_machine.countPc(1);
		// Park where the fixed-budget run used to leave the machine: the
		// engine blocked in its receive and main at its spin, which the
		// borrowed calls that follow (--call, the sequencer branch) require.
		if(out.stop == Stop::Gate && runToMainSpin() != Stop::Gate)
		{
			out.stop = Stop::Fault;
			out.stopWhy = m_why;
		}
		if(out.stop != Stop::Time && out.stop != Stop::Gate)
			out.stopWhy = m_why;
		out.partPtr = m_machine.peek32(g_partPtr);
		out.savedBank = m_savedBank;
		out.finalBank = m_machine.read8(g_curBank);
		out.ms = (m_sample - start) / g_sampleHz * 1000.0;
		return out;
	}

	// -- M6c: the sequencer under the real scheduler -------------------------
	void Rtos::setFrame(const bool _on)
	{
		m_frame = _on;
		if(auto* co = m_machine.coprocessor())
			co->setFrameClock(_on);		// O17b: the rt mode's fence applies only while frames are taken
		// Route A's `rt.next_frame = rt.sample + FRAME_PERIOD`: the first
		// boundary is one period from HERE, not from a clock that has been
		// running since the boot. Route A also switches to its exact
		// instruction clock at this point; this port has counted executed
		// instructions all along, so there is nothing to switch.
		if(_on)
			m_nextFrame = m_sample + g_framePeriod;
	}

	void Rtos::setFrameFromDsp(const bool _on)
	{
		m_frameFromDsp = _on;
		auto* co = m_machine.coprocessor();
		if(!co)
			return;
		co->setHostWordHook(_on ? std::function<bool(int)>([this](int)
		{
			m_wake = true;		// O15a: a frame edge the horizon could not see
			if(!m_frame)
			{
				m_dspEdgeLatched = true;		// delivered the moment the frame clock comes on
				return true;
			}
			m_framePending = true;
			m_nextFrame = m_sample + g_framePeriod;	// the eDMA boundary rule and the idle skip still read it
			return true;
		}) : std::function<bool(int)>());
	}

	uint8_t Rtos::selectBankLive(const uint32_t _bank, const double _ms)
	{
		if(runToMainSpin() != Stop::Gate)
			return m_machine.read8(g_curBank);
		// msg[0] = the select-bank opcode, msg[1] = the bank.
		m_machine.poke32(g_sysMsgScratch,
			(g_selectBankCase << 24) | ((_bank & 0x0f) << 16));
		uint32_t d0 = 0;
		if(!postMessage(g_sysQueue, g_sysMsgScratch, d0))
			return m_machine.read8(g_curBank);
		// O15e: watched, in bursts, no idle skip -- see loadProjectLive's wait.
		wakeOnWrite(g_curBank, 1, m_curBankWatched);
		const std::function<bool()> switched = [this, _bank] { return m_machine.read8(g_curBank) == (_bank & 0xff); };
		RunSpec s;
		s.ms = _ms;
		s.stop = &switched;
		s.stopOnEvent = true;
		s.idleSkip = false;
		s.needInstall = false;
		runLoop(s);
		return m_machine.read8(g_curBank);
	}

	std::pair<uint8_t, uint8_t> Rtos::seqSelectLive(const uint32_t _bank, const uint32_t _pattern)
	{
		if(runToMainSpin() == Stop::Gate)
		{
			uint32_t d0 = 0;
			callAsMain(g_fwSeqSelect, {_bank, _pattern}, d0);
		}
		return {m_machine.read8(g_fwSeqBank), m_machine.read8(g_fwSeqPattern)};
	}

	uint8_t Rtos::internalClock()
	{
		const auto midi = m_machine.read8(g_fwMidiSettings);
		m_machine.write8(g_fwMidiSettings, static_cast<uint8_t>(midi & ~1u));
		return midi;
	}

	bool Rtos::startTransportLive()
	{
		if(runToMainSpin() != Stop::Gate)
			return false;
		uint32_t d0 = 0;
		if(!callAsMain(g_fwTransport, {0}, d0))
			return false;
		for(uint32_t t = 0; t < 8; ++t)
		{
			if(runToMainSpin() != Stop::Gate)
				return false;
			if(!callAsMain(g_fwStartTrack, {t}, d0))
				return false;
		}
		return true;
	}

	uint8_t Rtos::pokeTrig(const uint32_t _step)
	{
		const auto blob = m_machine.peek32(g_partPtr);
		const auto at = blob + 7 - (_step - 1) / 8;
		const auto v = static_cast<uint8_t>(m_machine.read8(at) | (1u << ((_step - 1) % 8)));
		m_machine.write8(at, v);
		return v;
	}

	void Rtos::watchPc(const std::vector<uint32_t>& _addrs)
	{
		// Delegated to the machine, which sees the boot as well -- see
		// Machine::notePcWatch for why that matters.
		m_machine.watchPc(_addrs);
	}

	void Rtos::watchMem(const uint32_t _addr, const uint32_t _len)
	{
		m_machine.addWriteWatch(_addr, _addr + _len - 1,
			[this](const uint32_t _a, const uint8_t _size, const uint32_t _val, const uint32_t _pc)
			{
				if(m_memWrites.size() < 2000000)	// ⚠️ was 20,000: a boot-time init filled it before the frames phase began (O9b)
					m_memWrites.push_back({m_sample, curTcb(), _pc, _a, _val, _size, m_machine.instructions()});
			});
	}

	void Rtos::installTrigLog()
	{
		if(m_trigLogInstalled)
			return;
		m_trigLogInstalled = true;
		m_machine.addWriteWatch(g_fwLiveNibble, g_fwLiveNibble + 7,
			[this](const uint32_t _addr, uint8_t, const uint32_t _val, const uint32_t _pc)
			{
				const auto v = _val & 0xff;
				if(v)
					m_liveNibble.push_back({m_frameCount, _addr - g_fwLiveNibble, v, _pc});
			});
		m_machine.addWriteWatch(g_fwTrigWords, g_fwTrigWords + 15,
			[this](const uint32_t _addr, uint8_t, const uint32_t _val, const uint32_t _pc)
			{
				const auto v = _val & 0xffff;
				if(v)
					m_trigWords.push_back({m_frameCount, (_addr - g_fwTrigWords) / 2, v, _pc});
			});
	}

	uint64_t Rtos::ticks() const
	{
		uint64_t n = 0;
		for(const auto& a : m_acks)
			if(a.vector == g_tickVector)
				++n;
		return n;
	}

	uint32_t Rtos::setMainLevelLive(const uint32_t _level, const double _ms)
	{
		if(runToMainSpin() != Stop::Gate)
			return m_machine.peek32(g_mainGainTable);
		m_machine.poke32(g_sysMsgScratch, (g_setMainLevelCase << 24) | ((_level & 0x7f) << 16));
		uint32_t d0 = 0;
		if(!postMessage(g_sysQueue, g_sysMsgScratch, d0))
			return m_machine.peek32(g_mainGainTable);
		// O15e: watched, in bursts, no idle skip -- see loadProjectLive's wait.
		wakeOnWrite(g_mainGainTable, 4, m_gainTableWatched);
		const std::function<bool()> filled = [this] { return m_machine.peek32(g_mainGainTable) != 0; };
		RunSpec s;
		s.ms = _ms;
		s.stop = &filled;
		s.stopOnEvent = true;
		s.idleSkip = false;
		s.needInstall = false;
		runLoop(s);
		runToMainSpin();
		return m_machine.peek32(g_mainGainTable);
	}

	bool Rtos::requestCardMount()
	{
		// msg[0] = 16 selects the card case; msg[1] must be non-zero.
		m_machine.poke32(g_sysMsgScratch, 0x10010000);
		uint32_t d0 = 0;
		return postMessage(g_sysQueue, g_sysMsgScratch, d0);
	}

	std::unordered_set<uint32_t> Rtos::ran() const
	{
		return m_dispatches.ran();
	}

	bool Rtos::gate(std::vector<std::string>* _problems) const
	{
		std::vector<std::string> problems;
		char buf[256];

		for(const auto& want : g_expectedTasks)
		{
			const bool found = std::any_of(m_created.begin(), m_created.end(), [&](const Created& c)
			{
				return c.tcb == want.tcb && c.entry == want.entry && c.prio == want.prio
					&& c.stack == want.stack && c.size == want.size && c.creator == want.creator;
			});
			if(!found)
			{
				std::snprintf(buf, sizeof buf, "never created with the expected fields: %s (tcb %#x)",
					taskName(want.tcb), want.tcb);
				problems.emplace_back(buf);
			}
		}

		const auto did = ran();
		for(const auto& want : g_expectedTasks)
			if(!did.count(want.tcb))
			{
				std::snprintf(buf, sizeof buf, "never ran: %s (tcb %#x)", taskName(want.tcb), want.tcb);
				problems.emplace_back(buf);
			}
		if(!did.count(g_mainTcb))
			problems.emplace_back("never ran: main");

		if(m_firstSwitch.first != g_bootTcb || m_firstSwitch.second != g_mainTcb)
		{
			std::snprintf(buf, sizeof buf, "first switch %#x -> %#x, expected boot -> main",
				m_firstSwitch.first, m_firstSwitch.second);
			problems.emplace_back(buf);
		}

		if(_problems)
			*_problems = problems;
		return problems.empty();
	}

	namespace
	{
		std::string base64(const std::vector<uint8_t>& _in)
		{
			static const char* const g_alphabet =
				"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
			std::string out;
			out.reserve((_in.size() + 2) / 3 * 4);
			for(size_t i = 0; i < _in.size(); i += 3)
			{
				const uint32_t a = _in[i];
				const uint32_t b = i + 1 < _in.size() ? _in[i + 1] : 0;
				const uint32_t c = i + 2 < _in.size() ? _in[i + 2] : 0;
				const uint32_t v = (a << 16) | (b << 8) | c;
				out += g_alphabet[(v >> 18) & 63];
				out += g_alphabet[(v >> 12) & 63];
				out += i + 1 < _in.size() ? g_alphabet[(v >> 6) & 63] : '=';
				out += i + 2 < _in.size() ? g_alphabet[v & 63] : '=';
			}
			return out;
		}
	}

	void Rtos::writeM6cJson(const std::string& _path, const M6c& _m) const
	{
		std::ofstream f(_path);
		f << "{\n";
		const auto log = [&f](const char* _name, const std::vector<TrigWrite>& _v, const uint64_t _frame0)
		{
			f << " \"" << _name << "\": [";
			bool first = true;
			for(const auto& w : _v)
			{
				f << (first ? "" : ", ") << "[" << static_cast<int64_t>(w.frame - _frame0)
				  << ", " << w.index << ", " << w.value << "]";
				first = false;
			}
			f << "],\n";
		};
		log("m6c_trig", m_liveNibble, _m.frame0);
		log("m6c_trig_words", m_trigWords, _m.frame0);
		f << " \"m6c_ticks\": " << (_m.ticks - _m.ticks0) << ",\n";
		f << " \"m6c_frames\": " << _m.frames << ",\n";
		f << " \"m6c_bank\": [" << _m.savedBank << ", " << _m.finalBank << ", "
		  << _m.seqBank << ", " << _m.seqPattern << "]\n}\n";
	}

	void Rtos::writeGoldenJson(const std::string& _path) const
	{
		std::ofstream f(_path);
		f << "{\n";
		f << " \"handoff_pc\": " << g_handoff << ",\n";

		f << " \"auto_pokes\": [";
		bool first = true;
		for(const auto& p : m_machine.autoPokes())
		{
			f << (first ? "\n" : ",\n") << "  {\"pc\": " << p.pc << ", \"addr\": " << p.addr
			  << ", \"value\": " << p.value << "}";
			first = false;
		}
		f << (first ? "" : "\n ") << "],\n";

		f << " \"created\": [";
		first = true;
		for(const auto& c : m_created)
		{
			f << (first ? "\n" : ",\n") << "  {\"sample\": " << c.sample << ", \"tcb\": " << c.tcb
			  << ", \"entry\": " << c.entry << ", \"prio\": " << c.prio << ", \"stack\": " << c.stack
			  << ", \"stack_size\": " << c.size << ", \"creator\": " << c.creator
			  << ", \"name\": \"" << taskName(c.tcb) << "\"}";
			first = false;
		}
		f << (first ? "" : "\n ") << "],\n";

		std::vector<uint32_t> did(ran().begin(), ran().end());
		std::sort(did.begin(), did.end());
		f << " \"ran\": [";
		for(size_t i = 0; i < did.size(); ++i)
			f << (i ? ", " : "") << did[i];
		f << "],\n";

		f << " \"first_switch\": [" << m_firstSwitch.first << ", " << m_firstSwitch.second << "],\n";

		f << " \"dispatches\": [";
		first = true;
		for(size_t i = 0; i < m_dispatches.size() && i < 200; ++i)
		{
			const auto& d = m_dispatches[i];
			f << (first ? "\n" : ",\n") << "  {\"sample\": " << d.sample << ", \"tcb\": " << d.tcb
			  << ", \"pc\": " << d.pc << "}";
			first = false;
		}
		f << (first ? "" : "\n ") << "],\n";

		f << " \"gate_ms\": " << ms() << ",\n";
		f << " \"pit0_fired\": " << pit0Fired() << ",\n";
		f << " \"dtim1_fired\": " << dtimFired(1) << ", \"dtim2_fired\": " << dtimFired(2) << ",\n";
		// THE SERIAL STREAM, not its length -- see route A's golden writer and
		// the O5 section of git show 3ceba41:docs/history/COLDFIRE_PORT.md. ⚠️ The COUNT tracks the `ips`
		// knob (5731 at 3900/3990, 4831 at 4100/4200/4300) because the
		// transmit ring drains in bursts; the BYTES do not.
		f << " \"serial_sent\": [" << serialA() << ", " << serialB() << "],\n";
		f << " \"serial_a\": \"" << base64(serialTxA()) << "\",\n";
		f << " \"serial_b\": \"" << base64(serialTxB()) << "\"\n}\n";
	}
}
