"""MODE DEFAULTS -- landing on a MODE on the panel re-defaults the knobs
around it, from the manifests' ModeViews.

The mode cave (tools/build/mode_names.py) renames a mode's knobs on the
unit; the views' DEFAULTS were applied only by the remixer and by
ot_project (stamp-defaults, set-fx). On the panel a MODE turn kept the
previous mode's values: BusDelay's GRAIN at CLEAN's knobs (15 Sep 2026,
image 25) was "a bit of a mess", at its view's values "pretty good".

Both page-2 editors -- FX2 0x4003a9dc and FX1 0x4003abe4 -- call the
project-dirty routine 0x40027e00 between their Part/shadow stores and
their live-lane store; the two jsr sites are detoured to modedef.s, which
replays the call and then, when the slot just edited is a module's MODE
slot and the value names one of its views, writes the view's defaults:
page-1 slots through the stock page-1 writer 0x40054cd8(track, flat,
value), page-2 slots with the editor's own stores (Part, shadow, live
lane, the slot's redraw flag). SEND (slot 0 of the bus engines) is never
in a view. The table is generated per remix from every module in the
image that declares ModeViews. A MODE over MIDI (CC MAP) is
re-defaulted too: its cave calls CC_MODEDEF2 / CC_MODEDEF1 here after its
write.

Measured under the port (tools/verify/verify_modedefaults.py, in make
verify when OT_PROJECT is set): the FX2 editor called on T1 with MODE ->
GRAIN leaves the GRAIN view's bytes in the live lane, page 1 and page 2;
the FX1 editor likewise for a station. Not measured: the panel redraw on
hardware.
"""

from remix.schema import Gate, Category, Proof, Detour, Kind, Linked, Module

H = bytes.fromhex


def table_inc(modules):
    """The view table, one entry per module with ModeViews:
    id, mode slot, nviews, then per view: mode, npairs, (slot, value)*;
    0xff ends it."""
    rows = ["MODEDEF_TABLE:"]
    for key in sorted(modules):
        m = modules[key]
        views = getattr(m, "mode_views", ())
        if not views or m.mode_slot is None or m.menu is None:
            continue
        rows.append(f"| {key}: id 0x{m.menu.fx2_id:02x}, MODE on slot {m.mode_slot}")
        rows.append(f"        .byte   {m.menu.fx2_id}, {m.mode_slot}, {len(views)}")
        for v in views:
            pairs = sorted(v.defaults.items())
            body = ", ".join(f"{s}, {val}" for s, val in pairs)
            rows.append(f"        .byte   {v.mode}, {len(pairs)}" + (f", {body}" if pairs else ""))
    rows.append("        .byte   0xff")
    return "\n".join(rows) + "\n"


MODULE = Module(
    name="mode-defaults",
    key="MODE DEFAULTS",
    kind=Kind.CF_PATCH,
    category=Category.BUS, author="sambanks", author_url="https://github.com/sambanks",
    proof=Proof.HARDWARE, proof_note="Sam's MKII (images 26/27, 15 Sep 2026)",
    doc="A MODE turned on the panel re-defaults the knobs around it "
        "(the manifests' ModeViews), on FX1 and FX2.",
    linked=(Linked("modedef", "modules/mode-defaults/modedef.s", include=table_inc, dram=True),),
    detours=(
        Detour(0x4003AAEA, H("4eb940027e00"), "modedef", "fx2_hook",
               "FX2 page-2 editor: after the Part store, apply the mode's view", kind="jsr"),
        Detour(0x4003ACF2, H("4eb940027e00"), "modedef", "fx1_hook",
               "FX1 page-2 editor: after the Part store, apply the mode's view", kind="jsr"),
    ),
    gates=(Gate('tools/verify/verify_modedefaults.py'),),
)
