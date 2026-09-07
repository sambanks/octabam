#include "rtos.h"

#include <utility>

#include <algorithm>
#include <cstdio>
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
		// INTC1 source 43 = PIT0 (vector 171, the scheduler); 44 = PIT1 (the
		// storage layer's delay timer). INTC0 source 1 is the DSP frame clock
		// and 27/28 the serial blocks -- both are later milestones, and their
		// lines are simply absent here rather than stubbed true, which is what
		// route A's own defaults amount to (`frame=False`, and the UARTs'
		// transmit interrupt cleared at seeding with nothing queued to
		// receive).
		m_intc1.addLine(43, [this] { return m_pit0.irq(); });
		m_intc1.addLine(44, [this] { return m_pit1.irq(); });
		m_intc0.addLine(27, [this] { return m_uart64.irq(); });
		m_intc0.addLine(28, [this] { return m_uart68.irq(); });
		// INTC0 source 1 = the DSP frame clock (vector 0x41), and sources
		// 8..23 are eDMA channels 0..15 (MCF5445x). 8, 9 and 15 are the ones
		// the frame exchange raises.
		m_frame = _frame;
		m_intc0.addLine(1, [this] { return m_frame && m_framePending; });
		for(uint32_t ch = 0; ch < 16; ++ch)
			m_intc0.addLine(8 + ch, [this, ch] { return m_edma.irq(ch); });
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
		if(_addr >= g_dspi && _addr < g_dspi + 0x100)   { _out = m_dspi.read(_addr - g_dspi, _size); return true; }
		if(_addr >= Edma::g_base && _addr < Edma::g_tcd + 16 * 32) { _out = m_edma.read(_addr, _size); return true; }
		for(auto* u : {&m_uart64, &m_uart68})
			if(_addr >= u->base() && _addr < u->base() + 0x20)
			{
				_out = u->read(_addr - u->base(), _size);
				return true;
			}
		return false;
	}

	void Rtos::peripheralWrite(const uint32_t _addr, const uint8_t _size, const uint32_t _val, const bool _replay)
	{
		if(_addr >= g_intc0 && _addr < g_intc0 + 0x100) m_intc0.write(_addr - g_intc0, _size, _val);
		else if(_addr >= g_intc1 && _addr < g_intc1 + 0x100) m_intc1.write(_addr - g_intc1, _size, _val);
		else if(_addr >= g_pit0 && _addr < g_pit0 + 0x10) m_pit0.write(_addr - g_pit0, _size, _val, m_sample);
		else if(_addr >= g_pit1 && _addr < g_pit1 + 0x10) m_pit1.write(_addr - g_pit1, _size, _val, m_sample);
		else if(_addr >= g_dspi && _addr < g_dspi + 0x100) m_dspi.write(_addr - g_dspi, _size, _val, _replay);
		else if(_addr >= Edma::g_base && _addr < Edma::g_tcd + 16 * 32) m_edma.write(_addr, _size, _val, _replay);
		else
		{
			for(auto* u : {&m_uart64, &m_uart68})
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
		if(m_quirks.clearTransmitInterrupt)
			for(auto* u : {&m_uart64, &m_uart68})
				u->clearTransmitInterrupt();

		m_machine.setPeripheralHandlers(
			[this](uint32_t a, uint8_t s, uint32_t& o) { return peripheralRead(a, s, o); },
			[this](uint32_t a, uint8_t s, uint32_t v) { peripheralWrite(a, s, v, false); });

		// An INTFRC write is a RESCHEDULE REQUEST and has to be seen inside
		// the instruction that made it. This loop steps one instruction at a
		// time and re-evaluates interrupts after every one, so the hook only
		// has to count them -- route A needed it to break its burst.
		// The frame latch is cleared when the CPU TAKES vector 0x41 (INTC0
		// base 64 + source 1), which is where route A clears it.
		m_machine.setAckHook([this](const uint8_t _vec, uint8_t)
		{
			if(_vec == m_intc0.vectorBase() + 1)
			{
				m_framePending = false;
				++m_frameCount;
			}
		});

		m_intc0.setForceHook([this](uint64_t) { ++m_forces; });
		m_intc1.setForceHook([this](uint64_t) { ++m_forces; });
		m_installed = true;
	}

	void Rtos::tickTimers()
	{
		m_pit0.advance(m_sample);
		m_pit1.advance(m_sample);
		if(m_frame)
			while(m_sample >= m_nextFrame)
			{
				m_framePending = true;			// a latch, not a count: a masked
				m_nextFrame += g_framePeriod;	// edge source remembers ONE edge
			}
		// The eDMA is told the boundary even when the frame clock is off:
		// its paced completions are the DSP's clock, not the interrupt's, and
		// the TCD state is real in every run.
		m_edma.setBoundary(m_nextFrame);
		m_edma.advance(m_sample);
	}

	bool Rtos::anyPending() const
	{
		uint32_t l, s;
		return m_intc0.top(l, s) || m_intc1.top(l, s);
	}

	bool Rtos::nextExpiry(double& _out) const
	{
		bool any = m_frame;
		double best = m_nextFrame;
		for(const auto* p : {&m_pit0, &m_pit1})
		{
			double e;
			if(p->nextExpiry(e) && (!any || e < best))
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
		if(!m_installed)
		{
			if(m_why.empty())
				m_why = "install() was not called";
			return Stop::Fault;
		}
		const double end = m_sample + _ms * g_sampleHz / 1000.0;
		uint64_t idleRuns = 0;

		while(m_sample < end)
		{
			// ⚠️ ONLY when something could have changed it. `gate()` walks the
			// created list and rebuilds the ran() set, so evaluating it per
			// instruction costs more than the emulator itself -- the first
			// version of this loop did exactly that and looked like a hang.
			// A create or a dispatch is the only thing that can move it.
			if(_untilGate && m_gateDirty)
			{
				m_gateDirty = false;
				if(gate())
				{
					m_why = "the M6a gate passed";
					return Stop::Gate;
				}
			}

			const auto pc = m_machine.pc();

			// IDLE. Main parks in `bras .` and never blocks, so level 0 is
			// never empty and there is no idle path in the kernel to model:
			// a PC sitting there with nothing deliverable means the machine
			// is waiting for a timer, and the clock can simply be advanced to
			// it (route A's "idle skips").
			if(pc == g_mainSpin && !anyPending())
			{
				double ex;
				if(!nextExpiry(ex))
				{
					m_why = "idle at main's spin with no timer armed: deadlock";
					return Stop::Fault;
				}
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

			if(pc == g_create)
				recordCreate();

			// The scheduler's `rte` is the moment a task is (re)entered: the
			// TCB it is entering is already current, and the PC it resumes at
			// is the one the frame pops. So the record is taken AFTER the
			// instruction, from the new PC -- route A records exactly the
			// popped PC, not the address of the rte.
			const bool atSchedRte = pc == g_schedRte;

			if(!m_machine.step())
			{
				m_why = m_machine.why();
				return Stop::Illegal;
			}
			m_sample += 1.0 / m_ips;

			if(atSchedRte)
			{
				const auto cur = curTcb();
				m_dispatches.push_back({m_sample, cur, m_machine.pc()});
				m_gateDirty = true;
				if(m_firstSwitch.first && !m_firstSwitch.second)
					m_firstSwitch.second = cur;
			}
			// The first trap #0 is the boot handing over: whatever context it
			// saves is the "from" half of the first switch.
			if(!m_firstSwitch.first && pc == g_handoff)
				m_firstSwitch.first = curTcb();

			tickTimers();
			deliver();
		}
		m_why = "time";
		return Stop::Time;
	}

	std::unordered_set<uint32_t> Rtos::ran() const
	{
		std::unordered_set<uint32_t> out;
		for(const auto& d : m_dispatches)
			out.insert(d.tcb);
		return out;
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
		// THE SERIAL STREAM, not its length -- see route A's golden writer and
		// the O5 section of COLDFIRE_PORT.md. ⚠️ The COUNT tracks the `ips`
		// knob (5731 at 3900/3990, 4831 at 4100/4200/4300) because the
		// transmit ring drains in bursts; the BYTES do not.
		f << " \"serial_sent\": [" << serialA() << ", " << serialB() << "],\n";
		f << " \"serial_a\": \"" << base64(serialTxA()) << "\",\n";
		f << " \"serial_b\": \"" << base64(serialTxB()) << "\"\n}\n";
	}
}
