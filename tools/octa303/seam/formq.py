"""Ask whether instruction texts have a stock site: formq.py <dsp_forms.py> <CHIP.md> <worktree> 'insn' ...
Each instruction is assembled alone (labels: write them as a number) and decoded."""
import importlib.util, pathlib, sys
spec = importlib.util.spec_from_file_location('df', sys.argv[1]); df = importlib.util.module_from_spec(spec); spec.loader.exec_module(df)
W = pathlib.Path(sys.argv[3])
df.DIS = W / 'vendor/dsp56300/build/source/disassemble/dsp56kDisassemble'
df.ASM = W / 'vendor/dsp56300/build/source/dsp_host/dsp_asm'
stock = df.stock_forms([W / 'out/dsp/payload_A.asm', W / 'out/dsp/payload_B.asm'])
rows = df.register_rows(sys.argv[2])
for ins in sys.argv[4:]:
    words, err = df.assemble_text('qzq9:\n        ' + ins + '\n')
    if err: print('ERR  %-34s %s' % (ins, err)); continue
    f = df.disassemble(words, '800')
    for k, ex in f.items():
        print('%-4s %-34s -> %s   (%s)' % ('OK' if k in stock else 'ROW' if k in rows else 'NEW', ins, k, ex.split(';')[0][8:].strip()))
