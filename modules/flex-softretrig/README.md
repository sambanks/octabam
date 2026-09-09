# flex-softretrig

See the manifest docstring and RTOS_FORK 10.47. Port-scored, unflashed.

Score any change to the cave in the port before a flash:

    out/emu/ot_emu --image <image with the cave> --card n128fix_card.img \
      --set OCTABAM --project RECT --sequencer --internal-clock --dsp \
      --frames 21000 --main-level 64 --load-ms 20000 --audio-in tone1k.wav \
      --pre-roll 200 --block-dump n128.dump
    python3 tools/scratch/loopcompare.py n128.dump 82687.5     # every pair: shift +0
    (g65fix, 42000 frames, 161280)                             # unchanged: shift +0

Threshold 64 samples is `cmpil #64` twice in the source; the pinned bytes
carry it, so change both and re-pin.
