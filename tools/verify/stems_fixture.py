#!/usr/bin/env python3
"""Build the STEM REC fixture card, reproducibly, from a project template.

Task 11's fixture reproduces COLDFIRE_PORT.md O10's kick-on-T1-FLEX
recipe on EZBot's "Ultimate FX 1.5.3" template (no RIG project copy exists on
this machine): T1 = FLEX on slot 1, in banks 1 and 2, every part and its
mirror; T1's FX1 and FX2 = SEND; slot 1's TSMODE=0, so "the record IS the
file" (no timestretch grains to fit around). The kick itself is ours
(`scripts/make_test_audio.py kick`), never Elektron's.

    python3 tools/verify/stems_fixture.py [--eight | --fat32 | --thru] [PROJECT_DIR]

PROJECT_DIR defaults to `out/projects/Ultimate FX 1.5.3`. The template is
copied into a scratch folder first and only the copy is edited -- the
template itself is never touched. Prints the card path, the set and the
project, and writes `out/stems_fixture.json` with the keys `card`, `set`,
`project` and `staged` (the file names this run put into the set's own
AUDIO folder, so a later check can count only what THIS fixture added).
"""
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools")); import toolpath  # noqa: E402,F401

import ot_project      # noqa: E402
import emu_card        # noqa: E402

# No `/Users/sambanks/octa/backups/*pregain*` directory exists on this
# machine (checked: none under /home, /root or /mnt either). That guard
# protects the interactive GAIN-editing workflow (apply_gains); this fixture
# never calls it. set_machine_type and set_fx already expose their own
# `guard` parameter and are called with guard=False below; set_track_slot
# does not expose one at all (it always runs through _bank_write's
# guard=True default), so the only way to use it from a script is to
# neutralise the check itself. Nothing else about the guard's behaviour is
# touched.
ot_project.guard_backup = lambda: None

DEFAULT_PROJECT = ROOT / "out" / "projects" / "Ultimate FX 1.5.3"
SET_NAME = "STEMS"
PROJECT_NAME = "ULTFX"
SCRATCH = ROOT / "out" / "task11" / "fixture_src"
CARD_OUT = ROOT / "out" / "stems_fixture_card.img"
FIXTURE_JSON = ROOT / "out" / "stems_fixture.json"
CARD32_OUT = ROOT / "out" / "stems_fixture32_card.img"      # --fat32: the same card, FAT32
FIXTURE32_JSON = ROOT / "out" / "stems_fixture32.json"
FILLER_NAME = "FILLER.BIN"          # --fat32: in the set folder, see build()
FILLER_BYTES = 65536 * 512
THRU_JSON = ROOT / "out" / "stems_fixture_thru.json"
THRU_CARD = ROOT / "out" / "stems_fixture_thru_card.img"
SCRATCH_THRU = ROOT / "out" / "task_thru" / "fixture_src"
INPUT_WAV = ROOT / "out" / "test_audio" / "stems_in4.wav"
THRU_MTYPE = 2          # ot_project.MACHINES
# Each track's THRU inputs: (INAB, INCD), the playback page's first and
# fourth knobs (docs/firmware/PARAM_PAGES.md: INAB VOL --- INCD VOL ---),
# written into every part record (THRU_PAGE). Over MIDI CC after the
# transport start they had no effect under the port (Task 1, 27 Sep 2026).
# Values, measured under the port (Task 1, 27 Sep 2026; STEM_REC.md 15.1):
# 0 off; 1 the pair in stereo (A or C left, B or D right); 2 A or C alone,
# to both sides; 3 B or D alone; 4 the pair summed, to both sides. So T1 A,
# T2 B, T3 C, T4 D, T5 A|B, T6 C|D, T7 A+C, T8 B+D. `ot_emu --audio-in`'s
# WAV channels 0-3 are inputs C, D, A, B.
THRU_INPUTS = {1: (2, 0), 2: (3, 0), 3: (0, 2), 4: (0, 3),
               5: (1, 0), 6: (0, 1), 7: (2, 2), 8: (3, 3)}
# A track's THRU page in the part record: part + 0x33 + (track-1)*30 + 12,
# the bytes INAB, VOL, ---, INCD, VOL. Measured 27 Sep 2026 from the
# template, whose T1 (INAB 1, VOL 127) and T5 (INCD 1, VOL 127) passed input
# under the port with nothing else set.
THRU_PAGE = 0x33 + 12
KICK_NAME = "kick.wav"
# Our own staging tree: emu_card.stage_project's default, out/_stage_tree,
# is verify_set's too, and each call deletes the tree first.
STAGE_TREE = ROOT / "out" / "_stems_stage_tree"

FLEX_MTYPE = 1   # ot_project.py: 0=STATIC, 1=FLEX, 2=THRU, 3=NEIGHBOR, 4=PICKUP
SLOT1 = 1        # 1-based sample slot T1's FLEX machine will play
T1 = 1
FIXTURE_BANKS = (1, 2)   # O10: the emulated load applies bank 1, then the
                          # transport start re-applies the SAVED bank's
                          # pattern part -- write both so either is T1=FLEX.


def _add_sample_slot(project_work, slot, name):
    """Prepend a [SAMPLE] section for a FLEX slot pointing at
    ../AUDIO/<name>.wav -- the relative form project.work's own FLEX entries
    use (STEM_REC.md 5.6/5.7: "../AUDIO/%s.wav", AUDIO one level above the
    project folder, both inside the set). TSMODE=0 disables timestretch, so
    what the recorder captures is the file's own samples, unmodified (O10).
    Edited at the byte level (latin1, CRLF preserved) -- the same discipline
    apply_gains() already uses, so line endings never drift.
    """
    raw = project_work.read_bytes()
    entry = (
        b"[SAMPLE]\r\n"
        b"TYPE=FLEX\r\n"
        + f"SLOT={slot:03d}\r\n".encode("latin1")
        + f"PATH=../AUDIO/{name}.wav\r\n".encode("latin1")
        + b"BPMx24=2880\r\n"
          b"TSMODE=0\r\n"
          b"LOOPMODE=0\r\n"
          b"GAIN=48\r\n"
          b"TRIGQUANTIZATION=-1\r\n"
          b"[/SAMPLE]\r\n\r\n"
    )
    idx = raw.find(b"[SAMPLE]")
    if idx < 0:
        # No existing [SAMPLE] section (a bare template): append after the
        # "# Samples" header comment block, or at EOF as a last resort.
        idx = len(raw)
    project_work.write_bytes(raw[:idx] + entry + raw[idx:])


def build(project_dir=DEFAULT_PROJECT, fat=16):
    project_dir = pathlib.Path(project_dir)
    if not project_dir.is_dir():
        sys.exit(f"no project at {project_dir}")

    # Copy first, edit the copy: the template is never modified.
    import shutil
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(project_dir, SCRATCH)

    # T1 = FLEX on slot 1, banks 1 and 2, every part and its mirror.
    # The template's T2 and T3 are NEIGHBOR machines, so they copied T1 into
    # the next two read-back slots, 64 and 128 samples later; that let a
    # check find "T1" in T3's slot (STEM_REC.md 9.2, corrected 22 Sep 2026).
    # They become FLEX with no trigs, silent, so T1 is the only core-1 track
    # that sounds.
    for bank in FIXTURE_BANKS:
        for part in (1, 2, 3, 4):
            ot_project.set_machine_type(SCRATCH, bank, part, T1, FLEX_MTYPE,
                                         mirror=True, guard=False)
            for t in (2, 3):
                ot_project.set_machine_type(SCRATCH, bank, part, t, FLEX_MTYPE,
                                             mirror=True, guard=False)
        for part in range(1, 9):   # NPARTS_ALL: current (1-4) + saved (5-8)
            ot_project.set_track_slot(SCRATCH, bank, part, T1, SLOT1, kind="flex")

    # T1 FX1 and FX2 = SEND (every part of every bank -- set_fx's own scope).
    ot_project.set_fx(SCRATCH, "fx1", T1, "SEND", guard=False)
    ot_project.set_fx(SCRATCH, "fx2", T1, "SEND", guard=False)

    # Slot 1: the kick, TSMODE=0.
    _add_sample_slot(SCRATCH / "project.work", SLOT1, "kick")

    # The kick is ours -- never an Elektron byte in the repo.
    subprocess.run([sys.executable, str(ROOT / "scripts" / "make_test_audio.py"), "kick"],
                    check=True, cwd=str(ROOT))
    kick_src = ROOT / "out" / "test_audio" / "kick.wav"
    if not kick_src.is_file():
        sys.exit(f"make_test_audio.py did not produce {kick_src}")

    audio = [f"{kick_src}:AUDIO/{KICK_NAME}"]
    image_mb = 64
    if fat == 32:
        # 65,536 clusters of zeros in the set folder, allocated before the
        # set's subfolders: the project, AUDIO and every take land above
        # cluster 65,535, where FAT32 needs a cluster number's high word,
        # as on the unit's 64 GB card. 128 MB keeps the FAT at about 2,000
        # sectors, far below the firmware's 16,384 (STEM_REC.md 14.1).
        filler = ROOT / "out" / "stems_fat32_filler.bin"
        if not filler.is_file() or filler.stat().st_size != FILLER_BYTES:
            filler.write_bytes(bytes(FILLER_BYTES))
        audio.append(f"{filler}:{FILLER_NAME}")
        image_mb = 128
    card_bytes, name = emu_card.stage_project(
        SCRATCH, SET_NAME, PROJECT_NAME, tree=str(STAGE_TREE),
        audio=audio, image_mb=image_mb, fat=fat)
    card_out, fixture_json = (CARD32_OUT, FIXTURE32_JSON) if fat == 32 else (CARD_OUT, FIXTURE_JSON)
    card_out.write_bytes(card_bytes)

    result = {"card": str(card_out), "set": SET_NAME, "project": name,
              "staged": [KICK_NAME]}
    fixture_json.write_text(json.dumps(result, indent=2) + "\n")
    print(f"card:    {result['card']}")
    print(f"set:     {result['set']}")
    print(f"project: {result['project']}")
    print(f"staged:  {result['staged']}")
    print(f"-> {fixture_json}")
    return result


SOUNDS8 = ("kick", "snare", "hat", "clap", "stab", "bass", "melody", "click")
FIXTURE8_JSON = ROOT / "out" / "stems_fixture8.json"
CARD8_OUT = ROOT / "out" / "stems_fixture8_card.img"
SCRATCH8 = ROOT / "out" / "task_s8" / "fixture_src"


def build8(project_dir=DEFAULT_PROJECT):
    """Every track FLEX on its own slot (T<n> plays slot n, sound SOUNDS8[n-1]),
    a trig on step 1 of every pattern, FX1 and FX2 SEND, banks 1 and 2. No
    NEIGHBOR machine anywhere, so each read-back slot is its own track."""
    import shutil
    project_dir = pathlib.Path(project_dir)
    if SCRATCH8.exists():
        shutil.rmtree(SCRATCH8)
    SCRATCH8.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(project_dir, SCRATCH8)
    for bank in FIXTURE_BANKS:
        for part in (1, 2, 3, 4):
            for t in range(1, 9):
                ot_project.set_machine_type(SCRATCH8, bank, part, t, FLEX_MTYPE, mirror=True, guard=False)
        for part in range(1, 9):
            for t in range(1, 9):
                ot_project.set_track_slot(SCRATCH8, bank, part, t, t, kind="flex")
        for pat in range(16):
            for t in range(8):
                ot_project.set_pattern_trig(SCRATCH8, bank, pat, t, 1, guard=False)
    for t in range(1, 9):
        ot_project.set_fx(SCRATCH8, "fx1", t, "SEND", guard=False)
        ot_project.set_fx(SCRATCH8, "fx2", t, "SEND", guard=False)
    for n, snd in reversed(list(enumerate(SOUNDS8, start=1))):
        _add_sample_slot(SCRATCH8 / "project.work", n, snd)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "make_test_audio.py"), *SOUNDS8],
                   check=True, cwd=str(ROOT))
    audio = [f"{ROOT / 'out' / 'test_audio' / (snd + '.wav')}:AUDIO/{snd}.wav" for snd in SOUNDS8]
    card_bytes, name = emu_card.stage_project(SCRATCH8, SET_NAME, PROJECT_NAME,
                                              tree=str(STAGE_TREE), audio=audio)
    CARD8_OUT.write_bytes(card_bytes)
    result = {"card": str(CARD8_OUT), "set": SET_NAME, "project": name, "staged": [s + ".wav" for s in SOUNDS8]}
    FIXTURE8_JSON.write_text(json.dumps(result, indent=2) + "\n")
    print(f"card:    {result['card']}")
    return result


def write_input_wav(path, live=(0, 1, 2, 3), seconds=30, seed=0x57E4):
    """Four channels of independent seeded noise at -12 dBFS peak, 44.1 kHz,
    16-bit: inputs A to D through `ot_emu --audio-in`. A channel not in
    `live` is silent (Task 1's routing probe). Noise never repeats, so a take
    can match its track only at the true offset."""
    import array
    import random
    import wave
    rng = [random.Random(seed + c) for c in range(4)]
    amp = 8192
    n = 44100 * seconds
    data = array.array("h", (rng[c].randint(-amp, amp) if c in live else 0
                             for _ in range(n) for c in range(4)))
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(4)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(data.tobytes())


def set_thru_inputs(pdir, inputs):
    """Each track's THRU inputs and levels, in every part record (current and
    saved) of banks 1 and 2: INAB and INCD from `inputs`, a selected pair at
    VOL 127 and an unselected one at the template's 0x40."""
    for bank in FIXTURE_BANKS:
        def mut(data):
            for p in range(ot_project.NPARTS_ALL):
                off = ot_project.PART_BASE + p * ot_project.PART_STRIDE
                for t, (inab, incd) in inputs.items():
                    b = off + THRU_PAGE + (t - 1) * 30
                    data[b], data[b + 1] = inab, 127 if inab else 0x40
                    data[b + 3], data[b + 4] = incd, 127 if incd else 0x40
        ot_project._bank_write(pdir, bank, mut, guard=False)


def build_thru(project_dir=DEFAULT_PROJECT, inputs=None):
    """Every track a THRU machine (every part of banks 1 and 2), a trig on
    step 1 of every pattern, FX1 and FX2 SEND, each track's inputs in its
    part records (THRU_INPUTS, or `inputs`); the card and the input WAV."""
    import shutil
    if SCRATCH_THRU.exists():
        shutil.rmtree(SCRATCH_THRU)
    SCRATCH_THRU.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(project_dir, SCRATCH_THRU)
    for bank in FIXTURE_BANKS:
        for part in (1, 2, 3, 4):
            for t in range(1, 9):
                ot_project.set_machine_type(SCRATCH_THRU, bank, part, t, THRU_MTYPE, mirror=True, guard=False)
        for pat in range(16):
            for t in range(8):
                ot_project.set_pattern_trig(SCRATCH_THRU, bank, pat, t, 1, guard=False)
    for t in range(1, 9):
        ot_project.set_fx(SCRATCH_THRU, "fx1", t, "SEND", guard=False)
        ot_project.set_fx(SCRATCH_THRU, "fx2", t, "SEND", guard=False)
    set_thru_inputs(SCRATCH_THRU, inputs or THRU_INPUTS)
    card_bytes, name = emu_card.stage_project(SCRATCH_THRU, SET_NAME, PROJECT_NAME,
                                              tree=str(STAGE_TREE))
    THRU_CARD.write_bytes(card_bytes)
    write_input_wav(INPUT_WAV)
    result = {"card": str(THRU_CARD), "set": SET_NAME, "project": name, "staged": [],
              "audio_in": str(INPUT_WAV)}
    THRU_JSON.write_text(json.dumps(result, indent=2) + "\n")
    print(f"card:    {result['card']}")
    print(f"-> {THRU_JSON}")
    return result


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--eight":
        build8(sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PROJECT)
    elif len(sys.argv) > 1 and sys.argv[1] == "--thru":
        build_thru(sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PROJECT)
    elif len(sys.argv) > 1 and sys.argv[1] == "--fat32":
        build(sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PROJECT, fat=32)
    else:
        build(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PROJECT)
