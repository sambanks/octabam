# cx-poly-meter

`cx-poly` with **CF METER** and **CF METER IDLE** for on-unit performance
measurement. DARK REV is omitted because its DSP words hold CF METER's
readout insert. CX OSC remains configured with `VOICES=POLY`.

Set track 8's FX2 to **CF Meter** to read the meter. The insert carries the
ColdFire frame-interrupt duration and DSP frame timing; CF METER IDLE adds the
ColdFire idle-time reading. Use `tools/harness/cfmeter.py` to decode a capture.

This is a measurement build. Its proof remains CHECK until this exact image is
confirmed on hardware.
