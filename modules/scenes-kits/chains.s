| SCENES KITS -- the bridge that lets MIDI SCENES and Octakit share the
| one stock instruction they both hook: the entry of apply_part
| (0x40009094). Linked into the platform runtime beside his units, so
| his symbols resolve directly; hers arrive as link-time values.
|
| His wrapper (midisc code2.s `apply`) did: save the caller's return
| address into apply_ret, put `after` on the stack in its place, jsr pack,
| replay the two displaced prologue instructions, jmp 0x4000909c. Her
| entry (gk_stock_engine_part_load_and_publish) replays that prologue
| itself, runs stock's body through her trampoline and publishes -- so the
| chain is his pre-work, then a jump into her entry, never a second replay.
|
| One rule of hers to respect: while her lifecycle state is not "active"
| (boot-time part loads) she decides her path by comparing the STOCK
| caller's return address on the stack against known sites, and anything
| else is her fatal. So the return-address swap only happens once she is
| active; before that the site is hers alone, and his boot-time unpack of
| the first part's locks is skipped (the next apply does it).
        .text
        .global chain_apply_part
chain_apply_part:
        tst.l   (__gk_lifecycle_state).l      | 0 = active
        bne.s   1f
        move.l  (%sp),(apply_ret).l           | his: keep the caller for `after`
        move.l  #after,(%sp)                  | ... and return through `after` (unpack)
        jsr     (pack).l                      | his: pack the outgoing part's locks
1:      jmp     (CHAIN_APPLY_NEXT).l          | hers: prologue, stock body, publish, rts
