"""TRACK PATTERNS -- each track plays its own pattern of the playing bank,
clip style: a change is queued per track and lands at the end of that
track's own loop. Everything else (tempo, the Part's machines, samples and
FX, scenes, MASTER LENGTH, chains) stays stock.

How: where the sequencer hands a track's step to the step handler
(trackpattern.c, adapter.c), the pattern argument is replaced by the
track's own; where the per-track advance compares the track's counter with
its length, the length comes from that pattern. A track with no change set
gets exactly what stock passes.

The gesture: hold [TRACK n], hold [PATTERN], press [TRIG k] queues pattern
k for track n (M1..M8 in MIDI mode); without a TRACK key held, PATTERN +
TRIG is stock's global change, which clears every override. The trig LEDs
of a current track on its own pattern blink (README.md).

  0x400a2d76  audio tick: the pattern argument of 0x4009d1e8
  0x400a39c0  MIDI tick: the pattern argument of 0x4009cf4c
  0x4009dc8c  audio rebuild after an edit: the pattern argument (8, padded)
  0x4009e3e2  MIDI rebuild: the same (8, padded)
  0x400a3d88  audio per-track advance: the length the counter wraps at
  0x400a3ea8  MIDI per-track advance: the same
  0x40056b50  PATTERN layer's trig press: the gesture, with a TRACK key held
  0x4007e9b6  LED dispatcher, after a page's LED callback: the trig LEDs of a
              track on its own pattern (blink in GRID REC, its trigs outside,
              its pattern in the PATTERN layer while TRACK is held)

Every site was read from the contributor's original 1.40C
(INVESTIGATION.md section 4); each `expect` is the stock instructions the
detour displaces.
"""
from remix.schema import Category, Evidence, Level, Detour, Kind, Linked, Module, Gate

H = bytes.fromhex

MODULE = Module(
    name="trackpatterns",
    key="TRACK PATTERNS",
    kind=Kind.CF_PATCH,
    category=Category.MACHINES,
    author="pgstath", author_url="https://github.com/pgstath",
    evidence=(Evidence(Level.UNIT, unit="MKII", who="pgstath", image="OCTABAM3", date="2026-10-21",
        note="(remix trackpatterns), 21 Oct 2026: functional tests and trig LEDs passed (contributor's report)"),),
    doc="Each track plays its own pattern of the playing bank; changes land at the track's loop end.",
    linked=(Linked("trackpatterns", "modules/trackpatterns/trackpatterns.s", cpu="5475", dram=True),),
    detours=(
        Detour(0x400a2d76, H("2f032f2f0056"),
               "trackpatterns", "tp_audio_tick", "audio tick: the track's own pattern", kind="jmp"),
        Detour(0x400a39c0, H("2f042f032f07"),
               "trackpatterns", "tp_midi_tick", "MIDI tick: the track's own pattern", kind="jmp"),
        Detour(0x4009dc8c, H("7939800065be2f04"),
               "trackpatterns", "tp_audio_rebuild", "audio rebuild: the track's own pattern", kind="jmp", pad_to=8),
        Detour(0x4009e3e2, H("7539800065be2f02"),
               "trackpatterns", "tp_midi_rebuild", "MIDI rebuild: the track's own pattern", kind="jmp", pad_to=8),
        Detour(0x400a3d88, H("73817100b081"),
               "trackpatterns", "tp_audio_length", "audio advance: the length of the track's own pattern", kind="jmp"),
        Detour(0x400a3ea8, H("73817100b081"),
               "trackpatterns", "tp_midi_length", "MIDI advance: the length of the track's own pattern", kind="jmp"),
        Detour(0x40056b50, H("4a79460d1ab6"),
               "trackpatterns", "tp_pattern_key", "PATTERN + TRIG with a TRACK key held: that track's pattern", kind="jmp"),
        Detour(0x4007e9b6, H("2f024e90588f"),
               "trackpatterns", "tp_led_pass", "LED pass: the trig LEDs of a track on its own pattern", kind="jmp"),
    ),
    gates=(Gate("modules/trackpatterns/verify.py", remix_arg=False),),
)
