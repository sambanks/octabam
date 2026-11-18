"""TRACK TRIG MODES -- each track (T1-T8, M1-M8) remembers its trig mode.

Stock has one trig mode for every track (and one stash per side across
[MIDI]), so moving between a CHROMATIC track and a SLICES track means
FUNC + UP / DOWN every time. Here the mode chosen on a track comes back
when that track is selected again, QUICK MUTE and DELAY CTRL included.
RAM only: every track starts in TRACKS at power-up. ttm.s has the detail.
"""

from remix.schema import Category, Detour, Kind, Linked, Module, Proof

H = bytes.fromhex

MODULE = Module(
    name="track-trig-modes",
    key="TRACK TRIG MODES",
    kind=Kind.CF_PATCH,
    category=Category.UTILITIES, author="8thmyth", author_url="",
    proof=Proof.PORT, proof_note="verify_track_trig_modes under the port; not yet on a unit",
    doc="Each track (T1-T8, M1-M8) remembers its trig mode, every mode included.",
    linked=(Linked("ttm", "modules/track-trig-modes/ttm.s", dram=True),),
    detours=(
        Detour(0x40051F1E, H("4eb9400359ac"), "ttm", "ttm_set",
               "the trig mode list's setter (one direction): store the mode for the current track", kind="jsr"),
        Detour(0x40051F8E, H("4eb9400359ac"), "ttm", "ttm_set",
               "the trig mode list's setter (the other direction): store the mode for the current track", kind="jsr"),
        Detour(0x40083C2E, H("13c28000000013c2100b14cc"), "ttm", "ttm_sel",
               "the track select's two track stores: replayed, then the track's mode", pad_to=12),
        Detour(0x400555DE, H("42b946c7d2c0"), "ttm", "ttm_midi",
               "the [MIDI] key, after stock's side swap: the new track's mode"),
    ),
)
