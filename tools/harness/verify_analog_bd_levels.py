#!/usr/bin/env python3
"""Compare actual shipped 808/909 defaults with fixed-window hit RMS."""
import math
import pathlib
import re
import bd808
import bd909
from analog_bassdrum import DEFAULTS


def main():
    source=(bd909.ROOT/'modules/analog-bassdrum/engine.c').read_text()
    defaults=[int(x) for x in re.search(r'ab_mc_defaults\[AB_PARAMS\] = \{([^}]+)',source)[1].split(',')]
    assert defaults==DEFAULTS, 'level gate defaults drifted from firmware'
    levels=[]
    out=bd909.ROOT/'out/analog-bassdrum/levels';out.mkdir(parents=True,exist_ok=True)
    for model,module in enumerate((bd808,bd909)):
        symbols=module.build();knobs=defaults.copy();knobs[6]=model
        samples=module.render(symbols,bd909.hits(knobs,seconds=2,at=(0,)), 'matched-default')[0]
        rms=lambda n: 10*math.log10(sum(v*v for v in samples[:n])/n)
        peak=20*math.log10(max(map(abs,samples)))
        levels.append((rms(4410),rms(22050)))
        assert -9 < peak < -1, ('default output/headroom',model,peak)
        assert -21 < levels[-1][1] < -19, ('nominal hit level',model,levels[-1])
        bd909.wav(out/f'{808 if model==0 else 909}-default.wav',samples)
        print(f'{808 if model==0 else 909}: peak {peak:.2f} dBFS, '
              f'100 ms RMS {levels[-1][0]:.2f}, 500 ms RMS {levels[-1][1]:.2f} dBFS')
    assert abs(levels[0][0]-levels[1][0])<.5, ('attack/body level mismatch',levels)
    assert abs(levels[0][1]-levels[1][1])<.2, ('hit energy mismatch',levels)
    print('PASS actual defaults: 100 ms RMS within 0.5 dB, 500 ms RMS within 0.2 dB')

if __name__=='__main__': main()
