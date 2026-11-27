"""Forms of a dsp_asm source with no stock site and no CHIP.md register row, by sam/main's tools/build/dsp_forms.py
definition (assembled at P:$800, decoded by dsp56kDisassemble).  usage: forms2.py <dsp_forms.py> <CHIP.md> <worktree> src.asm"""
import importlib.util, pathlib, sys
spec = importlib.util.spec_from_file_location('df', sys.argv[1]); df = importlib.util.module_from_spec(spec); spec.loader.exec_module(df)
W = pathlib.Path(sys.argv[3])
df.DIS = W / 'vendor/dsp56300/build/source/disassemble/dsp56kDisassemble'
df.ASM = W / 'vendor/dsp56300/build/source/dsp_host/dsp_asm'
stock = df.stock_forms([W / 'out/dsp/payload_A.asm', W / 'out/dsp/payload_B.asm'])
rows = df.register_rows(sys.argv[2])
words, err = df.assemble_words(sys.argv[4])
if err: sys.exit(err)
mine = df.disassemble(words, '800')
nos = {f: ex for f, ex in mine.items() if f not in stock}
for f, ex in sorted(nos.items()):
    print('%-5s %-40s e.g. %s' % ('ROW' if f in rows else 'NEW', f, ex.split(';')[0].strip()))
print('%d forms, %d without a stock site, %d of them with no register row' % (len(mine), len(nos), sum(f not in rows for f in nos)))
