"""Render regressions for the shared stereo block limiter."""


def verify(render, check, frames, rail, min_ceiling=.25):
    ceiling_span = .75 - min_ceiling
    ceiling = int((.75 - 127 * ceiling_span / 128) * rail)
    quiet = [int(.05 * rail)] * (frames * 8)
    left, right = render(quiet, MIX=0, LIM=127)
    check("LIM max preserves quiet dry exactly", left == quiet and right == quiet)
    for offset in (0, 1, frames - 1, frames, frames + 1):
        for sign in (-1, 1):
            src = [0] * (frames * 8)
            src[frames * 3 + offset] = sign * int(.95 * rail)
            left, right = render(src, MIX=0, LIM=127)
            peak = max(abs(x) for x in left + right)
            check(f"LIM catches first transient, offset {offset}, sign {sign}",
                  ceiling - 16 <= peak <= ceiling + 4)
    src = [0] * (frames * 4) + [int(.95 * rail)] * (frames * 4)
    other = [x // 2 for x in src]
    left, right = render(src, MIX=0, LIM=127, right_samples=other)
    peak = max(abs(x) for x in left + right)
    check(f"LIM max peak near ceiling ({peak / rail:.3f} FS, target {ceiling / rail:.3f})",
          .90 * ceiling <= peak <= 1.04 * ceiling)
    check("LIM preserves stereo balance", max(abs(l - 2*r) for l,r in zip(left,right)) <= 3)
    left, right = render(src, MIX=0, LIM=0, right_samples=other)
    check("LIM off preserves stereo dry exactly", left == src and right == other)
