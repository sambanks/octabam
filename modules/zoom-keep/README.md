# ZOOM KEEP

The audio editor keeps its zoom when a slice is auditioned, and every page (TRIM, SLICE, EDIT) keeps its own zoom and place in time across tracks. In SLICES trig mode a trig picks and plays a slice in the editor, and stock zooms the SLICE page out to fit the whole slice every time, so an edit zoomed in on a marker is thrown away at each audition. With ZOOM KEEP the zoom stays and only the slice start is scrolled into view.

Author: [8thmyth](https://github.com/8thmyth). ColdFire only, one linked DRAM unit (`zoomkeep.s`, a dozen instructions), no settings.

## How

Stock's slice select 0x40071668 calls the view fit 0x40077138(view, start, end, 0) at 0x40071712. A jsr detour there calls `zk_fitkeep` instead, which scrolls the slice start into view with the editor's own 0x40077004(view, &&frame) and returns 1 ("handled"), so the caller skips its own two scrolls. Nothing else changes: the selection, the marker and the voice are stock's.

## Every page keeps its zoom across tracks (16 Nov 2026)

Loading a sample into the editor (opening it, or a track key inside it) runs one routine per page that re-fits that page's view to the whole new sample with the same fit 0x40077138: TRIM's view 0x400ce724 (jsr at 0x4006f87c, in 0x4006f7a6), SLICE's 0x400ceb14 (0x40071b38, in 0x40071a02) and EDIT's 0x400cef60 (0x40074110 in 0x4007409c, and 0x40074216 in 0x400741c0). Measured under the port on the lazy-chop-mods image: the T1 -> T2 track key writes each view's frames-a-pixel (+0x10) and first frame (+0x18) from exactly these calls; which page owns which view was read by zooming on each page key. None of the four callers reads the fit's result.

`zk_loadkeep` stands in for those four calls. A view that has been fitted once since power-on keeps its zoom and its first frame (the same place in time); a first frame that would leave the screen past the sample's end, or before its start, is moved (the end at the right edge; a sample shorter than the screen from its start), with the fit's own margins. The first load after power-on is stock's fit: the views hold a default zoom of 3 at boot (measured), so a bit per view in `zk_seen` tells instead. LOCK EDIT positions the SLICE view itself after its open, as before (its gates pass unchanged).

## Who calls what ZOOM KEEP changes (trap-stock-callee; asked in sambanks/octabam#1099)

- **The slice select 0x40071668** (the 0x40071712 detour): one stock call, `jsr` at 0x4004f9d4 in 0x4004f8dc, which is reached from 0x4005028e (in 0x400501d8) and 0x40050156 (in 0x400500e6). Under the port (lazy-chop-mods image): a trig in SLICES trig mode reaches 0x4005028e on its press and its release, also with [TRACK] or [FUNC] held, and only the press selected a slice; grid recording, normal trig mode, the sequencer playing (SLICES or normal trig mode, 2.5 s each), LEVEL, knob A, the track key and opening or closing the editor never called 0x40071668. 0x40050156 was not reached in these runs (inferred: another entry of the same trig handler). LOCK EDIT calls 0x40071668 itself and positions the view afterwards. So every caller is an audition or LOCK EDIT.
- **The four page fits** (zk_loadkeep): reached only through the editor's sample load (its open and a track key inside it), measured as above; their routines have no direct callers in 1.40C (they are reached through the page records).
