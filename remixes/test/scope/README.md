# test/scope

Stock effects plus **SCOPE** and **TUNER**, sharing their TEMPO, frame and UI hooks through **HOOKS**.

**DOWN + TEMPO** = OSC / XY / ALL (4×2); **UP + TEMPO** = TUNER.
On a unit (Ilia, 2026-11-15): `SCOPE T1.RMX`; user reports SCOPE and TUNER both work through the shared hooks.
Build: `REMIX=test/scope`. The targeted HOOKS gate reaches Unicorn but exits with `SIGILL` here.
