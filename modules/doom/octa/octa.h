/* octabam DOOM -- the Octatrack platform under doomgeneric.
 *
 * SPDX-License-Identifier: GPL-2.0-or-later (it links with doomgeneric).
 *
 * Every firmware address here is OS 1.40C and was measured by another
 * module first; the provenance is beside each one. Calls follow the
 * firmware's own convention, which is GCC's m68k-elf one: arguments pushed
 * as longs, the caller pops, the result in d0 -- so a pointer result is
 * declared as a long and cast (GCC may look for a pointer in a0).
 */
#ifndef OCTA_H
#define OCTA_H

#include <stdint.h>
#include <stddef.h>

/* ---- the window system (modules/dj-decks/screen.s, measured under the
 * port and on an MKII, 29 Sep 2026) ---------------------------------- */
#define FW_CREATE   0x4005829c  /* (w, h, 0, 0, prio, close) -> handle     */
#define FW_FRAME    0x40056f4c  /* (handle)                                 */
#define FW_DESTROY  0x40055db4  /* (&handle)                                */
#define FW_CLEAR    0x40035624  /* (surface)                                */
#define FW_TEXT     0x40012bd8  /* (font, surf, x, y, limit, str); y from the bottom */
#define FW_FONT     0x400ba876  /* the small UI font (docs/firmware/PANEL.md) */
#define FW_SCRDIRTY 0x46c7c72c  /* 1 = the screen wants a flush             */
#define WIN_SURFACE 36          /* handle + 36 = the window's surface       */
#define SURF_BUF    12          /* surface + 12 = its 1-bit plane           */

/* ---- soft timers, input layers, the UI task's deferred call ---------- */
#define FW_TIMER    0x40031a0c  /* (period in sys ticks, fn) -> handle; ~120 Hz (BSRET7BP) */
#define FW_UNTIMER  0x40031abc  /* (handle)                                 */
#define FW_LPUSH    0x40031494  /* (layer)                                  */
#define FW_LPOP     0x4003146c  /* (layer)                                  */
#define FW_POST     0x40000c3c  /* (queue, {u8 21, u32 fn})                 */
#define FW_UIQUEUE  0x460d17ce  /* the queue 0x40063660 posts its deferred calls to */
#define SYS_HZ      120

/* ---- the card (modules/os-switch/switch.s osw_load; docs/firmware/STORAGE.md) */
#define FS_OPEN     0x46c8242a  /* vtable slots: (path, "r") -> fd           */
#define FS_CLOSE    0x46c82422  /* (fd)                                     */
#define FS_SIZE     0x46c8241e  /* (fd) -> bytes                            */
#define FS_READ     0x46c82426  /* (fd, buf, sectors)                       */
#define FS_MOUNTED  0x46c8240e  /* nonzero once a file system is up (bp_open's test) */

/* ---- DRAM: 2,728 pages off the top of the audio page arena (manifest.py
 * ArenaReserve), of which Doom uses the lower 2,200. The top 528 are
 * Octakit's window, which stock zero-fills at every project load
 * (docs/contributing/PLACEMENT.md); DOOM holds the project load back, but it
 * does not bet on that. manifest.py re-derives both ends from
 * tools/remix/arena.py and refuses on drift. ---------------------------- */
#define DOOM_RAM_BASE  0x45029de0u
#define DOOM_RAM_END   0x45d0dde0u
#define DOOM_STACK     (256u * 1024u)

/* keys (docs/firmware/PANEL.md section 4c; tools/emu/lcd_view.py) */
#define K_TRIG1  0x00
#define K_TEMPO  0x18
#define K_PROJ   0x1c
#define K_DOWN   0x20
#define K_RIGHT  0x21
#define K_STOP   0x27
#define K_PLAY   0x28
#define K_REC    0x29
#define K_CUE    0x2a
#define K_FUNC   0x2d
#define K_PTN    0x2e
#define K_BANK   0x2f
#define K_YES    0x31
#define K_NO     0x32
#define K_UP     0x33
#define K_LEFT   0x34

/* entry.S */
int  doom_run(void (*fn)(void), void *stack_top);  /* 0, or doom_bail's code */
void doom_bail(int code) __attribute__((noreturn));
extern void osw_reset(void) __attribute__((noreturn));  /* modules/os-switch: park, panel, soft reset */

/* doom_octa.c */
void octa_log(const char *s, size_t n);
extern char *octa_heap_next, *octa_heap_end;

/* mono.c: Doom's 320x200 8-bit frame, lut = luminance per palette entry
 * -> 128x64, one bit a pixel, the panel's layout; view = the 3D view's 168
 * rows into the top 56 (a HUD line below) */
void mono_frame(const uint8_t *src, const uint8_t *lut, uint8_t *plane, int view);

#endif
