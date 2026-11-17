# ZOOM KEEP

The audio editor keeps its zoom when a slice is auditioned. In SLICES trig mode a trig picks and plays a slice in the editor, and stock zooms the SLICE page out to fit the whole slice every time, so an edit zoomed in on a marker is thrown away at each audition. With ZOOM KEEP the zoom stays and only the slice start is scrolled into view.

Author: [8thmyth](https://github.com/8thmyth). ColdFire only, one linked DRAM unit (`zoomkeep.s`, a dozen instructions), no settings.

## How

Stock's slice select 0x40071668 calls the view fit 0x40077138(view, start, end, 0) at 0x40071712. A jsr detour there calls `zk_fitkeep` instead, which scrolls the slice start into view with the editor's own 0x40077004(view, &&frame) and returns 1 ("handled"), so the caller skips its own two scrolls. Nothing else changes: the selection, the marker and the voice are stock's.

Loading a sample into the editor (opening it, or a track key inside it) re-fits every page's view with the same 0x40077138. Four jsr detours (0x4006f87c TRIM, 0x40071b38 SLICE, 0x40074110 and 0x40074216 EDIT) call `zk_loadkeep` instead: once a page has been fitted since power-on it keeps that zoom and its first frame (the same place in time), moving them only so the sample stays on screen; the first load after power-on still gets stock's fit. LOCK EDIT positions the SLICE view itself after its open, as before.

## Who calls what ZOOM KEEP changes (trap-stock-callee; asked in sambanks/octabam#1099)

- **The slice select 0x40071668** (the 0x40071712 detour): one stock call, `jsr` at 0x4004f9d4 in 0x4004f8dc, which is reached from 0x4005028e (in 0x400501d8) and 0x40050156 (in 0x400500e6). Under the port (lazy-chop-mods image): a trig in SLICES trig mode reaches 0x4005028e on its press and its release, also with [TRACK] or [FUNC] held, and only the press selected a slice; grid recording, normal trig mode, the sequencer playing (SLICES or normal trig mode, 2.5 s each), LEVEL, knob A, the track key and opening or closing the editor never called 0x40071668. 0x40050156 was not reached in these runs (inferred: another entry of the same trig handler). LOCK EDIT calls 0x40071668 itself and positions the view afterwards. So every caller is an audition or LOCK EDIT.
  `tools/build/where.py 0x40071668` lists only this README's citations (it indexes docs and disassembles; it does not search callers), so the callers above come from the static scan and the port runs.

## Measured

- Under the ColdFire port (`tools/verify/verify_zoom_keep.py`, scenario `aedview`): encoder F zooms in; in SLICES trig mode TRIG 2 selects slice 2 with the zoom unchanged and slice 2's start in view; TRIG 1 selects slice 1 with the zoom still unchanged.
- Under the port (scenario `aedtracks`): the first open after power-on is fitted by stock on all three pages; TRIM, SLICE and EDIT each zoomed differently on track 1 all keep their zoom on track 2 and on returning to track 1, with each page's place in time kept where it was inside the sample.
- On 8thmyth's MKI (image OCTABAMHC, #1099's combined remix at commit a1bd2d2, 14 Nov 2026, and personal builds to T8 = c8e93954, 16 Nov): zoomed in on a marker, auditioning slices keeps the zoom. No issues found.

## Inferred / open

- Every caller of 0x40071668 keeps the zoom; the callers are listed above (the SLICES trig audition and LOCK EDIT).
- Every caller of 0x40077138 on an editor load keeps the zoom once that page has been fitted (the four callers above); the first load after power-on is stock's fit. On 8thmyth's MKI (personal build T9, 17 Nov 2026) TRIM and EDIT kept their zoom and place in time over about 40 track switches while SLICE re-fitted; the four callers here fix that path found after the port gate passed. A re-check of the final SLICE fix on the unit is still open (the `aedtracks` gate above is under the port).
