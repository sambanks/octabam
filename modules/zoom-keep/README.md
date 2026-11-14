# ZOOM KEEP

The audio editor keeps its zoom when a slice is auditioned. In SLICES trig mode a trig picks and plays a slice in the editor, and stock zooms the SLICE page out to fit the whole slice every time, so an edit zoomed in on a marker is thrown away at each audition. With ZOOM KEEP the zoom stays and only the slice start is scrolled into view.

Author: [8thmyth](https://github.com/8thmyth). ColdFire only, one linked DRAM unit (`zoomkeep.s`, a dozen instructions), no settings.

## How

Stock's slice select 0x40071668 calls the view fit 0x40077138(view, start, end, 0) at 0x40071712. A jsr detour there calls `zk_fitkeep` instead, which scrolls the slice start into view with the editor's own 0x40077004(view, &&frame) and returns 1 ("handled"), so the caller skips its own two scrolls. Nothing else changes: the selection, the marker and the voice are stock's.

## Measured

- Under the ColdFire port (`tools/verify/verify_zoom_keep.py`, scenario `aedview`): encoder F zooms in; in SLICES trig mode TRIG 2 selects slice 2 with the zoom unchanged and slice 2's start in view; TRIG 1 selects slice 1 with the zoom still unchanged.
- On 8thmyth's MKI (image OCTABAMHC, remix `test/octabam-lazy-chop`, 14 Nov 2026): zoomed in on a marker, auditioning slices keeps the zoom. No issues found.

## Inferred / open

- Every caller of 0x40071668 now keeps the zoom. The trig audition and LOCK EDIT (which fits the view itself afterwards) were checked; other callers in 1.40C were not traced.
