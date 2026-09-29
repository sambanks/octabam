# `bottleservice-pf` -- bottleservice-ret plus POST FADER

[`bottleservice-ret`](../bottleservice-ret/README.md) plus
[POST FADER](../../modules/post-fader/manifest.py): every bus send (SEND's
DEL and REV, and the hosts' own) follows its track's fader, mute and solo,
the way an aux send does on a mixer. The knobs on the panel keep their
values; only what the DSP hears is scaled, by (LEVEL/128)^2 -- the mixer's
own law. A muted (or unsoloed) track sends nothing and does not count as a
sender, so the others keep their level.

A scene or the crossfader on a track's LEVEL moves its sends too.

## Where it has run

Not flashed.
