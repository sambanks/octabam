| SYNTH MACHINE -- PLACE=DRAM wrapper around upstream page.s.
| Tim's page.s keeps fm_descriptor / pg_resolve file-local (CAVE form:
| machine.s reaches them through engine_abi's absolute FM_DESC at
| 0x400d24d0). In the platform runtime those labels must be global so
| remix.inc can `.set FM_DESC, fm_descriptor` and the linker binds
| machine.s's .long FM_DESC to the DRAM page (else the chooser jumps
| into the emptied cave and the unit takes VEC 04 at 0x400d24d0).
        .global fm_descriptor, pg_resolve
        .include "modules/synth/upstream/synth/page.s"
