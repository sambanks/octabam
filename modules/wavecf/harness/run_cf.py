"""engine.c built for the ColdFire, run under the patched Unicorn on ref_wavecf.py's stream.
usage: run_cf.py engine.elf engine.bin table.bin cmds.bin out.i32
Writes the samples big-endian; prints instructions a sample (eng_render) and the worst block."""
import bisect, os, re, struct, subprocess, sys
EMAC_LIB = os.path.join(os.path.dirname(__file__), "../../../.venv/lib/unicorn-emac")
if not os.path.isdir(EMAC_LIB):          # stock Unicorn halves every fractional EMAC product: its answer would be wrong, not slow
    sys.exit("run_cf.py needs the EMAC-fixed Unicorn at .venv/lib/unicorn-emac (make emu-unicorn)")
os.environ.setdefault("LIBUNICORN_PATH", EMAC_LIB)
from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_BLOCK
from unicorn.m68k_const import UC_M68K_REG_A7

elf, binf, tablef, cmdsf, outf = sys.argv[1:6]
CODE, TABLE, ENG, OUT, STACK, RET = 0x10000, 0x100000, 0x200000, 0x220000, 0x3f0000, 0x300000
syms = {m.group(2): int(m.group(1), 16) for m in re.finditer(r"([0-9a-f]+) T (\w+)", subprocess.check_output(["m68k-elf-nm", elf], text=True))}
starts = sorted(int(m.group(1), 16) for m in re.finditer(r"^\s+([0-9a-f]+):\t", subprocess.check_output(["m68k-elf-objdump", "-d", elf], text=True), re.M))

uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
uc.mem_map(0, 0x400000)
uc.mem_write(CODE, open(binf, "rb").read())
uc.mem_write(TABLE, open(tablef, "rb").read())
uc.mem_write(RET, b"\x4e\x71")
PROLOGUE = 0x300100          # MACSR fractional (0x20), ACC0 clear: what the machine's renderer sets on entry
uc.mem_write(PROLOGUE, bytes.fromhex("a93c00000020" "a13c00000000"))
uc.emu_start(PROLOGUE, PROLOGUE + 12)
count = [0]
def on_block(uc, addr, size, _):
    count[0] += bisect.bisect_left(starts, addr + size) - bisect.bisect_left(starts, addr)
uc.hook_add(UC_HOOK_BLOCK, on_block)

def call(fn, *args):
    sp = STACK - 4 * len(args) - 4
    uc.mem_write(sp, struct.pack(">I" + "I" * len(args), RET, *[a & 0xffffffff for a in args]))
    uc.reg_write(UC_M68K_REG_A7, sp)
    count[0] = 0
    uc.emu_start(fn, RET)
    return count[0]

call(syms["wcf_init"], ENG, TABLE)
data = open(cmdsf, "rb").read()
pos, out, blocks, total, worst = 0, open(outf, "wb"), 0, 0, 0
note_n = [0, 0]; knob_n = [0, 0]
while pos < len(data):
    n = struct.unpack_from(">I", data, pos)[0]; pos += 4
    for _ in range(n):
        op, a, b, c = struct.unpack_from(">IIII", data, pos); pos += 16
        if op == 0: call(syms["eng_pos"], ENG, a)
        elif op == 1: call(syms["eng_on"], ENG, a, b, c)
        elif op == 2: call(syms["eng_off"], ENG, a)
        elif op == 4: note_n[0] += call(syms["wcf_note"], ENG, a, b, c); note_n[1] += 1
        elif op == 5: knob_n[0] += call(syms["wcf_knobs"], ENG, a, b, c); knob_n[1] += 1
        elif op == 7: call(syms["wcf_scale"], ENG, a)
        elif op == 3: call(syms["eng_adsr"], ENG, a, b)
        elif op == 6: call(syms["wcf_setup"], ENG, a & 0xff, (a >> 8) & 0xff, (a >> 16) & 0xff, (a >> 24) & 0xff, b & 0xff, (b >> 8) & 0xff)
    r = call(syms["eng_render"], ENG, OUT, 16)
    total += r; worst = max(worst, r)
    out.write(bytes(uc.mem_read(OUT, 64)))
    blocks += 1
out.close()
extra = (f"  wcf_note {note_n[0] / note_n[1]:.0f} instr/call" if note_n[1] else "") + (f"  wcf_knobs {knob_n[0] / knob_n[1]:.0f} instr/call" if knob_n[1] else "")
if extra: print(extra.strip())
print(f"blocks {blocks}  eng_render {total / (16 * blocks):.1f} instr/sample mean, worst block {worst / 16:.1f}/sample")
