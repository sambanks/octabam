# octabam manual

octabam is an unofficial community remixer for the Elektron Octatrack's
operating system. Not affiliated with Elektron.

It composes **modules** — each one credited to its author — into **remixes**:
named selections, built into one firmware image from your own copy of OS
1.40C. The build places the code, wires the hooks by symbol, refuses
collisions by name, and proves every ported module against its author's own
build, byte for byte. No firmware is distributed here: a built image contains
Elektron's OS, so you build it yourself, on your machine.

!!! warning "This is not official Elektron firmware"
    Flashing a modified OS can leave the unit unusable until you recover it
    ([Safety and recovery](safety.md)), and puts your warranty in
    question. You flash at your own risk.

    **Do not share a built image.** A built `.bin` or `.syx` contains
    Elektron's OS.

The three remixes:

| remix | what it adds | effects | where it has run |
|---|---|---|---|
| [octabam-core](remix-core.md) | the core modules only | all 14 stock effects, both menus unchanged (LO-FI's AMF knob fixed) | port gates only; not on a unit |
| [octabam-inserts](remix-inserts.md) | core + insert effects | SPECTRUM, CHARACTER, MODULATION, TRANSIENT and EUCLID on FX1 and FX2, GATE VERB, the stock DELAY | port gates only; not on a unit |
| [octabam-bus](remix-bus.md) | core + a delay and reverb bus | DELAY on track 1, REVERB on track 5, SEND on every other track, the stock DELAY on track 8; SPECTRUM, CHARACTER and MODULATION on FX1 | port gates only; not on a unit |

None of the three has run on a unit. Each is verified under the port: an
emulator build boots the image and every gate passes, but the emulator is not
the hardware. The closest thing to a hardware run is bottleservice — the same
delay and reverb bus without the core modules — which ran on Sam's MKII
(images A0–A6, recorded in the changelog).

Start here:

- [Choosing a remix](choosing.md) — the three compared.
- [Build and flash](build-flash.md) — from nothing installed to a flashed unit.
- [BRAIN](brain.md) — the on-unit screens: templates, settings, defaults, and
  switching remixes from the card.
- [Modules reference](reference/modules.md) — every module, credited to its
  author, with its proof status.
- [Safety and recovery](safety.md) — the recovery procedure and its limits.

The repository: https://github.com/sambanks/octabam
