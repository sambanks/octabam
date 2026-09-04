"""BusDelay's GRAIN reader: four grains per line, or two.

ONE COPY OF THE SUBSTITUTION, imported by both the builder and the pricer.
They disagreed the first time this lever was written -- the image was rolled
to two grains and `make cycles` still priced four, so the saving the lever
exists for was invisible in the tool that measures it.

Three edits and nothing else (the markers live in the engine source):

  ; GRAINCNT   the two rolled loops count 2 instead of 4
  ; GRAINOFF   the grain-to-grain phase offset doubles, G/4 -> G/2, so two
              grains still tile the cycle
  ; GRAINMK    the makeup doubles: FOUR triangle windows at quarter offsets
              sum to exactly 2, TWO at half offsets sum to exactly 1

The doubling is `asl #$1`, the engine's own arithmetic form -- it keeps the
extension byte consistent with A1, which a logical shift would not
(CLAUDE.md's A2-staleness trap, paid on the next store).
"""

MARKERS = (("; GRAINCNT\n", 2), ("; GRAINOFF\n", 1), ("; GRAINMK\n", 2))


def census(src):
    """[(marker, found, expected)] for every marker whose count is wrong."""
    return [(m, src.count(m), n) for m, n in MARKERS if src.count(m) != n]


def roll(src, grains):
    """The delay source with its GRAIN reader rolled to `grains` per line."""
    if grains == 4:
        return src
    bad = census(src)
    if bad:
        raise ValueError("; ".join(f"{m.strip()}: {f} markers, expected {n}"
                                   for m, f, n in bad))
    src = src.replace("; GRAINCNT\n        do      #4,", "        do      #2,")
    src = src.replace("; GRAINOFF\n", """        move    x:(r7+$39),a
        asl     #$1,a,a                 ; grain-to-grain offset G/4 -> G/2
        move    a1,x0
        move    x0,x:(r7+$39)
""", 1)
    return src.replace("; GRAINMK\n", """        asl     #$1,b,b                 ; two windows sum to 1, not 2
""")
