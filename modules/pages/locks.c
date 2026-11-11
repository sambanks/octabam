/* PAGES LOCKS -- parameter locks and scene locks for the parameters a PAGES
 * client declares lockable (manifest.py LOCKS).
 *
 * The client keeps its page, its window and its values (the Part's); PAGES
 * keeps the locks:
 *
 *   step locks   GRID RECORDING, trigs held, a knob turned on the client's
 *                page: the held steps of the edited pattern take the lock
 *                (EVENTS edit.held: stock's held-step editor 0x400508e4 is the
 *                encoders' handler then, measured under the port). FUNC held
 *                while turning removes it.
 *   scene locks  a scene key held, a knob turned on the page: the held scene
 *                of the edited Part takes the lock (EVENTS edit.scene_held:
 *                stock's scene knob handler 0x40053498, measured). FUNC held
 *                removes it.
 *
 * With a trig or a scene held, a knob on a PAGES page that takes no lock is
 * dropped: stock would lock the page under the window (LIVE's under NEXT).
 *
 * Playback is the client's: it calls pg_lk_step() when its sequencer step is
 * decided and pg_lk_value() when it reads a lockable value. A step's locks
 * hold as the page declares: HOLD_TRIG (stock's: until the track's next trig;
 * a step with page locks counts as a trigless trig) or HOLD_STEP (that step
 * only). Scene locks morph with the crossfader as stock's do (SCENES P2's
 * formula: A * wA + B * (0x8000 - wA), wA from the frame's weights).
 *
 * Every lock is one 32-bit entry of a sorted pool (binary search):
 *   bit 31     kind: 0 step lock, 1 scene lock
 *   30..27     bank
 *   26..23     pattern (step lock) or Part (scene lock)
 *   22..20     track
 *   19..14     step (step lock) or scene
 *   13..11     page id (manifest.py LOCKS, 1..7)
 *   10..8      slot (the knob, A..F = 0..5)
 *   7..0       value
 * Saved with the project through STORE (client 10): PGLOCKS.WORK, written at
 * the bank writer and the project store when it changed, copied to
 * PGLOCKS.STRD at the project store, back at the project reload; read at a
 * load; emptied by a new project (DRUMMER's and FREE LOOP's form). A file that
 * is not that is never written over: STORE lists it and asks.
 */
#include <stdint.h>

#define ADDR(a) ((volatile uint8_t *)(uintptr_t)(a))
#define U8(a)  (*(volatile uint8_t *)ADDR(a))
#define U16(a) (*(volatile uint16_t *)ADDR(a))
#define U32(a) (*(volatile uint32_t *)ADDR(a))
#define DATA __attribute__((section(".data")))

enum {
    HELD        = 0x460d174au,   /* word: the held trig keys, bit i = trig i + 1 */
    STEPPAGE    = 0x460d174cu,   /* long: the step page's first step */
    SCENE_HELD  = 0x460d169cu,   /* long: 0 none, 1 scene A, else B */
    FUNC_HELD   = 0x46c7dd26u,   /* long: FUNCTION held */
    DBPTR       = 0x46c82456u,   /* long: the edited bank's window */
    BLOB        = 0x400e21e0u,   /* bank 0's window */
    BANK_STRIDE = 0x9b340u,
    PART_STRIDE = 0x18b2u,
    SEL_OFF     = 0x8ed90u,      /* Part: scene A, B at +1 */
    UI_PART     = 0x100b14cfu,
    UI_PTN      = 0x100b14d0u,
    TRK_BANK    = 0x8000182au,   /* + t: the track's playing bank, 0xff none */
    TRK_PART    = 0x80001832u,   /* + t: its Part */
    WEIGHTS     = 0x80003c60u,   /* + 4t: hi word = -wA */
    SCENE_A_OFF = 0x80000006u,   /* nonzero: scene A disabled */
    SCENE_B_OFF = 0x80000007u,
    EDITED      = 0x460d173au,   /* stock's knob commit: a held trig was edited */
    UI_TRACK    = 0x100b14ccu,
    PTN_STRIDE  = 0x8ed8u,       /* a bank's pattern (STEP_LOCKS.md section 1) */
    TRK_STRIDE  = 0x91au,        /* a pattern's audio track */
    TRIGS       = 0x00u,         /* track + 0..7: the trigs, step s = byte 7 - s/8, bit s%8 (measured) */
    TRIGLESS    = 0x10u,         /* track + 0x10..0x17: the trigless trigs (FUNC + TRIG; measured) */
    CLIP        = 0x460c8122u,   /* stock's clipboard, track-shaped (PLOCKS P2's) */
    UNDO        = 0x460bf218u,   /* stock's undo buffer */
    LOCKS_AT    = 0x59u,         /* track + 0x59: its 64 x 32 lock bytes; a buffer's at +0x28 */
};

#define POOL 4096u
#define CLIP_POOL 1024u                            /* the clipboard's and the undo buffer's locks */
#define TMP 1024u
#define PAGES 8u
#define SLOTS 8u
#define TRACKS 8u
#define NONE 0xffffu
#define HOLD_TRIG 0u
#define HOLD_STEP 1u
#define KEYMASK 0xffffff00u

DATA uint32_t pg_lk_pool[POOL];
DATA uint32_t pg_lk_count;
DATA uint32_t pg_lk_clip[CLIP_POOL], pg_lk_clip_n;  /* stock's clipboard's page locks (bank, pattern 0) */
DATA uint32_t pg_lk_undo[CLIP_POOL], pg_lk_undo_n;  /* its undo buffer's */
DATA uint32_t pg_lk_tmp[TMP];                       /* a copy's entries, between the two pools */
DATA uint32_t pg_lk_full;                          /* turns refused: the pool full */
DATA uint16_t pg_lk_active[PAGES][TRACKS][SLOTS];  /* the step locks playing */
DATA uint8_t  pg_lk_ready;
DATA uint8_t  pg_lk_dirty;                         /* the pool differs from PGLOCKS.WORK */
DATA uint8_t  pg_lk_nowrite, pg_lk_backup;         /* a refused file: not written over (STORE asks) */

/* manifest.py's generated glue (locks.s): the clients' callbacks by page id. */
extern const uint8_t pg_lk_hold[PAGES];
unsigned pg_lk_cb_ctx(void);                       /* 0 none, else 0x8000 | page << 8 | track */
unsigned pg_lk_cb_any(void);                       /* nonzero: any PAGES page in front, locks or not */
int pg_lk_cb_turn(unsigned page, unsigned slot, unsigned value, int delta);   /* -1: not lockable */
unsigned pg_lk_cb_part(unsigned page, unsigned track, unsigned slot);
void pg_lk_cb_redraw(unsigned page);

static void lk_ready(void)
{
    unsigned p, t, s;
    if (pg_lk_ready)
        return;
    for (p = 0; p < PAGES; p++)
        for (t = 0; t < TRACKS; t++)
            for (s = 0; s < SLOTS; s++)
                pg_lk_active[p][t][s] = NONE;
    pg_lk_ready = 1;
}

static uint32_t lk_key_of(unsigned scene, unsigned bank, unsigned pp, unsigned track, unsigned ss,
                       unsigned page, unsigned slot)
{
    return (uint32_t)(scene & 1u) << 31 | (uint32_t)(bank & 15u) << 27 | (uint32_t)(pp & 15u) << 23
         | (uint32_t)(track & 7u) << 20 | (uint32_t)(ss & 63u) << 14 | (uint32_t)(page & 7u) << 11
         | (uint32_t)(slot & 7u) << 8;
}

/* ---- a sorted pool (the project's, the clipboard's, the undo buffer's) */

/* The first entry of e[0..n) whose key is >= key. */
static unsigned p_lower(const uint32_t *e, unsigned n, uint32_t key)
{
    unsigned lo = 0, hi = n;
    while (lo < hi) {
        unsigned mid = (lo + hi) >> 1;
        if ((e[mid] & KEYMASK) < key)
            lo = mid + 1;
        else
            hi = mid;
    }
    return lo;
}

static unsigned p_put(uint32_t *e, uint32_t *n, unsigned cap, uint32_t key, unsigned value)
{
    unsigned i = p_lower(e, *n, key), j;
    if (i < *n && (e[i] & KEYMASK) == key) {
        if ((e[i] & 0xffu) != (value & 0xffu) && e == pg_lk_pool)
            pg_lk_dirty = 1;
        e[i] = key | (value & 0xffu);
        return 1;
    }
    if (*n >= cap) {
        pg_lk_full++;
        return 0;
    }
    for (j = *n; j > i; j--)
        e[j] = e[j - 1];
    e[i] = key | (value & 0xffu);
    (*n)++;
    if (e == pg_lk_pool)
        pg_lk_dirty = 1;
    return 1;
}

/* Every entry whose key is in [lo, lo + span) goes. */
static void p_del(uint32_t *e, uint32_t *n, uint32_t lo, uint32_t span)
{
    unsigned i = p_lower(e, *n, lo), j = i, k;
    while (j < *n && (e[j] & KEYMASK) - lo < span)
        j++;
    if (j == i)
        return;
    for (k = i; j < *n; k++, j++)
        e[k] = e[j];
    *n = k;
    if (e == pg_lk_pool)
        pg_lk_dirty = 1;
}

/* The entries of [sbase, sbase + span) in one pool become those of
 * [dbase, dbase + span) in another (or the same): the destination's go first. */
static void p_copy(const uint32_t *se, unsigned sn, uint32_t sbase,
                   uint32_t *de, uint32_t *dn, unsigned dcap, uint32_t dbase, uint32_t span)
{
    unsigned i = p_lower(se, sn, sbase), m = 0;
    for (; i < sn && (se[i] & KEYMASK) - sbase < span && m < TMP; i++)
        pg_lk_tmp[m++] = se[i] - sbase;           /* the offset in the range, the value kept */
    p_del(de, dn, dbase, span);
    for (i = 0; i < m; i++)
        p_put(de, dn, dcap, dbase + (pg_lk_tmp[i] & KEYMASK), pg_lk_tmp[i] & 0xffu);
}

static unsigned lk_lower(uint32_t key)
{
    return p_lower(pg_lk_pool, pg_lk_count, key);
}

/* The entry's value, or NONE. */
static unsigned lk_get(uint32_t key)
{
    unsigned i = lk_lower(key);
    return i < pg_lk_count && (pg_lk_pool[i] & KEYMASK) == key ? pg_lk_pool[i] & 0xffu : NONE;
}

static unsigned lk_put(uint32_t key, unsigned value)
{
    return p_put(pg_lk_pool, &pg_lk_count, POOL, key, value);
}

static void lk_del(uint32_t key)
{
    p_del(pg_lk_pool, &pg_lk_count, key, 1u << 8);
}

static unsigned lk_ui_bank(void)
{
    uint32_t b = U32(DBPTR);
    return b >= BLOB ? (b - BLOB) / BANK_STRIDE : 0;
}

static unsigned lk_ui_scene(void)
{
    unsigned held = U32(SCENE_HELD);
    uint32_t sel = U32(DBPTR) + SEL_OFF + (U8(UI_PART) & 3u) * PART_STRIDE;
    return U8(sel + (held == 1 ? 0u : 1u)) & 15u;
}

/* The step carries a trig of its own (TRIG) or a trigless one (FUNC + TRIG):
 * a step's locks need one, as stock's (the user places it; PAGES never does). */
static unsigned lk_has_trig(unsigned bank, unsigned ptn, unsigned track, unsigned step)
{
    uint32_t t = BLOB + bank * BANK_STRIDE + ptn * PTN_STRIDE + track * TRK_STRIDE + 7u - (step >> 3);
    return ((U8(t + TRIGS) | U8(t + TRIGLESS)) >> (step & 7u)) & 1u;
}

/* stock's knob commit (0x4004f0aa): the held trigs were edited, so their
 * release is no tap (PLOCKS P2's pe_commit; DEVELOPMENT.md). */
static void lk_commit(void)
{
    U32(EDITED) = 1;
    U16(0x460d1a9eu) = 0;
    U16(0x460d1aa0u) = 0;
    U16(0x460d1aa2u) = 0;
    U16(0x460d1aa4u) = 0;
    U16(0x460d1aa6u) = 0;
    U16(0x460d10dcu) = 0;
}

/* One lock turned: a missing lock starts from the Part's value. */
static void lk_turn(uint32_t key, unsigned page, unsigned track, unsigned slot, int delta)
{
    unsigned cur = lk_get(key);
    int v;
    if (U32(FUNC_HELD)) {
        lk_del(key);
        return;
    }
    if (cur == NONE)
        cur = pg_lk_cb_part(page, track, slot) & 0xffu;
    v = pg_lk_cb_turn(page, slot, cur, delta);
    if (v >= 0)
        lk_put(key, (unsigned)v);
}

/* ---- EVENTS edit.held: GRID RECORDING, trigs held -------------------- */

unsigned pg_lk_claim(unsigned encoder, int delta)
{
    (void)delta;
    return encoder <= 5u && U16(HELD) != 0 && (pg_lk_cb_ctx() != 0 || pg_lk_cb_any() != 0);
}

/* The native frame: (encoder, ticks), returns to stock's caller. */
void pg_handle(unsigned encoder, int delta)
{
    unsigned ctx = pg_lk_cb_ctx(), page = (ctx >> 8) & 7u, track = ctx & 7u, held = U16(HELD), i;
    unsigned bank = lk_ui_bank(), ptn = U8(UI_PTN) & 15u, first = U32(STEPPAGE);
    lk_ready();
    if (encoder > 5u)
        return;
    if (!ctx) {                                   /* a PAGES page that takes no lock: the turn is */
        lk_commit();                              /* nobody's (not the stock page's under it), the */
        return;                                   /* trigs' release no tap */
    }
    if (pg_lk_cb_turn(page, encoder, 0, 0) >= 0) {
        for (i = 0; i < 16u; i++)
            if ((held & (1u << i)) && lk_has_trig(bank, ptn, track, first + i))   /* no trig: no lock */
                lk_turn(lk_key_of(0, bank, ptn, track, first + i, page, encoder), page, track, encoder, delta);
    }
    lk_commit();
    pg_lk_cb_redraw(page);
}

/* ---- EVENTS edit.scene_held: a scene key held ------------------------ */

unsigned pg_lk_scene_claim(unsigned encoder, int delta)
{
    (void)delta;
    return encoder <= 5u && U32(SCENE_HELD) != 0 && (pg_lk_cb_ctx() != 0 || pg_lk_cb_any() != 0);
}

void pg_scene_handle(unsigned encoder, int delta)
{
    unsigned ctx = pg_lk_cb_ctx(), page = (ctx >> 8) & 7u, track = ctx & 7u;
    lk_ready();
    if (!ctx || encoder > 5u)
        return;
    if (pg_lk_cb_turn(page, encoder, 0, 0) >= 0)
        lk_turn(lk_key_of(1, lk_ui_bank(), U8(UI_PART) & 3u, track, lk_ui_scene(), page, encoder), page, track, encoder, delta);
    pg_lk_cb_redraw(page);
}

/* ---- the client's playback ------------------------------------------ */

/* The track's step `step` of (bank, pattern) is decided; `trig` nonzero when
 * the step carries a trig of the track's own (a trigless one too): its locks
 * play from there (hold 'trig': to the next trig; 'step': that step only). */
void pg_lk_step(unsigned page, unsigned track, unsigned bank, unsigned pattern, unsigned step, unsigned trig)
{
    uint32_t key;
    unsigned i, s;
    volatile uint16_t *act;
    lk_ready();
    if (page >= PAGES || track >= TRACKS)
        return;
    act = pg_lk_active[page][track];
    if (trig || pg_lk_hold[page] == HOLD_STEP)   /* a trig: its locks, the others the Part's */
        for (s = 0; s < SLOTS; s++)
            act[s] = NONE;
    if (!trig)
        return;
    key = lk_key_of(0, bank, pattern, track, step, page, 0);
    for (i = lk_lower(key); i < pg_lk_count && (pg_lk_pool[i] & 0xfffff800u) == key; i++)
        act[(pg_lk_pool[i] >> 8) & 7u] = (uint16_t)(pg_lk_pool[i] & 0xffu);
}

/* The value the client plays: its step lock or `base` (the Part's), then
 * the playing Part's scene locks on the crossfader. */
unsigned pg_lk_value(unsigned page, unsigned track, unsigned slot, unsigned base)
{
    unsigned v = base, bank, part, sa, sb, a, b, off;
    uint32_t win;
    int32_t wa;
    if (!pg_lk_ready || page >= PAGES || track >= TRACKS || slot >= SLOTS)
        return base;
    if (pg_lk_active[page][track][slot] != NONE)
        v = pg_lk_active[page][track][slot];
    bank = U8(TRK_BANK + track);
    if (bank > 15u)
        return v;
    part = U8(TRK_PART + track) & 3u;
    win = BLOB + bank * BANK_STRIDE + part * PART_STRIDE + SEL_OFF;
    sa = U8(win) & 15u;
    sb = U8(win + 1u) & 15u;
    off = (U8(SCENE_A_OFF) ? 1u : 0u) | (U8(SCENE_B_OFF) ? 2u : 0u);
    a = off & 1u ? NONE : lk_get(lk_key_of(1, bank, part, track, sa, page, slot));
    b = off & 2u ? NONE : lk_get(lk_key_of(1, bank, part, track, sb, page, slot));
    if (a == NONE && b == NONE)
        return v;
    if (a == NONE)
        a = v;
    if (b == NONE)
        b = v;
    wa = -(int32_t)(int16_t)(U32(WEIGHTS + 4u * track) >> 16);
    if (wa < 0)
        wa = 0;
    if (wa > 0x8000)
        wa = 0x8000;
    return (unsigned)(((int32_t)a * wa + (int32_t)b * (0x8000 - wa) + 0x4000) >> 15);
}

/* For the page's drawing: 0xffff when no trig or scene is held; else the
 * lock under the first held trig (GRID RECORDING) or the held scene, bit 8
 * set when there is one (its value in bits 0..7), bit 9 set for a scene. */
unsigned pg_lk_shown(unsigned page, unsigned track, unsigned slot)
{
    unsigned held = U16(HELD), i, v;
    lk_ready();
    if (U32(SCENE_HELD)) {
        v = lk_get(lk_key_of(1, lk_ui_bank(), U8(UI_PART) & 3u, track, lk_ui_scene(), page, slot));
        return 0x200u | (v == NONE ? 0u : 0x100u | v);
    }
    if (!held)
        return NONE;
    for (i = 0; i < 16u && !(held & (1u << i)); i++)
        ;
    v = lk_get(lk_key_of(0, lk_ui_bank(), U8(UI_PTN) & 15u, track, U32(STEPPAGE) + i, page, slot));
    return v == NONE ? 0u : 0x100u | v;
}

/* The held step's number (1..64) or scene (1..16) for the page's title, 0 none. */
unsigned pg_lk_where(void)
{
    unsigned held = U16(HELD), i;
    if (U32(SCENE_HELD))
        return 0x100u | (lk_ui_scene() + 1u);
    if (!held)
        return 0;
    for (i = 0; i < 16u && !(held & (1u << i)); i++)
        ;
    return U32(STEPPAGE) + i + 1u;
}

/* ---- PGLOCKS.WORK through STORE (locks.s: the file calls) --------------
 * {MAGIC 'PGLK', VERSION, count, CRC-32 of the entries} then the pool's
 * `count` entries, sorted. */
enum { PG_MAGIC = 0x50474c4bu, PG_VERSION = 1u, F_COPY = 0x40016388u };
extern char pg_lk_path[260], pg_lk_path2[260];
int32_t  pg_file_path(const char *format, char *out);
int32_t  pg_file_open(const char *path, const char *mode);
int32_t  pg_file_read(void *buffer, uint32_t length);
int32_t  pg_file_write(const void *buffer, uint32_t length);
void     pg_file_close(void);
uint32_t pg_file_crc(const void *buffer, uint32_t length);
void     pg_file_refuse(void);
typedef uint32_t (*Copy)(const char *, const char *, uint32_t);

static const char WORK[] = "%s/pglocks.work", STRD[] = "%s/pglocks.strd", BAK[] = "%s/pglocks.bak";

static int32_t lk_copy(const char *to, const char *from)
{
    pg_file_path(to, pg_lk_path);
    pg_file_path(from, pg_lk_path2);
    return (int32_t)((Copy)(uintptr_t)F_COPY)(pg_lk_path, pg_lk_path2, 0);
}

static void lk_clear(void)
{
    unsigned p, t, s;
    pg_lk_count = 0;
    for (p = 0; p < PAGES; p++)
        for (t = 0; t < TRACKS; t++)
            for (s = 0; s < SLOTS; s++)
                pg_lk_active[p][t][s] = NONE;
    pg_lk_ready = 1;
}

static void lk_save(void)
{
    uint32_t head[4];
    if (pg_lk_nowrite || !pg_lk_dirty)
        return;
    if (pg_lk_backup) {
        pg_lk_backup = 0;
        lk_copy(BAK, WORK);
    }
    head[0] = PG_MAGIC;
    head[1] = PG_VERSION;
    head[2] = pg_lk_count;
    head[3] = pg_file_crc(pg_lk_pool, 4u * pg_lk_count);
    pg_file_path(WORK, pg_lk_path);
    if (pg_file_open(pg_lk_path, "w") < 0)
        return;
    if (pg_file_write(head, sizeof head) == 1 && (!pg_lk_count || pg_file_write(pg_lk_pool, 4u * pg_lk_count) == 1))
        pg_lk_dirty = 0;
    pg_file_close();
}

/* The file's entries: sorted, each key once, a page id 1..7 and a slot 0..5. */
static unsigned lk_valid(unsigned n)
{
    unsigned i;
    for (i = 0; i < n; i++) {
        uint32_t e = pg_lk_pool[i], page = (e >> 11) & 7u, slot = (e >> 8) & 7u;
        if (!page || slot > 5u || (i && (pg_lk_pool[i - 1] & KEYMASK) >= (e & KEYMASK)))
            return 0;
    }
    return 1;
}

static void lk_load(void)
{
    uint32_t head[4];
    unsigned good = 0;
    pg_lk_nowrite = 0;
    pg_lk_backup = 0;
    lk_clear();
    pg_file_path(WORK, pg_lk_path);
    if (pg_file_open(pg_lk_path, "r") >= 0) {
        good = pg_file_read(head, sizeof head) == 1 && head[0] == PG_MAGIC && head[1] == PG_VERSION
               && head[2] <= POOL && (!head[2] || pg_file_read(pg_lk_pool, 4u * head[2]) == 1)
               && pg_file_crc(pg_lk_pool, 4u * head[2]) == head[3] && lk_valid(head[2]);
        pg_file_close();
        if (good)
            pg_lk_count = head[2];
        else {
            pg_lk_count = 0;
            pg_lk_nowrite = 1;
            pg_file_refuse();
        }
    }
    pg_lk_dirty = 0;
}

void pg_st_loadall_pre(void)   { lk_clear(); }
void pg_st_loadall_post(void)  { lk_load(); }
void pg_st_loadmask_post(void) { lk_load(); }
void pg_st_newproj(void)
{
    lk_clear();
    pg_lk_nowrite = 0;
    pg_lk_backup = 0;
    pg_lk_dirty = 0;
}
void pg_st_bankw_post(void) { lk_save(); }
void pg_st_pstore_pre(void) { lk_save(); }
void pg_st_pstore_post(void)
{
    if (!pg_lk_nowrite)
        lk_copy(STRD, WORK);
}
void pg_st_preload_post(void)
{
    if (lk_copy(WORK, STRD) >= 0)
        lk_load();
}
/* A refused PGLOCKS.WORK: IGNORE (0) / OVERWRITE (1) / BACKUP (2); the
 * writes happen at the next save. */
void pg_lk_answer(unsigned answer)
{
    if (!answer)
        return;
    if (answer == 2)
        pg_lk_backup = 1;
    pg_lk_nowrite = 0;
    pg_lk_dirty = 1;
}

/* ---- the locks follow the steps: EVENTS edit.copy_pre and edit.steps ---- */

/* A stock address that starts a track -> its pool and that track's first key,
 * 0 none: the bank RAM (`locks` 0: the track's record; 1: its lock bytes at
 * +0x59), the clipboard and the undo buffer (track-shaped; their lock
 * snapshot at +0x28 is track 0's). */
static uint32_t *lk_where(uint32_t a, unsigned locks, uint32_t **n, unsigned *cap, uint32_t *base)
{
    uint32_t off;
    unsigned b, p, t;
    if (locks) {
        if (a == CLIP + 0x28u || a == UNDO + 0x28u)
            a -= 0x28u;
        else
            a -= LOCKS_AT;
    }
    if (a >= CLIP && a < CLIP + 8u * TRK_STRIDE && (a - CLIP) % TRK_STRIDE == 0) {
        *n = &pg_lk_clip_n; *cap = CLIP_POOL;
        *base = lk_key_of(0, 0, 0, (a - CLIP) / TRK_STRIDE, 0, 0, 0);
        return pg_lk_clip;
    }
    if (a >= UNDO && a < UNDO + 8u * TRK_STRIDE && (a - UNDO) % TRK_STRIDE == 0) {
        *n = &pg_lk_undo_n; *cap = CLIP_POOL;
        *base = lk_key_of(0, 0, 0, (a - UNDO) / TRK_STRIDE, 0, 0, 0);
        return pg_lk_undo;
    }
    if (a < BLOB || a >= BLOB + 16u * BANK_STRIDE)
        return 0;
    off = a - BLOB;
    b = off / BANK_STRIDE;
    off -= b * BANK_STRIDE;
    if (off >= 16u * PTN_STRIDE)
        return 0;
    p = off / PTN_STRIDE;
    off -= p * PTN_STRIDE;
    if (off % TRK_STRIDE || off / TRK_STRIDE >= 8u)
        return 0;
    t = off / TRK_STRIDE;
    *n = &pg_lk_count; *cap = POOL;
    *base = lk_key_of(0, b, p, t, 0, 0, 0);
    return pg_lk_pool;
}

/* memcpy(dst, src, len) at stock's pattern / track copy sites, before it: a
 * track (0x91a) or a pattern (0x8ed8) between the bank RAM, the clipboard and
 * the undo buffer, or a track's lock bytes (64 x 32, a trig paste's or
 * clear's undo snapshot), take their page locks along. */
void pg_lk_copy(uint32_t dst, uint32_t src, uint32_t len)
{
    uint32_t *se, *de, *sn, *dn, sbase, dbase, span = 1u << 20;
    unsigned scap, dcap, locks = len == 64u * 32u;
    if (!pg_lk_ready || (len != TRK_STRIDE && len != PTN_STRIDE && !locks))
        return;
    se = lk_where(src, locks, &sn, &scap, &sbase);
    de = lk_where(dst, locks, &dn, &dcap, &dbase);
    if (!se || !de)
        return;
    if (len == PTN_STRIDE) {                      /* a pattern: both at their track 0 */
        if (((sbase >> 20) & 7u) || ((dbase >> 20) & 7u))
            return;
        span = 8u << 20;
    }
    p_copy(se, *sn, sbase, de, dn, dcap, dbase, span);
}

static uint32_t *lk_clip(uint32_t clip, uint32_t **n)
{
    if (clip == CLIP) { *n = &pg_lk_clip_n; return pg_lk_clip; }
    if (clip == UNDO) { *n = &pg_lk_undo_n; return pg_lk_undo; }
    return 0;
}

/* edit.steps (EVENTS manifest.py): op and its arguments. */
void pg_lk_steps(unsigned op, uint32_t a, uint32_t b, uint32_t c, uint32_t d, uint32_t e)
{
    unsigned bank = lk_ui_bank(), i;
    uint32_t *ce, *cn;
    if (!pg_lk_ready)
        return;
    switch (op) {
    case 0:                                       /* a trig taken off: its locks go */
        if (a < 64u)
            p_del(pg_lk_pool, &pg_lk_count, lk_key_of(0, bank, U8(UI_PTN), U8(UI_TRACK), a, 0, 0), 1u << 14);
        break;
    case 1:                                       /* hold trigs + PLAY: the held steps' locks */
        for (i = 0; i < 16u; i++)
            if ((d & 0xffffu) >> i & 1u)
                p_del(pg_lk_pool, &pg_lk_count, lk_key_of(0, bank, a, b, (c & 3u) * 16u + i, 0, 0), 1u << 14);
        break;
    case 2:                                       /* clear a track: bit 0, its steps and locks */
        if (c & 1u)
            p_del(pg_lk_pool, &pg_lk_count, lk_key_of(0, bank, a, b, 0, 0, 0), 1u << 20);
        break;
    case 3:                                       /* trig copy: held step bit b -> record b */
        ce = lk_clip(a, &cn);
        if (!ce)
            break;
        for (i = 0; i < 16u; i++)
            if ((e & 0xffffu) >> i & 1u)
                p_copy(pg_lk_pool, pg_lk_count, lk_key_of(0, bank, b, c, (d & 3u) * 16u + i, 0, 0),
                       ce, cn, CLIP_POOL, lk_key_of(0, 0, 0, 0, i, 0, 0), 1u << 14);
        break;
    case 4:                                       /* trig paste: record d -> step e */
        ce = lk_clip(a, &cn);
        if (ce && d < 64u && e < 64u)
            p_copy(ce, *cn, lk_key_of(0, 0, 0, 0, d, 0, 0),
                   pg_lk_pool, &pg_lk_count, POOL, lk_key_of(0, bank, b, c, e, 0, 0), 1u << 14);
        break;
    }
}
