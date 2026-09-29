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
    proof=Proof.HARDWARE, proof_note="an MKII, 29 Sep 2026 (OCTABAM4-14); `verify_boottrace`",
    doc="Probe: a MIDI note on MIDI OUT at each boot stage, the DSP upload's record "
        "echoes and any stall, for finding where a boot hangs.",
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
        Detour(0x40000432, H("3239400dea48"), "boot_trace", "tr_clock",
               "the OS entry's clock check: note 9, velocity = the PLL multiplier byte"),
        Detour(0x40000450, H("487900000096"), "boot_trace", "tr_reprog_branch",
               "the OS entry's bootstrap-reprogram branch: note 10 (must never appear)"),
        Detour(0x4000F9B4, H("4feffff048d71c04"), "boot_trace", "tr_reprog",
               "the bootstrap reprogram: note 11", pad_to=8),
        Detour(0x40001D4C, H("4feffff048d7041c"), "boot_trace", "tr_bootup",
               "a DSP bootstrap upload: note 14, velocity = the core", pad_to=8),
        Detour(0x40001B18, H("4feffff448d7040c"), "boot_trace", "tr_records",
               "a DSP payload's records: note 15, velocity = the core", pad_to=8),
        Detour(0x40001B82, H("303920000008"), "boot_trace", "tr_echo",
               "the records' echo wait: note 16 with the ISR, when late"),
        Detour(0x40001BB4, H("7403b4806d000186"), "boot_trace", "tr_rececho",
               "a record's echo: note 17 (and 19 when it is not a type)", pad_to=8),
        Detour(0x40001B46, H("303920000008"), "boot_trace", "tr_tx1",
               "the record sender's wait before a record's type: stall report"),
        Detour(0x40001C4C, H("303920000008"), "boot_trace", "tr_tx3",
               "the record sender's wait before a data word: stall report"),
        Detour(0x40001CF4, H("7403b4806646"), "boot_trace", "tr_lastecho",
               "the final record's echo: note 18"),
        Detour(0x4000D9A6, H("4cd77fff4fef00fc4e73"), "boot_trace", "tr_frame_end",
               "the audio frame interrupt's return: note 8, once", pad_to=10),
    ),
    gates=(Gate("tools/verify/verify_boottrace.py"),),
)
