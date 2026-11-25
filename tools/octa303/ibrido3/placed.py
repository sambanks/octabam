"""The hybrid's DSP half as an image placed it: P words of OCTA303 SEAM against an assembly of o3h.asm at the same
address with the ptable literal set to where the build put the table and p:( read as x:(; the table's words in the
curve bank record; the seam's jsr.  usage (worktree root): placed.py image.bin A|B p_addr table_addr"""
import os, pathlib, subprocess, sys, tempfile
sys.path.insert(0, 'tools/build')
import dsp_modmap as M
img = pathlib.Path(sys.argv[1]).read_bytes(); tag = sys.argv[2]; pa = int(sys.argv[3], 16); ta = int(sys.argv[4], 16)
HERE = os.path.dirname(os.path.abspath(__file__))
pay = {t: (va, ln) for t, va, ln in M.payloads_of(img)}[tag]
mods, b = M.modules(img, *pay)
def word(space, a):
    for sp, addr, cnt, data in mods:
        if sp == space and addr <= a < addr + cnt: return M.w24(b, data + 3 * (a - addr))
    return None
src = open('modules/octa303-seam/o3h.asm').read().replace('$fab1e0', '$%x' % ta).replace('p:(', 'x:(')
with tempfile.TemporaryDirectory() as d:
    open(d + '/s.asm', 'w').write(src)
    r = subprocess.run(['vendor/dsp56300/build/source/dsp_host/dsp_asm', '-in', d + '/s.asm', '-org', '%x' % pa, '-out', d + '/s.bin'], capture_output=True, text=True)
    bb = open(d + '/s.bin', 'rb').read()
mine = [bb[i] | bb[i + 1] << 8 | bb[i + 2] << 16 for i in range(0, len(bb), 3)]
diff = [i for i, w in enumerate(mine) if word(0, pa + i) != w]
print('payload %s: %d words at P:0x%05x, %d differ from o3h.asm assembled there' % (tag, len(mine), pa, len(diff)))
sys.path.insert(0, 'tools/octa303'); sys.path.insert(0, HERE); import gen_o3h as G
tab = [int(v) & 0xFFFFFF for v in G.ptable]           # v9.1: pin 6, FM's, the clip's and DRIV's tables
td = [i for i, v in enumerate(tab) if word(1, ta + i) != v]
print('  table: %d words at X:0x%05x, %d differ' % (len(tab), ta, len(td)))
seam = {'A': 0x39C, 'B': 0x1A2}[tag]
print('  seam P:0x%03x: %06x %06x (jsr >0x%05x expected: 0bf080 %06x)' % (seam, word(0, seam), word(0, seam + 1), pa, pa))
