"""REPITCH -- tempo-following variable-speed playback as TSTR raw value 4."""

from remix.schema import Detour, Kind, Linked, Module, Poke, SymbolRef

H = bytes.fromhex
KNOB, SELECT4, SELECT5 = 0x400479B4, 0x40046C28, 0x40046AB4

MODULE = Module(
    name="repitch",
    key="REPITCH",
    kind=Kind.CF_PATCH,
    doc="Adds TSTR REPITCH (STATIC/FLEX and the sample's own TIMESTRETCH): "
        "project-tempo following by playback speed, without grains; PTCH off.",
    linked=(Linked("repitch", "modules/repitch/repitch.s"),),
    detours=(
        Detour(0x4000406A, H("082f000400436608"), "repitch", "rate_gate",
               "resolve REPITCH for the track the increment is built for", pad_to=8),
        Detour(0x4000409E, H("71d6a3460c404000"), "repitch", "pitch_gate",
               "REPITCH: PTCH not applied", pad_to=8),
        Detour(0x40004100, H("a1c0eca027400024"), "repitch", "rate_hook",
               "scale the shared CPU/DSP playback increment", pad_to=8),
        Detour(0x40007D96, H("712a00147404"), "repitch", "tstr_resolve",
               "the voice renderer resolves REPITCH to OFF: dry, forwards and back"),
        Detour(0x4006E71C, H("4879400b94f660000154"), "repitch", "attr_label",
               "audio editor ATTR: TIMESTRETCH prints REPITCH", pad_to=10),
        Detour(0x4006EE56, H("7202b28066000094"), "repitch", "attr_up",
               "audio editor ATTR: TIMESTRETCH up, BEAT -> REPITCH", pad_to=8),
        Detour(0x4006EF7C, H("20280110b2806608"), "repitch", "attr_down",
               "audio editor ATTR: TIMESTRETCH down, REPITCH -> BEAT", pad_to=8),
    ),
    symbol_refs=(
        SymbolRef(0x400D310E, 0x4003B6A4, "repitch", "tstr_fmt",
                  "STATIC TSTR formatter"),
        SymbolRef(0x400D32A0, 0x4003B6A4, "repitch", "tstr_fmt",
                  "FLEX TSTR formatter"),
        SymbolRef(0x400D3116, KNOB, "repitch", "ptch_widget",
                  "STATIC PTCH knob"),
        SymbolRef(0x400D32A8, KNOB, "repitch", "ptch_widget",
                  "FLEX PTCH knob"),
    ),
    pokes=(
        Poke(0x400D30DE, H("00000004"), H("00000005"),
             "STATIC TSTR count 4 -> 5"),
        Poke(0x400D3270, H("00000004"), H("00000005"),
             "FLEX TSTR count 4 -> 5"),
        # The select widget draws nothing past its own position count
        # (`cmp #3` at 0x40046c7c): stock's unused five-position twin.
        Poke(0x400D313E, SELECT4.to_bytes(4, "big"), SELECT5.to_bytes(4, "big"),
             "STATIC TSTR widget 4 -> 5 positions"),
        Poke(0x400D32D0, SELECT4.to_bytes(4, "big"), SELECT5.to_bytes(4, "big"),
             "FLEX TSTR widget 4 -> 5 positions"),
    ),
)
