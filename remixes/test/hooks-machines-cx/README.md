# hooks-machines-cx (test remix)

OCTA303 and CX OSC in one image: HOOKS gives the track's machine list seven rows, OCTA-303 on row 5 and CX OSC on row 6, and the list scrolls. See [HOOKS](../../../modules/hooks/README.md) (`machine_rows`).

`tools/verify/verify_hooks.py hooks-machines-cx` checks the bridged sites in this image after
`make bus REMIX=hooks-machines-cx`.

## Where it has run

Not flashed. Built, and its sites checked (verify_hooks); verify_octa303_ui and verify_cxosc pass on this image under the port with a fresh project (31 Oct 2026), and CX OSC chosen from the panel signs `CX 1` (a scratch script, not a gate).
