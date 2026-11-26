/* APPLY SCENE: the firmware side. Every entry is a key handler `(code, edge)`
 * that the scene keys' own tables call (manifest.py), so all of it runs in the
 * UI task, where stock's own key handlers and toasts run. Nothing here runs
 * in the sequencer tick or the frame interrupt. edge: 1 press, 2 repeat,
 * 0 release (MAINMENU.md section 6). */
#include "apply.h"

#define U8(a)  (*(volatile uint8_t *)(uintptr_t)(a))
#define U16(a) (*(volatile uint16_t *)(uintptr_t)(a))
#define U32(a) (*(volatile uint32_t *)(uintptr_t)(a))
#define FN(addr, ...) ((uint32_t (*)(__VA_ARGS__))(uintptr_t)(addr))
/* The platform leaves a unit's .bss as the boot left it, nonzero on the unit
 * (TRAPS trap-dram-bss): state read before the unit first writes it lives in
 * .data; verify.py checks the symbols' sections. */
#define DATA __attribute__((section(".data")))

enum {
    KEY_ROWS   = 0x46100b18u,   /* the panel's key rows: key code c held = bit c&7 of byte c>>3 (PANEL.md 4b) */
    SCENE_A    = 0x19u,
    SCENE_B    = 0x1au,
    YES        = 0x31u,
    LAYERS     = 0x460d165cu,   /* -> the input layers, the base layer first (MAINMENU.md 6c) */
    MIDI_MODE  = 0x80000012u,   /* long: nonzero in MIDI mode */
    MASTER     = 0x80000034u,   /* MASTER TRACK on (BOOT.md) */
    BANK_RAM   = 0x46c82456u,   /* -> the bank's RAM (STEP_LOCKS.md) */
    PARTS      = 0x8ed80u,      /* bank RAM + this + Part * PART_SIZE: the Part */
    PART_SIZE  = 0x18b2u,
    UI_PART    = 0x100b14cfu,   /* byte: the Part the pages edit */
    UI_TRACK   = 0x100b14ccu,   /* byte: the audio track the pages edit */
    UI_PATTERN = 0x100b14d0u,   /* byte: the pattern edited */
    UI_BANK    = 0x100b14ceu,   /* byte: the bank stock's scene assign passes on */
    P_SCENE_A  = 0x10u,         /* Part: scene A's slot (0xff none) */
    P_SCENE_B  = 0x11u,
    P_MACHINE  = 0x22u,         /* Part + track: the machine */
    P_SRC      = 0x2au,         /* Part + track * 30 + machine * 6: SRC page 1 */
    P_PAGES    = 0x11au,        /* Part + track * 24: LFO, AMP, FX1, FX2 page 1, six each */
    P_SCENES   = 0x662u,        /* Part + scene * 0x100 + track * 0x20: a scene's locks */
    P_ID1      = 0x00u,         /* Part + track: the FX1 effect id; FX2's at P_ID2 */
    P_ID2      = 0x08u,
    P_P2       = 0x2feu,        /* Part + track * 30 + j: FX1 page 2 (j 0-5), FX2's (j 6-11) (PARAM_PAGES.md 5b) */
    LANE_P2    = 0x80000842u,   /* + track * 72 + j: the live page-2 values (0x80000810 + 0x32) */
    DESC1      = 0x400d5f58u,   /* FX1 descriptors by id; FX2's table is the remix's (aps_desc2) */
    DESC_COUNT = 0x9au,         /* descriptor + (6 + slot) * 4 + this: the slot's value count */
    CS1_PARTS  = 0x100a4eceu,   /* the battery-backed copy of the bank's Parts, + Part * PART_SIZE */
    PART_EDITED = 0x95048u,     /* bank RAM + this: bit p = Part p changed */
    PART_EDITED2 = 0x100b145eu,
    BANK_EDITED = 0x9b332u,     /* bank RAM + this: long 1, the bank changed */
    EDITED     = 0x100f8598u,   /* long 1: the project changed */
    SCN_CACHE  = 0x460c80f0u,   /* stock's scene write clears it when 4 or 14 (0x40025b40) */
    WEIGHTS    = 0x80003c60u,   /* + 4 * track: the scene weights (MIDI.md appendix C) */
    SCENE_OFF_A = 0x80000006u,  /* byte: scene A muted (FUNC + SCENE A) */
    SCENE_OFF_B = 0x80000007u,
    GRID_REC   = 0x460d1736u,   /* long: nonzero in GRID RECORDING */
    HELD       = 0x460d174au,   /* u16: the trig keys held in GRID RECORDING, bit k = trig k + 1 */
    STEP_PAGE  = 0x460d174cu,   /* long: the step of trig key 1 on the page shown */
    LIVE_REC   = 0x460d172au,   /* long: nonzero while the recorder runs (LIVE RECORDING) */
    TRANSPORT  = 0x800065b8u,   /* long: 1 while the sequencer plays */
    PATTERN_SIZE = 0x8ed8u,
    TRACK_SIZE = 0x91au,
    LOCKS      = 0x59u,         /* track record + this + step * 32 + flat: a step's lock */
    TRIGLESS   = 0x10u,         /* track record + this: the trigless trig mask; + 0 the trig mask */
    CS1_PATTERNS = 0x1001614eu, /* the battery-backed copy of the bank's patterns, same offsets */
    W_PAGE1    = 0x40054cd8u,   /* (track, flat, value): stock's page-1 writer (PARAM_PAGES.md 5) */
    LOCKS_DONE = 0x40027e00u,   /* (): after a lock is written (the lock editor's call) */
    TRACK_DONE = 0x4009da20u,   /* (track): the track's steps prepared again */
    ED_FLAG1   = 0x460d173au,   /* the lock editor's tail (cxosc po_octave, plocks-p2 pe_commit) */
    ED_WORDS   = 0x460d1a9eu,
    ED_WORD6   = 0x460d10dcu,
    ED_FLAG2   = 0x460d1750u,
    ED_CALL    = 0x400418e0u,
    ED_END     = 0x40027de4u,
    PAGE_DRAW  = 0x4004d948u,   /* (-1): the page's values drawn again */
    LOCK_LEDS  = 0x400339d8u,   /* (): the step-has-lock LEDs again (SEQ) */
    SCENE_SET  = 0x40002df4u,   /* (bank, Part, scene, side 0 A / 1 B): the scene's values to the engine */
    NOTIFY     = 0x4005a2b8u,   /* (text, ticks): stock's toast */
    ASSIGN_A   = 0x40052a18u,   /* (code): SCENE A + trig, stock */
    ASSIGN_B   = 0x40052944u,
    SCENE_PRESS = 0x4004348cu,  /* (code, edge): the SCENE keys' press, stock */
};

enum { TOAST = 48, TRACKS = 8, STEPS = 64 };

int32_t aps_tracks_all(void);   /* hooks.s: the TRACKS setting, 0 ACTIVE, 1 ALL */
int32_t aps_p2(void);           /* hooks.s: 1 when SCENES P2 is in the image */
uint32_t aps_desc2(void);       /* hooks.s: the remix's FX2 descriptor table */
void aps_p2_changed(void);      /* hooks.s: SCENES P2 reads the cells again */

/* ---- reading the Part ---- */

static uint32_t bank(void) { return U32(BANK_RAM); }
static unsigned part_no(void) { return U8(UI_PART) & 3; }
static volatile uint8_t *part(void) { return (volatile uint8_t *)(uintptr_t)(bank() + PARTS + part_no() * PART_SIZE); }

static int held(unsigned code) { return (U8(KEY_ROWS + (code >> 3)) >> (code & 7)) & 1; }
static unsigned scenes_held(void) { return (held(SCENE_A) ? AP_A : 0) | (held(SCENE_B) ? AP_B : 0); }

static void knobs(unsigned t, uint8_t *knob) {
    volatile uint8_t *p = part();
    unsigned m = p[P_MACHINE + t];
    for (unsigned k = 0; k < 6; k++) knob[k] = p[P_SRC + t * 30 + m * 6 + k];
    for (unsigned k = 6; k < AP_FLATS; k++) knob[k] = p[P_PAGES + t * 24 + (k - 6)];
}

static const uint8_t *scene(unsigned slot, unsigned t) {
    if (slot > 15) return 0;
    return (const uint8_t *)(uintptr_t)(part() + P_SCENES + slot * 0x100 + t * AP_SCENE_BYTES);
}

/* Flats never written: XVOL (a scene lock only), and track 8's SRC and AMP
 * with MASTER TRACK on. */
static uint32_t skip(unsigned t) {
    uint32_t s = 1u << AP_XVOL;
    if (t == 7 && U8(MASTER)) s |= 0x3fu | (0x3fu << 12);
    return s;
}

/* ---- page 2 (SCENES P2's cells) ---- */

static void knobs2(unsigned t, uint8_t *knob) {
    volatile uint8_t *p = part();
    for (unsigned j = 0; j < AP_P2; j++) knob[j] = p[P_P2 + t * 30 + j];
}

/* A scene's eight cells, or 0 for no scene. */
static const uint8_t *cells_of(unsigned slot, uint8_t *cells) {
    if (slot > 15) return 0;
    volatile uint8_t *p = part();
    for (unsigned i = 0; i < AP_CELLS; i++) {
        cells[2 * i] = p[P_SCENES + slot * 0x100 + i * AP_SCENE_BYTES + 30];
        cells[2 * i + 1] = p[P_SCENES + slot * 0x100 + i * AP_SCENE_BYTES + 31];
    }
    return cells;
}

/* The cells written back where they changed, the Part and its battery copy.
 * The frame pass reads a key before its value: a cell is emptied first,
 * then given its value, then its key. */
static void put_cells(unsigned slot, const uint8_t *cells) {
    volatile uint8_t *p = part();
    volatile uint8_t *c = (volatile uint8_t *)(uintptr_t)(CS1_PARTS + part_no() * PART_SIZE);
    for (unsigned i = 0; i < AP_CELLS; i++) {
        uint32_t off = P_SCENES + slot * 0x100 + i * AP_SCENE_BYTES + 30;
        uint8_t key = cells[2 * i], val = cells[2 * i + 1];
        if (p[off] == key && p[off + 1] == val) continue;
        if (p[off] != key) p[off] = c[off] = 0xff;
        p[off + 1] = c[off + 1] = val;
        p[off] = c[off] = key;
    }
}

/* Bit j: page-2 value j of track t is a select (fewer than 128 values),
 * which the crossfader snaps. */
static uint32_t selects(unsigned t) {
    volatile uint8_t *p = part();
    uint32_t m = 0;
    for (unsigned fx = 0; fx < 2; fx++) {
        uint32_t table = fx ? aps_desc2() : DESC1, desc = U32(table + 4 * p[(fx ? P_ID2 : P_ID1) + t]);
        if (!desc) continue;
        for (unsigned k = 0; k < 6; k++)
            if (U32(desc + (6 + k) * 4 + DESC_COUNT) < 128) m |= 1u << (fx * 6 + k);
    }
    return m;
}

/* Page-2 value j of track t: the Part, its battery copy and the live lane
 * (the stock page-2 editors' stores, MAINMENU.md 7). */
static void put_p2(unsigned t, unsigned j, uint8_t v) {
    uint32_t off = P_P2 + t * 30 + j;
    part()[off] = v;
    U8(CS1_PARTS + part_no() * PART_SIZE + off) = v;
    U8(LANE_P2 + t * 72 + j) = v;
}

/* The values `which` gives track t. `blend_mutes`: a muted scene is no side
 * of a blend (the frame builder's rule); an explicit A or B applies anyway. */
static uint32_t values(unsigned which, unsigned t, uint8_t *out, uint8_t *knob) {
    volatile uint8_t *p = part();
    const uint8_t *a = scene(p[P_SCENE_A], t), *b = scene(p[P_SCENE_B], t);
    if (which == AP_AB) {
        if (U8(SCENE_OFF_A)) a = 0;
        if (U8(SCENE_OFF_B)) b = 0;
    }
    uint32_t w = U32(WEIGHTS + 4 * t);
    knobs(t, knob);
    return ap_values(which, a, b, knob, ap_weight_a(w), ap_weight_b(w), skip(t), out);
}

/* The tracks a gesture takes (TRACKS): the edited one, or all eight. */
static uint8_t scope(void) { return (uint8_t)(aps_tracks_all() ? 0xff : 1u << (U8(UI_TRACK) & 7)); }

static void toast(const char *text) { FN(NOTIFY, const char *, uint32_t)(text, TOAST); }

static const char T_NOTHING[] = "NOTHING TO APPLY";
static const char T_LOCKED[] = "SCENE LOCKS SET";
static const char T_SAVED[] = "BLEND SAVED";
static const char T_CA[] = "SCENE A COMMITTED";
static const char T_CB[] = "SCENE B COMMITTED";
static const char T_CAB[] = "BLEND COMMITTED";

/* ---- writing scenes: the Part's copy and its battery twin ---- */

static void put_row(unsigned slot, unsigned t, const uint8_t *row) {
    volatile uint8_t *p = part();
    uint32_t off = P_SCENES + slot * 0x100 + t * AP_SCENE_BYTES;
    for (unsigned i = 0; i < AP_SCENE_BYTES; i++) {
        p[off + i] = row[i];
        U8(CS1_PARTS + part_no() * PART_SIZE + off + i) = row[i];
    }
}

static void get_row(unsigned slot, unsigned t, uint8_t *row) {
    const uint8_t *s = scene(slot, t);
    for (unsigned i = 0; i < AP_SCENE_BYTES; i++) row[i] = s[i];
}

static void part_edited(void) {
    uint32_t b = bank(), pn = part_no();
    U8(b + PART_EDITED) |= (uint8_t)(1u << pn);
    U8(PART_EDITED2) |= (uint8_t)(1u << pn);
    U32(b + BANK_EDITED) = 1;
    U32(EDITED) = 1;
}

/* After scene bytes changed: SCENES P2's cache dropped, and each side that
 * shows a changed slot sent to the engine again (its working copy). */
static void scenes_done(uint32_t slots) {
    volatile uint8_t *p = part();
    uint32_t pn = part_no();
    part_edited();
    if (U32(SCN_CACHE) == 4 || U32(SCN_CACHE) == 14) U32(SCN_CACHE) = 0;
    FN(LOCKS_DONE, void)();
    if (p[P_SCENE_A] < 16 && (slots >> p[P_SCENE_A]) & 1)
        FN(SCENE_SET, uint32_t, uint32_t, uint32_t, uint32_t)(U8(UI_BANK), pn, p[P_SCENE_A], 0);
    if (p[P_SCENE_B] < 16 && (slots >> p[P_SCENE_B]) & 1)
        FN(SCENE_SET, uint32_t, uint32_t, uint32_t, uint32_t)(U8(UI_BANK), pn, p[P_SCENE_B], 1);
}

/* ---- 1: the scenes into the Part ---- */

/* The Part takes the values on the tracks in scope, and the parameters it
 * took are unlocked in the two assigned scenes (the commit), so the
 * crossfader leaves them where they are. */
static void to_part(unsigned which) {
    volatile uint8_t *p = part();
    unsigned changed = 0, cleared = 0, p2 = aps_p2() != 0, p2_cleared = 0;
    unsigned sa = p[P_SCENE_A], sb = p[P_SCENE_B];
    uint32_t slots = 0;
    uint8_t tracks = scope();
    for (unsigned t = 0; t < TRACKS; t++) {
        if (!(tracks & (1u << t))) continue;
        uint8_t out[AP_FLATS], knob[AP_FLATS], row[AP_SCENE_BYTES];
        uint8_t ca[2 * AP_CELLS], cb[2 * AP_CELLS], out2[AP_P2], knob2[AP_P2];
        uint32_t mask = values(which, t, out, knob), mask2 = 0;
        for (unsigned k = 0; k < AP_FLATS; k++)
            if ((mask & (1u << k)) && out[k] != knob[k]) {
                FN(W_PAGE1, uint32_t, uint32_t, uint32_t)(t, k, out[k]);
                changed++;
            }
        if (p2) {
            const uint8_t *a = cells_of(sa, ca), *b = cells_of(sb, cb);
            if (which == AP_AB) {
                if (U8(SCENE_OFF_A)) a = 0;
                if (U8(SCENE_OFF_B)) b = 0;
            }
            knobs2(t, knob2);
            mask2 = ap_p2_values(which, a, b, t, knob2, ap_weight_a(U32(WEIGHTS + 4 * t)), selects(t), out2);
            for (unsigned j = 0; j < AP_P2; j++)
                if ((mask2 & (1u << j)) && out2[j] != knob2[j]) {
                    put_p2(t, j, out2[j]);
                    changed++;
                }
        }
        if (!(mask | mask2)) continue;
        for (unsigned side = 0; side < 2; side++) {
            unsigned slot = side ? sb : sa;
            if (slot > 15 || (side && slot == sa)) continue;
            get_row(slot, t, row);
            unsigned n = ap_clear(row, mask);
            if (n) {
                put_row(slot, t, row);
                slots |= 1u << slot;
                cleared += n;
            }
            if (!mask2) continue;
            cells_of(slot, ca);
            n = ap_p2_clear(ca, t, mask2);
            if (!n) continue;
            put_cells(slot, ca);
            slots |= 1u << slot;
            cleared += n;
            p2_cleared += n;
        }
    }
    if (p2_cleared) aps_p2_changed();
    if (!changed && !cleared) {
        toast(T_NOTHING);
        return;
    }
    part_edited();
    if (cleared) scenes_done(slots);
    else FN(LOCKS_DONE, void)();
    FN(PAGE_DRAW, int32_t)(-1);
    toast(which == AP_A ? T_CA : which == AP_B ? T_CB : T_CAB);
}

/* ---- 2 and 3: the values as step locks ---- */

static uint32_t track_rec(unsigned t) {
    return (uint32_t)U8(UI_PATTERN) * PATTERN_SIZE + t * TRACK_SIZE;
}

/* Write track t's values on one step: the RAM record and its battery copy. */
static unsigned lock_step(unsigned t, unsigned step, uint32_t mask, const uint8_t *out) {
    uint32_t off = track_rec(t) + LOCKS + step * AP_SCENE_BYTES, b = bank();
    unsigned n = 0;
    for (unsigned k = 0; k < AP_FLATS; k++)
        if (mask & (1u << k)) {
            U8(b + off + k) = out[k];
            U8(CS1_PATTERNS + off + k) = out[k];
            n++;
        }
    if (n) {
        U32(b + BANK_EDITED) = 1;
        U32(EDITED) = 1;
        FN(LOCKS_DONE, void)();
    }
    return n;
}

/* GRID RECORDING, trig keys held: the held steps of the edited track. The
 * lock editor's own tail after the stores, so letting the trigs go keeps them
 * (plocks-p2 DEVELOPMENT.md: without it the release counts as a tap). */
static void to_held_steps(unsigned which) {
    unsigned t = U8(UI_TRACK) & 7, n = 0;
    uint8_t out[AP_FLATS], knob[AP_FLATS];
    uint32_t mask = values(which, t, out, knob);
    uint16_t keys = U16(HELD);
    for (unsigned k = 0; k < 16; k++)
        if (keys & (1u << k)) n += lock_step(t, (U32(STEP_PAGE) + k) & (STEPS - 1), mask, out);
    if (!n) {
        toast(T_NOTHING);
        return;
    }
    FN(TRACK_DONE, uint32_t)(t);
    U32(ED_FLAG1) = 1;
    for (unsigned i = 0; i < 5; i++) U16(ED_WORDS + 2 * i) = 0;
    U16(ED_WORD6) = 0;
    U32(ED_FLAG2) = 1;
    FN(ED_CALL, void)();
    FN(LOCK_LEDS, void)();
    FN(PAGE_DRAW, int32_t)(-1);
    FN(ED_END, void)();
    toast(T_LOCKED);
}

/* ---- the base layer's own keys, for everything this module does not take ---- */

static void stock_key(uint32_t code, uint32_t edge) {
    uint32_t layer = U32(LAYERS);
    if (!layer) return;
    for (uint32_t r = U32(layer + 4); r && U8(r) != 0xff; r += 26)
        if (U8(r) == code) {
            uint32_t h = U32(r + (edge == 0 ? 6 : edge == 1 ? 2 : 10));
            if (h + 1 > 1) FN(h, uint32_t, uint32_t)(code, edge);
            return;
        }
}

DATA uint8_t aps_owned;           /* this module took YES's press: its release is ours */

/* SCENE A / B held, YES: the press decides. */
void aps_yes(uint32_t code, uint32_t edge) {
    if (edge == 1) {
        unsigned which = scenes_held();
        aps_owned = 0;
        if (!which || U32(MIDI_MODE)) {
            stock_key(code, edge);
            return;
        }
        aps_owned = 1;
        /* LIVE RECORDING while playing: nothing. Stock's page-1 writer would
         * record the values as p-locks on the trig being played instead of
         * writing the Part, and there is no live recording here. */
        if (U32(LIVE_REC) && U32(TRANSPORT) == 1) return;
        if (U32(GRID_REC) && U16(HELD)) to_held_steps(which);
        else to_part(which);
        return;
    }
    if (!aps_owned) stock_key(code, edge);
    else if (edge == 0) aps_owned = 0;
}

/* GRID RECORDING with trig keys held: a SCENE key's press writes the locks
 * (with the other scene key held, the blend), then stock's press. */
void aps_scene_press(uint32_t code, uint32_t edge) {
    if (edge == 1 && U32(GRID_REC) && U16(HELD) && !U32(MIDI_MODE)) {
        unsigned which = (code == SCENE_A ? AP_A : AP_B) | scenes_held();
        to_held_steps(which);
    }
    FN(SCENE_PRESS, uint32_t, uint32_t)(code, edge);
}

/* ---- 4: SCENE A + SCENE B + trig k: the blend into scene k ---- */

/* The blend's page-1 rows into scene `slot` (with `write`), or only counted.
 * Returns the number of locks. */
static unsigned blend_rows(unsigned slot, int write) {
    volatile uint8_t *p = part();
    unsigned locked = 0;
    uint8_t row[AP_SCENE_BYTES];
    for (unsigned t = 0; t < TRACKS; t++) {
        const uint8_t *a = scene(p[P_SCENE_A], t), *bb = scene(p[P_SCENE_B], t);
        if (U8(SCENE_OFF_A)) a = 0;
        if (U8(SCENE_OFF_B)) bb = 0;
        uint8_t knob[AP_FLATS];
        uint32_t w = U32(WEIGHTS + 4 * t);
        knobs(t, knob);
        uint32_t s = skip(t);
        if (!(t == 7 && U8(MASTER))) s &= ~(1u << AP_XVOL);    /* a scene may lock XVOL */
        locked += ap_scene(a, bb, knob, ap_weight_a(w), ap_weight_b(w), s, scene(slot, t), row);
        if (write) put_row(slot, t, row);
    }
    return locked;
}

/* The blend's page-2 cells (SCENES P2), from the scenes as they are. A
 * scene holds eight: a lock past the eighth is dropped. Returns how many. */
static unsigned blend_cells(uint8_t *cells) {
    volatile uint8_t *p = part();
    uint8_t ca[2 * AP_CELLS], cb[2 * AP_CELLS];
    const uint8_t *a = cells_of(p[P_SCENE_A], ca), *bb = cells_of(p[P_SCENE_B], cb);
    if (U8(SCENE_OFF_A)) a = 0;
    if (U8(SCENE_OFF_B)) bb = 0;
    unsigned n = 0;
    for (unsigned i = 0; i < 2 * AP_CELLS; i++) cells[i] = 0xff;
    for (unsigned t = 0; t < TRACKS; t++) {
        uint8_t knob2[AP_P2], out2[AP_P2];
        knobs2(t, knob2);
        uint32_t m2 = ap_p2_values(AP_AB, a, bb, t, knob2, ap_weight_a(U32(WEIGHTS + 4 * t)), selects(t), out2);
        n += ap_p2_set(cells, t, m2, out2);
    }
    return n;
}

/* Nothing locked in either scene: the slot is left as it is. */
static void save_blend(unsigned slot) {
    uint8_t cells[2 * AP_CELLS];
    unsigned p2 = aps_p2() != 0, n2 = p2 ? blend_cells(cells) : 0;
    if (!blend_rows(slot, 0) && !n2) {
        toast(T_NOTHING);
        return;
    }
    blend_rows(slot, 1);
    if (p2) {
        put_cells(slot, cells);
        aps_p2_changed();
    }
    scenes_done(1u << slot);
    FN(PAGE_DRAW, int32_t)(-1);
    toast(T_SAVED);
}

static void trig(uint32_t code, uint32_t edge, uint32_t stock) {
    if (edge == 1 && scenes_held() == AP_AB && !U32(MIDI_MODE) && code < 16) {
        save_blend(code);
        return;
    }
    FN(stock, uint32_t, uint32_t)(code, edge);
}

void aps_trig_a(uint32_t code, uint32_t edge) { trig(code, edge, ASSIGN_A); }
void aps_trig_b(uint32_t code, uint32_t edge) { trig(code, edge, ASSIGN_B); }
