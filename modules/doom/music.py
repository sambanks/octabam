#!/usr/bin/env python3
"""Doom's music for the card, rendered from YOUR WAD on this machine.

    python3 modules/doom/music.py DOOM1.WAD OUTDIR

Every D_* lump (Doom's MUS songs) is played through libADLMIDI's OPL3
emulator with bank 16, "DMX (Bobby Prince v1)" -- Doom's own instrument set,
the Sound Blaster sound -- once through, no loop; ffmpeg then makes it the
format octa/doom_audio.c streams: WAV, IMA ADPCM, mono, 22,050 Hz (about
11 KB a second). The files are the WAD's music and so yours, like the WAD:
never in the repo, copied to the card's /DOOMMUS/ beside DOOM1.WAD.

Needs:
  adlmidiplay  libADLMIDI's demo player built WAV-only, e.g.
               git clone https://github.com/Wohlstand/libADLMIDI
               cmake -S libADLMIDI -B build -DWITH_MIDIPLAY=ON \\
                     -DMIDIPLAY_WAVE_ONLY=ON -DUSE_NUKED_EMULATOR=ON
               cmake --build build          (then $ADLMIDIPLAY=build/adlmidiplay)
  ffmpeg
"""
import os
import pathlib
import shutil
import struct
import subprocess
import sys
import tempfile

RATE = 22050
BANK = "16"                     # DMX (Bobby Prince v1)


def lumps(wad):
    b = wad.read_bytes()
    if b[:4] not in (b"IWAD", b"PWAD"):
        sys.exit(f"{wad}: not a WAD")
    n, off = struct.unpack("<ii", b[4:12])
    for i in range(n):
        pos, size, name = struct.unpack("<ii8s", b[off + 16 * i:off + 16 * i + 16])
        yield name.rstrip(b"\0").decode("latin1"), b[pos:pos + size]


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    wad, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
    adl = os.environ.get("ADLMIDIPLAY") or shutil.which("adlmidiplay")
    if not adl or not pathlib.Path(adl).exists():
        sys.exit("adlmidiplay not found: set $ADLMIDIPLAY (see this file's header)")
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found")
    out.mkdir(parents=True, exist_ok=True)
    work = pathlib.Path(tempfile.mkdtemp(prefix="doommus."))
    n = 0
    for name, data in lumps(wad):
        if not name.startswith("D_") or data[:4] != b"MUS\x1a":
            continue
        mus = work / f"{name}.mus"
        mus.write_bytes(data)
        r = subprocess.run([adl, str(mus), BANK], cwd=work, capture_output=True, text=True)
        wav = next(iter(work.glob(f"{name}*.wav")), None)
        if r.returncode or wav is None:
            sys.exit(f"{name}: adlmidiplay failed\n{(r.stdout + r.stderr)[-800:]}")
        dst = out / f"{name}.WAV"
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-ac", "1",
                            "-ar", str(RATE), "-c:a", "adpcm_ima_wav", str(dst)],
                           capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"{name}: ffmpeg failed\n{r.stderr[-800:]}")
        wav.unlink()
        n += 1
        print(f"  {dst.name}: {dst.stat().st_size:,} B")
    print(f"{n} songs -> {out}")


if __name__ == "__main__":
    main()
