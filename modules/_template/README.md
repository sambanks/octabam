# <Module name>

One paragraph: what it is and why it exists.

(`modules/hello/README.md` is this template filled in, for a module small
enough to read whole.)

## Status

Where it actually stands. Separate **measured** from **inferred** — this
project has been burned by confident numbers more than once, so say what
would falsify a claim rather than writing "found it" for something reasoned.

## Parameters

| slot | name | what it does |
|---|---|---|
| 0 | P0 | |

## Open

What you know is unresolved. A named open question is worth more than a
clean-looking README.

## Gates

How a reader reproduces your measurements, in the order they must run.
`tools/verify_hello.py` is the pattern: predict the arithmetic exactly, drive
both signs, and make the tool refuse to run if the id it resolves is the
fallback rather than your effect.
