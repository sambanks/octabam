"""BRAIN's boot screen: a brain over OCTABAM, 128 x 64, one bit a pixel,
drawn from shapes (never a copied bitmap). pixel(x, y, frame) is True where
the panel lights; y counts from the top. hooks.s brain_boot_frame draws the
same reveal from the columns manifest.py boot_inc generates; verify_brain
compares a frame bit for bit. `python3 bootart.py out.png [frame]` renders
one frame."""
import math
W, H = 128, 64

FONT = {  # 5 x 7
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
}
WORD, SCALE, TOP = "OCTABAM", 2, 48
WX0 = (W - (len(WORD) * 6 - 1) * SCALE) // 2

def word_pixel(x, y):
    if not (TOP <= y < TOP + 7 * SCALE):
        return False
    gx = (x - WX0) // SCALE
    if gx < 0:
        return False
    ch, col = divmod(gx, 6)
    if ch >= len(WORD) or col == 5:
        return False
    return FONT[WORD[ch]][(y - TOP) // SCALE][col] == "1"

CX, CY = 60, 23

def radius(th):
    """The cerebrum's outline in polar form round (CX, CY): an egg, wider at
    the front (left), a temporal bulge low down, gyri bumps all round."""
    rx, ry = 33, 19
    base = (rx * ry) / math.hypot(ry * math.cos(th), rx * math.sin(th))
    front = 1.0 + 0.10 * math.cos(th - math.pi) ** 3 if math.cos(th) < 0 else 1.0
    temporal = 1.0 + 0.12 * math.exp(-((th - 2.3) ** 2) / 0.08)      # low, at the front-bottom
    under = 0.82 if math.sin(th) > 0.35 and math.cos(th) > -0.2 else 1.0   # the underside tucks in
    bumps = 1.0 + 0.045 * math.sin(11 * th)
    return base * front * temporal * under * bumps

def cerebrum(x, y):
    dx, dy = x - CX, y - CY
    return math.hypot(dx, dy) <= radius(math.atan2(dy, dx))

def cerebellum(x, y):
    return ((x - 83) / 11) ** 2 + ((y - 37) / 6.5) ** 2 <= 1.0 and not cerebrum(x, y)

def stem(x, y):
    return 70 <= x <= 76 and 34 <= y <= 46 - (x - 70) // 2 and not cerebrum(x, y) and not cerebellum(x, y)

def edge(f, x, y):
    return f(x, y) and not (f(x - 1, y) and f(x + 1, y) and f(x, y - 1) and f(x, y + 1))

def _seg(x, y, pts, r=0.55):
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        vx, vy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((x - ax) * vx + (y - ay) * vy) / (vx * vx + vy * vy)))
        if (x - ax - t * vx) ** 2 + (y - ay - t * vy) ** 2 <= r * r:
            return True
    return False

# the folds: short wandering curves, in grid coordinates
FOLDS = [
    [(40, 14), (44, 11), (48, 14), (52, 11), (56, 13)],
    [(60, 9), (64, 13), (68, 10), (72, 13), (76, 11)],
    [(34, 22), (38, 19), (42, 22), (46, 19)],
    [(50, 20), (54, 17), (58, 20), (62, 18), (66, 21), (70, 18), (74, 20), (80, 18)],
    [(38, 29), (42, 26), (47, 29), (52, 27)],
    [(56, 28), (61, 25), (66, 28), (71, 26), (76, 28)],
    [(84, 14), (86, 19), (84, 24), (86, 28)],          # the parietal-occipital fold
    [(58, 5), (57, 10), (59, 15), (57, 20), (59, 24)],  # the central fold
]

def brain_pixel(x, y):
    if edge(cerebrum, x, y) or edge(cerebellum, x, y) or edge(stem, x, y):
        return True
    if cerebellum(x, y) and (y - 33) % 2 == 0 and x % 3 != 0:
        return True
    if cerebrum(x, y) and any(_seg(x, y, f) for f in FOLDS):
        return True
    return False

def pixel(x, y, frame=559):
    """frame 0..559 (the OS animation's DTIM3 time over its 2.8 s): the brain
    draws in from the left by frame 200 (frame * 128 / 200 columns), the
    word from 240 to 400 ((frame - 240) * 128 / 160 columns)."""
    reveal = min(W, frame * W // 200)
    if brain_pixel(x, y) and x < reveal:
        return True
    if frame >= 240 and word_pixel(x, y) and x < (frame - 240) * W // 160:
        return True
    return False

def png(path, frame=559, scale=4):
    from PIL import Image
    im = Image.new("1", (W * scale, H * scale), 0)
    px = im.load()
    for y in range(H):
        for x in range(W):
            if pixel(x, y, frame):
                for a in range(scale):
                    for b in range(scale):
                        px[x * scale + a, y * scale + b] = 1
    im.save(path)

if __name__ == "__main__":
    import sys
    png(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 559)
