"""BOOT TRACE -- a probe: one MIDI note on MIDI OUT at each boot stage.

Built for OS SWITCH's hardware bring-up: after a switch the unit stops on
the OCTABAM screen, and only the unit can say where. Notes 1..8 (the OS
entry, the DSP upload's start and return, the panel link's init, the MKII
panel handshake, the UI's panel check, the first audio frame interrupt
entered and returned): the last note a MIDI monitor on
MIDI OUT receives names the stage that hangs. trace.s has the table.
Note 1 is sent by OS SWITCH's chainloader when both are in the image.
"""

from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Proof

H = bytes.fromhex

MODULE = Module(
    name="boot-trace",
    key="BOOT TRACE",
    kind=Kind.CF_PATCH,
    category=Category.REFERENCE, author="sanderlegit", author_url="https://github.com/sanderlegit",
    proof=Proof.PORT, proof_note="the notes on the port's MIDI OUT (`verify_boottrace`)",
    doc="Probe: a MIDI note on MIDI OUT at each boot stage (1..8), for finding where a boot hangs.",
    linked=(Linked("boot_trace", "modules/boot-trace/trace.s", cpu="5475"),),
    detours=(
        Detour(0x40001E50, H("420013c0fc0a400c"), "boot_trace", "tr_dsp",
               "the DSP upload's entry: note 2", pad_to=8),
        Detour(0x40000512, H("4eb94000f938"), "boot_trace", "tr_dsp_done",
               "the boot after the DSP upload returned: note 3"),
        Detour(0x4001F834, H("4e56fff048d7040c"), "boot_trace", "tr_panel",
               "the panel link's init: note 4", pad_to=8),
        Detour(0x4001F4DC, H("4fefffd848d70cfc"), "boot_trace", "tr_handshake",
               "the MKII panel loader handshake: note 5", pad_to=8),
        Detour(0x40061C94, H("4ab946c8d18c"), "boot_trace", "tr_ui",
               "the UI's panel report check: note 6"),
        Detour(0x4000AAD0, H("4fefff0448d77fff"), "boot_trace", "tr_frame",
               "the audio frame interrupt's entry: note 7, once", pad_to=8),
        Detour(0x4000D9A6, H("4cd77fff4fef00fc4e73"), "boot_trace", "tr_frame_end",
               "the audio frame interrupt's return: note 8, once", pad_to=10),
    ),
    gates=(Gate("tools/verify/verify_boottrace.py"),),
)
