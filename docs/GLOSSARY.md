# Glossary

The words this repository uses for its own parts. Octatrack terms (track,
Part, pattern, scene, machine) mean what Elektron's manual says.

| term | meaning |
|---|---|
| **module** | One contribution: an effect, a machine, a feature, a fix or a service. `modules/<name>/manifest.py` declares it. |
| **remix** | A named selection of modules, built into one image. `remixes/<name>/remix.py`. |
| **image** | A built firmware file: `.bin` for the card, `.syx` for MIDI, `.RMX` for REMIX SWITCH. It contains Elektron's OS, so it is never shared. |
| **stock** | Elektron's OS 1.40C as shipped, and anything in it. |
| **manifest** | A module's `manifest.py`: what the module is, its knobs, and every address, hook and id it claims. |
| **claim** | Something a module reserves: a cave, a hook site, an effect id, a memory range. The build refuses two modules with the same claim. |
| **ledger** | The part of the build that checks claims (`tools/remix/ledger.py`). |
| **ColdFire** | The Octatrack's main CPU. It runs the OS: the panel, the sequencer, the card, MIDI and USB. |
| **DSP**, **core A / core B** | The two DSP56300 audio cores. Core A runs tracks 5–8, core B tracks 1–4. |
| **payload** | The program the OS uploads to a DSP core. Payload A and payload B are the two cores' programs. |
| **insert** | A DSP effect that processes its own track only. Most effects are inserts. |
| **bus**, **server**, **client** | The delay and reverb bus in Octabam Bus. A server (the bus delay, the bus reverb) owns the shared mix; a client (SEND) feeds it from a track. |
| **cave** | A free stretch of the OS image that a module's ColdFire code is placed in. |
| **DRAM unit** | A module's ColdFire code linked into the runtime that is unpacked into RAM at boot, for code too large for a cave. |
| **detour** | A jump written over a stock instruction, so the OS runs a module's code there. |
| **hook** | A stock site several modules can attach to; `modules/hooks` calls each in turn. |
| **demand loader** | Copies an effect's code into the DSP only while a track uses it, so more effects fit than memory holds at once. |
| **STORE**, **EVENTS**, **HOOKS** | Shared services modules build on: saving their own data with the project, hearing transport and MIDI events, and sharing stock sites. Specs in `docs/specs/`. |
| **BRAIN** | The on-unit settings and templates menu (**PROJ → BRAIN**), and the module behind it. |
| **oracle** | The author's own build of a ported mod. The port must match it byte for byte. |
| **the port** | `tools/emu/ot_emu`: an emulator of the whole unit that the gates boot images in. |
| **dsp_host** | The DSP emulator that renders an effect to audio (`tools/harness/`). |
| **gate** | One automated check a change must pass, usually `tools/verify/verify_<name>.py`. |
| **reach** | The set of gates a change can affect. CI runs them on every pull request (`make reach`). |
| **refhash** | The check that a change to the build left every artifact bit-identical (`scripts/refhash.sh`). |
