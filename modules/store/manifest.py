"""STORE -- the stock sites where a project's side files are written, read,
copied and cleared, and where a Part is saved or cleared, owned once.

KITS (kits.work), PLOCKS P2 (p2lkNN.work) and MIDI SCENES' storage each need
the same stock events: a load of every bank, a masked bank load, a new
project, the bank writer, the project store and reload, the bank file copy,
the bank to and from CS1, and the Part Save and Part Clear. The ledger
allows one detour on a site, so STORE holds the detours and calls each
client's handler at the event (modules/store/store.s). A client names its
handlers in CLIENTS below; a client that is not in the remix is left out of
the tables.
"""

from remix.schema import Category, Detour, Kind, Linked, Module, Proof

H = bytes.fromhex

# Events, in the order a table lists a client's handler. A handler is
# `<prefix>_st_<event>`; d0, d1, d2 carry the arguments store.s documents.
EVENTS = (
    "loadall_pre", "loadall_post", "loadmask_pre", "loadmask_post", "newproj",
    "bankw_pre", "bankw_post", "pstore_pre", "pstore_post", "preload_post",
    "bankcopy", "tocs1", "fromcs1", "partsaved", "partclear",
)

# (module key, symbol prefix, events handled). Table order is run order.
CLIENTS = (
    ("PLOCKS P2", "plk", ("loadall_pre", "loadmask_pre", "newproj", "bankw_pre",
                          "bankcopy", "tocs1", "fromcs1")),
    ("KITS", "kits", ("loadall_pre", "loadall_post", "loadmask_pre", "loadmask_post",
                      "newproj", "bankw_post", "pstore_pre", "pstore_post",
                      "preload_post", "partsaved", "partclear")),
    ("MIDI SCENES", "scn", ("loadall_pre", "loadmask_pre", "newproj", "bankw_post",
                            "pstore_pre", "pstore_post", "preload_post", "tocs1",
                            "fromcs1", "partclear")),
)


# A client's number in the refusal registry (store_refuse) and in ans_tab.
CLIENT_IDS = {"PLOCKS P2": 0, "KITS": 1, "MIDI SCENES": 2}


def store_inc(modules):
    out = ["ans_tab:"]
    for key, _prefix, _events in sorted(CLIENTS, key=lambda c: CLIENT_IDS[c[0]]):
        pre = {k: p for k, p, _e in CLIENTS}[key]
        out.append(f"        .long   {pre}_st_answer" if key in modules else "        .long   0")
    for ev in EVENTS:
        out.append(f"ev_{ev}:")
        for key, prefix, handled in CLIENTS:
            if key in modules and ev in handled:
                out.append(f"        .long   {prefix}_st_{ev}")
        out.append("        .long   0")
    return "\n".join(out) + "\n"


MODULE = Module(
    name="store",
    key="STORE",
    kind=Kind.CF_PATCH,
    category=Category.PARTS, author="sambanks", author_url="https://github.com/sambanks",
    proof=Proof.PORT, proof_note="",
    doc="Platform: the stock save, load, copy, CS1 and Part sites KITS and PLOCKS P2 share.",
    linked=(Linked("store", "modules/store/store.s", dram=True, include=store_inc),),
    detours=(
        Detour(0x40090504, H("4feffeb848d77cfc"), "store", "store_loadall",
               "a load of every bank", pad_to=8),
        Detour(0x400905D4, H("4feffeb848d77cfc"), "store", "store_loadmask",
               "a masked bank load (LOAD PROJECT, the power-up, reloads)", pad_to=8),
        Detour(0x400909D8, H("2f0a42a74eb94000fd34"), "store", "store_newproj",
               "a new, empty project", pad_to=10),
        Detour(0x400917C8, H("4e56febc48d73cfc"), "store", "store_bankw",
               "the bank writer: after the banks", pad_to=8),
        Detour(0x400918AA, H("45f9400e21e0"), "store", "store_bankw_mid",
               "inside the bank writer, after the project directory is made and before "
               "the first bankNN.work", kind="jmp", pad_to=6),
        Detour(0x4008EE74, H("4e56fdd048d73cfc"), "store", "store_pstore",
               "the project store (.work -> .strd)", pad_to=8),
        Detour(0x4008F180, H("4e56fdd048d73cfc"), "store", "store_preload",
               "the project reload (.strd -> .work)", pad_to=8),
        Detour(0x4008EE42, H("4eb940016388"), "store", "store_fcopy",
               "bank store's .work -> .strd copy", kind="jsr"),
        Detour(0x4008F14E, H("4eb940016388"), "store", "store_fcopy",
               "bank reload's .strd -> .work copy", kind="jsr"),
        Detour(0x4008EF9A, H("2a3c40016388"), "store", "store_d5_ef9a",
               "project store: the copy each bank file goes through",
               kind="jmp", pad_to=6),
        Detour(0x4008F02E, H("2a3c40016388"), "store", "store_d5_f02e",
               "project store: the copy each bank file goes through",
               kind="jmp", pad_to=6),
        Detour(0x4008F2A6, H("2a3c40016388"), "store", "store_d5_f2a6",
               "project reload: the copy each bank file goes through",
               kind="jmp", pad_to=6),
        Detour(0x4008F33A, H("2a3c40016388"), "store", "store_d5_f33a",
               "project reload: the copy each bank file goes through",
               kind="jmp", pad_to=6),
        Detour(0x4000FAF0, H("2f0a2f022f3c0008ed80"), "store", "store_tocs1",
               "stock copies the current bank into CS1", kind="jmp", pad_to=10),
        Detour(0x40025808, H("4eb94000fbb4"), "store", "store_fromcs1",
               "power-up: the bank back from CS1", kind="jsr"),
        Detour(0x4004A9C4, H("4cd70c1c4fef00144e75"), "store", "store_partsaved",
               "the Part Save's tail", pad_to=10),
        Detour(0x4004A9D0, H("4feffff048d70c0c"), "store", "store_partclear",
               "the Part Clear's entry", pad_to=8),
    ),
)
