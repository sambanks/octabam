/* DRUMMER -- the firmware side: what the detours call. Every address is
 * measured in INVESTIGATION.md (phases 1-2, port).
 *
 *   dr_on_step(t)      sequencer tick, right after the step builder (0x400a2d82):
 *                      the engine decides the step; a hit is a trig the
 *                      builder did not make (0x46c7a810 = 29 ...) or the
 *                      track's own; the hit's slice and level wait in a
 *                      small ring for the voice start.
 *   dr_frame()         the packer, after it points 0x800062a8 at the frame's
 *                      page records (0x4000d3ae): on a DRUMMER track the
 *                      knobs (scenes and LFOs applied) are copied out and the
 *                      page record gets the playback values the stock voice
 *                      and renderer must see.
 *   dr_before_start(t, flags) / dr_after_start(t)   around the stock FLEX start
 *                      (0x4000f450 through the kind table 0x400d6458): the
 *                      slice through STRT (slice * 2, SLIC on): the queued
 *                      hit, or for a live start (flags bit 5: a trig key in
 *                      SLICES mode, in the AED too) the live STRT lock; then the
 *                      hit's VOL applied as stock applies a lock.
 *
 * Phase 4a: the DRUMMER tracks are dr_on[] (T1 in the test image), one
 * built-in kit; the machine row, its pages, the KIT window and drummer.work
 * come in 4b-4d. State lives in hooks.s (explicitly zeroed DRAM, no .bss). */
#include "drummer.h"

#ifdef DR_HOST
volatile uint8_t *dr_host_addr(uint32_t address);
#define ADDR(a) dr_host_addr((uint32_t)(a))
#else
#define ADDR(a) ((volatile uint8_t *)(uintptr_t)(a))
#endif
#define U8(a)  (*(volatile uint8_t *)ADDR(a))
#define U16(a) (*(volatile uint16_t *)ADDR(a))
#define U32(a) (*(volatile uint32_t *)ADDR(a))

enum {
    STEPCTR  = 0x800064d0u,  /* audio step counters, a byte per track */
    SEQ_TRANSPORT = 0x800065b8u, /* 0 stopped, 1 playing (TRACK PATTERNS, EUCLID) */
    TEMPO24  = 0x80001814u,  /* long: BPM x 24 (RECORDER.md) */
    RESTART  = 0x8000668du,  /* bit t: the track's first step since the transport start */
    KIND     = 0x46c7a810u,  /* + 4t: 29 a sample trig, 1 a trigless one (the builder's) */
    MTIME    = 0x46c7a830u,  /* + 4t: micro-timing, unit 110250 * scale */
    COUNT    = 0x46c7a14cu,  /* + 4t */
    LENGTH   = 0x46c77bfau,  /* + 4t: 2646000 * scale for a count of 1 */
    FP_PTR   = 0x800062a8u,  /* the packer's page record pointer: track t's while t is packed */
    LANE     = 0x80000810u,  /* + 72t: live values (locks), byte 31 the slot */
    DSPREC   = 0x80000a50u,  /* + 64t + 2k: the DSP halfword of lock slot k */
    RESTORE  = 0x80001538u,  /* + 4t: bit k = the lane's k goes back to the Part at the next trig */
    FLEX_SET = 0x100b14f0u,  /* + 0x448 * slot: the FLEX slot's settings, slice count at +1092 */
    STAGE    = 0x46c7aa24u,  /* + 32t: the step's staged locks (0xff none), n = -1 */
    PENDING  = 0x46c7ab30u,  /* + 32 (n * 8 + t): pending lock slot n */
};
#define LIVE_START 0x20u        /* start flags: 0xe0 a live start (0x40005030), 0xc0 the sequencer's (port) */
#define TRACKS 8
__attribute__((section(".data"))) uint8_t dr_live_strt[TRACKS];   /* a live start's STRT lock holds the lane */
#define RING 4
#define VOL_SLOT 15
#define SCALE_UNIT 2646000u     /* LENGTH / scale, count 1 */
#define MT_UNIT 110250u         /* MTIME / (scale * micro-timing step) */

typedef struct { uint8_t slice, vel, rtrg, rtim; uint32_t pos; } DrPend;   /* rtim: stock's RTIM value */

extern uint8_t  dr_on[TRACKS];
extern DrKit    dr_kit[TRACKS];
extern DrState  dr_state[TRACKS];
extern uint8_t  dr_knob[TRACKS][12];     /* PLAYBACK 1-6, then page 2 1-6 */
extern uint8_t  dr_knob_ok[TRACKS];      /* the frame copied this track's knobs */
extern uint32_t dr_pos[TRACKS], dr_pass[TRACKS], dr_scale[TRACKS];
extern uint8_t  dr_last_idx[TRACKS], dr_len[TRACKS], dr_strt[TRACKS], dr_kit_ready[TRACKS];
extern DrPend   dr_ring[TRACKS][RING];
extern DrHit    dr_last_hit[TRACKS];
extern uint8_t  dr_restarted[TRACKS];
extern uint8_t  dr_cur_style[TRACKS];   /* the style the engine played last (the KIT band shows it) */
extern uint8_t  dr_rtrg_now[TRACKS], dr_rtim_now[TRACKS];   /* the current hit's retrigs (page record) */
extern uint32_t dr_dbg[8];               /* image 46: tick calls, frames seeing a DRUMMER track, -, last kind, last transport, last idx, dr_on mask, - */                 /* image 45's test mode (kit.c): 0 all, 1 no engine, 2 no start wrapper, 3 no frame rewrite, 4 none */
extern uint8_t  dr_preview[TRACKS], dr_align[TRACKS][DR_SLICES], dr_shift[TRACKS], dr_phrase[TRACKS];
extern int8_t   dr_gain[TRACKS][DR_SLICES];   /* the KIT's GAIN, dB (kit.c) */
extern uint8_t  dr_redrum[TRACKS];       /* REDRUM (image 77, the KIT window's F): 0 off, 1 AUTO, 2..5 1 2 4 8 bars (kit.c) */
extern DrLoop   dr_loop[TRACKS];         /* REDRUM: the track's loop, rebuilt at every step (hooks.s) */
extern DrLoopBar dr_loop_bar;            /* REDRUM: the engine's scratch, one step at a time (hooks.s) */
extern uint8_t  dr_scene[TRACKS][DR_SLICES];  /* the KIT's SCENE: 0 none, else scene 1..16 (kit.c) */
extern uint8_t  dr_dose[TRACKS][DR_SLICES];   /* its DOSE, % (0 = 100) */
void dr_kit_tick(void);
extern uint8_t  dr_head[TRACKS], dr_count[TRACKS], dr_vel_now[TRACKS], dr_vol_base[TRACKS], dr_vol_mine[TRACKS];
extern uint32_t dr_stats[8];             /* builds, hits, injected, forced, starts, ring misses, frames, rebuilds */

/* ---- the machine: signature, pages, validator (machine.s calls these) ---- */

enum {
    BANK_PTR = 0x46c82456u, PART_IDX = 0x100b14cfu, PART_OFF = 0x8ed80u, PART_STRIDE = 0x18b2u,
    SIG = 60u,                    /* NEIGHBOR's PLAYBACK column: Part + 0x2a + 18 + 30t */
    MIX_AT = 0x2au,               /* KIT BALANCE: STATIC's PLAYBACK column, Part + 0x2a + 30t (unused on FLEX) */
    MIX_MARK = 63u,               /* NEIGHBOR's 4th byte, after "DR",1: MIX_MAGIC once KIT BALANCE is seeded */
    MIX_MAGIC = 'M',
    FILLS_AT = 0x1ecu,            /* FILLS (image 74): NEIGHBOR's SETUP column, Part + 0x1da + 18 + 30t (unused on FLEX) */
    FILLS_MARK = 64u,             /* NEIGHBOR's PLAYBACK 5th byte, after 'M': FILLS_MAGIC once FILLS is seeded */
    FILLS_MAGIC = 'F',
    DESC_SRC = 0x400d3176u,       /* the FLEX PLAYBACK descriptor's block (ANALOG BD's donor) */
    DESC_SIZE = 0x1cau,
    PB_TABLE = 0x400d5f38u, CUR_TRACK = 0x100b14ccu, FLEX_DEFAULTS = 0x400d320cu,
};
extern uint8_t  dr_desc[DESC_SIZE];
extern uint32_t dr_desc_ok;
extern const uint8_t dr_defaults[12];

static unsigned bank_ok(void)
{
    uint32_t b = U32(BANK_PTR);
    return b >= 0x40000000u && b < 0x48000000u;
}

static const volatile uint8_t *part_base(void)
{
    return (const volatile uint8_t *)ADDR(U32(BANK_PTR) + PART_OFF + (U8(PART_IDX) & 3u) * PART_STRIDE);
}

static unsigned signed_track(const volatile uint8_t *part, unsigned t)
{
    const volatile uint8_t *sig = part + SIG + 30u * t;
    return t < TRACKS && part[0x22 + t] == 1 && sig[0] == 'D' && sig[1] == 'R' && sig[2] == 1;
}

/* A stored machine type and its byte in the Part: row 5 for a DRUMMER track. */
unsigned dr_type(unsigned type, const volatile uint8_t *ptr)
{
    const volatile uint8_t *part;
    uintptr_t t;
    if (!bank_ok())
        return type;
    part = part_base();
    t = (uintptr_t)ptr - (uintptr_t)(part + 0x22);
    return type == 1 && t < TRACKS && signed_track(part, (unsigned)t) ? 5 : type;
}

static void put32(uint8_t *p, uint32_t v)
{
    p[0] = (uint8_t)(v >> 24); p[1] = (uint8_t)(v >> 16); p[2] = (uint8_t)(v >> 8); p[3] = (uint8_t)v;
}

static void text(uint8_t *p, const char *s, unsigned n)
{
    unsigned i = 0;
    for (; i + 1 < n && s[i]; ++i)
        p[i] = (uint8_t)s[i];
    for (; i < n; ++i)
        p[i] = 0;
}

enum { DR_K_STYL = 6 };                     /* STYL's knob: SETUP's A (image 61; LIVE's A before) */

/* STYL has 128 positions (a 24-value knob took a dozen detents a step in
 * stock's editor, measured: the style did not change), each style a run of them. */
static unsigned style_of_knob(unsigned v)
{
    unsigned s = v * DR_STYLES / 128u;
    return s < DR_STYLES ? s : DR_STYLES - 1u;
}

void dr_style_fmt(char *out, int value)
{
    text((uint8_t *)out, dr_style_name(style_of_knob(value < 0 ? 0u : (unsigned)value)), 5);
}

/* SEED shown as band:variant ("4:07"), TBL for 0 (the style's table). */
void dr_seed_fmt(char *out, int value)
{
    char b[5];
    unsigned v = value < 0 ? 0u : value > 127 ? 127u : (unsigned)value, var = dr_seed_variant(v);
    if (!var) {
        text((uint8_t *)out, "TBL", 5);
        return;
    }
    b[0] = (char)('1' + (v - 1u) / 16u);
    b[1] = ':';
    b[2] = (char)('0' + var / 10u);
    b[3] = (char)('0' + var % 10u);
    b[4] = 0;
    text((uint8_t *)out, b, 5);
}

/* CPLX shown as the engine reads it (level_cell): BAS, STD, CPX on the written
 * levels (0, 64, 127); in between the level below and how far the next one's
 * cells have come in, in percent ("B>50" half-way from BASIC to STANDARD). */
void dr_cplx_fmt(char *out, int value)
{
    static const char *const lv[3] = { "BAS", "STD", "CPX" };
    char b[5];
    unsigned v = value < 0 ? 0u : value > 127 ? 127u : (unsigned)value;
    unsigned pos = v * 256u / 127u, a = pos >> 7, f = (pos & 127u) * 100u / 128u;
    if (a >= 2 || !f) {
        text((uint8_t *)out, lv[a > 2 ? 2 : a], 5);
        return;
    }
    b[0] = a ? 'S' : 'B';
    b[1] = '>';
    b[2] = (char)('0' + f / 10u);
    b[3] = (char)('0' + f % 10u);
    b[4] = 0;
    text((uint8_t *)out, b, 5);
}

/* DRUMMER's page: FLEX's descriptor with its 12 knobs renamed. Page 1 (SRC)
 * is the live page, page 2 (FUNC + SRC, SETUP) the configuration. */
uint32_t dr_page(void)
{
    /* image 61: SEED <-> STYL and ORN <-> HUMN (the user's: the style is set
     * once, the seed and the ornaments are played) */
    static const char *const names[12] = { "SEED", "DENS", "CPLX", "ORN", "BRK", "GHST",
                                           "STYL", "VEL", "ALT", "SWNG", "HUMN", "VAR" };
    if (!dr_desc_ok) {
        const volatile uint8_t *src = (const volatile uint8_t *)ADDR(DESC_SRC);
        unsigned i;
        uint8_t *d = dr_desc;
        for (i = 0; i < DESC_SIZE; ++i)
            d[i] = src[i];
        /* the page's names as FLEX's at run time (SRC over PLAYBACK, measured
         * in RAM): the bar reads SRC > DRUMMER, an LFO destination SRC:SEED
         * (image 62 had DRUMMER > DRUMMER, the user's report) */
        text(d + 0x3c, "SRC", 5);
        text(d + 0x41, "SRC", 13);
        for (i = 0; i < 12; ++i) {
            text(d + 0x4e + 6 * i, names[i], 6);
            d[0x96 + i] = dr_defaults[i];
            put32(d + 0xa2 + 4 * i, 0);
            put32(d + 0xd2 + 4 * i, 128);
            put32(d + 0x102 + 4 * i, i == DR_K_STYL ? (uint32_t)(uintptr_t)dr_style_fmt
                                     : i == 0 ? (uint32_t)(uintptr_t)dr_seed_fmt
                                     : i == 2 ? (uint32_t)(uintptr_t)dr_cplx_fmt : 0);
            put32(d + 0x132 + 4 * i, 0);
            put32(d + 0x162 + 4 * i, 0);
        }
        /* draw nibbles (PARAM_PAGES.md: P+0x18a p8..p11, P+0x18e p0..p7, one per
         * knob, low nibble first): all twelve drawn, none linked */
        put32(d + 0x1c2, 0x1111u);
        put32(d + 0x1c6, 0x11111111u);
        dr_desc_ok = 1;
    }
    return (uint32_t)(uintptr_t)(dr_desc + 0x38);
}

uint32_t dr_track_page(const volatile uint8_t *type_ptr)
{
    (void)type_ptr;
    return dr_page();
}

/* The SRC SETUP and LFO names read PB_TABLE[row]: row 5 is DRUMMER's page. */
extern uint8_t dr_ml_pick;
__attribute__((section(".data"))) uint32_t dr_pb_flex;                       /* PB_TABLE[1] (FLEX's page) while a pick has it */
/* FLEX's slot list opened from DRUMMER's row (machine.s dr_setup_key) sets
 * the cursor to FLEX: the SETUP knobs beside the list stay DRUMMER's (PB_TABLE[1]
 * is DRUMMER's page until the pick ends). Called at the pick's RIGHT and each UI tick. */
void dr_pick_page(void)
{
    uint32_t page = dr_page();
    if (dr_ml_pick) {
        if (U32(PB_TABLE + 4u) != page) {
            dr_pb_flex = U32(PB_TABLE + 4u);
            U32(PB_TABLE + 4u) = page;
        }
    } else if (dr_pb_flex) {
        U32(PB_TABLE + 4u) = dr_pb_flex;
        dr_pb_flex = 0;
    }
}

void dr_ui_tick(void)
{
    U32(PB_TABLE + 5u * 4u) = dr_page();
    dr_pick_page();
    dr_kit_tick();
}

/* The stock validator sees FLEX's defaults on a DRUMMER track's 12 knob
 * bytes (its ranges would clamp DRUMMER's values: RTRG holds BRK), then
 * they are put back. ANALOG BD's form. */
extern int dr_stock_validate(void *part);
int dr_validate_part(uint8_t *part)
{
    uint8_t saved[TRACKS][12], mixs[TRACKS][7];
    unsigned mask = 0, t, k;
    const volatile uint8_t *stock = (const volatile uint8_t *)ADDR(FLEX_DEFAULTS);
    int result;
    for (t = 0; t < TRACKS; ++t)
        if (signed_track(part, t)) {
            mask |= 1u << t;
            for (k = 0; k < 12; ++k) {
                unsigned at = (k < 6 ? 0x2au : 0x1dau) + 30u * t + 6u + k % 6u;
                saved[t][k] = part[at];
                part[at] = stock[k];
            }
            for (k = 0; k < 6; ++k) {            /* KIT BALANCE in STATIC's bytes: stock's FLEX defaults meanwhile */
                mixs[t][k] = part[MIX_AT + 30u * t + k];
                part[MIX_AT + 30u * t + k] = stock[k];
            }
            mixs[t][6] = part[MIX_MARK + 30u * t];
        }
    result = dr_stock_validate(part);
    for (t = 0; t < TRACKS; ++t)
        if (mask & (1u << t))
        {
            for (k = 0; k < 12; ++k) {
                unsigned at = (k < 6 ? 0x2au : 0x1dau) + 30u * t + 6u + k % 6u;
                part[at] = saved[t][k];
            }
            for (k = 0; k < 6; ++k)
                part[MIX_AT + 30u * t + k] = mixs[t][k];
            part[MIX_MARK + 30u * t] = mixs[t][6];
        }
    return result;
}

/* ---- NEXT (SRC after KIT BALANCE, kit.c): the orders ----------------------
 *
 * A WHEN is the trigger: armed, the order fires on the next beat, bar,
 * phrase or two phrases, then WHEN is back to none (RAM: an order is a live
 * gesture). B-F stay set, in the Part (THRU's SETUP column of the track,
 * unused on FLEX, marked 'N' after FILLS' 'F'): the musician turns WHEN alone
 * for the next one.
 *   B RUN   STOP (the grid's trigs still play) or SILENT (they do not); while
 *           stopped, either resumes. The engine runs on unheard, so a resume
 *           lands in the groove.
 *   C HOW   how B stops or resumes: DRY, CRASH (on the 1), FILL (ending on
 *           the 1), FILL+CR, PICKUP (a half-beat lead-in, then the crash on
 *           a resume)
 *   D FILL  the order's fill (it plays one even without B): TRIP, 6LET,
 *           RUDI, 3:4 the family, LONG a whole bar
 *   E STYL  the style from the 1 on, until the STYL knob is turned
 *   F BRK   a break from the 1: a beat, two, a bar of BRK cuts, or a bar of
 *           stutter
 * A fill needs the order on a bar's 1 (BEAT mid-bar: no fill). */
enum { NX_WHEN, NX_RUN, NX_HOW, NX_FILL, NX_STYL, NX_BRK, NX_N };
enum { NXW_NONE, NXW_BEAT, NXW_BAR, NXW_PHRS, NXW_2PHR, NXW_MAX = NXW_2PHR };
enum { HOW_DRY, HOW_CRASH, HOW_FILL, HOW_FILLCR, HOW_PICKUP, HOW_MAX = HOW_PICKUP };
enum { NXF_NONE, NXF_TRIP, NXF_6LET, NXF_RUDI, NXF_34, NXF_LONG, NXF_MAX = NXF_LONG };
enum { NXB_NONE, NXB_BEAT, NXB_2BEAT, NXB_BAR, NXB_STUT, NXB_MAX = NXB_STUT };
enum { NX_AT = 0x1e6u,             /* B-F: THRU's SETUP column, Part + 0x1da + 12 + 30t (no THRU setup knob; FILLS is NEIGHBOR's, + 18) */
       NX_MARK = 65u, NX_MAGIC = 'N',   /* NEIGHBOR's PLAYBACK 6th byte, after 'F' */
       BRK_CUTS = 76u, BRK_STUTTER = 112u };
__attribute__((section(".data"))) uint8_t  dr_nx_when[TRACKS];   /* A, armed (RAM) */
__attribute__((section(".data"))) uint32_t dr_nx_at[TRACKS];     /* dr_pos of the step it fires on */
__attribute__((section(".data"))) uint8_t  dr_stopped[TRACKS];   /* 0 playing, else B's value that stopped it */
__attribute__((section(".data"))) uint8_t  dr_nx_flash[TRACKS];  /* UI ticks the page shows "done" */
__attribute__((section(".data"))) uint32_t dr_vbar[TRACKS];      /* the step decided last: its bar, */
__attribute__((section(".data"))) uint8_t  dr_vstep[TRACKS], dr_vlen[TRACKS];   /* step in it, bar length */
__attribute__((section(".data"))) uint8_t  dr_nx_fz[TRACKS];     /* this bar ends in the order's fill (heard while stopped) */
__attribute__((section(".data"))) uint8_t  dr_nx_let[TRACKS];    /* the order's 1 plays though it stops (its crash) */
__attribute__((section(".data"))) uint8_t  dr_nx_land[TRACKS];   /* on the order's 1: 0 the engine's landing, 1 a crash, 2 none */
__attribute__((section(".data"))) uint8_t  dr_sty_ovr[TRACKS];   /* E's style + 1 in force, 0 none */
__attribute__((section(".data"))) uint8_t  dr_sty_knob[TRACKS];  /* the STYL knob when it came (0xff: read at the next step) */
__attribute__((section(".data"))) uint8_t  dr_brk_left[TRACKS], dr_brk_val[TRACKS];   /* F: steps to go, its BRK */

/* B-F's value (0 for an unmarked Part); WHEN's from RAM. */
unsigned dr_nx_get(unsigned t, unsigned i)
{
    const volatile uint8_t *part;
    if (i == NX_WHEN)
        return dr_nx_when[t];
    if (i >= NX_N || !bank_ok())
        return 0;
    part = part_base();
    return part[NX_MARK + 30u * t] == NX_MAGIC ? part[NX_AT + 30u * t + i - 1u] & 0x3fu : 0;
}

/* Steps from the step decided last to WHEN's next boundary (beat, bar, phrase, two). */
static unsigned nx_steps(unsigned t, unsigned when)
{
    unsigned len = dr_vlen[t] ? dr_vlen[t] : DR_STEPS, s = dr_vstep[t], ph = dr_phrase[t] == 8 ? 8u : 4u;
    unsigned bs = len == 12 ? 3u : 4u;
    if (when == NXW_BEAT)
        return bs - s % bs;
    if (when == NXW_BAR)
        return len - s;
    if (when == NXW_2PHR)
        ph *= 2;
    return (ph - 1u - dr_vbar[t] % ph) * len + (len - s);
}

/* A WHEN turned: the order's step, from now (the first step when the transport is stopped). */
void dr_nx_arm(unsigned t, unsigned when)
{
    dr_nx_when[t] = (uint8_t)(when > NXW_MAX ? NXW_MAX : when);
    if (when)
        dr_nx_at[t] = U32(SEQ_TRANSPORT) == 1 && dr_pos[t] ? dr_pos[t] + nx_steps(t, when) : 1u;
}

/* The step being decided (dr_pos) is the order's 1: B, E and F take effect,
 * WHEN back to none. Before params_of, so the style and the break play on it. */
static void nx_fire(unsigned t)
{
    unsigned run, how, brk, len = dr_vlen[t] ? dr_vlen[t] : DR_STEPS, beat = len == 12 ? 3u : 4u;
    dr_nx_let[t] = 0;
    dr_nx_land[t] = 0;
    if (!dr_nx_when[t] || dr_pos[t] < dr_nx_at[t])
        return;
    run = dr_nx_get(t, NX_RUN);
    how = dr_nx_get(t, NX_HOW);
    if (run) {
        unsigned crash = how == HOW_CRASH || how == HOW_FILLCR || (how == HOW_PICKUP && dr_stopped[t]);
        dr_nx_land[t] = (uint8_t)(crash ? 1 : 2);
        if (dr_stopped[t]) {
            dr_stopped[t] = 0;
        } else {
            dr_stopped[t] = (uint8_t)(run > 2 ? 2 : run);
            dr_nx_let[t] = (uint8_t)crash;
        }
    }
    if (dr_nx_get(t, NX_STYL)) {
        dr_sty_ovr[t] = (uint8_t)dr_nx_get(t, NX_STYL);
        dr_sty_knob[t] = 0xff;
    }
    brk = dr_nx_get(t, NX_BRK);
    if (brk) {
        dr_brk_left[t] = (uint8_t)(brk == NXB_BEAT ? beat : brk == NXB_2BEAT ? 2u * beat : len);
        dr_brk_val[t] = (uint8_t)(brk == NXB_STUT ? BRK_STUTTER : BRK_CUTS);
    }
    dr_nx_when[t] = NXW_NONE;
    dr_nx_flash[t] = 40;
}

/* The order's knobs over the step's: E's style (until STYL turns), F's break,
 * and the fill on the bar before the order's 1. */
static void nx_params(unsigned t, DrParams *p, unsigned knob_styl)
{
    if (dr_sty_ovr[t]) {
        if (dr_sty_knob[t] == 0xff)
            dr_sty_knob[t] = (uint8_t)knob_styl;
        if (knob_styl != dr_sty_knob[t])
            dr_sty_ovr[t] = 0;                   /* the knob turned: the knob's style */
        else if (dr_sty_ovr[t] <= DR_STYLES)
            p->style = (uint8_t)(dr_sty_ovr[t] - 1u);
    }
    if (dr_brk_left[t])
        p->brk = dr_brk_val[t];
}

static void nx_fill(unsigned t, DrParams *p, unsigned step, unsigned len)
{
    unsigned run = dr_nx_get(t, NX_RUN), how = dr_nx_get(t, NX_HOW), f = dr_nx_get(t, NX_FILL), z;
    unsigned k = dr_nx_when[t] && dr_nx_at[t] > dr_pos[t] ? dr_nx_at[t] - dr_pos[t] : 0;
    dr_nx_fz[t] = 0;
    if (!k || k + step != len || !(f || (run && how >= HOW_FILL)))
        return;                                  /* not the bar before the order's 1, or no fill */
    if (f == NXF_LONG)
        z = 3;
    else if (run && how == HOW_PICKUP && !f)
        z = 0;                                   /* half a beat */
    else if (p->fill[DR_F_LONG] && p->fill[DR_F_LONG] <= DR_LONG_MAX)
        z = p->fill[DR_F_LONG];                  /* FILLS' LONG: 1BT 2BT BAR */
    else
        z = 1;                                   /* a beat */
    p->brk = (uint8_t)(32u + 8u * z + 4u);       /* BRK's fill zone of that length, this bar */
    p->fill[DR_F_FREQ] = 1;                      /* BRK's fill alone (no VAR one besides) */
    p->fill[DR_F_LONG] = 0;
    if (f == NXF_TRIP || f == NXF_6LET)
        p->fill[DR_F_FILL] = 3;
    if (f == NXF_6LET)
        p->fill[DR_F_TRIP] = 2;
    if (f == NXF_RUDI)
        p->fill[DR_F_FILL] = 2;
    if (f == NXF_34)
        p->fill[DR_F_FILL] = 4;
    dr_nx_fz[t] = 1;
}

static void reset_track(unsigned t)
{
    unsigned i;
    uint8_t *p = (uint8_t *)&dr_state[t];
    for (i = 0; i < sizeof(DrState); i++)
        p[i] = 0;
    dr_pass[t] = 0;
    dr_pos[t] = 0;
    dr_last_idx[t] = 0;
    dr_len[t] = 0;
    dr_head[t] = 0;
    dr_count[t] = 0;
    dr_brk_left[t] = 0;
    if (dr_nx_when[t])                           /* an order armed: on the first step played */
        dr_nx_at[t] = 1;
}

static unsigned slice_count(unsigned t)
{
    unsigned slot = U8(LANE + 72u * t + 31u), n;
    if (slot >= 136)
        return 0;
    n = U32(FLEX_SET + 0x448u * slot + 1092u);
    return n > DR_SLICES ? DR_SLICES : n;
}

/* RTIM for a retrig interval of u/24 step (u 1..24). Measured under the port
 * (FLEX, RTRG 3, 120 BPM): RTIM 47 / 63 / 79 / 95 repeat every 434 / 1094 /
 * 2756 / 6946 samples, half a step at 79 and twice as long every 12:
 * RTIM = 79 + 12 log2(u / 12). */
static const uint8_t RTIM_OF[25] = { 79, 36, 48, 55, 60, 64, 67, 70, 72, 74, 76, 77, 79,
                                     80, 81, 82, 83, 84, 85, 86, 88, 89, 89, 90, 91 };
static unsigned rtim_of(unsigned u)
{
    return RTIM_OF[u <= 24 ? u : 24];
}

/* dr_kit_ready: 0 nothing yet, 1 a kit (AUTO, the KIT window or
 * drummer.work), 2 empty and AUTO not offered yet (kit.c asks on the page). */
static void ensure_kit(unsigned t)
{
    if (dr_kit_ready[t])
        return;
    dr_kit_init(&dr_kit[t], 0);                  /* every slice OUT: only the track's trigs play */
    dr_kit_ready[t] = 2;
}

/* REDRUM: the loop from the slot the lane plays -- its slices' starts and ALIGN,
 * the trim (FLEX settings + 300 / + 304), TRIM_BARS x 100 (+ 284) and the
 * tempo (BPM x 24, + 276; SAMPLE_SAVE.md 8.1-8.2) -- rebuilt at every step,
 * so a slice, trim or ALIGN edit is heard at once; 0 off or no loop. */
static unsigned loop_bars100(unsigned t, uint32_t set)
{
    unsigned r = dr_redrum[t];                   /* 1 AUTO: the slot's TRIM_BARS; 2..5 1 2 4 8 bars (image 78) */
    return r >= 2 && r <= 5 ? 100u << (r - 2u) : U32(set + 284u);
}

static const DrLoop *loop_of(unsigned t)
{
    unsigned slot = U8(LANE + 72u * t + 31u), n;
    uint32_t set;
    if (!dr_redrum[t] || slot >= 128)
        return 0;
    set = FLEX_SET + 0x448u * slot;
    n = U32(set + 1092u);
    if (!n)
        return 0;
    dr_loop_build(&dr_loop[t], (const uint32_t *)ADDR(set + 312u), n > DR_SLICES ? DR_SLICES : n,
                  U32(set + 300u), U32(set + 304u), loop_bars100(t, set), U32(set + 276u), dr_align[t]);
    return dr_loop[t].len ? &dr_loop[t] : 0;
}

/* The KIT window's F: the loop's steps as REDRUM lays it (0 none) and the slot's slices in *slices. */
unsigned dr_loop_view(unsigned t, unsigned *slices)
{
    unsigned slot = U8(LANE + 72u * t + 31u), n;
    uint32_t set;
    *slices = 0;
    if (slot >= 128)
        return 0;
    set = FLEX_SET + 0x448u * slot;
    n = U32(set + 1092u);
    if (n > DR_SLICES)
        n = DR_SLICES;
    *slices = n;
    return n ? dr_loop_steps((const uint32_t *)ADDR(set + 312u), n, U32(set + 300u), U32(set + 304u),
                             loop_bars100(t, set), U32(set + 276u)) : 0;
}

/* PAGES' locks (hooks.s: PAGES' functions when the remix has them, else the
 * Part's values as they are): KIT BALANCE takes step and scene locks. */
void dr_pl_step(unsigned page, unsigned track, unsigned bank, unsigned pattern, unsigned step, unsigned trig);
unsigned dr_pl_value(unsigned page, unsigned track, unsigned slot, unsigned base);

static void params_of(unsigned t, DrParams *p)
{
    const uint8_t *k = dr_knob[t];
    uint8_t lane[12];
    if (!dr_knob_ok[t]) {                    /* no frame packed yet: the lane (no scene, no LFO) */
        unsigned i;
        for (i = 0; i < 6; i++) {
            lane[i] = U8(LANE + 72u * t + i);
            lane[6 + i] = U8(LANE + 72u * t + 0x20u + i);
        }
        k = lane;
    }
    /* LIVE (page 1): SEED DENS CPLX ORN BRK GHST; CONFIG (SETUP): STYL VEL ALT SWNG HUMN VAR */
    p->style = (uint8_t)style_of_knob(k[DR_K_STYL]);
    p->seed = k[0]; p->dens = k[1]; p->cplx = k[2]; p->orn = k[3]; p->brk = k[4]; p->ghost = k[5];
    nx_params(t, p, k[DR_K_STYL]);
    p->vel = k[7]; p->round = k[8]; p->time = k[9]; p->human = k[10]; p->var = k[11];
    p->shift = dr_shift[t]; p->phrase = dr_phrase[t] == 8 ? 8 : 4; p->reserved[0] = p->reserved[1] = 0;
    p->loop = loop_of(t);
    p->bar = &dr_loop_bar;
    {   /* KIT BALANCE (FUNC held on LIVE): the zones' mix in the Part's STATIC PLAYBACK
         * bytes, once marked (kit.c seeds them at 64); 64 before */
        const volatile uint8_t *part = bank_ok() ? part_base() : 0;
        unsigned i, marked = part && part[MIX_MARK + 30u * t] == MIX_MAGIC;
        for (i = 0; i < DR_MIXES; i++)          /* a step lock, then the scenes (PAGES' locks) */
            p->mix[i] = (uint8_t)(dr_pl_value(DR_LK_PAGE, t, i, marked ? part[MIX_AT + 30u * t + i] & 0x7fu : 64u) & 0x7fu);
        marked = part && part[FILLS_MARK + 30u * t] == FILLS_MAGIC;   /* FILLS: AUTO each before */
        for (i = 0; i < DR_FILLS; i++)
            p->fill[i] = marked ? (uint8_t)(part[FILLS_AT + 30u * t + i] & 0x0f) : 0;
    }
}

/* The slice's SCENE on its hit: the scene's cells of this track (Part +
 * 0x662 + (scene * 8 + track) * 32, byte k = parameter k, 0xff none; PARAM_PAGES.md
 * 5g) go into the trig's lock block as locks, DOSE of the way from the Part's
 * value, so they play on this hit and stock puts the Part's values back at the
 * next trig (STEP_LOCKS.md section 3). Pages LFO, AMP, FX1 and FX2 (6..29):
 * PLAYBACK is DRUMMER's own knobs, 30-31 carry no knob. A lock the trig has
 * of its own wins. */
static void scene_locks(unsigned t, unsigned slice, uint32_t blk)
{
    const volatile uint8_t *part, *cell;
    unsigned scene = dr_scene[t][slice], k;
    int dose = dr_dose[t][slice] ? dr_dose[t][slice] : 100;
    if (!scene || scene > 16 || !bank_ok())
        return;
    part = part_base();
    cell = part + 0x662u + ((scene - 1u) * 8u + t) * 32u;
    for (k = 6; k < 30; k++) {
        int v = cell[k], base;
        if (v == 0xff || U8(blk + k) != 0xff)
            continue;
        base = part[0x11au + 24u * t + (k - 6u)];
        v = base + (v - base) * dose / 100;
        U8(blk + k) = (uint8_t)(v < 0 ? 0 : v > 127 ? 127 : v);
    }
}

/* Both builder calls end here: the sequencer tick's (0x400a2d7e, idx = the
 * track's counter, lock_slot = its n) and the rebuild's (0x4009dc9e, at the
 * transport start and after an edit: idx = the step it builds, lock_slot
 * -1). A second call for the step already decided replays that decision
 * (the engine moves once per step); the transport start resets once. */
static void on_build(unsigned t, unsigned idx, int lock_slot, unsigned bank, unsigned ptn, unsigned step)
{
    unsigned bar, forced, kind, n, restart, dup;
    DrParams p;
    DrHit h;
    DrPend *e;

    if (t >= TRACKS)
        return;
    dr_on[t] = (uint8_t)(bank_ok() && signed_track(part_base(), t));   /* not only at frames: the
                                                                        * start's rebuilds come first */
    if (!dr_on[t])
        return;
    dr_stats[0]++;
    ensure_kit(t);
    /* Stopped: the rebuilds (the load, edits, and the two that build the
     * first step right before the transport starts, measured) each decide
     * their step from a fresh state, so the first step played is bar 0's
     * from the reset. The performance then goes on from that state. A
     * transport started without a rebuild before it resets at its first
     * build. */
    restart = (U8(RESTART) >> t) & 1u;
    if (U32(SEQ_TRANSPORT) != 1) {
        reset_track(t);
        dr_restarted[t] = 1;
    } else if (!dr_restarted[t] || restart) {
        reset_track(t);
        dr_restarted[t] = 1;
    }
    dup = dr_pos[t] && idx == dr_last_idx[t];
    if (!dup && idx < dr_last_idx[t])
        dr_pass[t]++;
    if (!dup) {
        dr_last_idx[t] = (uint8_t)idx;
        if (idx + 1 > dr_len[t])
            dr_len[t] = (uint8_t)(idx + 1);
        dr_pos[t]++;
    }

    kind = U32(KIND + 4u * t);
    forced = kind == 29;
    /* the builder's step: its page locks, and its trig (a call again for the
     * same step, a dup, is no trig: KIND is then the hit DRUMMER added) */
    dr_pl_step(DR_LK_PAGE, t, bank, ptn, step, !dup && (kind == 29 || kind == 1));
    dr_dbg[3] = kind;
    dr_dbg[4] = U32(SEQ_TRANSPORT);
    dr_dbg[5] = idx;
    if (forced && U32(COUNT + 4u * t) == 1) {
        unsigned s = U32(LENGTH + 4u * t) / SCALE_UNIT;
        if (s)
            dr_scale[t] = s;
    }
    if (!dr_scale[t])
        dr_scale[t] = 6;                         /* 1X until a trig shows the track's scale */
    n = slice_count(t);
    dr_kit[t].count = (uint8_t)n;
    if (dup) {
        h = dr_last_hit[t];
    } else {
        /* the style's bar (16 steps, 12 for 12/8) laid on the track's own
         * steps: every pass of the pattern starts a bar on its step 1, a
         * pattern that is not a whole number of bars ends on a short one
         * (counted from the transport start, the bars drifted from the
         * pattern's: reported on the unit) */
        unsigned len, plen = dr_len[t] ? dr_len[t] : 16u;
        nx_fire(t);                              /* NEXT's order, on its 1 */
        params_of(t, &p);
        len = p.loop ? DR_STEPS : dr_style_len(p.style);   /* REDRUM: 4/4 bars */
        bar = dr_pass[t] * ((plen + len - 1u) / len) + idx / len;
        nx_fill(t, &p, idx % len, len);
        if (dr_nx_land[t] == 1 && dr_state[t].fill_len < 4)
            dr_state[t].fill_len = 4;            /* C's crash: the engine's landing on this 1 */
        else if (dr_nx_land[t] == 2)
            dr_state[t].fill_len = 0;            /* C without one: no landing */
        dr_cur_style[t] = p.style;
        dr_step(&dr_kit[t], &p, &dr_state[t], bar, idx % len, forced, &h);
        dr_vbar[t] = bar;
        dr_vstep[t] = (uint8_t)(idx % len);
        dr_vlen[t] = (uint8_t)len;
        if (dr_brk_left[t])
            dr_brk_left[t]--;
        if (dr_stopped[t] && !dr_nx_let[t] && !forced && !(dr_nx_fz[t] && (h.flags & DRF_FILL)))
            h.play = 0;                          /* stopped: the groove runs on, unheard (the order's fill heard) */
        dr_last_hit[t] = h;
    }
    if (forced && dr_stopped[t] == 2 && !dr_nx_let[t]) {
        U32(KIND + 4u * t) = 1;                  /* SILENT: the grid's trig made trigless (its locks only) */
        return;
    }
    if (!h.play)
        return;
    dr_stats[1]++;
    if (!forced) {
        unsigned i;
        /* the trig's lock block: none. Stock fills it only for the trigs it
         * builds (the staging 0x46c7aa24 + 32t for n = -1, else pending slot
         * n, STEP_LOCKS.md section 3); an added trig would apply what is
         * there (zeros at boot: every PLAYBACK / LFO / AMP value of the track
         * to 0, measured under the port) */
        uint32_t blk = lock_slot < 0 ? STAGE + 32u * t : PENDING + 32u * ((unsigned)lock_slot * 8u + t);
        for (i = 0; i < 32; i++)
            U8(blk + i) = 0xff;
        U32(KIND + 4u * t) = 29;
        U32(COUNT + 4u * t) = 1;
        /* the transport's first step: no start before the transport starts
         * (stock drops it, measured: the hit was lost and the queue lagged) */
        int mt = dr_pos[t] <= 1u && h.mtime < 0 ? 0 : h.mtime;
        U32(MTIME + 4u * t) = (uint32_t)((int32_t)mt * (int32_t)(MT_UNIT * dr_scale[t]));
        U32(LENGTH + 4u * t) = SCALE_UNIT * dr_scale[t];
        dr_stats[2]++;
    } else {
        dr_stats[3]++;
    }
    if (h.slice < DR_SLICES && dr_scene[t][h.slice])
        scene_locks(t, h.slice, lock_slot < 0 ? STAGE + 32u * t
                                              : PENDING + 32u * ((unsigned)lock_slot * 8u + t));
    /* ALIGN: the slice's hit lands on the step. The micro-timing word counts
     * samples x tempo24 (one 1/24-step unit = 110250 x scale, measured: phase
     * 2), so the slice starts align ms earlier; never more than stock's -23. */
    if (!dup && h.slice < DR_SLICES && dr_align[t][h.slice]) {
        int32_t unit = (int32_t)(MT_UNIT * dr_scale[t]);
        int32_t early = (int32_t)dr_align[t][h.slice] * 441 / 10 * (int32_t)U32(TEMPO24);
        int32_t m = (int32_t)U32(MTIME + 4u * t) - early;
        U32(MTIME + 4u * t) = (uint32_t)(m < -23 * unit ? -23 * unit : m);
    }
    /* drop hits whose start never came (a trig stock dropped, two on one
     * instant): a hit starts at most half a step after its grid (micro-timing
     * <= +12), before the next step is built, so one older than the step
     * before this one is stale (an entry kept one step more made every later
     * start play the hit before it, measured) */
    while (dr_count[t] && dr_ring[t][dr_head[t]].pos + 1u < dr_pos[t]) {
        dr_head[t] = (uint8_t)((dr_head[t] + 1u) % RING);
        dr_count[t]--;
    }
    if (dup && dr_count[t] && dr_ring[t][(dr_head[t] + dr_count[t] - 1u) % RING].pos == dr_pos[t])
        return;                                  /* the first call queued it */
    if (dr_count[t] == RING) {
        dr_head[t] = (uint8_t)((dr_head[t] + 1u) % RING);
        dr_count[t]--;
    }
    e = &dr_ring[t][(dr_head[t] + dr_count[t]) % RING];
    e->slice = h.slice;
    e->vel = h.vel;
    e->rtrg = h.rtrg;
    e->rtim = h.rtrg ? rtim_of(h.rtim) : 79u;
    e->pos = dr_pos[t];
    dr_count[t]++;
}

void dr_on_step(unsigned t, int lock_slot, unsigned bank, unsigned ptn, unsigned step)
{
    dr_dbg[0]++;
    on_build(t, U8(STEPCTR + t), lock_slot, bank, ptn, step);
}

void dr_on_rebuild(unsigned t, unsigned idx, unsigned bank, unsigned ptn, unsigned step)
{
    dr_stats[7]++;
    on_build(t, idx, -1, bank, ptn, step);
}

void dr_frame(void)
{
    unsigned t, i, mask = 0;
    uint32_t base = U32(FP_PTR);
    const volatile uint8_t *part = bank_ok() ? part_base() : 0;
    dr_stats[6]++;
    for (t = 0; t < TRACKS; t++) {
        uint32_t rec = base + 48u * t;
        dr_on[t] = (uint8_t)(part && signed_track(part, t));
        if (dr_on[t]) {
            mask |= 1u << t;
        }
        if (!dr_on[t]) {
            dr_knob_ok[t] = 0;
            continue;
        }
        if (dr_live_strt[t] && !(U32(RESTORE + 4u * t) & 2u))
            dr_live_strt[t] = 0;                 /* the next trig gave STRT (DENS) back to the Part */
        for (i = 0; i < 6; i++)                  /* halfword value << 8: its high byte; a slice a */
            if (!(i == 1 && dr_live_strt[t] && dr_knob_ok[t]))   /* live start locked is not DENS */
                dr_knob[t][i] = U8(rec + 2u * i);
        for (i = 0; i < 6; i++)
            dr_knob[t][6 + i] = U8(rec + 24u + i);
        dr_knob_ok[t] = 1;
        U16(rec + 0) = 64u << 8;                 /* PTCH centre */
        U16(rec + 2) = (uint16_t)(dr_strt[t] << 8);
        U16(rec + 4) = 0;                        /* LEN: the slice alone */
        U16(rec + 6) = 127u << 8;                /* RATE forward */
        U16(rec + 8) = (uint16_t)(dr_rtrg_now[t] << 8);   /* the hit's retrigs (a flam, a roll) */
        U16(rec + 10) = (uint16_t)((dr_rtim_now[t] ? dr_rtim_now[t] : 79u) << 8);
        U8(rec + 24) = 0;                        /* LOOP off */
        U8(rec + 25) = 1;                        /* SLIC on */
        U8(rec + 26) = 0;
        U8(rec + 27) = 0;
        U8(rec + 28) = 0;                        /* TSTR off */
        U8(rec + 29) = 0x40;
    }
    dr_dbg[6] = mask;
    if (mask)
        dr_dbg[1]++;
}

/* A hit's retrigs (RTRG / RTIM in the page record) are stock's: it restarts
 * the voice by another path than this entry (measured: the retrig starts never
 * came here), reading the page record, which dr_frame keeps on the hit's
 * slice; only the hit itself takes a queue entry. */
void dr_before_start(unsigned t, unsigned flags)
{
    uint32_t rec = U32(FP_PTR);
    unsigned slice = dr_strt[t] >> 1, vel = 100;
    dr_rtrg_now[t] = 0;
    dr_rtim_now[t] = 79;
    if (dr_preview[t]) {                         /* the KIT window plays a slice */
        slice = dr_preview[t] - 1u;
        dr_preview[t] = 0;
    } else if (flags & LIVE_START) {
        /* A trig key in SLICES trig mode (in the AED too), a track key: stock
         * put the slice in the live lock (STRT = 2n, 0x46c7dfda + 32t + 1),
         * then moved it to the lane and set the restore bit before this start
         * (port: 0x4000b778 clears the buffer, 0x4000c5f2 / 0x4000c604). Not
         * the engine's queue. Without a STRT lock (a track key), the last slice. */
        if (U32(RESTORE + 4u * t) & 2u) {
            slice = U8(LANE + 72u * t + 1u) >> 1;
            dr_live_strt[t] = 1;
        }
        dr_stats[5]++;
    } else if (dr_count[t]) {
        DrPend *e = &dr_ring[t][dr_head[t]];
        slice = e->slice;
        vel = e->vel;
        dr_rtrg_now[t] = e->rtrg;
        dr_rtim_now[t] = e->rtim;
        dr_head[t] = (uint8_t)((dr_head[t] + 1u) % RING);
        dr_count[t]--;
    } else {
        slice = 0;                               /* a sequencer start the engine did not queue */
    }
    dr_strt[t] = (uint8_t)(slice * 2u);
    dr_vel_now[t] = (uint8_t)vel;
    U8(rec + 2) = dr_strt[t];
    U8(rec + 25) = 1;
    U16(rec + 8) = (uint16_t)(dr_rtrg_now[t] << 8);
    U16(rec + 10) = (uint16_t)(dr_rtim_now[t] << 8);
    dr_stats[4]++;
}

/* 256 x 10^(dB / 20), DR_GAIN_MIN..DR_GAIN_MAX dB: the factor on the hit's
 * VOL, which the hit already scales linearly by its velocity (VOL's own law in
 * dB is not measured: the GAIN's dB are those of that value). */
static unsigned gain_q8(int db)
{
    static const uint16_t Q8[DR_GAIN_MAX - DR_GAIN_MIN + 1] = {
        16, 18, 20, 23, 26, 29, 32, 36, 41, 46, 51, 57, 64, 72, 81, 91,
        102, 114, 128, 144, 162, 181, 203, 228, 256, 287, 322, 362, 406, 455, 511 };
    if (db < DR_GAIN_MIN || db > DR_GAIN_MAX)
        return 256;
    return Q8[db - DR_GAIN_MIN];
}

void dr_after_start(unsigned t)
{
    unsigned lane = U8(LANE + 72u * t + VOL_SLOT), base, vol;
    /* The level the hit scales: the lane's VOL (the Part's, or a lock), unless
     * the lane still holds what the last hit wrote. Not the restore bit of
     * 0x80001538: on the unit it can be set at power-up, which kept the base
     * at 0 and every hit silent until the machine was chosen again (reported). */
    if (!dr_vol_mine[t] || lane != dr_vol_mine[t] || !dr_vol_base[t])
        dr_vol_base[t] = (uint8_t)lane;
    base = dr_vol_base[t];
    vol = base * dr_vel_now[t] / 100u;
    vol = vol * gain_q8(dr_gain[t][(dr_strt[t] >> 1) % DR_SLICES]) >> 8;   /* the slice's GAIN */
    if (vol > 127)
        vol = 127;
    if (!vol && base)
        vol = 1;
    dr_vol_mine[t] = (uint8_t)vol;
    U8(LANE + 72u * t + VOL_SLOT) = (uint8_t)vol;
    U16(DSPREC + 64u * t + 2u * VOL_SLOT) = (uint16_t)(vol << 8);
    U32(RESTORE + 4u * t) |= 1u << VOL_SLOT;
}

_Static_assert(sizeof(DrKit) == 268, "hooks.s reserves 268 bytes a DrKit");
_Static_assert(sizeof(DrState) == 32, "hooks.s reserves 32 bytes a DrState");
#ifndef DR_HOST
_Static_assert(sizeof(DrLoop) == 258, "hooks.s reserves 258 bytes a DrLoop");
_Static_assert(sizeof(DrLoopBar) == 612, "hooks.s reserves 612 bytes for DrLoopBar");
#endif
_Static_assert(sizeof(DrPend) == 8, "hooks.s reserves 8 bytes a ring entry");
_Static_assert(sizeof(DrHit) == 8, "hooks.s reserves 8 bytes a DrHit");
