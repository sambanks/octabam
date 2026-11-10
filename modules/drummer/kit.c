/* DRUMMER -- the KIT window: each slice's zone, role, ALIGN and GAIN, and
 * the track's SHIFT and phrase. Compiled in one unit after drummer.c and
 * adapter.c (generate.py), whose helpers and state it uses.
 *
 * TRIG + BANK on a DRUMMER track (audio mode, any trig key held, the held key
 * picks the first slice shown) opens it, the size of MAIN MENU as CHORDS'
 * chooser (SCALES' recipe). UP / DOWN move the cursor and play the slice;
 * the trig keys jump to the slices of the page of sixteen the cursor is on
 * and play them; LEFT / RIGHT the three pages (dr_kw_enc says what A-F do on
 * each; page 3 is the track's settings as switches); the footer reminds
 * FUNC + RIGHT (AUTO again, every GAIN back to 0 dB); YES or NO closes. The
 * kit lives in RAM until drummer.work.
 *
 * A slice plays through the stock trig of the track (0x40005030, as the
 * SLICES trig mode's 0x4004f8dc), its slice handed to the start wrapper by
 * dr_preview (no STRT lock: STRT is DENS on a DRUMMER track). */

#define DATA __attribute__((section(".data")))
#define FN(addr, ...) ((uint32_t (*)(__VA_ARGS__))(uintptr_t)(addr))

enum {
    MIDI_MODE = 0x80000012u,    /* long: nonzero in MIDI mode */
    KEY_ROWS  = 0x46100b18u,    /* the key matrix's last state, a byte a row: rows 0-1 = trig keys 1-16 */
    SETUP_WIN = 0x400bcd14u,    /* -> the setup window's record, +8 nonzero while open (CHORDS) */
    SCRDIRTY  = 0x46c7c72cu,
    WCREATE   = 0x4005829cu,    /* (w, h, dx, dy, class, closed) -> handle */
    WDESTROY  = 0x40055db4u,    /* (&handle) */
    WTITLE    = 0x40057c84u,    /* (window, title, 0) */
    WINSIDE   = 0x400356a8u,    /* (surface) */
    LPUSH     = 0x40031494u,
    LPOP      = 0x4003146cu,
    TEXT      = 0x40012bd8u,    /* (font, surface, x, y, limit, text) */
    FILLR     = 0x40012254u,    /* (surface, x1, y1, x2, y2, mode) */
    RULE      = 0x40011910u,    /* (surface, x, y, w, h) */
    FONT      = 0x400ba876u,
    ARROW_UP  = 0x400b4315u,
    ARROW_DOWN = 0x400b4317u,
    TRIG_FIRE = 0x40005030u,    /* (track, 0x1d, 1, -1): the track's trig now (the SLICES mode's) */
    TRIG_EVT  = 0x46c80354u,    /* + 4t: the track's live trig event, 0x40 = the key let go (0x4004fa46) */
    TRIG_HOLD = 0x460d1ae2u,    /* bit t: stock skips the release (0x4004fa3a) */
    DIALOG    = 0x4006d57cu,    /* (title, lines, text[], 3, answer(0 = YES)): stock's YES/NO box (STORE's) */
    DIALOG_OPEN = 0x460e5cd0u,  /* long: nonzero while a stock dialog owns the keys (SCALES) */
    NOTIFY    = 0x4005a2b8u,    /* (text, ticks): stock's toast */
    FUNC_HELD = 0x46c7dd26u,    /* long: nonzero while [FUNCTION] is down */
    SLOT_STATE = 0x46c922c4u,   /* + 44 slot: flags (bit 0 stereo, bit 1 16-bit), +16 frames (SAMPLE_SAVE.md) */
};
enum { KW_W = 118, KW_H = 64, KW_DX = -1, KW_CLASS = 5, KW_ROWS = 4, KW_PITCH = 7, KW_ROW0 = 34,
       KW_BAR1 = 3, KW_BAR2 = 107, KW_FOOT = 4, KW_PAGES = 3,
       KW_X_ZONE = 16, KW_X_ROLE = 52, KW_X_LNK = 80 };   /* page 1's columns (image 60's ROLE and LNK sat off their titles) */

/* The ZONE column: the nine zones, combos of two, out of the kit. */
typedef struct { const char *name; uint8_t zone; uint16_t combo; } KwZone;
#define M(a, b) (uint16_t)((1u << (a)) | (1u << (b)))
static const KwZone ZONES[] = {
    { "KICK", DR_KICK, 0 }, { "SNARE", DR_SNARE, 0 }, { "GHOST", DR_GHOST, 0 }, { "HAT C", DR_HATC, 0 },
    { "HAT O", DR_HATO, 0 }, { "RIDE", DR_RIDE, 0 }, { "CRASH", DR_CRASH, 0 }, { "TOM", DR_TOM, 0 },
    { "PERC", DR_PERC, 0 },
    { "BD+HC", DR_COMBO, M(DR_KICK, DR_HATC) }, { "BD+HO", DR_COMBO, M(DR_KICK, DR_HATO) },
    { "BD+CR", DR_COMBO, M(DR_KICK, DR_CRASH) }, { "SD+HC", DR_COMBO, M(DR_SNARE, DR_HATC) },
    { "SD+HO", DR_COMBO, M(DR_SNARE, DR_HATO) }, { "SD+CR", DR_COMBO, M(DR_SNARE, DR_CRASH) },
    { "BD+SD", DR_COMBO, M(DR_KICK, DR_SNARE) },
    { "OUT", DR_OUT, 0 },
};
#define NZONES (sizeof ZONES / sizeof ZONES[0])
#include "autokit.h"
static const char *const ROLES[DR_ROLES] = { "ACC", "NRM", "SFT" };

extern const uint8_t dr_up_layer[], dr_kw_layer[];
unsigned dr_loop_view(unsigned t, unsigned *slices);      /* adapter.c: REDRUM's loop steps, the slot's slices */
DATA uint32_t dr_kw;              /* the window, 0 closed */
DATA uint8_t  dr_kw_pushed, dr_up_pushed, dr_kw_t, dr_kw_sel, dr_kw_top;
DATA uint8_t  dr_preview[TRACKS]; /* a slice + 1 the next start of the track plays, 0 none */
DATA uint8_t  dr_release[TRACKS]; /* UI ticks until the preview's key is let go, 0 none */
DATA uint8_t  dr_align[TRACKS][DR_SLICES] = { { 0 } };   /* ms the slice's hit is played earlier */
DATA uint8_t  dr_shift[TRACKS], dr_phrase[TRACKS] = { 4, 4, 4, 4, 4, 4, 4, 4 };
DATA uint8_t  dr_redrum[TRACKS];    /* REDRUM (image 77): the sample's own loop as the groove; 0 off, 1 AUTO, 2..5 1 2 4 8 bars */
DATA int8_t   dr_gain[TRACKS][DR_SLICES] = { { 0 } };   /* dB, DR_GAIN_MIN..DR_GAIN_MAX: the slice's level */
DATA uint8_t  dr_scene[TRACKS][DR_SLICES] = { { 0 } };  /* 0 none, else the Part's scene 1..16 on its hits */
DATA uint8_t  dr_dose[TRACKS][DR_SLICES] = { { 0 } };   /* how far, % in steps of 5; 0 = 100 */
DATA uint8_t  dr_simtol[TRACKS] = { 6, 6, 6, 6, 6, 6, 6, 6 };   /* SIMILAR: AUTO's tolerance, 0 off */
DATA uint8_t  dr_simmode[TRACKS] = { 0 };       /* 0 the copies OUT, 1 LINKED */
DATA uint8_t  dr_link[TRACKS][DR_SLICES] = { { 0 } };   /* the group's kept slice + 1, 0 alone */
DATA uint8_t  dr_kw_rprev;        /* RIGHT's key row bit at the last UI tick */
DATA uint8_t  dr_kw_page;         /* 0 ZONE ROLE, 1 ALIGN GAIN SCENE DOSE, 2 the track's settings */
DATA char     dr_kw_band[40];      /* the title, "KIT T1 BRKB SHFT P4 2/2" at most (image 55's
                                  * "... SHIFT PHR4 2/2", 27 bytes in 24, overflowed into
                                  * the page state with SHIFT on: reported on the unit) */

static void kw_text(uint32_t s, int x, int y, const char *t)
{
    FN(TEXT, uint32_t, uint32_t, int, int, int, const char *)(FONT, s, x, y, -1, t);
}
static void dots(uint32_t s, int x, int y, int w, int h);
static void centred(uint32_t s, int cx, int y, const char *t);

static char *put_s(char *p, const char *s)
{
    while (*s)
        *p++ = *s++;
    return p;
}

static char *put_u(char *p, unsigned v, unsigned digits)
{
    char d[4];
    unsigned n = 0;
    do {
        d[n++] = (char)('0' + v % 10);
        v /= 10;
    } while (v && n < 4);
    while (n < digits && n < 4)
        d[n++] = '0';
    while (n)
        *p++ = d[--n];
    return p;
}

static char *put_db(char *p, int v)
{
    if (v > 0)
        *p++ = '+';
    else if (v < 0) {
        *p++ = '-';
        v = -v;
    }
    return put_u(p, (unsigned)v, 1);
}

static unsigned zone_index(const DrKit *k, unsigned i)
{
    unsigned z;
    for (z = 0; z < NZONES; z++)
        if (ZONES[z].zone == k->zone[i] && (ZONES[z].zone != DR_COMBO || ZONES[z].combo == k->combo[i]))
            return z;
    return k->zone[i] == DR_COMBO ? 9 : NZONES - 1;
}

/* The track's trig as a trig key pressed (the SLICES mode's 0x4004f8dc), and
 * let go three UI ticks later as stock lets go (0x46c80354 + 4t = 0x40): a
 * press never let go left the track held, and PLAY silent until a slice was
 * played in SLICES mode (reported on the unit). */
static void kw_release(unsigned t)
{
    if (!(U8(TRIG_HOLD) >> t & 1u))
        U32(TRIG_EVT + 4u * t) = 0x40;
    dr_release[t] = 0;
}

static void kw_play(unsigned t, unsigned slice)
{
    if (dr_release[t])
        kw_release(t);
    dr_preview[t] = (uint8_t)(slice + 1);
    FN(TRIG_FIRE, unsigned, unsigned, unsigned, int)(t, 0x1d, 1, -1);
    dr_release[t] = 3;
}

/* The sample's slices, read now: the kit's count is only refreshed when a
 * step is built, and a kit read from drummer.work has 0 until then (the window
 * showed one row before the first PLAY, measured). */
static unsigned kw_count(void)
{
    unsigned n = slice_count(dr_kw_t);
    dr_kit[dr_kw_t].count = (uint8_t)n;
    return n ? n : 1;
}

/* A box of 5 x 5 pixels at (x, y), filled inside when on (page 3's switches). */
static void kw_box(uint32_t s, int x, int y, unsigned on)
{
    int i;
    FN(RULE, uint32_t, int, int, int, int)(s, x, y, x + 4, 1);
    FN(RULE, uint32_t, int, int, int, int)(s, x, y + 4, x + 4, 1);
    for (i = 1; i < 4; i++) {
        FN(RULE, uint32_t, int, int, int, int)(s, x, y + i, x, 1);
        FN(RULE, uint32_t, int, int, int, int)(s, x + 4, y + i, x + 4, 1);
        if (on)
            FN(RULE, uint32_t, int, int, int, int)(s, x + 1, y + i, x + 3, 1);
    }
}

/* Page 3: the track's settings, one an encoder, as switches; E SAVE KIT
 * (image 68: no title row, rows 6 pixels apart from the top; image 77 four
 * pixels higher, for F REDRUM). */
static void kw_settings(uint32_t s)
{
    unsigned t = dr_kw_t, tol = dr_simtol[t];
    char line[20], *p;
    int y = KW_ROW0 + 11;
    kw_text(s, 4, y, "A SHIFT");
    kw_box(s, 52, y, dr_shift[t]);
    kw_text(s, 60, y, dr_shift[t] ? "ON" : "OFF");
    y -= 6;
    kw_text(s, 4, y, "B PHRASE");
    kw_box(s, 52, y, dr_phrase[t] != 8);
    kw_text(s, 60, y, "4 BARS");
    kw_box(s, 86, y, dr_phrase[t] == 8);
    kw_text(s, 94, y, "8");
    y -= 6;
    kw_text(s, 4, y, "C SIMILAR");
    kw_box(s, 52, y, tol != 0);
    p = put_s(line, "TOL ");
    p = put_u(p, tol, 1);
    *p = 0;
    kw_text(s, 60, y, tol ? line : "OFF");
    y -= 6;
    kw_text(s, 4, y, "D COPIES");
    kw_box(s, 52, y, dr_simmode[t] == AK_DUP_OUT);
    kw_text(s, 60, y, "OUT");
    kw_box(s, 76, y, dr_simmode[t] == AK_DUP_LINK);
    kw_text(s, 84, y, "LINK");
    y -= 6;
    kw_text(s, 4, y, "E KIT FILE");
    kw_text(s, 52, y, "TURN E TO SAVE");
    y -= 6;
    kw_text(s, 4, y, "F REDRUM");
    kw_box(s, 52, y, dr_redrum[t]);
    if (dr_redrum[t]) {                          /* image 78: the loop as REDRUM lays it, "AUTO 8BAR 32SL" */
        unsigned n, steps = dr_loop_view(t, &n);
        p = put_s(line, dr_redrum[t] == 1 ? "AUTO " : "");
        if (!steps) {
            p = put_s(p, "NO SLICES");
        } else {
            p = put_u(p, steps / DR_STEPS, 1);
            p = put_s(p, dr_redrum[t] == 1 ? "BAR " : " BARS ");
            p = put_u(p, n, 1);
            p = put_s(p, dr_redrum[t] == 1 ? "SL" : " SL");
        }
        *p = 0;
        kw_text(s, 60, y, line);
    } else {
        kw_text(s, 60, y, "OFF");
    }
}

static void kw_draw(void)
{
    uint32_t s;
    int w, top;
    unsigned r;
    char *p, line[28];
    const DrKit *k = &dr_kit[dr_kw_t];
    if (!dr_kw)
        return;
    s = dr_kw + 36;
    p = put_s(dr_kw_band, "KIT T");
    p = put_u(p, dr_kw_t + 1u, 1);
    *p++ = ' ';
    p = put_s(p, dr_style_name(dr_cur_style[dr_kw_t]));     /* the style the engine plays */
    p = put_s(p, dr_shift[dr_kw_t] ? " SHFT P" : " P");
    p = put_u(p, dr_phrase[dr_kw_t], 1);
    *p++ = ' ';
    p = put_u(p, dr_kw_page + 1u, 1);
    p = put_s(p, "/3");
    *p = 0;
    FN(WTITLE, uint32_t, const char *, int)(dr_kw, dr_kw_band, 0);
    FN(WINSIDE, uint32_t)(s);
    w = (int)U32(s);
    top = (int)U32(s + 4) - 20;
    if (dr_kw_page == 0) {                       /* each title over its column, values left-aligned under it */
        kw_text(s, 4, top + 2, "SL");
        kw_text(s, KW_X_ZONE, top + 2, "ZONE");
        kw_text(s, KW_X_ROLE, top + 2, "ROLE");
        kw_text(s, KW_X_LNK, top + 2, "LNK");
    } else if (dr_kw_page == 1) {
        kw_text(s, 4, top + 2, "SL ALGN GAIN SCN DOSE");
    }
    if (dr_kw_page != 2)                         /* page 3: its five rows from the top (image 68) */
        FN(RULE, uint32_t, int, int, int, int)(s, 4, top - 1, w - 6, 1);
    dots(s, 4, KW_FOOT + 7, w - 10, 1);          /* the footer: AUTO's chord, on every page */
    centred(s, w / 2, KW_FOOT, "FUNC + RIGHT TO AUTO KIT");
    if (dr_kw_page == 2) {
        kw_settings(s);
        U32(SCRDIRTY) = 1;
        return;
    }
    if (dr_kw_top > 0)
        kw_text(s, w - 8, KW_ROW0 + 1, (const char *)ARROW_UP);
    if (dr_kw_top + (unsigned)KW_ROWS < kw_count())
        kw_text(s, w - 8, KW_ROW0 + 1 - (KW_ROWS - 1) * KW_PITCH, (const char *)ARROW_DOWN);
    for (r = 0; r < (unsigned)KW_ROWS && dr_kw_top + r < kw_count(); r++) {
        unsigned i = dr_kw_top + r, z = zone_index(k, i);
        int y = KW_ROW0 - (int)r * KW_PITCH;
        p = put_u(line, i + 1, 2);
        *p = 0;
        kw_text(s, 4, y + 1, line);
        if (!dr_kw_page) {
            kw_text(s, KW_X_ZONE, y + 1, ZONES[z].name);
            if (k->zone[i] != DR_OUT)
                kw_text(s, KW_X_ROLE, y + 1, ROLES[k->role[i] < DR_ROLES ? k->role[i] : 1]);
            if (dr_link[dr_kw_t][i]) {           /* a group of similar slices: its kept one */
                line[0] = '=';
                p = put_u(line + 1, dr_link[dr_kw_t][i], 1);
                *p = 0;
                kw_text(s, KW_X_LNK, y + 1, line);
            }
        } else {
            unsigned sc = dr_scene[dr_kw_t][i];
            p = put_u(line, dr_align[dr_kw_t][i], 1);   /* ms */
            *p = 0;
            kw_text(s, 16, y + 1, dr_align[dr_kw_t][i] ? line : "-");
            p = put_db(line, dr_gain[dr_kw_t][i]);
            *p = 0;
            kw_text(s, 36, y + 1, dr_gain[dr_kw_t][i] ? line : "-");
            p = put_u(line, sc, 1);
            *p = 0;
            kw_text(s, 56, y + 1, sc ? line : "--");
            if (sc) {
                p = put_u(line, dr_dose[dr_kw_t][i] ? dr_dose[dr_kw_t][i] : 100u, 1);
                *p++ = '%';
                *p = 0;
                kw_text(s, 72, y + 1, line);
            }
        }
        if (i == dr_kw_sel)
            FN(FILLR, uint32_t, int, int, int, int, int)(s, KW_BAR1, y, KW_BAR2, y + 6, -1);
    }
    U32(SCRDIRTY) = 1;
}

static void kw_scroll(void)
{
    if (dr_kw_sel < dr_kw_top)
        dr_kw_top = dr_kw_sel;
    else if (dr_kw_sel >= dr_kw_top + (unsigned)KW_ROWS)
        dr_kw_top = (uint8_t)(dr_kw_sel - (KW_ROWS - 1));
}

void dr_kw_closed(void)
{
    dr_kw = 0;
    if (dr_kw_pushed) {
        dr_kw_pushed = 0;
        FN(LPOP, const void *)(dr_kw_layer);
    }
}

void dr_kw_close(void)
{
    if (dr_kw)
        FN(WDESTROY, uint32_t *)(&dr_kw);
    dr_kw_closed();
}

static unsigned trigs_held(void)
{
    return (unsigned)U8(KEY_ROWS) | (unsigned)U8(KEY_ROWS + 1) << 8;
}

static unsigned ui_drummer_track(void)
{
    unsigned t = U8(CUR_TRACK) & 7u;
    if (U32(MIDI_MODE) || !bank_ok() || !signed_track(part_base(), t))
        return TRACKS;
    return t;
}

/* BANK with a trig key held on a DRUMMER track (stock's TRIG + BANK is BANK's
 * own SELECT BANK, measured: BANK alone, then a trig, still picks a bank). */
void dr_kit_up(void)
{
    unsigned t = ui_drummer_track(), held = trigs_held(), first = 0;
    if (t >= TRACKS || dr_kw || !held)
        return;
    ensure_kit(t);
    while (!(held >> first & 1))
        first++;
    dr_kw_t = (uint8_t)t;
    dr_kw_sel = (uint8_t)(first < kw_count() ? first : 0);
    dr_kw_top = 0;
    kw_scroll();
    dr_kw = FN(WCREATE, int, int, int, int, int, void (*)(void))(KW_W, KW_H, KW_DX, 0, KW_CLASS, dr_kw_closed);
    if (!dr_kw)
        return;
    FN(LPUSH, const void *)(dr_kw_layer);
    dr_kw_pushed = 1;
    kw_draw();
}

/* UP / DOWN (with stock's repeat): one slice, heard. */
void dr_kw_ud(unsigned key)
{
    if (!dr_kw) {
        dr_kw_closed();
        return;
    }
    if (key == 0x33) {
        if (!dr_kw_sel)
            return;
        dr_kw_sel--;
    } else {
        if (dr_kw_sel + 1u >= kw_count())
            return;
        dr_kw_sel++;
    }
    kw_scroll();
    kw_play(dr_kw_t, dr_kw_sel);
    kw_draw();
}

/* A trig key: that slice of the cursor's page of sixteen, heard. */
void dr_kw_trig(unsigned k)
{
    unsigned i = (dr_kw_sel & ~15u) + (k & 15u);
    if (!dr_kw || i >= kw_count())
        return;
    dr_kw_sel = (uint8_t)i;
    kw_scroll();
    kw_play(dr_kw_t, i);
    kw_draw();
}

/* Page 1: A ZONE, B ROLE. Page 2: A ALIGN, B GAIN, E SCENE, F DOSE (GAIN
 * turns a LINKED group together). Page 3: A SHIFT, B PHRASE, C SIMILAR's
 * tolerance, D SIMILAR's copies OUT / LINK. */
static void kw_save(void);

void dr_kw_enc(unsigned index, int delta)
{
    DrKit *k;
    unsigned i, play = 0;
    if (!dr_kw) {
        dr_kw_closed();
        return;
    }
    k = &dr_kit[dr_kw_t];
    i = dr_kw_sel;
    {                                            /* every page on one set of handlers */
        static const uint8_t AS[KW_PAGES][6] = { { 0, 1, 9, 9, 9, 9 }, { 2, 5, 9, 9, 6, 7 }, { 3, 4, 10, 11, 12, 13 } };
        index = AS[dr_kw_page < KW_PAGES ? dr_kw_page : 0][index < 6 ? index : 2];
    }
    if (index == 0) {
        int z = (int)zone_index(k, i) + (delta > 0 ? 1 : -1);
        if (z < 0)
            z = (int)NZONES - 1;
        if (z >= (int)NZONES)
            z = 0;
        k->zone[i] = ZONES[z].zone;
        k->combo[i] = ZONES[z].combo;
        play = k->zone[i] != DR_OUT;
    } else if (index == 1) {
        int r = (int)k->role[i] + (delta > 0 ? 1 : -1);
        k->role[i] = (uint8_t)(r < 0 ? DR_ROLES - 1 : r >= DR_ROLES ? 0 : r);
        play = 1;
    } else if (index == 2) {
        int a = (int)dr_align[dr_kw_t][i] + delta * 2;
        dr_align[dr_kw_t][i] = (uint8_t)(a < 0 ? 0 : a > 250 ? 250 : a);
    } else if (index == 3) {
        dr_shift[dr_kw_t] = (uint8_t)(delta > 0);
    } else if (index == 4) {
        dr_phrase[dr_kw_t] = (uint8_t)(delta > 0 ? 8 : 4);
    } else if (index == 5) {
        unsigned j, grp = dr_link[dr_kw_t][i];
        for (j = 0; j < DR_SLICES; j++)
            if (j == i || (grp && dr_link[dr_kw_t][j] == grp)) {
                int g = (int)dr_gain[dr_kw_t][j] + (delta > 0 ? 1 : -1);
                dr_gain[dr_kw_t][j] = (int8_t)(g < DR_GAIN_MIN ? DR_GAIN_MIN : g > DR_GAIN_MAX ? DR_GAIN_MAX : g);
            }
        play = k->zone[i] != DR_OUT;
    } else if (index == 6) {                     /* SCENE: -- 1..16 */
        int c = (int)dr_scene[dr_kw_t][i] + (delta > 0 ? 1 : -1);
        dr_scene[dr_kw_t][i] = (uint8_t)(c < 0 ? 0 : c > 16 ? 16 : c);
    } else if (index == 7) {                     /* DOSE: 5..100 % */
        int d = (int)(dr_dose[dr_kw_t][i] ? dr_dose[dr_kw_t][i] : 100u) + (delta > 0 ? 5 : -5);
        d = d < 5 ? 5 : d > 100 ? 100 : d;
        dr_dose[dr_kw_t][i] = (uint8_t)(d == 100 ? 0 : d);
    } else if (index == 10) {                    /* SIMILAR: OFF 1..15 */
        int c = (int)dr_simtol[dr_kw_t] + (delta > 0 ? 1 : -1);
        dr_simtol[dr_kw_t] = (uint8_t)(c < 0 ? 0 : c > AK_TOL_MAX ? AK_TOL_MAX : c);
    } else if (index == 11) {                    /* SIMILAR: OUT / LINK */
        dr_simmode[dr_kw_t] = (uint8_t)(delta > 0 ? AK_DUP_LINK : AK_DUP_OUT);
    } else if (index == 13) {                    /* REDRUM: OFF AUTO 1 2 4 8 bars (image 78) */
        int r = (int)dr_redrum[dr_kw_t] + (delta > 0 ? 1 : -1);
        dr_redrum[dr_kw_t] = (uint8_t)(r < 0 ? 0 : r > 5 ? 5 : r);
    } else if (index == 12) {                    /* SAVE KIT: asked */
        kw_save();
        return;
    } else {
        return;
    }
    if (play)
        kw_play(dr_kw_t, i);
    kw_draw();
}

/* ---- AUTO (autokit.c on the slot's audio in RAM) ------------------------ */

/* (slot, frame, &run) -> a pointer to the frame, run = the frames contiguous
 * from it: stock's pool walk 0x4009499c (the WAV writer's), hooks.s. The
 * audio is big-endian in RAM: 16-bit, or 24-bit in 3 bytes (measured: a
 * stereo 16-bit slot reads as the file byte-swapped, port). */
const uint8_t *dr_sample_at(unsigned slot, uint32_t frame, uint32_t *run);

typedef struct { unsigned slot, stereo, fbytes, sbytes; const uint8_t *p; uint32_t from, len; } AkRam;
DATA AkFeatures dr_ak_feat[DR_SLICES] = { { 0 } };
DATA uint8_t dr_ask_t, dr_asking, dr_kw_redo, dr_ak_copies;
DATA uint8_t dr_ask_keep;                        /* the question's NO keeps the kit (a new sample) */
/* The FLEX slot a track had when a SETUP window opened on it (0xff: none open). */
DATA uint8_t dr_slot_seen[TRACKS] = { 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff };
/* Image 70: the FLEX slot each track's kit was made for (0xff: not seen yet, taken at the next tick), and
 * one kit put aside per track -- the one a Part or bank change replaced, with its slot -- so a set going
 * back and forth between two Parts finds each sample's kit, edits kept, with no file read. */
DATA uint8_t dr_kit_slot[TRACKS] = { 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff };
typedef struct {
    uint8_t slot, simtol, simmode, pad;
    DrKit kit;
    uint8_t align[DR_SLICES];
    int8_t gain[DR_SLICES];
    uint8_t link[DR_SLICES];
} DrKitAside;
#define DR_ASIDE0 { .slot = 0xff }
DATA DrKitAside dr_aside[TRACKS] = { DR_ASIDE0, DR_ASIDE0, DR_ASIDE0, DR_ASIDE0,
                                     DR_ASIDE0, DR_ASIDE0, DR_ASIDE0, DR_ASIDE0 };
DATA uint8_t dr_loaded;
DATA uint8_t dr_rtrg_now[TRACKS], dr_rtim_now[TRACKS];
DATA uint8_t dr_cur_style[TRACKS];
DATA uint32_t dr_dbg[8] = { 0 };           /* image 45 only: F in the KIT window, FUNC + NO shows the counters */         /* a project has been loaded or made (store.c): the slots are there */
DATA const char *dr_ask_lines[3] = { 0 };

/* ---- the kit file (image 68): NAME.drk beside the sample ----------------
 * What the sample's sound decides (zones, roles, combos, priority, ALIGN,
 * GAIN, the SIMILAR groups, tolerance and mode), with the slices it was made
 * on (their count and a CRC-32 of their bounds). SCENE, DOSE, SHIFT and PHRASE
 * stay in the project (drummer.work): they are the Part's and the player's.
 * The engine task reads and writes it (store.c dr_job, posted through its
 * queue as BRAIN's jobs are); the UI fills it before a save and applies it
 * after a load. */
typedef struct {
    uint8_t n, simtol, simmode, pad;
    uint32_t sig;                                 /* CRC-32 of the n slices' bounds (FLEX settings + 312) */
    uint8_t zone[DR_SLICES], role[DR_SLICES];
    uint16_t combo[DR_SLICES];
    uint8_t align[DR_SLICES], prio[DR_ZONES], pad2[3];
    int8_t gain[DR_SLICES];
    uint8_t link[DR_SLICES];
} DrkFile;
_Static_assert(sizeof(DrkFile) == 8 + 7 * DR_SLICES + 12, "the .drk payload, version 1");
enum { DRK_IDLE, DRK_BUSY, DRK_SAVED, DRK_FAILED, DRK_FOUND, DRK_STALE, DRK_NONE };
enum { DRK_SAVE = 1, DRK_LOAD = 2 };
DATA DrkFile dr_drk;
DATA volatile uint8_t dr_drk_res;                /* the job's outcome (DRK_*), taken by the UI tick */
DATA uint8_t dr_drk_t = 0xff, dr_drk_case;      /* the job's track (0xff none); 1 no kit yet, 2 a new sample, 3 SAVE */
void dr_drk_post(unsigned kind, unsigned slot);  /* store.c */

static int ak_read_ram(void *ctx, uint32_t frame)
{
    AkRam *x = ctx;
    const uint8_t *q;
    int l, r;
    if (!x->p || frame < x->from || frame >= x->from + x->len) {
        uint32_t run = 0;
        x->p = dr_sample_at(x->slot, frame, &run);
        x->from = frame;
        x->len = run;
        if (!x->p || !run) {
            x->p = 0;
            return 0;
        }
    }
    q = x->p + (frame - x->from) * x->fbytes;
    l = (int16_t)(q[0] << 8 | q[1]);
    r = x->stereo ? (int16_t)(q[x->sbytes] << 8 | q[x->sbytes + 1]) : l;
    return (l + r) / 2;
}

/* The track's kit from its sample's slices; the slice count, 0 for none. */
static unsigned autokit(unsigned t)
{
    unsigned slot = U8(LANE + 72u * t + 31u), n, i, flags;
    uint32_t set;
    AkRam ram;
    if (slot >= 128)
        return 0;
    set = FLEX_SET + 0x448u * slot;
    n = U32(set + 1092u);
    if (!n)
        return 0;
    if (n > DR_SLICES)
        n = DR_SLICES;
    flags = U32(SLOT_STATE + 44u * slot);
    ram.slot = slot;
    ram.stereo = flags & 1u;
    ram.sbytes = flags & 2u ? 2u : 3u;
    ram.fbytes = ram.sbytes * (ram.stereo ? 2u : 1u);
    ram.p = 0;
    ram.from = ram.len = 0;
    for (i = 0; i < n; i++)
        ak_features(ak_read_ram, &ram, U32(set + 312u + 12u * i), U32(set + 316u + 12u * i), &dr_ak_feat[i]);
    dr_kit_init(&dr_kit[t], n);
    for (i = 0; i < DR_SLICES; i++)
        dr_gain[t][i] = 0;                       /* a new kit: every GAIN back to 0 dB */
    dr_ak_copies = (uint8_t)ak_kit(dr_ak_feat, n, &dr_kit[t], dr_align[t], dr_simtol[t], dr_simmode[t], dr_link[t]);
    dr_kit_ready[t] = 1;
    return n;
}

static void kit_done(unsigned n, unsigned t)
{
    static const char *const none = "NO SLICES: SLICE THE SAMPLE";
    DATA static char msg[32];
    char *p = put_s(msg, "AUTO KIT T");
    if (!n) {
        FN(NOTIFY, const char *, unsigned)(none, 0x60);
        return;
    }
    p = put_u(p, t + 1, 1);
    p = put_s(p, ": ");
    p = put_u(p, n, 1);
    p = put_s(p, " SLICES");
    if (dr_ak_copies) {                          /* "8 SIMILAR OUT": the toast's box holds ~16 (DATE/TIME STORED) */
        p = put_u(msg, dr_ak_copies, 1);
        p = put_s(p, dr_simmode[t] ? " SIMILAR LINKED" : " SIMILAR OUT");
    }
    *p = 0;
    FN(NOTIFY, const char *, unsigned)(msg, 0x40);
}

/* The answer to "KIT: AUTO?" (0 YES). NO leaves the kit empty, kept. */
void dr_ask_answer(int answer)
{
    unsigned t = dr_ask_t, n;
    dr_asking = 0;
    if (t >= TRACKS)
        return;
    if (!dr_kw_redo && !dr_ask_keep && dr_kit_ready[t] != 2) {
        dr_kw_redo = 0;
        return;                                  /* the track got a kit meanwhile (a load): keep it */
    }
    if (answer == 0) {
        dr_ak_copies = 0;
        n = autokit(t);
        if (!n) {
            unsigned i;
            for (i = 0; i < DR_SLICES; i++)
                dr_link[t][i] = 0;
            dr_kit_init(&dr_kit[t], 0);
            dr_kit_ready[t] = 1;
        }
        kit_done(n, t);
    } else if (!dr_kw_redo && !dr_ask_keep) {    /* the first question: NO is an empty kit */
        unsigned i;
        for (i = 0; i < DR_SLICES; i++)
            dr_link[t][i] = 0;
        dr_kit_init(&dr_kit[t], 0);
        dr_kit_ready[t] = 1;
    }                                            /* AUTO AGAIN / a new sample: NO keeps the kit */
    dr_kw_redo = 0;
    dr_ask_keep = 0;
}

static unsigned lane_slot(unsigned t)
{
    return U8(LANE + 72u * t + 31u);
}

static void drk_gather(unsigned t)
{
    const DrKit *k = &dr_kit[t];
    unsigned i;
    for (i = 0; i < DR_SLICES; i++) {
        dr_drk.zone[i] = k->zone[i];
        dr_drk.role[i] = k->role[i];
        dr_drk.combo[i] = k->combo[i];
        dr_drk.align[i] = dr_align[t][i];
        dr_drk.gain[i] = dr_gain[t][i];
        dr_drk.link[i] = dr_link[t][i];
    }
    for (i = 0; i < DR_ZONES; i++)
        dr_drk.prio[i] = k->prio[i];
    dr_drk.simtol = dr_simtol[t];
    dr_drk.simmode = dr_simmode[t];
    dr_drk.pad = dr_drk.pad2[0] = dr_drk.pad2[1] = dr_drk.pad2[2] = 0;
}

/* The file's values, clamped as drummer.work's (store.c apply). */
static void drk_apply(unsigned t)
{
    DrKit *k = &dr_kit[t];
    unsigned i;
    dr_kit_init(k, 0);
    for (i = 0; i < DR_SLICES; i++) {
        k->zone[i] = dr_drk.zone[i] <= DR_COMBO ? dr_drk.zone[i] : DR_OUT;
        k->role[i] = dr_drk.role[i] < DR_ROLES ? dr_drk.role[i] : DR_NORMAL;
        k->combo[i] = dr_drk.combo[i];
        dr_align[t][i] = dr_drk.align[i] <= 250 ? dr_drk.align[i] : 250;
        dr_gain[t][i] = dr_drk.gain[i] < DR_GAIN_MIN ? DR_GAIN_MIN : dr_drk.gain[i] > DR_GAIN_MAX ? DR_GAIN_MAX : dr_drk.gain[i];
        dr_link[t][i] = dr_drk.link[i] <= DR_SLICES ? dr_drk.link[i] : 0;
    }
    for (i = 0; i < DR_ZONES; i++)
        if (dr_drk.prio[i] < DR_ZONES)
            k->prio[i] = dr_drk.prio[i];
    dr_simtol[t] = dr_drk.simtol <= AK_TOL_MAX ? dr_drk.simtol : AK_TOL_DEFAULT;
    dr_simmode[t] = dr_drk.simmode ? AK_DUP_LINK : AK_DUP_OUT;
    dr_kit_ready[t] = 1;
}

static void ask(unsigned t, const char *title, const char *line);

static unsigned flex_slot(unsigned t);

/* A project load or a new project: its kits are its samples' (taken at the next tick), nothing aside. */
void dr_kit_slots_reset(void)
{
    unsigned t;
    for (t = 0; t < TRACKS; t++) {
        dr_kit_slot[t] = 0xff;
        dr_aside[t].slot = 0xff;
    }
}

/* A copy of the track's kit put aside, with the slot it was made for. */
static void aside_keep(unsigned t)
{
    DrKitAside *a = &dr_aside[t];
    const uint8_t *y = (const uint8_t *)&dr_kit[t];
    uint8_t *x = (uint8_t *)&a->kit;
    unsigned i;
    for (i = 0; i < sizeof(DrKit); i++)
        x[i] = y[i];
    for (i = 0; i < DR_SLICES; i++) {
        a->align[i] = dr_align[t][i];
        a->gain[i] = dr_gain[t][i];
        a->link[i] = dr_link[t][i];
    }
    a->simtol = dr_simtol[t];
    a->simmode = dr_simmode[t];
    a->slot = dr_kit_slot[t];
}

/* The track's kit and the one put aside trade places. */
static void aside_swap(unsigned t)
{
    DrKitAside *a = &dr_aside[t];
    uint8_t *x = (uint8_t *)&a->kit, *y = (uint8_t *)&dr_kit[t], b;
    unsigned i;
    for (i = 0; i < sizeof(DrKit); i++) {
        b = x[i]; x[i] = y[i]; y[i] = b;
    }
    for (i = 0; i < DR_SLICES; i++) {
        int8_t g = a->gain[i];
        b = a->align[i]; a->align[i] = dr_align[t][i]; dr_align[t][i] = b;
        a->gain[i] = dr_gain[t][i]; dr_gain[t][i] = g;
        b = a->link[i]; a->link[i] = dr_link[t][i]; dr_link[t][i] = b;
    }
    b = a->simtol; a->simtol = dr_simtol[t]; dr_simtol[t] = b;
    b = a->simmode; a->simmode = dr_simmode[t]; dr_simmode[t] = b;
    b = a->slot; a->slot = dr_kit_slot[t]; dr_kit_slot[t] = b;
}

/* The question AUTO asks (cs 1: no kit yet, 2: another sample), after a look
 * for the sample's kit file: the engine task reads it, the tick takes the
 * outcome. No sliced sample: asked at once. */
static void drk_start(unsigned t, unsigned cs)
{
    unsigned slot = flex_slot(t);                /* the Part's sample (the lane may still play the old one) */
    if (cs == 2 && dr_kit_slot[t] != 0xff && dr_kit_slot[t] != slot)
        aside_keep(t);                           /* the old sample's kit kept: a Part back on it gets it back */
    dr_kit_slot[t] = (uint8_t)slot;              /* the kit to come is this sample's, whatever the answer */
    if (slot < 128 && slice_count(t)) {
        dr_drk_t = (uint8_t)t;
        dr_drk_case = (uint8_t)cs;
        dr_drk_res = DRK_BUSY;
        dr_drk_post(DRK_LOAD, slot);
        return;
    }
    if (cs == 2) {
        dr_ask_keep = 1;
        ask(t, "DRUMMER: NEW SAMPLE", "A KIT FROM ITS SLICES?");
    } else {
        ask(t, "DRUMMER KIT", "THIS TRACK HAS NO KIT YET");
    }
}

/* A Part or bank change gave a DRUMMER track another sample (any track, shown or not; no SETUP window
 * picking it): the kit put aside if it is that sample's (the kits trade places), else the current one put
 * aside and the sample's kit file looked for (case 4: found, loaded; else the kit stays, nothing asked --
 * a set is playing). One file job at a time: the next track at a later tick. */
static void part_follow(unsigned shown, unsigned setup)
{
    unsigned t, slot;
    if (!dr_loaded || !bank_ok())
        return;
    for (t = 0; t < TRACKS; t++) {
        if (!signed_track(part_base(), t) || dr_kit_ready[t] != 1)
            continue;
        slot = flex_slot(t);
        if (slot >= 128)
            continue;
        if (dr_kit_slot[t] == 0xff) {            /* a loaded or new kit: the sample it plays now */
            dr_kit_slot[t] = (uint8_t)slot;
            continue;
        }
        if (slot == dr_kit_slot[t] || dr_slot_seen[t] != 0xff || (setup && t == shown) || dr_drk_t == t)
            continue;
        if (dr_aside[t].slot == slot) {
            aside_swap(t);
            continue;
        }
        if (dr_drk_t != 0xff)
            return;
        aside_keep(t);                           /* a copy aside, with its slot; the kit plays on meanwhile */
        dr_kit_slot[t] = (uint8_t)slot;
        dr_drk_t = (uint8_t)t;
        dr_drk_case = 4;
        dr_drk_res = DRK_BUSY;
        dr_drk_post(DRK_LOAD, slot);
        return;
    }
}

/* The job's outcome, once (a load for another track than the one shown:
 * applied if found, else dropped; the question comes back with the track). */
static void drk_take(unsigned shown, unsigned free)
{
    unsigned t = dr_drk_t, res = dr_drk_res, cs = dr_drk_case;
    if (t >= TRACKS || res <= DRK_BUSY)
        return;
    if (cs == 3) {
        FN(NOTIFY, const char *, unsigned)(res == DRK_SAVED ? "KIT FILE SAVED" : "KIT FILE NOT SAVED", 0x40);
    } else if (res == DRK_FOUND) {
        drk_apply(t);
        FN(NOTIFY, const char *, unsigned)("KIT FILE LOADED", 0x40);
    } else if (cs == 4) {
        if (t == shown)
            FN(NOTIFY, const char *, unsigned)("NO KIT FILE", 0x40);   /* the kit stays */
    } else if (t != shown) {
        ;
    } else if (!free) {
        return;                                  /* asked when the screen is free */
    } else if (cs == 2) {
        dr_ask_keep = 1;
        ask(t, "DRUMMER: NEW SAMPLE", res == DRK_STALE ? "ITS KIT FILE IS OUT OF DATE" : "A KIT FROM ITS SLICES?");
    } else {
        ask(t, "DRUMMER KIT", res == DRK_STALE ? "ITS KIT FILE IS OUT OF DATE" : "THIS TRACK HAS NO KIT YET");
    }
    dr_drk_t = 0xff;
    dr_drk_res = DRK_IDLE;
}

/* SAVE KIT (page 3, E): asked, then written by the engine task. */
DATA const char *dr_save_lines[3] = { 0 };
DATA char dr_save_name[28];
DATA uint8_t dr_save_t;
void dr_save_answer(int answer)
{
    unsigned t = dr_save_t;
    dr_asking = 0;
    if (answer != 0 || t >= TRACKS || dr_drk_t != 0xff || dr_kit_ready[t] != 1)
        return;
    drk_gather(t);
    dr_drk_t = (uint8_t)t;
    dr_drk_case = 3;
    dr_drk_res = DRK_BUSY;
    dr_drk_post(DRK_SAVE, lane_slot(t));
}

static void kw_save(void)
{
    unsigned t = dr_kw_t, slot = lane_slot(t), i, b = 0, n = 0;
    const volatile char *path;
    if (!dr_kw || dr_asking)
        return;
    if (slot >= 128 || dr_kit_ready[t] != 1 || !slice_count(t) || dr_drk_t != 0xff) {
        FN(NOTIFY, const char *, unsigned)("NO KIT TO SAVE", 0x40);
        return;
    }
    path = (const volatile char *)ADDR(FLEX_SET + 0x448u * slot);
    for (i = 0; i < 200 && path[i]; i++)
        if (path[i] == '/')
            b = i + 1;
    for (i = b; path[i] && path[i] != '.' && n < 20; i++)
        dr_save_name[n++] = path[i];
    dr_save_name[n] = 0;
    put_s(dr_save_name + n, ".DRK")[0] = 0;
    dr_kw_close();                               /* stock's box does not show over our window */
    dr_save_t = (uint8_t)t;
    dr_asking = 1;
    dr_save_lines[0] = dr_save_name;
    dr_save_lines[1] = "YES: SAVE IT BESIDE THE SAMPLE";
    dr_save_lines[2] = "NO: CANCEL";
    FN(DIALOG, const char *, int, const char *const *, int, void (*)(int))("SAVE KIT FILE?", 3, dr_save_lines, 3, dr_save_answer);
}

static void ask(unsigned t, const char *title, const char *line)
{
    dr_ask_t = (uint8_t)t;
    dr_asking = 1;
    dr_ask_lines[0] = line;
    dr_ask_lines[1] = "YES: AUTO KIT FROM THE SLICES";
    dr_ask_lines[2] = dr_kw_redo || dr_ask_keep ? "NO: KEEP THE KIT" : "NO: AN EMPTY KIT";
    FN(DIALOG, const char *, int, const char *const *, int, void (*)(int))(title, 3, dr_ask_lines, 3, dr_ask_answer);
}

/* LEFT: the page before (1 ZONE ROLE, 2 ALIGN GAIN SCENE DOSE, 3 the track). */
void dr_kw_left(void)
{
    if (!dr_kw || dr_asking || !dr_kw_page)
        return;
    dr_kw_page--;
    kw_draw();
}

/* FUNC + RIGHT: AUTO again (asked first; the kit is replaced). FUNC held
 * puts stock's own key layer over ours, so the chord is read from the key
 * rows each UI tick (dr_kit_tick). */
static void kw_auto(void)
{
    unsigned t = dr_kw_t;
    if (!dr_kw || dr_asking)
        return;
    dr_kw_close();                               /* stock's box does not show over our window (port) */
    dr_kw_redo = 1;
    ask(t, "KIT: AUTO AGAIN?", "THE KIT IS REPLACED");
}

/* RIGHT: the page after. */
void dr_kw_right(void)
{
    if (dr_kw && !dr_asking && dr_kw_page + 1u < KW_PAGES) {
        dr_kw_page++;
        kw_draw();
    }
}



/* The FLEX slot a track's Part names (0xff with no bank). */
static unsigned flex_slot(unsigned t)
{
    if (!bank_ok())
        return 0xff;
    return part_base()[0x2ca + 5u * t + 1u];
}

/* ---- KIT BALANCE: SRC pressed again on a DRUMMER track's LIVE page (PAGES) */

/* The zones' mix, six bytes of the Part (STATIC's PLAYBACK column of the
 * track, unused on a FLEX track; adapter.c MIX_AT), shown in a window
 * (PAGES' page after LIVE: SRC again) and turned by A-F; 64 is the style's (100 %), 0 the zone out, 127 twice as busy (198 %). */
enum { PAGE_SHOWN = 0x460d1684u,                  /* the page key shown: 0 SRC, 2 AMP (port) */
       PART_DIRTY = 0x9b332u, SRAM_PART = 0x100a4eceu, SRAM_DIRTY = 0x100f8598u, EDITED = 0x40027e00u };
extern const uint8_t dr_l2_layer[];
DATA uint32_t dr_l2;              /* the window, 0 closed */
DATA uint8_t  dr_l2_t, dr_l2_pushed, dr_l2_view;   /* view: 0 KIT BALANCE, 1 FILLS (SRC once more) */
static const char *const MIXN[DR_MIXES] = { "KICK", "SNARE", "HATS", "CYMB", "TOMS", "PERC" };

/* A Part byte of the current Part and its battery copy, marked edited (stock's
 * SETUP commit: 0x4005a5a8). */
static void part_put(unsigned off, unsigned v)
{
    volatile uint8_t *part = (volatile uint8_t *)part_base();
    uint32_t bank = U32(BANK_PTR);
    part[off] = (uint8_t)v;
    U8(SRAM_PART + ((uint32_t)(uintptr_t)part - bank - PART_OFF) + off) = (uint8_t)v;
    U32(bank + PART_DIRTY) = 1;
    U32(SRAM_DIRTY) = 1;
    FN(EDITED, void)();
}

/* KIT BALANCE's six bytes at 64 the first time (marked after "DR",1). */
static void l2_seed(unsigned t)
{
    unsigned i;
    if (part_base()[MIX_MARK + 30u * t] == MIX_MAGIC)
        return;
    for (i = 0; i < DR_MIXES; i++)
        part_put(MIX_AT + 30u * t + i, 64);
    part_put(MIX_MARK + 30u * t, MIX_MAGIC);
}

/* A dotted line, one pixel in two (h 1: across, w 1: down). */
static void dots(uint32_t s, int x, int y, int w, int h)
{
    int i;
    for (i = 0; i < (w > h ? w : h); i += 2)
    {
        int px = w > h ? x + i : x, py = w > h ? y : y + i;
        FN(RULE, uint32_t, int, int, int, int)(s, px, py, px, 1);   /* (x1, y, x2, rows): measured */
    }
}

/* Text centred on cx (the font is 4 pixels a character, KIT's columns). */
static void centred(uint32_t s, int cx, int y, const char *t)
{
    int n = 0;
    while (t[n])
        n++;
    kw_text(s, cx - n * 2, y, t);
}

/* KIT BALANCE (image 67, the user's: the percentages were hard to set): one
 * row a zone, its name, a bar and a short value. The bar's middle tick is the
 * style as written (64, "="), left takes hits out ("-20" a fifth of them,
 * "OUT" all), right adds the style's other levels' hits ("+40" two fifths of
 * them); past the small tick (100) free steps come in too, the bar dotted
 * there. A-F move 5 % a detent and stop once on the middle. */
enum { L2_ROW0 = 41, L2_X_BAR = 28, L2_X_VAL = 92, L2_FREE = 100 };

static int l2_step(unsigned v)                    /* the detent nearest v, -20..20 */
{
    return v <= 64 ? -(int)(((64u - v) * 20u + 32u) / 64u) : (int)(((v - 64u) * 20u + 31u) / 63u);
}

static unsigned l2_value(int k)                   /* a detent's byte */
{
    return k < 0 ? 64u - ((unsigned)-k * 64u + 10u) / 20u : 64u + ((unsigned)k * 63u + 10u) / 20u;
}

static int l2_x(unsigned v)                       /* v's place on the bar, L2_X_BAR..+60 */
{
    return v <= 64 ? L2_X_BAR + (int)(v * 30u / 64u) : L2_X_BAR + 30 + (int)((v - 64u) * 30u / 63u);
}

static void vline(uint32_t s, int x, int y, int h)
{
    int i;
    for (i = 0; i < h; i++)
        FN(RULE, uint32_t, int, int, int, int)(s, x, y + i, x, 1);
}

/* FILLS (image 74): DRUMMER's second page after LIVE (SRC once more, after
 * KIT BALANCE), the same window: six rows, A-F, each a choice, AUTO first
 * (the engine's: VAR, ORN, the style). Six bytes of the Part, NEIGHBOR's
 * SETUP column of the track (unused on FLEX), marked 'F' after KIT
 * BALANCE's 'M'; the engine reads them each step (params_of). */
static const char *const FILLN[DR_FILLS] = { "FILL", "FREQ", "LONG", "STIK", "ORCH", "TRIP" };
static const char *const FILL_V[] = { "AUTO", "WRIT", "RUDI", "TRIP", "3:4" };
static const char *const FREQ_V[] = { "AUTO", "BRK", "2BAR", "PHRS" };   /* AUTO: BRK's and VAR's; else BRK's */
static const char *const LONG_V[] = { "AUTO", "1BT", "2BT", "BAR" };
static const char *const ORCH_V[] = { "AUTO", "TOMS", "SNR", "SWAP" };
static const char *const TRIP_V[] = { "AUTO", "8TH", "6LET", "8>6" };
static const char *const FILL_HELP[DR_FILLS] = { "FAMILY", "WHEN", "HOW LONG", "STICKING", "DRUMS", "TRIPLETS" };

static void fills_seed(unsigned t)
{
    unsigned i;
    if (part_base()[FILLS_MARK + 30u * t] == FILLS_MAGIC)
        return;
    for (i = 0; i < DR_FILLS; i++)
        part_put(FILLS_AT + 30u * t + i, 0);
    part_put(FILLS_MARK + 30u * t, FILLS_MAGIC);
}

static unsigned fills_max(unsigned i, unsigned fam)
{
    static const uint8_t MAX[DR_FILLS] = { DR_FILL_MAX, DR_FREQ_MAX, DR_LONG_MAX, 0, DR_ORCH_MAX, DR_TRIP_MAX };
    return i == DR_F_STIK ? dr_fill_sticks(fam ? fam - 1u : 0) : MAX[i];
}

static void fills_draw(uint32_t s)
{
    const volatile uint8_t *part = part_base();
    unsigned i, fam = part[FILLS_AT + 30u * dr_l2_t] & 0x0fu;
    int top = (int)U32(s + 4) - 20 + 2;
    for (i = 0; i < DR_FILLS; i++) {
        unsigned v = part[FILLS_AT + 30u * dr_l2_t + i] & 0x0fu;
        const char *t = "AUTO";
        int y = top - 7 * (int)i;
        if (i == DR_F_FILL)
            t = FILL_V[v <= DR_FILL_MAX ? v : 0];
        else if (i == DR_F_FREQ)
            t = FREQ_V[v <= DR_FREQ_MAX ? v : 0];
        else if (i == DR_F_LONG)
            t = LONG_V[v <= DR_LONG_MAX ? v : 0];
        else if (i == DR_F_ORCH)
            t = ORCH_V[v <= DR_ORCH_MAX ? v : 0];
        else if (i == DR_F_TRIP)
            t = TRIP_V[v <= DR_TRIP_MAX ? v : 0];
        else if (fam < 2 || fam > DR_FILL_MAX)
            t = "--";                            /* STIK: a family set first (RUDI, TRIP, 3:4) */
        else if (v)
            t = dr_fill_stick_name(fam - 1u, v - 1u);
        kw_text(s, 4, y, FILLN[i]);
        kw_text(s, 28, y, t);
        kw_text(s, 56, y, FILL_HELP[i]);
    }
}

/* A-F: one choice a detent; STIK only under a family set (its stickings). */
static void fills_enc(unsigned index, int delta)
{
    unsigned off = FILLS_AT + 30u * dr_l2_t, fam = part_base()[off] & 0x0fu, max;
    int v;
    if (index >= DR_FILLS)
        return;
    max = fills_max(index, fam);
    if (index == DR_F_STIK && (fam < 2 || fam > DR_FILL_MAX))
        return;
    v = (int)(part_base()[off + index] & 0x0fu) + delta;
    part_put(off + index, (unsigned)(v < 0 ? 0 : v > (int)max ? (int)max : v));
    if (index == DR_F_FILL && (part_base()[off + DR_F_STIK] & 0x0fu) > fills_max(DR_F_STIK, part_base()[off] & 0x0fu))
        part_put(off + DR_F_STIK, 0);            /* another family: its sticking AUTO */
}

static void l2_draw(void)
{
    uint32_t s;
    int top, x;
    unsigned i;
    char line[8], *p;
    if (!dr_l2)
        return;
    if (dr_l2_view) {
        s = dr_l2 + 36;
        p = put_s(dr_kw_band, "FILLS T");
        p = put_u(p, dr_l2_t + 1u, 1);
        *p = 0;
        FN(WTITLE, uint32_t, const char *, int)(dr_l2, dr_kw_band, 0);
        FN(WINSIDE, uint32_t)(s);
        fills_draw(s);
        U32(SCRDIRTY) = 1;
        return;
    }
    s = dr_l2 + 36;
    p = put_s(dr_kw_band, "KIT BALANCE T");
    p = put_u(p, dr_l2_t + 1u, 1);
    *p = 0;
    FN(WTITLE, uint32_t, const char *, int)(dr_l2, dr_kw_band, 0);
    FN(WINSIDE, uint32_t)(s);
    top = (int)U32(s + 4) - 20 + 2;
    for (i = 0; i < DR_MIXES; i++) {
        unsigned v = part_base()[MIX_AT + 30u * dr_l2_t + i] & 0x7fu;
        int y = top - 7 * (int)i, xf = l2_x(L2_FREE);
        kw_text(s, 4, y, MIXN[i]);
        FN(RULE, uint32_t, int, int, int, int)(s, L2_X_BAR, y + 2, xf, 1);    /* the bar: solid, */
        dots(s, xf + 2, y + 2, L2_X_BAR + 60 - xf - 2, 1);                    /* dotted past the free steps' tick */
        vline(s, L2_X_BAR, y, 5);                                             /* its ends, */
        vline(s, L2_X_BAR + 60, y, 5);
        vline(s, L2_X_BAR + 30, y, 5);                                        /* the style as written, */
        vline(s, xf, y + 3, 2);                                               /* the free steps */
        x = l2_x(v);
        FN(RULE, uint32_t, int, int, int, int)(s, x - 1, y, x + 1, 1);        /* the knob: 3 x 5 */
        vline(s, x - 1, y, 5);
        vline(s, x, y, 5);
        vline(s, x + 1, y, 5);
        if (!v)
            p = put_s(line, "OUT");
        else if (!l2_step(v))                     /* 64, or a byte set before image 67 next to it */
            p = put_s(line, "=");
        else {                                    /* the detent's: 5 % each */
            int k = l2_step(v);
            line[0] = v < 64 ? '-' : '+';
            p = put_u(line + 1, 5u * (unsigned)(k < 0 ? -k : k), 1);
        }
        *p = 0;
        kw_text(s, L2_X_VAL, y, line);
    }
    U32(SCRDIRTY) = 1;
}

static void l2_close(void)
{
    if (dr_l2)
        FN(WDESTROY, uint32_t *)(&dr_l2);
    dr_l2 = 0;
    dr_l2_view = 0;
    if (dr_l2_pushed) {
        dr_l2_pushed = 0;
        FN(LPOP, const void *)(dr_l2_layer);
    }
}

static void dr_l2_closed(void)
{
    dr_l2 = 0;
    dr_l2_view = 0;
    if (dr_l2_pushed) {
        dr_l2_pushed = 0;
        FN(LPOP, const void *)(dr_l2_layer);
    }
}

/* A-F: a zone's mix, 5 % a detent (l2_step). */
void dr_l2_enc(unsigned index, int delta)
{
    unsigned off;
    int k, v;
    if (!dr_l2 || index >= DR_MIXES)
        return;
    if (dr_l2_view) {
        fills_enc(index, delta);
        l2_draw();
        return;
    }
    off = MIX_AT + 30u * dr_l2_t + index;
    k = l2_step(part_base()[off] & 0x7fu);
    v = k + delta;
    if ((k < 0 && v > 0) || (k > 0 && v < 0))     /* the middle stops the turn once */
        v = 0;
    part_put(off, l2_value(v < -20 ? -20 : v > 20 ? 20 : v));
    l2_draw();
}

/* PAGES (audio mode, SRC pressed again on its page): KIT BALANCE is DRUMMER's
 * page after LIVE. Open only on a DRUMMER track (else the press does what
 * stock's does: nothing); closed off the SRC page, on another track, under
 * a SETUP window, the KIT or a dialog. */
unsigned dr_page_shown(void)
{
    return dr_l2 != 0;
}

/* PAGES closes the page shown before the next one: KIT BALANCE gives way to
 * FILLS in the same window (DRUMMER is one client, its two pages its own);
 * FILLS closes for real, the stock page next. */
void dr_page_close(void)
{
    if (dr_l2 && !dr_l2_view) {
        fills_seed(dr_l2_t);
        dr_l2_view = 1;
        l2_draw();
        return;
    }
    l2_close();
}

void dr_page_open(void)
{
    unsigned t = ui_drummer_track();
    if (dr_l2 || t >= TRACKS || dr_kw || dr_asking)
        return;
    l2_seed(t);
    dr_l2_t = (uint8_t)t;
    dr_l2_view = 0;
    dr_l2 = FN(WCREATE, int, int, int, int, int, void (*)(void))(KW_W, KW_H, KW_DX, 0, KW_CLASS, dr_l2_closed);
    if (!dr_l2)
        return;
    FN(LPUSH, const void *)(dr_l2_layer);
    dr_l2_pushed = 1;
    l2_draw();
}

void dr_page_tick(void)
{
    if (dr_l2 && (ui_drummer_track() != dr_l2_t || U32(PAGE_SHOWN) != 0 || dr_kw || dr_asking
                  || U32(DIALOG_OPEN) || U32(U32(SETUP_WIN) + 8)))
        l2_close();
}

/* Each UI tick: dr_up_layer (BANK only) pushed while a trig key is held on a
 * DRUMMER track and no window is up; the window closed when its track is no
 * longer DRUMMER or the unit goes to MIDI mode. */
void dr_kit_tick(void)
{
    unsigned want, r;
    for (r = 0; r < TRACKS; r++)
        if (dr_release[r] && !--dr_release[r])
            kw_release(r);
    if (dr_kw && ui_drummer_track() != dr_kw_t)
        dr_kw_close();
    {   /* FUNC + RIGHT (key 0x21: row 4, bit 1) in the window */
        unsigned right = U8(KEY_ROWS + 4) >> 1 & 1u;
        if (right && !dr_kw_rprev && dr_kw && U32(FUNC_HELD))
            kw_auto();
        dr_kw_rprev = (uint8_t)right;
    }
    {   /* a DRUMMER track shown with no kit yet: offer AUTO once its machine list has closed */
        unsigned t = ui_drummer_track(), setup = U32(U32(SETUP_WIN) + 8) != 0;
        unsigned free = dr_loaded && !dr_asking && !dr_kw && !U32(DIALOG_OPEN) && !setup;
        if (t < TRACKS && setup && dr_slot_seen[t] == 0xff)
            dr_slot_seen[t] = (uint8_t)flex_slot(t);
        drk_take(t, free);                       /* a kit file's job done (any track's) */
        part_follow(t, setup);                   /* a Part or bank change: each track's sample's kit */
        if (t < TRACKS) {
            ensure_kit(t);
            unsigned slot = flex_slot(t);
            /* A sample picked in a SETUP window (DRUMMER's RIGHT, or FLEX's list
             * before DRUMMER): asked when the window closes. A Part or bank
             * change during a set never asks (part_follow: its kit file, or the
             * kit put aside, else the kit stays). */
            free = free && !dr_asking && dr_drk_t == 0xff;
            if (dr_kit_ready[t] == 2 && free)
                drk_start(t, 1);                 /* its kit file, else AUTO? */
            else if (!setup && dr_slot_seen[t] != 0xff) {
                unsigned changed = slot != dr_slot_seen[t] && dr_kit_ready[t] == 1;
                dr_slot_seen[t] = 0xff;
                if (changed && free)
                    drk_start(t, 2);             /* another sample on the track: its kit file, else AUTO again? */
            }
        }
    }
    want = trigs_held() && ui_drummer_track() < TRACKS && !dr_kw && !U32(U32(SETUP_WIN) + 8);
    if (want && !dr_up_pushed) {
        FN(LPUSH, const void *)(dr_up_layer);
        dr_up_pushed = 1;
    } else if (!want && dr_up_pushed) {
        FN(LPOP, const void *)(dr_up_layer);
        dr_up_pushed = 0;
    }
}
