# `bottleservice` — the rig, USB, Octakit

[`usb-audio`](usb.md) (the rig + USB MIDI + USB AUDIO) with Em's Octakit
(256 Kits per Project in place of Parts) and the SCENES KITS bridge that
lets CC MAP and Octakit share the MIDI CC dispatch entry. Sam's own
selection; named after the set it is built for.

## What is in it

- Everything in [`usb-audio`](usb.md): the bus (BusDelay on T1, BusVerb on
  T5, SEND elsewhere), the three FX1 stations, TEMPO SYNC, CC MAP, MODE
  DEFAULTS, RIG HOSTS, TEMPO BUS, USB MIDI, USB AUDIO.
- **OCTAKIT** (Em, [ems-octakit](https://github.com/emuyia/ems-octakit)):
  [`modules/octakit/README.md`](../../modules/octakit/README.md). Her
  runtime takes the top 528 pages of the sample arena (3.2 MB); the USB
  platform reserve takes 1,707 at the bottom (10.5 MB): 12,367 pages for
  samples and recorders against stock's 14,602.
- **SCENES KITS**: the bridge, [`modules/scenes-kits`](../../modules/scenes-kits/manifest.py).
- **SCENES P2** (Sam Banks) — scene locks and the crossfader on page 2 of FX1 and FX2: hold a scene and turn a page-2 knob (FUNC + turn removes the lock); the fader lerps locked page-2 slots into the DSP frame, a select snapping at the midpoint; locks follow scene copy / paste / clear / undo and travel in the Part. Port only (`modules/scenes-p2/README.md`).
- **SCENES P2 KITS** (Sam Banks) — the bridge over Octakit's page-2 editor wrappers: a held-scene turn writes the lock pool and never enters her wrapper; every other turn reaches it whole.

DSP side identical to `bamsep26` (payload A 430 words free, B 1,128;
worst core priced 2,792 of 3,120). Image 1.19 MB.

## Status

- Not flashed.
- Under the port (26 Sep 2026): `OT_PROJECT=<the make accept stress project>
  make check REMIX=bottleservice` -- every gate, `verify_set` 900/900 frames.
  Kit save, FUNC+CUE reload, cross-Kit load and LOAD KIT copy/paste
  measured with page-1 values written by MODE DEFAULTS and page-2 values by
  CC MAP: `modules/octakit/README.md` "Calling the page-1 writer beside
  her".
- The defect that made this remix: TEMPO BUS and MODE DEFAULTS called the
  stock page-1 writer bare, and Octakit's rewrite of its dirty store halts
  on a call without her token. Fixed by pushing the token (26 Sep 2026);
  before that, a MODE change on the panel or over CC 68-73, or any TEMPO
  screen edit, would have stopped the unit.
- Not measured: hardware; her unsaved-changes marking after a tokened or
  page-2 write; UNDO KIT and pattern-paste after one; whether the rig's
  host stamping (`ot_project.py host`, `stamp-defaults`) survives her
  Parts->Kits migration (`rig-kits` has the same open question).

## Build and flash

As [`usb-audio`](usb.md#build-and-flash) with `REMIX=bottleservice`. **Back
up projects first**: Octakit migrates Parts to Kits on load and downgrading
may lose Kit data (her README). After the flash, on old projects:
`ot_project.py host` / `stamp-defaults` as for `bamsep26`.
