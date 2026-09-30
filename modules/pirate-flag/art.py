"""The Jolly Roger PIRATE FLAG draws: 128 x 64, one bit a pixel, made from
shapes here (never a copied bitmap). pixel(x, y) is True where the panel
lights; y counts from the top. The pole and the finial stay still; the
cloth (x >= CLOTH) waves in flag.s."""

import math

W, H = 128, 64
POLE = 9          # the pole's column
CLOTH = 12        # the first column of cloth


def _in_circle(x, y, cx, cy, r):
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def _near_segment(x, y, ax, ay, bx, by, r):
    vx, vy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((x - ax) * vx + (y - ay) * vy) / (vx * vx + vy * vy)))
    px, py = ax + t * vx, ay + t * vy
    return (x - px) ** 2 + (y - py) ** 2 <= r * r


def emblem(x, y):
    """The skull and crossbones, lit, centred on the cloth."""
    cx, cy = 68, 24
    # crossbones: two bars with knuckled ends, behind the skull
    for (ax, ay, bx, by) in ((cx - 22, cy + 8, cx + 22, cy + 24), (cx + 22, cy + 8, cx - 22, cy + 24)):
        if _near_segment(x, y, ax, ay, bx, by, 2.2):
            return True
        for (ex, ey), (dx, dy) in (((ax, ay), (bx - ax, by - ay)), ((bx, by), (ax - bx, ay - by))):
            n = math.hypot(dx, dy)
            ux, uy = dx / n, dy / n
            # two knobs at each end, across the bone
            for s in (-1, 1):
                if _in_circle(x, y, ex - uy * 2.6 * s, ey + ux * 2.6 * s, 2.6):
                    return True
    # the cranium and the jaw
    skull = _in_circle(x, y, cx, cy - 2, 11.5) or (cx - 7 <= x <= cx + 7 and cy + 4 <= y <= cy + 12)
    if not skull:
        return False
    # eyes, nose, the gaps between the teeth: holes in the skull
    if _in_circle(x, y, cx - 5, cy - 1, 3.4) or _in_circle(x, y, cx + 5, cy - 1, 3.4):
        return False
    if cy + 4 <= y <= cy + 6 and abs(x - cx) <= (y - (cy + 3)):
        return False
    if cy + 9 <= y <= cy + 12 and x in (cx - 4, cx - 1, cx + 2, cx + 5):
        return False
    return True


def pixel(x, y):
    # the pole, with a round finial
    if POLE - 1 <= x <= POLE + 1 and 5 <= y < H:
        return True
    if _in_circle(x, y, POLE, 3, 2.5):
        return True
    # the cloth: a black field with a lit hem, the emblem lit on it
    x0, x1, y0, y1 = CLOTH, 123, 6, 50
    if x0 <= x <= x1 and y0 <= y <= y1:
        if x in (x0, x1) or y in (y0, y1):
            return True
        return emblem(x, y)
    return False


def columns():
    """128 columns, each two longs of one big-endian 64-bit column: screen
    pixel (x, y) is "column 63 - y counted from the MSB" (docs/firmware/
    PANEL.md section 1), i.e. bit y from the LSB -- the top row is the LAST
    bit. (Written first as bit 63 - y from the LSB, it drew upside down.)"""
    out = []
    for x in range(W):
        v = 0
        for y in range(H):
            if pixel(x, y):
                v |= 1 << y
        out.append((v >> 32, v & 0xFFFFFFFF))
    return out
