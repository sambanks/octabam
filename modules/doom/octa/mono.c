/* octabam DOOM -- Doom's 320x200 frame on the Octatrack's 128x64 panel.
 *
 * SPDX-License-Identifier: GPL-2.0-or-later
 *
 * Box-filtered luminance (each panel pixel averages the source pixels it
 * covers), a 3x3 unsharp mask so walls keep their edges against their own
 * textures, a contrast stretch, then a 4x4 ordered dither: stable from
 * frame to frame, where an error-diffusion dither crawls. One bit a pixel:
 * the panel's second plane is not understood (docs/firmware/PANEL.md
 * section 1), so no greys. Tuned by eye against a 320x200 frame dumped
 * from the port (E1M1, the first room); the alternatives it was chosen
 * over are in README.md.
 *
 * Two framings: FULL scales all 200 rows to 64 (title, menus, the map,
 * intermissions); VIEW scales the 3D view's 168 rows to the top 56 and
 * leaves the bottom 8 for a line of text (doom_octa.c's HUD), since the
 * status bar at 128 pixels wide is unreadable.
 *
 * The plane layout (PANEL.md section 1, and lcd_view.py's window planes):
 * stored a quarter turn round, 128 rows of 8 bytes, one row per screen
 * column, MSB first; screen pixel (x, y), y from the top, is bit 63 - y of
 * row x. The frame is built off-screen and copied whole, so a flush never
 * sends half a frame.
 */
#include <string.h>
#include "octa.h"

#define SW 320
#define DW 128

static const uint8_t bayer[4][4] = {
    {  0,  8,  2, 10 },
    { 12,  4, 14,  6 },
    {  3, 11,  1,  9 },
    { 15,  7, 13,  5 },
};

static uint8_t lum[64][DW];
static uint8_t work[DW * 8];

/* src rows [0, sh) -> panel rows [0, dh) */
static void box(const uint32_t *src, int sh, int dh)
{
    static uint16_t row[SW];
    static uint32_t acc[DW];
    int x, y, sx, sy;
    for (y = 0; y < dh; y++) {
        int ya = y * sh / dh, yb = (y + 1) * sh / dh;
        for (x = 0; x < DW; x++)
            acc[x] = 0;
        for (sy = ya; sy < yb; sy++) {
            const uint32_t *p = src + sy * SW;
            for (sx = 0; sx < SW; sx++) {
                uint32_t c = p[sx];
                row[sx] = (uint16_t)((((c >> 16) & 0xff) * 77u + ((c >> 8) & 0xff) * 151u
                                      + (c & 0xff) * 28u) >> 8);
            }
            for (x = 0; x < DW; x++) {
                int xa = x * SW / DW, xb = (x + 1) * SW / DW;
                uint32_t s = 0;
                for (sx = xa; sx < xb; sx++)
                    s += row[sx];
                acc[x] += s;
            }
        }
        for (x = 0; x < DW; x++) {
            unsigned n = (unsigned)((x + 1) * SW / DW - x * SW / DW) * (unsigned)(yb - ya);
            lum[y][x] = (uint8_t)(acc[x] / n);
        }
    }
}

static int at(int y, int x, int dh)
{
    if (y < 0) y = 0;
    if (y >= dh) y = dh - 1;
    if (x < 0) x = 0;
    if (x >= DW) x = DW - 1;
    return lum[y][x];
}

void mono_frame(const uint32_t *src, uint8_t *plane, int view)
{
    int sh = view ? 168 : 200, dh = view ? 56 : 64;
    int x, y;
    box(src, sh, dh);
    memset(work, 0, sizeof work);
    for (y = 0; y < dh; y++) {
        for (x = 0; x < DW; x++) {
            int c = lum[y][x], s = 0, dy, dx, v;
            for (dy = -1; dy <= 1; dy++)
                for (dx = -1; dx <= 1; dx++)
                    s += at(y + dy, x + dx, dh);
            v = c + (c - s / 9);                   /* unsharp, k = 1 */
            v = (v - 20) * 8 / 5;                  /* stretch: Doom is dark */
            if (v > bayer[y & 3][x & 3] * 16 + 8) {
                int b = 63 - y;
                work[x * 8 + (b >> 3)] |= (uint8_t)(0x80u >> (b & 7));
            }
        }
    }
    memcpy(plane, work, sizeof work);
}
