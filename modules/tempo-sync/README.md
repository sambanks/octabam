# Tempo sync

Two ColdFire code caves — the project's first, and the worked example of a
module that changes what the firmware *does* rather than adding an effect.

**The publish cave** hooks the per-frame voice-record writer, replays the
instruction it displaced, and stores the project tempo, samples-per-MIDI-clock,
the crossfader position and any held MIDI note into four halfwords of the
record that are written every frame and never read. They arrive on the DSP
side as `r6+$6..$9`. Without it the DSP has no way to know what a bar is.

**The formatter cave** draws BongDelay's TIME knob: the division name while
the DSP's sticky snap holds one, milliseconds otherwise.

`NOTEMPO=1` installs neither, and the DSP side then reads zeros with SYNC a
no-op by design. `TEMPOCAVE=replay` installs a cave that only replays the
displaced instructions, which isolates the hook mechanism from the stores —
that diagnostic exists because two earlier revisions killed every voice on
the unit.

## Open

⚠️ **The publish cave filters on FX2 ids 6 and 7, and those ids are compiled
into the pinned machine code.** A module that changes its id does not change
this cave, and the two then disagree silently — the DSP simply never sees a
tempo. Patching values into a cave at build time is what would fix it.

Background: [`docs/DSP.md`](../../docs/DSP.md) §6c,
[`docs/PARAM_PAGES.md`](../../docs/PARAM_PAGES.md) §7.
