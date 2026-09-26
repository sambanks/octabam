# SCENES P2 KITS: the editor-entry bridge

Lets SCENES P2 and Octakit share the two page-2 editor entries (FX2
`0x4003a9dc`, FX1 `0x4003abe4`). `Kind.CF_PATCH`: two `Override`s, nothing
of its own to use. Requires both modules (`Module.requires`; the ledger
refuses a remix with the bridge and without them).

Her recipe writes `jmp <wrapper>` at each entry; the wrapper prepares a
kit-write token, calls the stock body and validates at her marker inside it
that the body stored what she expected (`track_twelve_byte_editor.S`). A
turn with a scene held must not reach the body. With the bridge her writes
are skipped and `P2_NEXT2` / `P2_NEXT1` are defined as the wrappers they
carried; SCENES P2's stubs sit at the entries and jump on to her wrapper
whenever no scene is held.

Measured under the port (rig-kits): the held-scene call returns and writes
the pool; the unheld call reaches her wrapper, which refuses a `--call` the
same way plain rig-kits does (no UI context).
