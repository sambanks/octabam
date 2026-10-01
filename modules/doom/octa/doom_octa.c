/* octabam DOOM -- doomgeneric's platform functions on the Octatrack.
 *
 * SPDX-License-Identifier: GPL-2.0-or-later
 *
 * Where Doom runs: in the UI task, on a stack of its own (entry.S
 * doom_run), one game tic per call. A soft timer on the sys tick (~120 Hz)
 * counts out 35 calls a second and posts each one to the UI task as a
 * deferred call, never more than one outstanding, so a slow frame slows
 * the game rather than queueing. Doom runs -singletics: a call is a tic.
 *
 * How it starts: DOOM holds the boot's project load (entry.S: the two
 * hooks OS SWITCH's boot picker uses, taken over by manifest.py's
 * Overrides), reads DOOM1.WAD from the card root into its own DRAM, opens
 * a full-screen window, pushes an input layer over every key and runs
 * D_DoomMain. No WAD: the boot goes on to OS SWITCH's hooks as if DOOM
 * were not there.
 *
 * How it ends: Doom's own QUIT (exit(0)), or FUNC + STOP at any time,
 * resets the unit through OS SWITCH's reset (DSP parked, panel reset, RCR
 * soft reset) with no switch pending, which boots the flashed image.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "octa.h"
#include "doomgeneric.h"
#include "doomkeys.h"
#include "d_event.h"
#include "doomstat.h"
#include "d_items.h"
#include "m_menu.h"
#include "i_video.h"

#define CALL(addr, type) ((type)(addr))

typedef long (*fw_create_t)(long, long, long, long, long, void (*)(void));
typedef long (*fw_1_t)(long);
typedef long (*fw_2_t)(long, long);
typedef long (*fw_text_t)(long, long, long, long, long, const char *);
typedef long (*fs_open_t)(const char *, const char *);
typedef long (*fs_read_t)(long, void *, long);

extern const uint8_t *octa_wad;
extern long octa_wad_len;

/* entry.S: the input layer and the deferred call's message */
extern uint8_t doom_layer[], doom_msg[];

static long win;                  /* the window's handle, 0 = none */
static long tmr = -1;
static volatile int pending;      /* a deferred tic posted and not yet run */
static unsigned tick_acc;
static volatile uint32_t sys_ticks;
static uint32_t slept_ms;
static int state;                 /* 0 never tried, 1 running, 2 dead (error shown), 3 no WAD */
static int func_held;
static int turn_l, turn_r;        /* LEFT / RIGHT held: the turn boost (tic) */
static char *stack_top;

/* ---- the log: a ring a port dump can read, and the panel's error page -- */
char octa_logbuf[8192];
unsigned octa_logpos;

void octa_log(const char *s, size_t n)
{
    while (n--) {
        octa_logbuf[octa_logpos % sizeof octa_logbuf] = *s++;
        octa_logpos++;
    }
}

static uint8_t *surface(void)
{
    return (uint8_t *)(win + WIN_SURFACE);
}

static uint8_t *plane(void)
{
    return *(uint8_t **)(surface() + SURF_BUF);
}

static void dirty(void)
{
    *(volatile long *)FW_SCRDIRTY = 1;
}

/* lines[] top to bottom, up to five */
static void panel_text(const char *const *lines, int n)
{
    int i;
    if (!win)
        return;
    CALL(FW_CLEAR, fw_1_t)((long)surface());
    for (i = 0; i < n; i++)
        CALL(FW_TEXT, fw_text_t)(FW_FONT, (long)surface(), 2, 52 - 12 * i, -1, lines[i]);
    dirty();
}

/* the last few log lines, for an I_Error */
static void panel_log(const char *title)
{
    static char lines[4][32];
    const char *ptr[5];
    int n = 0, i;
    unsigned end = octa_logpos, p = end;
    /* walk back over up to four lines */
    while (n < 4 && p > 0 && end - p < sizeof octa_logbuf - 1) {
        unsigned e = p;
        if (octa_logbuf[(p - 1) % sizeof octa_logbuf] == '\n')
            e = --p;
        while (p > 0 && end - p < sizeof octa_logbuf - 1
               && octa_logbuf[(p - 1) % sizeof octa_logbuf] != '\n')
            p--;
        if (e > p) {
            unsigned len = e - p > 31 ? 31 : e - p;
            for (i = 0; i < (int)len; i++)
                lines[3 - n][i] = octa_logbuf[(p + i) % sizeof octa_logbuf];
            lines[3 - n][len] = 0;
            n++;
        }
    }
    ptr[0] = title;
    for (i = 0; i < n; i++)
        ptr[1 + i] = lines[4 - n + i];
    panel_text(ptr, 1 + n);
}

/* ---- going home ------------------------------------------------------- */
static void go_home(void)
{
    static const char *const bye[] = { "DOOM", "", "BACK TO THE OS..." };
    panel_text(bye, 3);
    osw_reset();
}

/* ---- keys: Octatrack key -> up to three Doom keys ---------------------- */
static uint8_t kq[64];
static unsigned kq_r, kq_w;

static void kq_put(int pressed, unsigned char key)
{
    if (kq_w - kq_r >= sizeof kq / 2)
        return;
    kq[kq_w++ % sizeof kq] = (uint8_t)pressed;
    kq[kq_w++ % sizeof kq] = key;
}

/* The map (README.md "Controls"): arrows move and turn, YES fires and
 * confirms, NO uses and backs out, FUNC runs, CUE strafes with the arrows,
 * PATTERN / BANK strafe, trigs 1-7 pick weapons, TEMPO the map, STOP (or
 * PROJ) the menu, PLAY = ENTER. FUNC + STOP leaves Doom for the OS. */
static int keymap(int code, unsigned char out[3])
{
    int n = 0;
    switch (code) {
    case K_UP:    out[n++] = KEY_UPARROW; break;
    case K_DOWN:  out[n++] = KEY_DOWNARROW; break;
    case K_LEFT:  out[n++] = KEY_LEFTARROW; break;
    case K_RIGHT: out[n++] = KEY_RIGHTARROW; break;
    case K_YES:   out[n++] = KEY_FIRE; out[n++] = KEY_ENTER; out[n++] = 'y'; break;
    case K_NO:    out[n++] = KEY_USE; out[n++] = KEY_BACKSPACE; out[n++] = 'n'; break;
    case K_FUNC:  out[n++] = KEY_RSHIFT; break;
    case K_CUE:   out[n++] = KEY_RALT; break;
    case K_PTN:   out[n++] = KEY_STRAFE_L; break;
    case K_BANK:  out[n++] = KEY_STRAFE_R; break;
    case K_TEMPO: out[n++] = KEY_TAB; break;
    case K_STOP:
    case K_PROJ:  out[n++] = KEY_ESCAPE; break;
    case K_PLAY:  out[n++] = KEY_ENTER; break;
    default:
        if (code >= K_TRIG1 && code < K_TRIG1 + 7)
            out[n++] = (unsigned char)('1' + code - K_TRIG1);
    }
    return n;
}

void doom_kdown(long code)
{
    unsigned char out[3];
    int i, n;
    if (code == K_FUNC)
        func_held = 1;
    if (code == K_LEFT)
        turn_l = 1;
    if (code == K_RIGHT)
        turn_r = 1;
    if (state != 1)
        return;
    n = keymap((int)code, out);
    for (i = 0; i < n; i++)
        kq_put(1, out[i]);
}

/* FUNC + STOP, from FUNC's sub-layer (entry.S) */
void doom_home(long code)
{
    (void)code;
    go_home();
}

void doom_kup(long code)
{
    unsigned char out[3];
    int i, n;
    if (code == K_FUNC)
        func_held = 0;
    if (code == K_LEFT)
        turn_l = 0;
    if (code == K_RIGHT)
        turn_r = 0;
    if (state != 1)
        return;
    n = keymap((int)code, out);
    for (i = 0; i < n; i++)
        kq_put(0, out[i]);
}

/* knob A turns, as a mouse would; the rest are swallowed. 80 per detent is
 * 640 angle units after Doom's x8, about 3.5 degrees (24 was ~1 degree:
 * "a little slow" on the unit, 30 Sep 2026) */
void doom_enc(long index, long delta)
{
    event_t ev;
    if (state != 1 || index != 0)
        return;
    ev.type = ev_mouse;
    ev.data1 = 0;
    ev.data2 = (int)(delta * 80);
    ev.data3 = 0;
    D_PostEvent(&ev);
}

/* ---- doomgeneric's platform functions --------------------------------- */
void DG_Init(void)
{
    printf("DG_ScreenBuffer %p\n", (void *)DG_ScreenBuffer);   /* verify_doom reads it */
}

extern int messageToPrint;
void M_Drawer(void);

/* d_main.o calls this in place of M_Drawer (Makefile): a menu or a prompt
 * is drawn on black, not over the scene -- at 128 x 64 it is only readable
 * with nothing behind it. Palette entry 0 is black in every PLAYPAL. */
void octa_M_Drawer(void)
{
    if (menuactive || messageToPrint)
        memset(I_VideoBuffer, 0, SCREENWIDTH * SCREENHEIGHT);
    M_Drawer();
}

void DG_DrawFrame(void)
{
    int view, menu;
    if (!win)
        return;
    /* the 3D view with the status bar under it: the view, and a HUD line
     * of our own; everything else (title, menu, map, intermission) whole */
    view = gamestate == GS_LEVEL && !menuactive && !automapactive && screenblocks == 10;
    {
        /* the palette's luminance, every frame: damage and pickups swap
         * palettes, and 256 entries cost nothing beside the frame */
        static uint8_t lut[256];
        int i;
        menu = menuactive || messageToPrint;
        for (i = 0; i < 256; i++) {
            unsigned l = (colors[i].r * 77u + colors[i].g * 151u + colors[i].b * 28u) >> 8;
            if (menu)
                l = l * 3 > 255 ? 255 : l * 3;     /* the red menu font, lit solid */
            lut[i] = (uint8_t)l;
        }
        mono_frame(DG_ScreenBuffer, lut, plane(), view);
    }
    if (view) {
        static char hud[40];
        player_t *pl = &players[consoleplayer];
        ammotype_t at = weaponinfo[pl->readyweapon].ammo;
        if (at == am_noammo)
            snprintf(hud, sizeof hud, "HP %d  AR %d", pl->health, pl->armorpoints);
        else
            snprintf(hud, sizeof hud, "HP %d  AR %d  AMMO %d", pl->health, pl->armorpoints,
                     pl->ammo[at]);
        /* y is the glyphs' bottom edge counted from the panel's bottom, and
         * a glyph reaches one row below it: at y = 0 the whole string is
         * clipped (measured under the port, 30 Sep 2026) */
        CALL(FW_TEXT, fw_text_t)(FW_FONT, (long)surface(), 1, 1, -1, hud);
    }
    dirty();
}

void DG_SleepMs(uint32_t ms)
{
    slept_ms += ms;             /* virtual time: the wipe's wait must end */
}

uint32_t DG_GetTicksMs(void)
{
    return sys_ticks * 1000u / SYS_HZ + slept_ms;
}

int DG_GetKey(int *pressed, unsigned char *key)
{
    if (kq_r == kq_w)
        return 0;
    *pressed = kq[kq_r++ % sizeof kq];
    *key = kq[kq_r++ % sizeof kq];
    return 1;
}

void DG_SetWindowTitle(const char *title) { (void)title; }

/* ---- the clock and the tic -------------------------------------------- */
/* The arrows turn at Doom's keyboard rate (640 a tic, 320 for the first
 * six), which was slow on the unit; while LEFT or RIGHT is held in a level
 * a mouse turn of 60 (480 after the x8) rides along, ~1.75x. Not in the
 * menu or the map, where a mouse event means something else. */
#define TURN_BOOST 60

extern void doom_audio_update(void);
extern void doom_audio_off(void);
extern void doom_audio_service(void);

static void tic(void)
{
    if ((turn_l ^ turn_r) && gamestate == GS_LEVEL && !menuactive && !automapactive) {
        event_t ev;
        ev.type = ev_mouse;
        ev.data1 = 0;
        ev.data2 = turn_r ? TURN_BOOST : -TURN_BOOST;
        ev.data3 = 0;
        D_PostEvent(&ev);
    }
    doomgeneric_Tick();
    doom_audio_update();
}

static void dead(int code)
{
    doom_audio_off();
    if (code == 0x10000)        /* exit(0): Doom's QUIT */
        go_home();
    state = 2;
    panel_log("DOOM STOPPED  FUNC+STOP=OS");
}

/* the deferred call, in the UI task */
void doom_frame(void)
{
    int r;
    pending = 0;
    if (state != 1)
        return;
    r = doom_run(tic, stack_top);
    if (r)
        dead(r);
    else
        doom_audio_service();   /* the music's card reads: here, never in the tic */
}

/* the soft timer, every sys tick */
void doom_timer(void)
{
    sys_ticks++;
    tick_acc += 35;
    if (tick_acc >= SYS_HZ) {
        tick_acc -= SYS_HZ;
        if (!pending && state == 1) {
            pending = 1;
            CALL(FW_POST, fw_2_t)(FW_UIQUEUE, (long)doom_msg);
        }
    }
}

void doom_close(void)
{
    win = 0;                    /* the window system closed it */
}

/* ---- boot ------------------------------------------------------------- */
/* The WAD, whole, at the bottom of Doom's heap: 16-byte aligned and with no
 * block header, so no line of the copyback D-cache holds both a byte the
 * CPU wrote and a byte of the WAD. Read through the CACHED address, as
 * stock loads samples: the card driver moves sectors with the CPU (PIO, one
 * sector per interrupt: docs/firmware/KERNEL.md), so the lines it fills are
 * the lines Doom reads. (The first draft read through the uncached alias
 * into a malloc'd block whose header shared a line with the WAD's first 8
 * bytes: the port, which has no cache, could not have shown it.) */
static int read_wad(void)
{
    static const char path[] = "/DOOM1.WAD";
    long fd, len, left, need;
    uint8_t *buf, *p;
    if (!*(volatile long *)FS_MOUNTED || !*(volatile long *)FS_OPEN)
        return 0;
    fd = (*(fs_open_t *)FS_OPEN)(path, "r");
    if (fd < 0)
        return 0;
    len = (*(fw_1_t *)FS_SIZE)(fd);
    need = (len + 511) & ~511L;
    buf = (uint8_t *)(((uintptr_t)octa_heap_next + 15) & ~(uintptr_t)15);
    if (len < 12 || buf + need > (uint8_t *)octa_heap_end) {
        (*(fw_1_t *)FS_CLOSE)(fd);
        return 0;
    }
    for (p = buf, left = need >> 9; left > 0;) {
        long n = left > 8 ? 8 : left;     /* eight sectors a call, as OS UPGRADE reads */
        (*(fs_read_t *)FS_READ)(fd, p, n);
        p += n << 9;
        left -= n;
    }
    (*(fw_1_t *)FS_CLOSE)(fd);
    if (memcmp(buf, "IWAD", 4))
        return 0;
    octa_heap_next = (char *)(buf + need);
    octa_wad = buf;
    octa_wad_len = len;
    printf("DOOM1.WAD: %ld bytes at %p\n", len, buf);
    return 1;
}

static void doom_main(void)
{
    extern int detailLevel;
    /* low detail: the renderer draws 160 columns, each doubled -- the panel
     * shows 128, so nothing visible is lost and the column loops halve */
    detailLevel = 1;
    static char *argv[] = { "doom", "-iwad", "doom1.wad", "-singletics", "-mb", "6", NULL };
    doomgeneric_Create(6, argv);
}

/* Called from both boot hooks (entry.S). 1 = DOOM has the boot: hold the
 * project load. 0 = carry on as stock / OS SWITCH would. */
long doom_boot(void)
{
    static const char *const loading[] = { "DOOM", "", "LOADING DOOM1.WAD" };
    static const char *const nowad[] = { "DOOM", "NO DOOM1.WAD ON THE CARD", "BOOTING THE OS" };
    int r;
    if (state == 1 || state == 2)
        return 1;
    if (state == 3)
        return 0;
    state = 3;
    octa_heap_next = (char *)DOOM_RAM_BASE;
    octa_heap_end = (char *)(DOOM_RAM_END - DOOM_STACK);
    stack_top = (char *)DOOM_RAM_END;
    win = CALL(FW_CREATE, fw_create_t)(128, 64, 0, 0, 5, doom_close);
    panel_text(loading, 3);
    if (!read_wad()) {
        panel_text(nowad, 3);
        CALL(FW_DESTROY, fw_1_t)((long)&win);
        win = 0;
        return 0;
    }
    CALL(FW_LPUSH, fw_1_t)((long)doom_layer);
    state = 1;
    r = doom_run(doom_main, stack_top);
    if (r)
        dead(r);
    tmr = CALL(FW_TIMER, fw_2_t)(1, (long)doom_timer);
    return 1;
}

void octa_assert_fail(const char *e, const char *f, int l)
{
    printf("assert %s %s:%d\n", e, f, l);
    exit(-1);
}
