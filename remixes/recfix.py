"""recfix -- the recorder loop click fix, and nothing else.

Five ColdFire caves, no DSP code of ours, the 14 stock effects listed so
the chooser is stock's:

  FLEX SEEK BIND      a same-buffer re-bind is a SEEK for the DSP, not a new
                      note (removes the voice-restart transient)
  FLEX SEEK BIND CTR  the per-bind counter is held (removes the +/-1.5-sample
                      seam)
  RECORDER SPACING    each fixed-RLEN pass is exactly as long as the gap to
                      its next arm (removes the skipped sample on alternate
                      bars at tempos whose length is not an integer)
  RECORDER HOLD       a recorder-buffer voice reading one sample past its
                      recording repeats the last sample instead of reading
                      zero (sound-on-sound, SRC3 = the track, at tempos
                      whose bar is not a whole number of samples)
  RLEN PLEN           RLEN value PLEN (past MAX): one loop of the track's
                      pattern on its own scale, so TRIG ONE + QREC PLEN
                      records the next pass and stops

docs/firmware/RECORDER_CLICK.md has the reproduction. Measured on hardware
as OCTABAM83 (the first three plus the bus) and OCTABAM84 (the first
three); RECORDER HOLD is port-gated only. Whether RECORDER SPACING alone
would suffice is untested.
"""

from remix.schema import Remix

REMIX = Remix(
    name="recfix",
    doc="The recorder loop click: the four ColdFire fixes beside the stock FX2 "
        "chooser, no DSP code of our own.",
    modules=("FLEX SEEK BIND", "FLEX SEEK BIND CTR", "RECORDER SPACING",
             "RECORDER HOLD", "RLEN PLEN",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
