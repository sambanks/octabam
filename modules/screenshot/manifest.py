"""SCREENSHOT -- the unit answers Elektron's screenshot SysEx request on MIDI
OUT, so `elektron-screen-tool` (screendump) can read the screen.

Stock drops the request: its SysEx entry (0x40001918) takes `F0 00 20 3C 05 00
<b6>` only for b6 in 0x50..0x73. A jmp detour on that entry answers the
13-byte request `F0 00 20 3C <05|10> 00 00 .. .. .. .. 04 F7` with the
frame last sent to the panel (1,024 bytes at [0x400b970c], every window
composited over the page plane, already in the tool's column-major bit
order) as a 1,194-byte 7-bit-encoded reply, and hands every other message
back to stock. The reply goes back on the transport the request came on (DIN, or
USB-MIDI when the USB module is in the image). See screenshot.s."""

from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Proof

MODULE = Module(
    name="screenshot",
    key="SCREENSHOT",
    kind=Kind.CF_PATCH,
    category=Category.MIDI_USB, author="sambanks", author_url="https://github.com/sambanks",
    proof=Proof.PORT, proof_note="`verify_screenshot` under the port (29 checks, DIN and USB, the pixels against the decoded panel stream with a popup and MIXER up); on a unit, the build before the frame fix (a9f0d3d5): Sam's MKII, a looping remix BUILD 40, USB MIDI with `screendump` (`--trace`, `-x --framerate 10`), 4 Nov 2026: answered, upright, page screens only; the frame fix has not run on a unit",
    doc="Answers the Elektron screenshot SysEx request on MIDI OUT with the 128x64 screen, windows and popups included.",
    linked=(Linked("screenshot", "modules/screenshot/screenshot.s", dram=True),),
    gates=(Gate("tools/verify/verify_screenshot.py", remix_arg=False, venv=True),),
    detours=(
        Detour(0x40001918, bytes.fromhex("2f02206f0008"), "screenshot", "ss_hook",
               "stock's SysEx entry: the screenshot request is answered, everything else goes on to stock", kind="jmp"),
    ),
)
