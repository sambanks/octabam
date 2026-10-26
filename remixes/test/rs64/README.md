# `rs64` -- REMIX SWITCH in a 64-id image

[`remix-switch`](../remix-switch/README.md) in an image built with `id_space=64`, with BBD on FX2 id `0x25` in the shared window.

## What is in it

- **BRAIN** and **REMIX SWITCH** as in `remix-switch`.
- **BBD** -- [`modules/bbd/README.md`](../../../modules/bbd/README.md), on `0x25` through `Remix.ids`, placed in the window at `0x35000`.
- the 14 stock effects, listed so the chooser is stock's.

## Status

Port only. `verify_remix_switch` passes all 35 checks on it, as on `remix-switch`. Its DSP check re-uploads both payloads through the park, and
reads their addresses and lengths from the image: the 64-id layout adds a record to each payload and moves B, so the 32-id constants made the
upload walk fail (28 Oct 2026). Not flashed.
