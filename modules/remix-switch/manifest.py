"""REMIX SWITCH -- boot an OS image from the card without writing the flash.

BRAIN's MAIN MENU pane lists the `.RMX` files in /BRAIN/REMIXES/ (raw OS images:
`make rmx`) below its own rows, stages the chosen one at the top of the platform's arena
reserve with a mailbox, and resets the unit the way OS UPGRADE does after
it flashes. On the way back up, a chainloader in the OS entry (a ROM cave,
reached before the DSP upload or any other set-up) finds the mailbox,
checks the stage, copies it over the image the bootstrap just depacked and
calls it as the bootstrap called us. NOR is never written; a power-cycle
boots the flashed image again, and a staged image need not carry this
module (stock 1.40C itself is a valid target). Every remix that carries
BRAIN carries REMIX SWITCH (tools/remix/registry.py); until 8 Oct 2026 it was
a fifth root category of its own, OS, in every image (PR #542).

Two units: `chain.s` (the chainloader, a ROM cave: the DRAM runtime is not
depacked yet when it runs) and `switch.s` (the row, the picker, the load and
the reset, DRAM). `osw.inc` is the layout both share.
docs/proposals/FIRMWARE_SWITCHER.md is the design and what is measured;
README.md beside this file is the procedure.
"""

import pathlib

from remix.schema import Category, Detour, DspHook, DspSection, Gate, Kind, Linked, Module, Proof

H = bytes.fromhex
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def _include(_modules):
    """osw.inc, the TRACE switch and this image's own name."""
    # the image's own name (remix.brain.image_name: `<REMIX> <BUILD>`, the
    # name BRAIN's heading shows and make image gives the .RMX)
    # OSW_TRACE=1: this module's own BOOT TRACE notes (1 and 12 from the
    # chainloader, 13 before a switch's reset, 26/27 from the boot picker)
    # without the BOOT TRACE module, whose ROM-cave detours a full rig has
    # no room for (bottleservice-ret: CC MAP's page-2 cave, 30 Sep 2026)
    import os
    from remix import brain
    name = brain.image_name()
    return ((HERE / "osw.inc").read_text()
            + f"        .set    TRACE, {1 if 'BOOT TRACE' in _modules or os.environ.get('OSW_TRACE') == '1' else 0}\n"
            + "        .macro  OSW_SELF\n"
            + f"        .asciz  \"{name}\"\n"
            + "        .endm\n")


MODULE = Module(
    name="remix-switch",
    key="REMIX SWITCH",
    kind=Kind.HYBRID,
    category=Category.REFERENCE, author="sanderlegit", author_url="https://github.com/sanderlegit",
    proof=Proof.HARDWARE,
    proof_note="an MKII, 29 Sep 2026 (OCTABAM14 with BOOT TRACE): switched to its own "
               "image and to stock 1.40C, audio and play working; and with the park "
               "moved into the dead vector run (BSRETVEC) booted, played and switched "
               "away again -- 40 region words down to 18; `verify_remixswitch`. The list in "
               "BRAIN's pane and /BRAIN/REMIXES/ (8 Oct 2026): under the port only",
    doc="MAIN MENU > BRAIN lists the raw OS images (.RMX) in /BRAIN/REMIXES/ and boots the one "
        "picked without writing the flash; a power-cycle returns to the flashed image. "
        "At power-on a picker offers them before the project loads (3 s, then NO).",
    linked=(
        Linked("osw_chain", "modules/remix-switch/chain.s", loader=True, include=_include),
        Linked("osw_switch", "modules/remix-switch/switch.s", dram=True, include=_include),
    ),
    # Each DSP core, told by host command $12 before the reset, parks in a
    # boot-ROM loader of its own (dsp_park.asm): the soft reset restarts the
    # ColdFire but not the DSP, whose ROM only listens after a chip reset.
    dsp=DspSection(
        asm="modules/remix-switch/dsp_park.asm",
        priority=20,
        payloads=frozenset({"A", "B"}),
        hooks=(DspHook(0x1E, (0x0C001E, 0x000000), "osw_dsp",
                       "host command $0F (the DMA3 vector, dead in both payloads): "
                       "park in a loader"),),
        # WHOLLY in stock's dead interrupt vectors, so the park costs the
        # effect region NOTHING and a remix that harvests nothing can still
        # carry it. 31 words at P:$20..$3E (the DMA3..ESAI run, entered by
        # the hook above) and 8 at P:$06..$0D (debug, trap, NMI and the two
        # reserved slots) with a one-word bridge between them. $02 (stack
        # error) and $04 (illegal instruction) are deliberately left as
        # stock's freeze-traps: those two fire when something is already
        # wrong, and a frozen core is more diagnosable than one running park
        # words. verify_dspvectors audits every slot on every build.
        pins=(0x20, 0x06),
        pin_split_label="osw_tail",
    ),
    detours=(
        Detour(0x40000412, H("2e7c48000000"), "osw_chain", "osw_chain",
               "the OS entry, after it parks the bootstrap's argument: a staged image first"),
        Detour(0x40064C32, H("2f39400cbf6c"), "osw_switch", "osw_menu",
               "MAIN MENU opening: the OS list rescanned from the card"),
        Detour(0x4002574C, H("4879100f8378"), "osw_switch", "osw_bootpick",
               "the named project's (re)load post: the boot's first offers the card's "
               "images before the project loads"),
        Detour(0x4002573E, H("4eb9400228dc"), "osw_switch", "osw_bootfiles",
               "the last-set mount's LOADING FILES post: held with the load while the "
               "boot picker is up, posted after it in stock's order", kind="jsr"),
    ),
    # the list is BRAIN's pane (brain_list, brain_os_rows)
    requires=("BRAIN",),
    gates=(Gate("tools/verify/verify_remixswitch.py", venv=True),
           # The park's 40 words could come out of the DSP's unused
           # interrupt vectors instead of the effect region. That is only
           # safe while nothing arms an interrupt in those runs, and once
           # code lives there the freeze that would announce one is gone --
           # so the audit runs on every build, not in a session nobody
           # repeats.
           Gate("tools/verify/verify_dspvectors.py"),),
)
