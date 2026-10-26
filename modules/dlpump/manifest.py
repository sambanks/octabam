"""DLPUMP -- the demand loader's ColdFire half: watches which effects the tracks use, stages the
blocks of the ones that are not loaded and withdraws the ones nobody uses. Called from LOAD
METER's entry code (docs/proposals/DEMAND_LOAD.md, decision 9).
"""
import json
import pathlib

from remix.schema import Apply, Category, Detour, Gate, Kind, Linked, Module, Option, Proof, Setting, Store

RECORDS = pathlib.Path("out/dsp/demand_records.json")
CAPACITY = 2600                 # code words a block may hold: the staging area X:0x2906..0x3d55 takes 2 per word; the table is this size on every link
BLOCK_TRACK = {0: 6, 1: 7, 2: 2, 3: 3}   # window block (address >> 14 & 3) -> the FX2 track whose slot is there (0-based; docs/firmware/DSP.md section 7)
WIN = 0x30000
REVERBS = ("PLATE REV", "SPRING REV", "DARK REV")
TOAST_NAME_MAX = 10             # "EVICT <name> FIRST" must fit the popup, so a longer name is cut: 22 characters on one line (measured on the unit, 27 Oct 2026; a newline does not break the line)


def table_inc(modules, remix):
    """remix.inc: one record per Remix.window_demand effect (id, the track whose FX2 slot shares its block, the
    staged block, its length in halfwords, the withdraw message), then the blocks. The DSP stage writes
    RECORDS after the first link, so that link reserves CAPACITY words per effect with no content; the second
    link has the words and the same size."""
    from remix import stock
    recs = json.loads(RECORDS.read_text()) if RECORDS.is_file() else {}
    keys = list(remix.window_demand)
    phase_any = modules["DLPUMP"].build_values.get("PHASE", "PING0") == "ANY"
    grace = {"10 S": 13780, "2 S": 2756}[modules["DLPUMP"].build_values.get("GRACE", "10 S")]   # idle calls: 1,378 a second
    rows = [f"        .equ    DL_N, {len(keys)}", f"        .equ    PHASE_ANY, {int(phase_any)}", f"        .equ    GRACE, {grace}"]
    for key in REVERBS:
        rows.append(f"        .equ    DL_{key.split()[0]}, 0x{stock.BY_KEY[key].menu.fx2_id:02x}")
    rows.append("dl_tab:")
    for k, key in enumerate(keys):
        addr = dict(remix.window)[key]
        track = BLOCK_TRACK[(addr - WIN) >> 14 & 3]
        n = 7 + 2 * len(recs[key]["words"]) if key in recs else 0
        rows.append(f"        .long   0x{modules[key].menu.fx2_id:02x}, {track}, dl_blk{k}, {n}, dl_off{k}, dl_need{k}, dl_hold{k}")
    for k, key in enumerate(keys):
        track = BLOCK_TRACK[(dict(remix.window)[key] - WIN) >> 14 & 3]
        rec = recs.get(key)
        halves = []
        if rec:
            words = rec["words"]
            if len(words) > CAPACITY:
                raise ValueError(f"{key}: {len(words)} code words; DLPUMP reserves {CAPACITY}")
            halves = [k, rec["addr"] - WIN, len(words), rec["init"] - WIN, rec["proc"] - WIN]
            for w in words:
                halves += [w >> 8, w & 0xFF]
            total = sum(words) & 0xFFFFFF                   # the copier checks this before it publishes
            halves += [total >> 8, total & 0xFF]
        used = len(halves)
        rows.append(f"dl_blk{k}:")
        for i in range(0, used, 8):
            rows.append("        .word   " + ", ".join(str(h) for h in halves[i:i + 8]))
        rows.append(f"        .space  {2 * (2 * CAPACITY + 7) - 2 * used}")
        rows.append(f"dl_blk{k}_end:")
        rows.append(f"dl_off{k}:  .word   {k}, 0, 0, 0, 0")
        name = modules[key].menu.fullname.decode().upper()[:TOAST_NAME_MAX]      # as the chooser lists it, cut to fit
        rows.append(f'dl_need{k}: .asciz "EVICT T{track + 1} FX2 FIRST"')
        rows.append(f'dl_hold{k}: .asciz "EVICT {name} FIRST"')
        rows.append("        .balign 2")
    return "\n".join(rows) + "\n"


MODULE = Module(
    name="dlpump",
    key="DLPUMP",
    kind=Kind.CF_PATCH,
    category=Category.REFERENCE, author="sambanks", author_url="https://github.com/sambanks",
    proof=Proof.CHECK, proof_note="",
    doc="Host-writes a staged block to a DSP core, a chunk per frame interrupt (demand loader).",
    linked=(Linked("dlpump", "modules/dlpump/pump.s", cpu="5475", include=table_inc, dram=True),),
    detours=(
        Detour(0x4005578C, bytes.fromhex("2f032f02226f000c"), "dlpump", "dl_key",
               "the UI task's page-key handler: a toast the idle loop owes is shown at the next press", pad_to=8),
        Detour(0x4005272A, bytes.fromhex("b2806700020c"), "dlpump", "dl_sel_fx1",
               "FX1 chooser select, the 'same effect' test: refuse a demand effect that cannot be loaded"),
        Detour(0x400524BA, bytes.fromhex("b2806700021c"), "dlpump", "dl_sel_fx2",
               "FX2 chooser select, the 'same effect' test: the same"),
    ),
    store=Store("octabam.dlpump"),
    settings=(Setting(1, "PHASE", Option("PING0", "ANY"), default="PING0", apply=Apply.BUILD,
                      doc="PING0: send on the frames whose ping word is 0 (the port's delivering frames); ANY: on every "
                          "frame (a measurement build: the copier's counters show what the unit loses)"),
              Setting(2, "GRACE", Option("10 S", "2 S"), default="10 S", apply=Apply.BUILD,
                      doc="how long an unused effect stays loaded before it is withdrawn; a project load leaves every id at its "
                          "default for about 4 s (measured on a unit), so 10 S keeps the effects through it; 2 S is for the port gates"),),
    gates=(Gate("tools/verify/verify_dlload.py", venv=True),),
)
