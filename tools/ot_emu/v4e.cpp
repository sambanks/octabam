// The ColdFire V4e instructions the vendored Musashi does not have.
//
// WHY TRAP-AND-EMULATE, and not new opcode handlers. Musashi's tables are
// GENERATED, and the generator checked into `vendor/mc68k/Musashi/m68kmake.c`
// is NOT the one that produced the checked-in `m68kops.c`: regenerating with
// it rewrites every handler signature (the upstream fork threads a
// `m68ki_cpu_core*` through them, the shipped generator does not), an 18,984
// line diff. So the tables are effectively frozen. ✅ Measured, not assumed --
// regenerate into a scratch tree and diff, it is two commands.
//
// Instead: `m68ki_exception_illegal` calls the illegal-instruction callback
// FIRST and takes no exception if it returns nonzero (`m68kcpu.h`). That makes
// the callback a legal extension point. On entry `REG_PPC` is the faulting
// instruction's own address and `REG_PC` already points past its opcode word,
// so a handler decodes, executes, advances `REG_PC` over its extension words
// and returns 1.
//
// The cost is an exception round trip per instruction. Fine for `mvs`/`mvz`,
// which are ordinary moves scattered through the code; watch it for the EMAC,
// which the frame builder runs in bulk. If it ever matters, these handlers are
// the reference an opcode-table implementation gets diffed against.
//
// ⚠️ EVERY ENCODING HERE IS VERIFIED AGAINST `m68k-elf-objdump -m m68k:cfv4e`
// ON THE REAL IMAGE, never against a reading of the manual alone. This
// project has been bitten twice by a plausible encoding that assembled and did
// the wrong thing (`CLAUDE.md`: the assembler's `mpysu` family, `tfr a,b` as
// `rnd b`), and the emulator half cost a week this month (three defects in
// Unicorn's EMAC, each producing a confident wrong finding). The boot's own
// first two are the worked example:
//
//     4000043e:  73c1        mvzw %d1,%d1
//     40000440:  71c0        mvzw %d0,%d0
//
// which is opcode 0111 rrr 1 oo eeeeee with oo = 11, i.e. the table below.
#include "v4e.h"

#include "machine.h"

#include "mc68k/Musashi/m68k.h"
#include "mc68k/cpuState.h"

namespace ot::v4e
{
	namespace
	{
		constexpr uint32_t g_ccrN = 0x08, g_ccrZ = 0x04, g_ccrV = 0x02, g_ccrC = 0x01;

		uint32_t reg(Machine& _m, const m68k_register_t _r)
		{
			return m68k_get_reg(_m.getCpuState(), _r);
		}

		void setReg(Machine& _m, const m68k_register_t _r, const uint32_t _v)
		{
			m68k_set_reg(_m.getCpuState(), _r, _v);
		}

		m68k_register_t dReg(const uint32_t _i)
		{
			return static_cast<m68k_register_t>(M68K_REG_D0 + _i);
		}

		m68k_register_t aReg(const uint32_t _i)
		{
			return static_cast<m68k_register_t>(M68K_REG_A0 + _i);
		}

		// The PC, as the handler must see it: past the opcode word, pointing at
		// the first extension word. Musashi has already advanced it.
		uint32_t pc(Machine& _m)          { return reg(_m, M68K_REG_PC); }
		void     setPc(Machine& _m, uint32_t _v) { setReg(_m, M68K_REG_PC, _v); }

		uint16_t fetch16(Machine& _m)
		{
			const auto p = pc(_m);
			setPc(_m, p + 2);
			return _m.read16(p);
		}

		uint32_t fetch32(Machine& _m)
		{
			const uint32_t hi = fetch16(_m);
			return (hi << 16) | fetch16(_m);
		}

		// The brief extension word of (d8,An,Xn) / (d8,PC,Xn).
		uint32_t briefIndex(Machine& _m, const uint32_t _base)
		{
			const uint16_t ext = fetch16(_m);
			const uint32_t xn = (ext >> 12) & 7;
			const bool isA = (ext & 0x8000) != 0;
			uint32_t idx = isA ? reg(_m, aReg(xn)) : reg(_m, dReg(xn));
			if(!(ext & 0x0800))						// word index: sign-extended
				idx = static_cast<uint32_t>(static_cast<int32_t>(static_cast<int16_t>(idx)));
			idx <<= (ext >> 9) & 3;					// scale 1/2/4/8
			const auto disp = static_cast<int32_t>(static_cast<int8_t>(ext & 0xff));
			return _base + idx + static_cast<uint32_t>(disp);
		}
	}

	// Read a source operand of `_size` bytes through effective address
	// `mode`/`reg`, advancing the PC over any extension words.
	//
	// ⚠️ `-(An)` and `(An)+` on a BYTE with An = A7 adjust by TWO on the 68000,
	// to keep the stack even. Kept here 🟡 INFERRED for ColdFire, which has no
	// odd-address stack either; nothing in this firmware has exercised it yet,
	// and the falsifier is a `mvs.b -(%sp)` whose stack pointer comes back odd.
	// Write a LONGWORD operand through effective address `mode`/`reg`,
	// advancing the PC over any extension words. The alterable modes only --
	// PC-relative and immediate are not destinations, and a caller that asks
	// for one gets false rather than a silent write somewhere.
	bool writeEaLong(Machine& _m, const uint32_t _mode, const uint32_t _reg, const uint32_t _val)
	{
		switch(_mode)
		{
		case 0:														// Dn
			setReg(_m, dReg(_reg), _val);
			return true;
		case 1:														// An
			setReg(_m, aReg(_reg), _val);
			return true;
		case 2:														// (An)
			_m.write32(reg(_m, aReg(_reg)), _val);
			return true;
		case 3:														// (An)+
			{
				const auto a = reg(_m, aReg(_reg));
				_m.write32(a, _val);
				setReg(_m, aReg(_reg), a + 4);
				return true;
			}
		case 4:														// -(An)
			{
				const auto a = reg(_m, aReg(_reg)) - 4;
				setReg(_m, aReg(_reg), a);
				_m.write32(a, _val);
				return true;
			}
		case 5:														// (d16,An)
			{
				const auto disp = static_cast<int32_t>(static_cast<int16_t>(fetch16(_m)));
				_m.write32(reg(_m, aReg(_reg)) + static_cast<uint32_t>(disp), _val);
				return true;
			}
		case 6:														// (d8,An,Xn)
			_m.write32(briefIndex(_m, reg(_m, aReg(_reg))), _val);
			return true;
		case 7:
			switch(_reg)
			{
			case 0:													// (xxx).W
				{
					const auto a = static_cast<int32_t>(static_cast<int16_t>(fetch16(_m)));
					_m.write32(static_cast<uint32_t>(a), _val);
					return true;
				}
			case 1:													// (xxx).L
				_m.write32(fetch32(_m), _val);
				return true;
			default:
				return false;
			}
		default:
			return false;
		}
	}

	bool readEa(Machine& _m, const uint32_t _mode, const uint32_t _reg, const uint32_t _size,
		uint32_t& _out)
	{
		const auto load = [&](const uint32_t _addr)
		{
			return _size == 1 ? _m.read8(_addr) : _m.read16(_addr);
		};

		switch(_mode)
		{
		case 0:														// Dn
			_out = reg(_m, dReg(_reg));
			return true;
		case 1:														// An
			// ✅ MEASURED, not assumed: the storage stack reaches
			// `mvzw %a0,%d0` at 0x40017c10 (objdump -m m68k:cfv4e decodes it
			// exactly so), and another at 0x40017c2c. An address register IS
			// a legal MVS/MVZ source on this part, and leaving it out stopped
			// the card mount dead with "unimplemented opcode 71c8".
			_out = reg(_m, aReg(_reg));
			return true;
		case 2:														// (An)
			_out = load(reg(_m, aReg(_reg)));
			return true;
		case 3:														// (An)+
			{
				const auto a = reg(_m, aReg(_reg));
				const uint32_t step = (_size == 1 && _reg == 7) ? 2 : _size;
				_out = load(a);
				setReg(_m, aReg(_reg), a + step);
				return true;
			}
		case 4:														// -(An)
			{
				const uint32_t step = (_size == 1 && _reg == 7) ? 2 : _size;
				const auto a = reg(_m, aReg(_reg)) - step;
				setReg(_m, aReg(_reg), a);
				_out = load(a);
				return true;
			}
		case 5:														// (d16,An)
			{
				const auto disp = static_cast<int32_t>(static_cast<int16_t>(fetch16(_m)));
				_out = load(reg(_m, aReg(_reg)) + static_cast<uint32_t>(disp));
				return true;
			}
		case 6:														// (d8,An,Xn)
			_out = load(briefIndex(_m, reg(_m, aReg(_reg))));
			return true;
		case 7:
			switch(_reg)
			{
			case 0:													// (xxx).W
				{
					const auto a = static_cast<int32_t>(static_cast<int16_t>(fetch16(_m)));
					_out = load(static_cast<uint32_t>(a));
					return true;
				}
			case 1:													// (xxx).L
				_out = load(fetch32(_m));
				return true;
			case 2:													// (d16,PC)
				{
					const auto base = pc(_m);						// the extension word's own address
					const auto disp = static_cast<int32_t>(static_cast<int16_t>(fetch16(_m)));
					_out = load(base + static_cast<uint32_t>(disp));
					return true;
				}
			case 3:													// (d8,PC,Xn)
				{
					const auto base = pc(_m);
					_out = load(briefIndex(_m, base));
					return true;
				}
			case 4:													// #imm -- one word for .B and .W
				{
					const auto w = fetch16(_m);
					_out = _size == 1 ? (w & 0xff) : w;
					return true;
				}
			default:
				return false;
			}
		default:
			return false;
		}
	}

	// Set N and Z from a 32-bit result, clear V and C, leave X alone. This is
	// what MVS/MVZ do (CFPRM), and it is the shape every arithmetic addition
	// below will reuse.
	void setNZ(Machine& _m, const uint32_t _result)
	{
		auto sr = reg(_m, M68K_REG_SR);
		sr &= ~(g_ccrN | g_ccrZ | g_ccrV | g_ccrC);
		if(_result == 0)						sr |= g_ccrZ;
		if(static_cast<int32_t>(_result) < 0)	sr |= g_ccrN;
		setReg(_m, M68K_REG_SR, sr);
	}

	namespace
	{
		// MACSR bits (CFPRM Rev. 3, Table 1-5, and QEMU's cpu.h): bit 7 OMC,
		// bit 6 S/U, bit 5 F/I, bit 4 R/T. ❌ Until 8 Sep 2026 S/U was taken as
		// bit 4 here ("bit 4 S/U selects signed"), which is R/T: the frame
		// builder's two level chains run at MACSR 0xb0 (OMC|F/I|R/T) and 0x60
		// (S/U|F/I), and the swap read the first as "S/U" and the second as
		// plain -- so a `movclrl` in the second returned ACC[39:8] where the
		// chip returns the 16-bit-rounded ACC[39:24] in the LOW word (O9b).
		constexpr uint32_t g_macsrFractional = 0x20;	// F/I
		constexpr uint32_t g_macsrSigned     = 0x40;	// S/U (integer: 1 = unsigned; fractional: 16-bit rounding on the read-out)

		// One accumulator, 32 bits plus its 8-bit extensions. Musashi's
		// ColdFire state has no EMAC, so the port keeps its own -- four
		// accumulators and the two extension-byte registers.
		// Musashi's ColdFire state has no EMAC at all, so the whole unit lives
		// here: four accumulators, their extension bytes, and MACSR.
		// ⚠️ THE ACCUMULATOR IS 48 BITS AND HOLDS THE PRODUCT AT >>24, NOT >>32.
		// The first version kept a 32-bit accumulator and shifted each product
		// all the way down before adding it, which is right for ONE positive
		// product and off by one LSB for a SUBTRACT whose discarded low bits
		// are non-zero: floor(-floor(q/2^24)/2^8) is one less than
		// -floor(q/2^32). ✅ That is exactly the bit the M6c gate caught
		// (8 Sep 2026): the frame handler's `msacl` came out -15 where route
		// A had -16, the `spl` floor two instructions later turned it into
		// 1 instead of 0, and the sequencer's live nibble read 0x09 instead of
		// 0x08 on every write. Route A's model (QEMU's m68k EMAC plus
		// `tools/unicorn_emac_fractional.patch`) accumulates at >>24 and
		// shifts down by 8 only when the accumulator is READ.
		struct Emac
		{
			int64_t acc[4] = {};
			uint32_t macsr = 0;
			uint32_t mask = 0;		// the '&' form's address mask register
		};
		Emac g_emac;

		uint32_t macsr(Machine&) { return g_emac.macsr; }

		// Reading an accumulator OUT: the CFPRM's MOVCLR / MOVE-from-ACC
		// pseudocode (Rev. 3, chapter 6), every branch. ❌ Until 8 Sep 2026
		// this was route A's `get_macf` minus its S/U branch -- "fractional:
		// >> 8, no rounding because RT is clear in this firmware, no
		// saturation because OMC is clear too" -- and that comment was wrong
		// on both counts for the frame builder's level chain at
		// 0x4000ccae-0x4000ccfc, which runs with MACSR = 0x60. In FRACTIONAL
		// mode S/U is not signed/unsigned at all: it selects 16-BIT ROUNDING
		// on the read-out -- ACC[39:24], rounded by ACC[23:0], into Rx[15:0]
		// with Rx[31:16] zero. The firmware keeps the LOW words of two such
		// reads as a voice record's mode:level (`movclrl acc0,d3; swap d3;
		// movclrl acc1,d2; movew d2,d3`); with a plain >> 8 those words are
		// 0 and every voice renders at level zero (O9b, the silent output).
		constexpr uint32_t g_macsrOmc = 0x80, g_macsrRt = 0x10;
		uint32_t accRead(const uint32_t _n)
		{
			const auto macsr = g_emac.macsr;
			const auto acc = g_emac.acc[_n];				// ACC[47:0], sign-extended in an int64
			if(!(macsr & g_macsrFractional))
			{
				if(!(macsr & g_macsrSigned))				// signed integer mode
				{
					if(!(macsr & g_macsrOmc))
						return static_cast<uint32_t>(acc);
					const auto top = (acc >> 31) & 0x1ffff;		// ACC[47:31]
					if(top == 0 || top == 0x1ffff)
						return static_cast<uint32_t>(acc);
					return (acc >> 47) & 1 ? 0x80000000u : 0x7fffffffu;
				}
				if(!(macsr & g_macsrOmc))					// unsigned integer mode
					return static_cast<uint32_t>(acc);
				return ((acc >> 32) & 0xffff) == 0 ? static_cast<uint32_t>(acc) : 0xffffffffu;
			}
			// signed fractional mode
			auto saturate32 = [](const int64_t _v) -> uint32_t
			{
				const auto top = (_v >> 39) & 0x1ff;			// [47:39]
				if(top == 0 || top == 0x1ff)
					return static_cast<uint32_t>(_v >> 8);
				return (_v >> 47) & 1 ? 0x80000000u : 0x7fffffffu;
			};
			if(macsr & g_macsrSigned)
			{
				// 16-bit rounding: ACC[39:24] rounded by ACC[23:0] -> Rx[15:0]
				int64_t v = acc >> 24;							// keeps the sign from [47]
				const auto rem = acc & 0xffffff;
				if(rem > 0x800000 || (rem == 0x800000 && (v & 1)))
					++v;
				if(macsr & g_macsrOmc)
				{
					const auto top = (v >> 15) & 0x1ff;		// [47:39] of the rounded value = v[23:15]
					if(!(top == 0 || top == 0x1ff))
						return (v >> 23) & 1 ? 0x8000u : 0x7fffu;
				}
				return static_cast<uint32_t>(v & 0xffff);
			}
			if(macsr & g_macsrRt)
			{
				// 32-bit rounding: ACC[47:8] rounded by ACC[7:0]
				int64_t v = acc >> 8;
				const auto rem = acc & 0xff;
				if(rem > 0x80 || (rem == 0x80 && (v & 1)))
					++v;
				if(macsr & g_macsrOmc)
					return saturate32(v << 8);
				return static_cast<uint32_t>(v);
			}
			if(macsr & g_macsrOmc)
				return saturate32(acc);
			return static_cast<uint32_t>(acc >> 8);
		}

		// ... and writing one IN: route A's `move_mac`.
		void accWrite(const uint32_t _n, const uint32_t _v)
		{
			if(g_emac.macsr & g_macsrFractional)
				g_emac.acc[_n] = static_cast<int64_t>(static_cast<int32_t>(_v)) << 8;
			else if(g_emac.macsr & g_macsrSigned)
				g_emac.acc[_n] = static_cast<int64_t>(static_cast<int32_t>(_v));
			else
				g_emac.acc[_n] = static_cast<int64_t>(_v);
		}

		// The extension registers, exactly as route A's `get_mac_extf` /
		// `get_mac_exti` / `set_mac_extf` read and write them. Nothing this
		// firmware does reaches them on the M6c path; they are here so that a
		// path that DOES cannot quietly get a different answer.
		uint32_t accExtRead(const uint32_t _lo)
		{
			const auto a0 = static_cast<uint64_t>(g_emac.acc[_lo]);
			const auto a1 = static_cast<uint64_t>(g_emac.acc[_lo + 1]);
			if(!(g_emac.macsr & g_macsrFractional))
				return static_cast<uint32_t>(((a0 >> 32) & 0xffff) | ((a1 >> 16) & 0xffff0000));
			uint32_t v = static_cast<uint32_t>(a0 & 0x00ff);
			v |= static_cast<uint32_t>((a0 >> 32) & 0xff00);
			v |= static_cast<uint32_t>((a1 << 16) & 0x00ff0000);
			v |= static_cast<uint32_t>((a1 >> 16) & 0xff000000);
			return v;
		}

		void accExtWrite(const uint32_t _lo, const uint32_t _v)
		{
			int64_t res = g_emac.acc[_lo] & 0xffffffff00ll;
			res |= static_cast<int64_t>(static_cast<int16_t>(_v & 0xff00)) << 32;
			res |= _v & 0xff;
			g_emac.acc[_lo] = res;
			res = g_emac.acc[_lo + 1] & 0xffffffff00ll;
			res |= static_cast<int64_t>(static_cast<int32_t>(_v & 0xff000000)) << 16;
			res |= (_v >> 16) & 0xff;
			g_emac.acc[_lo + 1] = res;
		}
	}

	// The whole EMAC, as the MCF5445x does it and as the firmware's own
	// reciprocal tables prove (RTOS_FORK section 10.16): in FRACTIONAL mode a
	// signed product is taken and shifted LEFT ONE (the 2.62 product), and the
	// upper 40 bits are accumulated -- so `movclrl` of the result yields
	// (a * b) >> 31, not >> 32. `msac` SUBTRACTS, and which of the two it is
	// comes from bit 8 of the EXTENSION word, never from the opcode word.
	// THE WHOLE EMAC, and every field below came out of `m68k-elf-as
	// -mcpu=5475` / `objdump -m m68k:cfv4e`, never out of a reading of the
	// manual (standing rule 3). The listings are quoted beside each rule.
	//
	// ⚠️ THE FIRST VERSION OF THIS FUNCTION GOT FOUR FIELDS WRONG AND STILL
	// PASSED THE EMAC GATE, because every case the gate covered used acc0,
	// two data registers and no parallel load -- the one combination in which
	// all four defects are invisible (measured 8 Sep 2026, O6):
	//   1. the ACCUMULATOR NUMBER was read as ext bit 4 | ext bit 9; it is
	//      opcode bit 7 (LOW) and ext bit 4 (HIGH) -- and in the LOAD form
	//      the low bit is INVERTED (route A's `_emac_load_shim` carries the
	//      same `((~op >> 7) & 1)`, and objdump agrees: acc0 is `a498`,
	//      acc1 `a418`). The frame builder uses all four accumulators.
	//   2. an ADDRESS REGISTER source was read as the data register of the
	//      same number: `macl %a2,%d0` (`a08a`) multiplied d2, not a2.
	//   3. the two operand-half bits were applied to the wrong operands
	//      (`macw %d0u,%d1l` is ext 0x0040: bit 6 is the FIRST operand's).
	//   4. the parallel load handled ONLY (An)+, and the firmware's frame
	//      routine at 0x40003738 uses (An) and (d16,An) as well -- the
	//      (d16,An) form is SIX bytes and skipping its displacement word
	//      desynchronised the instruction stream, which is what actually
	//      stopped the port (an invented opcode two instructions later).
	// The gate now covers all four.
	Result emac(Machine& _m, const uint32_t _opcode)
	{
		// ---- the register moves: `1010 sss 1 d c eeeeee` -------------------
		// sss (bits 11-9) names the EMAC register: 0..3 = ACC0..3, 4 = MACSR,
		// 5 = ACCext01, 6 = MASK, 7 = ACCext23. Bit 8 is 1 for this family and
		// 0 for every MAC, which is what tells them apart. Bit 7 is the
		// direction (0 = <ea> into the EMAC register, 1 = out of it), bit 6
		// clears the accumulator on the way out (`movclr`), and bits 5-0 are
		// an <ea>: mode 0 = Dn, mode 1 = An, mode 7 reg 4 = #imm.
		//
		// ✅ m68k-elf-as -mcpu=5475:
		//     a900  movel %d0,%macsr        a90c  movel %a4,%macsr
		//     a93c 0000 0020  movel #32,%macsr     <- the frame handler's own,
		//                                             at 0x4000aeda
		//     a980  movel %macsr,%d0        ad81  movel %mask,%d1
		//     ab84  movel %accext01,%d4     af85  movel %accext23,%d5
		//     a100  movel %d0,%acc0         a180  movel %acc0,%d0
		//     a1c0  movclrl %acc0,%d0       a7c7  movclrl %acc3,%d7
		if(_opcode & 0x0100)
		{
			const uint32_t which = (_opcode >> 9) & 7;
			const bool out = (_opcode & 0x0080) != 0;
			const bool clear = (_opcode & 0x0040) != 0;
			const uint32_t mode = (_opcode >> 3) & 7;
			const uint32_t rn = _opcode & 7;

			const auto readEa = [&]() -> uint32_t
			{
				if(mode == 0)	return reg(_m, dReg(rn));
				if(mode == 1)	return reg(_m, aReg(rn));
				if(mode == 7 && rn == 4)
				{
					const uint32_t hi = fetch16(_m);
					return (hi << 16) | fetch16(_m);
				}
				return 0;
			};
			if(mode > 1 && !(mode == 7 && rn == 4))
				return Result::Unhandled;			// no other <ea> is reached; be loud

			if(!out)
			{
				const auto v = readEa();
				switch(which)
				{
				case 4: g_emac.macsr = v; break;
				case 5: accExtWrite(0, v); break;
				case 6: g_emac.mask = v; break;
				case 7: accExtWrite(2, v); break;
				default: accWrite(which, v); break;
				}
				return Result::Handled;
			}
			uint32_t v = 0;
			switch(which)
			{
			case 4: v = g_emac.macsr; break;
			case 5: v = accExtRead(0); break;
			case 6: v = g_emac.mask; break;
			case 7: v = accExtRead(2); break;
			default:
				v = accRead(which);
				if(clear)
					g_emac.acc[which] = 0;
				break;
			}
			setReg(_m, mode == 1 ? aReg(rn) : dReg(rn), v);
			return Result::Handled;
		}

		// ---- MAC / MSAC ----------------------------------------------------
		// The extension word is common to both forms:
		//     bit 11 size (1 = long), bits 10-9 scale, bit 8 SUBTRACT,
		//     bit 7 upper half of Rx, bit 6 upper half of Ry, bit 5 the '&'
		//     mask form, bit 4 the accumulator's HIGH bit.
		// ✅ `macw %d0u,%d1l,%acc0` is `a200 0040` and `macw %d0l,%d1u,%acc0`
		// is `a200 0080`, which is what pins bit 6 to the FIRST operand;
		// `macl %d0,%d1,<<,%acc2` is `a200 0a10`, which pins the scale.
		const uint16_t ext = fetch16(_m);
		const uint32_t mode = (_opcode >> 3) & 7;
		const bool subtract = (ext & 0x0100) != 0;			// ⚠️ EXTENSION word,
															// never the opcode word
		const bool wordOp = (ext & 0x0800) == 0;
		const bool upperRx = (ext & 0x0080) != 0;
		const bool upperRy = (ext & 0x0040) != 0;
		if(ext & 0x0020)		// the '&' form ANDs the loaded value with MASK
			return Result::Unhandled;			// not reached by this firmware; be loud
		if((ext >> 9) & 3)		// a scale factor (<< or >>) -- likewise
			return Result::Unhandled;

		uint32_t rx4 = 0, ry4 = 0, accN = 0;
		bool load = false, rwIsA = false;
		uint32_t rw = 0, an = 0, ea = 0;
		if(mode <= 1)
		{
			// ✅ Plain: `a003 0810 macl %d3,%d0,%acc2`, `a08a 0800 macl
			// %a2,%d0,%acc1`, `a040 0800 macl %d0,%a0,%acc0`. Rx is opcode
			// bits 11-9 with bit 6 as its A/D flag; Ry is bits 3-0, so the
			// <ea> mode field being 1 IS Ry's A/D flag.
			rx4 = ((_opcode >> 9) & 7) | (((_opcode >> 6) & 1) << 3);
			ry4 = _opcode & 0x0f;
			accN = ((_opcode >> 7) & 1) | (((ext >> 4) & 1) << 1);
		}
		else if(mode >= 2 && mode <= 5)
		{
			// ✅ With a parallel load: `a498 1800 macl %d0,%d1,%a0@+,%d2,%acc0`.
			// Opcode bits 11-9 are Rw (the load's destination) with bit 6 its
			// A/D flag, bits 5-3/2-0 are the load's <ea>, and BOTH multiply
			// sources move into the extension word: bits 15-12 = Rx, bits 3-0
			// = Ry, each 4-bit with 8..15 meaning An.
			//
			// ⚠️ THE ACCUMULATOR'S LOW BIT IS INVERTED HERE and this is not a
			// guess: objdump reads `a498 1800` as acc0 and `a418 1800` as
			// acc1, and route A's `_emac_load_shim` carries the same
			// `((~op >> 7) & 1)`. Both readings are binutils', so a chip that
			// disagreed would put every frame's arithmetic in the wrong
			// accumulator in BOTH emulators -- what would falsify it is a
			// hardware capture, which nobody has.
			load = true;
			rw = (_opcode >> 9) & 7;
			rwIsA = (_opcode & 0x0040) != 0;
			an = _opcode & 7;
			rx4 = (ext >> 12) & 0x0f;
			ry4 = ext & 0x0f;
			accN = ((~_opcode >> 7) & 1) | (((ext >> 4) & 1) << 1);

			// The parallel load is ALWAYS a longword (route A's shim says so
			// in as many words), and only these four modes exist.
			const auto base = reg(_m, aReg(an));
			switch(mode)
			{
			case 2: ea = base; break;
			case 3: ea = base; setReg(_m, aReg(an), base + 4); break;
			case 4: ea = base - 4; setReg(_m, aReg(an), ea); break;
			default:
				{
					const auto d16 = static_cast<int16_t>(fetch16(_m));
					ea = base + static_cast<uint32_t>(static_cast<int32_t>(d16));
				}
				break;
			}
		}
		else
		{
			return Result::Unhandled;
		}

		const auto readOperand = [&_m](const uint32_t _r4)
		{
			return (_r4 & 8) ? reg(_m, aReg(_r4 & 7)) : reg(_m, dReg(_r4 & 7));
		};
		const uint32_t rawX = readOperand(rx4);
		const uint32_t rawY = readOperand(ry4);

		// The operands. ✅ Route A's `gen_mac_extract_word`: in FRACTIONAL mode
		// a 16-bit half is placed in the HIGH half of a 32-bit value (so it is
		// multiplied as a 1.31 fraction); in signed integer mode it is
		// sign-extended, and in unsigned integer mode zero-extended.
		const bool fi = (macsr(_m) & g_macsrFractional) != 0;
		const bool su = (macsr(_m) & g_macsrSigned) != 0;
		const auto half = [fi, su](const uint32_t _v, const bool _upper) -> uint32_t
		{
			if(fi)
				return _upper ? (_v & 0xffff0000u) : (_v << 16);
			if(su)
				return _upper ? static_cast<uint32_t>(static_cast<int32_t>(_v) >> 16)
							  : static_cast<uint32_t>(static_cast<int32_t>(static_cast<int16_t>(_v)));
			return _upper ? (_v >> 16) : (_v & 0xffffu);
		};
		const uint32_t opX = wordOp ? half(rawX, upperRx) : rawX;
		const uint32_t opY = wordOp ? half(rawY, upperRy) : rawY;

		// ✅ Route A's three multiply helpers, verbatim in shape:
		//   fractional (`macmulf`, as patched by
		//   tools/unicorn_emac_fractional.patch): a SIGNED product shifted
		//   LEFT one into 1.63 and then >> 24 -- the accumulator's own
		//   alignment, EIGHT BITS FINER than what `movclrl` returns. ⚠️ It is
		//   the >>24 that matters: shifting each product all the way to >>32
		//   before accumulating loses a bit of the subtraction (see the Emac
		//   comment above, and the M6c gate that caught it).
		//   signed integer (`macmuls`): the product truncated to 48 bits.
		//   unsigned integer (`macmulu`): the product masked to 40 bits.
		int64_t addend;
		if(fi)
		{
			int64_t product = static_cast<int64_t>(static_cast<int32_t>(opX))
							* static_cast<int64_t>(static_cast<int32_t>(opY));
			product <<= 1;
			addend = product >> 24;			// MACSR's RT (round) bit is clear here
		}
		else if(su)
		{
			const auto product = static_cast<int64_t>(
				static_cast<uint64_t>(opX) * static_cast<uint64_t>(opY));
			addend = (product << 24) >> 24;
		}
		else
		{
			addend = static_cast<int64_t>(
				(static_cast<uint64_t>(opX) * static_cast<uint64_t>(opY)) & ((1ull << 40) - 1));
		}

		int64_t acc = g_emac.acc[accN];
		acc = subtract ? acc - addend : acc + addend;
		// `macsatf` with OMC clear: sign-extend from 48 bits (it also sets V
		// and the per-accumulator PAV bit, which nothing here reads).
		if(fi)
			acc = (acc << 16) >> 16;
		g_emac.acc[accN] = acc;

		// The load half. ⚠️ Route A writes Rw as a DATA register whatever the
		// A/D bit says; the bit is 0 at every site this firmware reaches
		// (`a090`, `a2a8`, `a099`, `a019` all have it clear), so the two
		// emulators agree today and would diverge only on a form neither has
		// met. The bit is honoured here because the encoding says so.
		if(load)
		{
			const uint32_t loaded = (static_cast<uint32_t>(_m.read16(ea)) << 16) | _m.read16(ea + 2);
			setReg(_m, rwIsA ? aReg(rw) : dReg(rw), loaded);
		}
		return Result::Handled;
	}

	Result execute(Machine& _m, const uint32_t _opcode)
	{
		// ---- MVS / MVZ ---------------------------------------------------
		// 0111 rrr 1 oo eeeeee, oo = 00 MVS.B, 01 MVS.W, 10 MVZ.B, 11 MVZ.W.
		// ✅ The two the boot reaches at 0x4000043e/0x40000440 disassemble as
		// `mvzw %d1,%d1` and `mvzw %d0,%d0` under m68k:cfv4e, which pins the
		// field layout; the sizes and the sign/zero split are CFPRM's.
		if((_opcode & 0xf100) == 0x7100)
		{
			const uint32_t dx     = (_opcode >> 9) & 7;
			const uint32_t opmode = (_opcode >> 6) & 3;
			const uint32_t mode   = (_opcode >> 3) & 7;
			const uint32_t rn     = _opcode & 7;
			const uint32_t size   = (opmode == 0 || opmode == 2) ? 1 : 2;

			uint32_t src = 0;
			if(!readEa(_m, mode, rn, size, src))
				return Result::Unhandled;

			uint32_t v;
			if(opmode < 2)		// MVS: sign-extend
				v = size == 1
					? static_cast<uint32_t>(static_cast<int32_t>(static_cast<int8_t>(src)))
					: static_cast<uint32_t>(static_cast<int32_t>(static_cast<int16_t>(src)));
			else				// MVZ: zero-extend
				v = size == 1 ? (src & 0xff) : (src & 0xffff);

			setReg(_m, dReg(dx), v);
			setNZ(_m, v);
			return Result::Handled;
		}

		// ---- MOV3Q ---------------------------------------------------------
		// 1010 iii 1 01 eeeeee -- a 3-bit immediate (0 encodes -1) to a
		// longword destination. ✅ `a340` assembles as `mov3ql #1,%d0`.
		//
		// ❌❌ THIS RETRACTS "only Dn is reached by this firmware". The
		// project load reaches `mov3q #-1,%a0@+` (`a158`) at 0x4009d8d0, in a
		// run of eight that clears a structure, and refusing it raised a real
		// line-A exception: the firmware's own handler printed
		// `EXCEPTION / VEC:0A / ADDR:4009D8D0` over the panel port and
		// executed `halt`. Measured 8 Sep 2026. ⚠️ Route A needs no shim for
		// this -- Unicorn's m68k implements MOV3Q natively -- so the only
		// machine that can be wrong here is this one, and "route A does not
		// have it either" is not evidence.
		//
		// Semantics are QEMU's `mov3q` (route A's own engine, so the oracle):
		// the condition codes are set from the 32-bit VALUE for every
		// destination, An included, and the destination is written LONG.
		if((_opcode & 0xf1c0) == 0xa140)
		{
			const uint32_t imm3 = (_opcode >> 9) & 7;
			const auto v = static_cast<uint32_t>(imm3 == 0 ? -1 : static_cast<int32_t>(imm3));
			const uint32_t mode = (_opcode >> 3) & 7;
			const uint32_t rn   = _opcode & 7;
			setNZ(_m, v);
			if(!writeEaLong(_m, mode, rn, v))
				return Result::Unhandled;
			return Result::Handled;
		}

		// ---- SATS ----------------------------------------------------------
		// `0100 1100 1000 0rrr` -- ✅ `m68k-elf-as -mcpu=5475` gives 4c80 /
		// 4c81 / 4c87 for %d0 / %d1 / %d7, and objdump reads the firmware's
		// own 4c80 at 0x4000346a as `satsl %d0`.
		//
		// The site is the per-frame EMAC routine (0x400031a0) that the frame
		// handler's completion state 5 calls, so it is on the M6c path and
		// nowhere near the boot: the port ran O1..O5 and the whole project
		// load without ever meeting it, then stopped dead there the moment
		// the frame clock had something to do (measured 8 Sep 2026, O6 --
		// "unimplemented opcode 4c80", 0 frames delivered).
		//
		// ✅ Semantics measured in ROUTE A'S ENGINE (six cases,
		// `tools/ot_emu/test_emac.cpp` carries them): with V set, a result
		// whose sign bit is CLEAR saturates to 0x80000000 and one whose sign
		// bit is SET saturates to 0x7fffffff -- the end of the range the
		// arithmetic wrapped away from; with V clear the value is untouched.
		//
		// ⚠️ THE FLAGS DISAGREE WITH THE MANUAL AND THIS FOLLOWS ROUTE A.
		// The CFPRM says N and Z are set from the result and V and C cleared.
		// Route A's engine updates **N only** -- a pre-set Z survives a
		// non-zero result and V/C are left as they were. Route A is the
		// oracle, and at the only site the firmware reaches, nothing between
		// the `sats` and the next flag-setting instruction reads the CCR
		// (three `movclrl`s and a `movel`). What would falsify it: a firmware
		// site that branches on Z or V after a SATS; then the manual wins and
		// both emulators are wrong.
		if((_opcode & 0xfff8) == 0x4c80)
		{
			const uint32_t rn = _opcode & 7;
			uint32_t v = reg(_m, dReg(rn));
			auto sr = reg(_m, M68K_REG_SR);
			if(sr & g_ccrV)
				v = (v & 0x80000000u) ? 0x7fffffffu : 0x80000000u;
			sr = (sr & ~g_ccrN) | ((v & 0x80000000u) ? g_ccrN : 0u);
			setReg(_m, M68K_REG_SR, sr);
			setReg(_m, dReg(rn), v);
			return Result::Handled;
		}

		// ---- ISA_C: BITREV / BYTEREV / FF1 ---------------------------------
		// `0000 0ooo 1100 0rrr`: 0x00C0 bitrev, 0x02C0 byterev, 0x04C0 ff1,
		// each ORed with the data register.
		//
		// ❌ THIS RETRACTS O2's NOTE that "byterev and ff1 are not V4e ...
		// nothing needs them". The assembler does refuse them for -mcpu=5475
		// and objdump prints `.short 0x04c2` rather than decoding it -- but
		// the FIRMWARE CONTAINS THEM and reaches one at 0x4004098e, in the
		// task-creation path, which is where the O4 run loop stopped
		// (measured 7 Sep 2026). A toolchain that will not assemble an opcode
		// is not evidence the part lacks it; the image is.
		//
		// ✅ The semantics are route A's `emu_bringup._isa_c_shim`, which is
		// the oracle: ff1 counts LEADING ZEROS and sets N and Z from the
		// SOURCE (not the result) with V and C cleared; bitrev and byterev
		// leave the condition codes alone.
		if((_opcode & 0xfff8) == 0x00c0 || (_opcode & 0xfff8) == 0x02c0 || (_opcode & 0xfff8) == 0x04c0)
		{
			const uint32_t rn = _opcode & 7;
			uint32_t v = reg(_m, dReg(rn));
			switch(_opcode & 0xfff8)
			{
			case 0x00c0:					// bitrev: reverse all 32 bits
				{
					uint32_t out = 0;
					for(uint32_t i = 0; i < 32; ++i)
						out |= ((v >> i) & 1u) << (31 - i);
					v = out;
				}
				break;
			case 0x02c0:					// byterev: reverse the four bytes
				v = ((v & 0x000000ffu) << 24) | ((v & 0x0000ff00u) << 8)
				  | ((v & 0x00ff0000u) >> 8) | ((v & 0xff000000u) >> 24);
				break;
			default:						// ff1: leading-zero count
				{
					auto sr = reg(_m, M68K_REG_SR) & ~0x0fu;
					if(v & 0x80000000u)		// N and Z from the SOURCE
						sr |= g_ccrN;
					if(v == 0)
						sr |= g_ccrZ;
					setReg(_m, M68K_REG_SR, sr);
					uint32_t bits = 0;
					for(uint32_t t = v; t; t >>= 1)
						++bits;
					v = 32 - bits;
				}
				break;
			}
			setReg(_m, dReg(rn), v);
			return Result::Handled;
		}

		// ---- the EMAC ------------------------------------------------------
		// The gate this port must pass before anything it computes is
		// trusted: `tools/ot_emu/test_emac.cpp`, and the hardware semantics it
		// encodes are docs/RTOS_FORK.md section 10.16 -- a week lost to three
		// defects in Unicorn's version of exactly this.
		//
		// ✅ Encodings from `m68k-elf-as -mcpu=5475`:
		//     a900            movel %d0,%macsr
		//     a1c0            movclrl %acc0,%d0
		//     a383            movel %acc1,%d3
		//     ab84            movel %accext01,%d4
		//     a200 0800       macl  %d0,%d1,%acc0
		//     a200 0900       msacl %d0,%d1,%acc0        (ext bit 8 = subtract)
		//     a418 1800       macl  %d0,%d1,%a0@+,%d2,%acc1
		//     a200 0080       macw  %d0l,%d1u,%acc0
		//     a200 0250       macw  %d0u,%d1l,<<,%acc2
		if((_opcode & 0xf000) == 0xa000)
			return emac(_m, _opcode);

		return Result::Unhandled;
	}
}
