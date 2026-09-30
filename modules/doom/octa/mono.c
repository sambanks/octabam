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
 * The input is Doom's own 8-bit frame (doomgeneric built CMAP256) and a
 * luminance per palette entry, so nothing converts 64,000 pixels to 32-bit
 * colour and back. Every panel column covers 2 or 3 source columns in a
 * fixed 2,3,2,3 pattern (320/128 = 2.5) and every panel row 3 or 4 source
 * rows, so the averages are sums times a reciprocal; the blur is a padded
 * separable 3x3. Measured under the port: the first draft (32-bit input,
 * a divide per pixel, nine clamped reads per blur) cost 4.5 M
 * instructions a frame, most of a tic.
 *
 * The plane layout (PANEL.md section 1, and lcd_view.py's window planes):
 * stored a quarter turn round, 128 rows of 8 bytes, one row per screen
 * column, MSB first; screen pixel (x, y), y from the top, is bit 63 - y of
 * row x counted from the MSB. The frame is built off-screen and copied
 * whole, so a flush never sends half a frame.
 */
#include <string.h>
#include "octa.h"

#define SW 320
#define DW 128

static const uint8_t bayer[4][4] = {
    {  8, 136,  40, 168 },
    { 200,  72, 232, 104 },
    {  56, 184,  24, 152 },
    { 248, 120, 216,  88 },
};

/* lum with a one-pixel border (replicated) for the blur */
static uint16_t lum[64 + 2][DW + 2];
static uint8_t work[DW * 8];

void mono_frame(const uint8_t *src, const uint8_t *lut, uint8_t *plane, int view)
{
    static uint16_t acc[DW];
    static uint16_t hs[64 + 2][DW];            /* horizontal 3-sums of lum */
    int sh = view ? 168 : 200, dh = view ? 56 : 64;
    int x, y, sy;

    /* box: panel row y = source rows [y*sh/dh, (y+1)*sh/dh) */
    for (y = 0; y < dh; y++) {
        int ya = y * sh / dh, yb = (y + 1) * sh / dh, rows = yb - ya;
        /* 1/(2*rows) and 1/(3*rows) in 16.16 */
        uint32_t r2 = 65536u / (2u * rows), r3 = 65536u / (3u * rows);
        memset(acc, 0, sizeof acc);
        for (sy = ya; sy < yb; sy++) {
            const uint8_t *p = src + sy * SW;
            uint16_t *a = acc;
            for (x = 0; x < DW; x += 2, p += 5, a += 2) {
                a[0] += lut[p[0]] + lut[p[1]];
                a[1] += lut[p[2]] + lut[p[3]] + lut[p[4]];
            }
        }
        for (x = 0; x < DW; x += 2) {
            lum[y + 1][x + 1] = (uint16_t)((acc[x] * r2) >> 16);
            lum[y + 1][x + 2] = (uint16_t)((acc[x + 1] * r3) >> 16);
        }
        lum[y + 1][0] = lum[y + 1][1];
        lum[y + 1][DW + 1] = lum[y + 1][DW];
    }
    memcpy(lum[0], lum[1], sizeof lum[0]);
    memcpy(lum[dh + 1], lum[dh], sizeof lum[0]);

    /* the blur, separable: horizontal 3-sums, then vertical */
    for (y = 0; y < dh + 2; y++) {
        const uint16_t *l = lum[y];
        uint16_t *h = hs[y];
        for (x = 0; x < DW; x++)
            h[x] = (uint16_t)(l[x] + l[x + 1] + l[x + 2]);
    }

    memset(work, 0, sizeof work);
    for (y = 0; y < dh; y++) {
        const uint8_t *th = bayer[y & 3];
        int b = 63 - y;
        uint8_t *wp = work + (b >> 3), bit = (uint8_t)(0x80u >> (b & 7));
        for (x = 0; x < DW; x++, wp += 8) {
            int c = lum[y + 1][x + 1];
            int s = hs[y][x] + hs[y + 1][x] + hs[y + 2][x];
            int v = 2 * c - (s * 7282 >> 16);      /* c + (c - s/9): unsharp, k = 1 */
            v = ((v - 20) * 104858) >> 16;         /* stretch x1.6: Doom is dark */
            if (v > th[x & 3])
                *wp |= bit;
        }
    }
    memcpy(plane, work, sizeof work);
}
