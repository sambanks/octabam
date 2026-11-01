# hooks-machines-all (test remix)

ANALOG BD, OCTA303 and CX OSC in one image: HOOKS gives the track's machine list eight rows, ANALOG BD on row 5, OCTA-303 on row 6 and CX OSC on row 7, and the list scrolls. See [HOOKS](../../../modules/hooks/README.md) (`machine_rows`).

`tools/verify/verify_hooks.py hooks-machines-all` checks the bridged sites in this image after
`make bus REMIX=hooks-machines-all`.

## Where it has run

Not flashed. Built, and its sites checked (verify_hooks); verify_analog_bassdrum_ui, verify_octa303_ui and verify_cxosc pass on this image under the port with a fresh project (31 Oct 2026), and CX OSC chosen from the panel (row 7) signs `CX 1` (a scratch script, not a gate).
