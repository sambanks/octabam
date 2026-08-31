"""The bench rig: eight tracks, an effect on each, knobs where the unit has them.

This is the layer the workbench was missing. Everything below it speaks
modules and payloads; an Octatrack user thinks in TRACKS -- which effect is
on track 5, what its page-1 knobs read, what the chooser offers on track 2.
The rig states that mapping once so the audition view, the emulator preview
and the composer all mean the same thing by "T5".

A rig is a BENCH FIXTURE, not a firmware statement: it is deliberately not
part of a remix file (a remix says what the image contains; the rig says what
the operator is currently listening to) and it persists to out/_rig.json so a
restarted workbench picks up where it left off.

Categories and track ranges are DERIVED from the manifests, never declared
here -- the manifest is the single place a module states what it is
(schema.py's whole reason to exist):

  SERVER  harness.is_server -- pays the bus costs, lives in ONE payload, and
          the payload decides its tracks: A serves TRACKS 5-8, B serves
          TRACKS 1-4 (measured 10 Aug 2026 via the MrkVerb32 marker flash,
          INVERTED from every earlier assumption -- test the reverb on
          track 5, not track 1).
  INSERT  a DSP_EFFECT with a menu entry and no server role -- sits in both
          payloads, runs on any track.
  SYSTEM  everything else: the SEND client, ColdFire patches. Plumbing the
          image needs, never something you put on a track.
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from remix import registry  # noqa: E402
from remix.schema import Kind  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
RIG_FILE = ROOT / "out/_rig.json"

TRACKS = range(1, 9)
# Which tracks each payload's core serves. Measured 10 Aug 2026 (MrkVerb32
# marker flash); the inversion from old docs cost two flashes, so this is the
# one place the workbench states it.
PAYLOAD_TRACKS = {"A": range(5, 9), "B": range(1, 5)}

SERVER, INSERT, SYSTEM = "server", "insert", "system"


def category(mod) -> str:
    if mod.harness is not None and mod.harness.is_server:
        return SERVER
    if mod.kind is Kind.DSP_EFFECT and mod.menu is not None:
        return INSERT
    return SYSTEM


def track_range(mod) -> range:
    """Tracks this module can be selected on. Empty range for SYSTEM."""
    cat = category(mod)
    if cat == INSERT:
        return TRACKS
    if cat == SYSTEM:
        return range(0)
    # A server lives in exactly one payload, and the manifest says which.
    # frozenset({"A","B"}) is the field's default, i.e. "never stated" -- a
    # server carrying it would silently show up on all eight tracks, so
    # refuse loudly instead (selftest.py holds this line for every module).
    p = mod.dsp.payloads if mod.dsp is not None else None
    if p is None or len(p) != 1:
        raise ValueError(
            f"{mod.name}: a SERVER must declare its single payload "
            f"(dsp.payloads), got {sorted(p) if p else p}")
    return PAYLOAD_TRACKS[next(iter(p))]


def effects() -> list:
    """Every module that can sit on a track (servers + inserts), by name."""
    return sorted((m for m in registry.modules().values()
                   if category(m) != SYSTEM), key=lambda m: m.name)


def available(track: int) -> list:
    return [m for m in effects() if track in track_range(m)]


def default_knobs(mod) -> dict[str, int]:
    """Manifest defaults for every named, drawn slot -- the values a fresh
    part boots with, which is also the honest render baseline (the SHMR=64
    lesson: a stale default pollutes every measurement)."""
    return {p.name.decode(): (p.default or 0)
            for p in mod.params if p.name and p.active}


def knob_max(mod, name: str) -> int:
    """Highest legal value: count-1 where the manifest states a count,
    else the stock 0..127 dial."""
    slot = mod.knob_map()[name]
    count = mod.params[slot].count
    return (count - 1) if count is not None else 127


class Rig:
    """Per-track effect assignment + per-track knob values."""

    def __init__(self):
        self.assign: dict[int, str | None] = {t: None for t in TRACKS}
        self.knobs: dict[int, dict[str, int]] = {t: {} for t in TRACKS}
        self.load()

    def set_effect(self, track: int, key: str | None):
        if key is not None:
            mod = registry.by_key(key)
            if track not in track_range(mod):
                raise ValueError(
                    f"{mod.name} cannot run on T{track} (tracks "
                    f"{track_range(mod).start}-{track_range(mod).stop - 1})")
            self.knobs[track] = default_knobs(mod)
        else:
            self.knobs[track] = {}
        self.assign[track] = key

    def effect(self, track: int):
        k = self.assign.get(track)
        return registry.by_key(k) if k else None

    # ---- persistence ----------------------------------------------------
    def save(self):
        RIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        RIG_FILE.write_text(json.dumps(
            {"assign": {str(t): k for t, k in self.assign.items()},
             "knobs": {str(t): v for t, v in self.knobs.items()}}, indent=1))

    def load(self):
        try:
            d = json.loads(RIG_FILE.read_text())
        except (OSError, ValueError):
            return
        keys = set(registry.modules())
        for t in TRACKS:
            k = d.get("assign", {}).get(str(t))
            if k in keys and t in track_range(registry.by_key(k)):
                self.assign[t] = k
                # Keep only knobs the manifest still names, seed the rest
                # from defaults -- a renamed knob must not resurrect a stale
                # value under its old meaning.
                mod = registry.by_key(k)
                fresh = default_knobs(mod)
                stored = d.get("knobs", {}).get(str(t), {})
                for n in fresh:
                    if n in stored and \
                            0 <= int(stored[n]) <= knob_max(mod, n):
                        fresh[n] = int(stored[n])
                self.knobs[t] = fresh
