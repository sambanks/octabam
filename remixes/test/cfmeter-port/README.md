# `cfmeter-port` — `cfmeter` without the idle loop, for the port gate

The same selection as [`cfmeter`](../cfmeter/README.md) without CF METER
IDLE. Until the ColdFire port advanced its clock only at
main's stock `bras .`, which the idle loop replaces, so `cfmeter` did not
load a project there; the port follows the detour now and `cfmeter`
passes its gates too. The idle slot reads 0 here.

    OT_PROJECT=<dir> make check REMIX=cfmeter-port
    python3 tools/harness/cfmeter.py --dump out/setverify/port.dump

With T8's FX2 = CF METER (`tools/hw/ot_project.py set-fx <dir> fx2 8 "CF
METER"`) the decoder prints the interrupt timing; a cycle is 2 s (16
slots), so the dump needs about 12,000 frames for two sync edges. The
module's own gate, `tools/verify/verify_cfmeter.py` (in `make check`
with a project), reads the DSP meter's slots straight from T8's instance
block instead, in 900 frames, with DBRN 0 / 40 / 127; see
[`modules/cfmeter/README.md`](../../../modules/cfmeter/README.md) "Measured
under the port". Not for flashing.
