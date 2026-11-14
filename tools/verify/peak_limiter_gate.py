"""Render regressions for the shared stereo block limiter."""


def verify(render, check, frames, rail):
    ceiling = int((1 - 127 * .25 / 128) * rail)
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
    check("LIM max stays within 2.6 dB of hot dry",
          .74 * rail <= peak <= ceiling + 4)
    check("LIM preserves stereo balance", max(abs(l - 2*r) for l,r in zip(left,right)) <= 3)
    left, right = render(src, MIX=0, LIM=0, right_samples=other)
    check("LIM off preserves stereo dry exactly", left == src and right == other)
