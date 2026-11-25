# OCTA303 v8.2 (10 Nov 2026): v7.9 plus the v8.1 savings that change no sample

v8.1 (branch `octa303-v81`, images ACIDV87/87A/87B) froze the sequencer on Marko's MK1 after one trig, and stuttered with
CUT/RES/ENV high (worse with dEVILish). Under the port it plays (play_gate.py passes on v8.1 too: the port counts
instructions and waits for the work, so it cannot see a CPU overload; TRAPS.md trap-blind-instrument). What differs, measured
in the cfsim model (cost_grid.log, cache_lines.log): v8.x costs ~+50 % instructions a voice, and its ladder tables give a
data working set of up to 17 KB a voice over 48 calls (the D-cache is 16 KB) against 3-5 KB for v7.9. Inferred, not
measured on the unit: the overload is the cause.

v8.2 = v7.9's engine (ladder, tables, sound) + three skips taken from v8.1, re-applied by hand:
- P11 (from 517daa36): VCA closed and the chain after it settled -> the same output word, the chain not run;
- P2 (from dda993a9): o3_ctrl's pitch block, env-mod depth and CUTB/ENVS glide steps skipped when their inputs are the last
  step's; o3_params' dEVILish block skipped when the twelve bytes and the source are unchanged. v8.1's GCOMP/W2 cache is NOT
  ported: v7.9's GCOMP reads O3_LG by the cutoff;
- the pedal's x5 as 4x + x (gen_tables asserts DIST_GAIN == 5). v8.1's EMAC pair is NOT ported: v7.9 stays EMAC-free.

Checks (cloud): test_octa303 125/125 (test_octa303_v82.log); v7.9 and v8.2 side by side, every output word equal, 4
scenarios x 1200 frames (v79_vs_v82.log: -26 % cycles a frame between notes, -18 % with dEVILish, -2 % notes back to back);
an independent review fuzzed 16 x 1200 frames (knobs, SETUP, dEVILish on/off/moved, split calls, STOP/PLAY): output and
state identical; play_gate.py: the project plays, 36,333 instructions a frame (v7.9 36,640; v8.1 40,756).
Written by Claude (Anthropic).
