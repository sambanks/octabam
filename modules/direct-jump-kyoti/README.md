# `direct-jump-kyoti` -- DIRECT_JUMP_KYOTI

An immediate pattern change, toggled with `[PTN]` + `[YES]` and OFF at every power-on. A cued pattern takes over on the next step, locked to the master clock: it plays where it would be had it been running since the last restart (PLAY, or the last normal pattern change), whatever its track lengths, scales or master settings.

Built from [Zac-Kyoti/octatrack-kyoti-fw](https://github.com/Zac-Kyoti/octatrack-kyoti-fw)
(submodule `upstream/`, pinned to `cd788e9`). `Kind.CF_PATCH`. One DRAM unit (`patch_directjump_v7.s`, `Linked(dram=True)`, 3,938 B) with hooks at `0x400a1f72` (the landing), `0x400a221c` (the MIDI START gate), `0x40043418` (the `[PTN]` release), `0x40009ebe` (the light Part apply) and `0x400a4850` (stock's pattern switch, its `jsr` to COND_RESET), and the `[PTN]`-layer YES record (the rest of that record is a `Keep`). Its on/off word lives in the unit, which the platform loader unpacks at every boot, so it comes up OFF. A remix with this module carries the platform loader and its 10 MiB arena reserve, unless another DRAM module already brings them.
`upstream/octabam-modules/direct-jump-kyoti/README.md` is the full description, with what was measured and what was inferred.

## Measured

- Every build re-links each cave or unit and compares it with the author's
  own bytes (`reference`); a difference refuses the build.
- `make check REMIX=direct-jump-kyoti` (`remixes/test/direct-jump-kyoti/`) builds and boots the
  image under the ColdFire port.

## On the unit

- 27-28 Sep 2026: the clock-locked timing and the Part change on the author's MKI (standalone image `140C_KDJ7`, and the KYOTI V1.0 combined image).
- 1 Oct 2026: from DRAM, in an octabam image with all six KYOTI modules (`kyoti-all`-style remix, OBKYOTI6 and OBKYOTI7): the toggle, OFF after a power-cycle with MUTE MODE's widened restore active, the clock-locked landing and the Part change.
- 15 Nov 2026, V7.2.2 (`109f54c`): the standalone image `140C_KDJ7`, with SILENCE TRACKS on: the pop at a Part-changing jump is gone. The same code in KYOTI V1.8C passed the author's walk-through: landings at other lengths and scales, a cue in the outgoing pattern's last step, trig conditions carried across a jump, and each track's Part at its own first trig with LFO AUTO CHANGE on. This octabam form has not been flashed.
- 16 Nov 2026, V7.3 (`cd788e9`): KYOTI V1.8C (`KY18C DJR1`). After a normal change from a 16-step A01 to a 12-step A02, a jump to a 12-step A03 lands in phase with A02, `1:2` trigs stay in step across it, and a Clyps one-track load after it stays in step. This octabam form has not been flashed.
- Emulator-verified only (author's `ot_emu`): Program Change on fast re-cues, MIDI tracks, START SILENT, and a RELOAD_FROM_PROJECT reload after a jump.

## Notes

- Not the same module as Tim Hastie's DIRECT JUMP (`modules/direct-jump/`, CHAIN AFTER: DIRECT). The ledger finds no shared address, but both change when a cued pattern takes over and they have not been run in one image: take one per remix.
- Requires BATCH_BUGFIXES (`requires`): DIRECT JUMP reads each track's live scale byte, and stock's per-track scale seed for a MIDI track can leave garbage there, which that module's MIDI Plays-Free fix removes. The source also guards every step-length lookup (scale bytes above 6 read as the master's, or 1x), so a garbage byte cannot divide by zero in the tick handler. The bundle's Part-change carryover fix also covers the handler a jump's Part change reaches.
- Not with OCTAKIT, for now: the module declares the conflict. Octakit runs every pattern switch as a checked Kit transaction, and a jump hands off the Part outside it; images with both were reported to crash. The ledger saw no shared byte. A bridge is planned (`upstream/reference/handoffs/DIRECTJUMP_OCTAKIT_SCOPE.md`).
