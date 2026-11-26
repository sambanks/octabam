# Glossary

Terms specific to this repository. Standard Octatrack terms (track, Part,
pattern, scene, machine) follow Elektron's manual.

| Term | Meaning |
|---|---|
| **module** | A single contributed feature: an effect, machine, utility, bugfix, or shared service, declared in `modules/<name>/manifest.py`. |
| **remix** | A named selection of modules built into a single firmware image, defined in `remixes/<name>/remix.py`. |
| **image** | A built firmware file (`.bin` for the CF card, `.syx` for MIDI, `.RMX` for REMIX SWITCH). Because it contains Elektron's OS, it must never be shared. |
| **stock** | Elektron's unmodified OS 1.40C and any code or data shipped with it. |
| **manifest** | A module's `manifest.py` file, which defines the module's metadata, parameters, and every address, hook, and ID it claims. |
| **claim** | A resource reserved by a module, such as a cave, hook site, effect ID, or memory range. The build rejects any combination of modules with overlapping claims. |
| **ledger** | The build component that checks claims for conflicts (`tools/remix/ledger.py`). |
| **ColdFire** | The Octatrack's main CPU, which runs the OS, front panel, sequencer, CF card, MIDI, and USB. |
| **DSP**, **core A / core B** | The two DSP56300 audio processor cores. Core A handles tracks 5–8 and core B handles tracks 1–4. |
| **payload** | The program uploaded by the OS to a DSP core. Payload A runs on core A and payload B runs on core B. |
| **insert** | A DSP effect that processes only the track it is placed on. Most effects are inserts. |
| **bus**, **server**, **client** | The shared delay and reverb bus in Octabam Bus. A server (Bus Delay or Bus Reverb) runs the shared effect, and a client (SEND) routes audio to it from a track. |
| **cave** | An unused region inside the stock OS image where a module's ColdFire code can be placed. |
| **DRAM unit** | ColdFire module code linked into a runtime that unpacks into DRAM at boot, used for code too large to fit in a ROM cave. |
| **detour** | A jump patched over a stock instruction to redirect execution into a module's code. |
| **hook** | A stock code site that multiple modules can attach to; `modules/hooks` dispatches each registered handler in turn. |
| **demand loader** | Loads an effect's DSP code only while a track is using it, allowing more effects in a remix than fit in DSP memory simultaneously. |
| **STORE**, **EVENTS**, **HOOKS** | Shared services that modules can use to save data with projects, subscribe to transport/MIDI events, and share stock code sites. See `docs/specs/`. |
| **BRAIN** | The on-unit settings and templates menu (**PROJ → BRAIN**), and the module that implements it. |
| **oracle** | The original author's compiled build of a ported mod, used as a byte-for-byte reference check. |
| **the port** | `tools/emu/ot_emu`, the full-unit emulator used by verification gates to boot and test firmware images. |
| **dsp_host** | The DSP emulator used to render effects to audio locally (`tools/harness/`). |
| **gate** | An automated verification check that a change must pass, usually a `tools/verify/verify_<name>.py` script. |
| **reach** | The set of gates affected by a diff. CI runs all reached gates on every pull request (`make reach`). |
| **refhash** | The check verifying that a build-system change leaves all output artifacts bit-identical (`scripts/refhash.sh`). |
