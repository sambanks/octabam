# Remix proposals

A remix proposal is a selection of modules that someone wants to run, written
down before it is a remix under `remixes/`. Each proposal is taken through
the stages below on hardware until it is **verified stable**, then lands as
`remixes/<name>/` with its proof.

## Stages

| stage | what is done | where the result is recorded |
|---|---|---|
| 1. proposed | the module list, who asked for it, the source of the request | the proposal page |
| 2. composes | `make bus REMIX=<name>` builds (no claim collision, every cave fits) | the proposal page: the build's refusal, quoted, or "builds" with the commit |
| 3. checked | `make check REMIX=<name>`, then `OT_PROJECT=<dir> make check REMIX=<name>` (the set under the port) | the proposal page: commands, commit, result |
| 4. on hardware | flashed on a named unit; the checklist below run | the proposal page, then `CHANGELOG.md` for the image |
| 5. verified stable | the checklist passed on at least two units, at least one of them not Sam's, on the same image | `remixes/<name>/` lands with `Proof.HARDWARE` and the units, images and dates in `proof_note` |

## Hardware checklist

Each item is run per unit and recorded with the unit (MKI/MKII), image and
date.

- boots; a project from the stock OS loads
- each module's own use steps from its README run as written
- PLAY / STOP over a full pattern chain, every bank used by the project
- project save, power cycle, reload: everything saved comes back
- one session of normal use (length recorded) with no halt, no audio fault
- anything that did go wrong goes into
  [FAILURE_MODES.md](../../contributing/FAILURE_MODES.md)

## Proposals

| proposal | modules | requested by | stage |
|---|---|---|---|
| [radiohagen](radiohagen.md) | the delay and reverb bus, SPECTRUM, CHARACTER, MODULATION, RLEN PLEN, TUNER | radiohagen | 2: composes |
|  |