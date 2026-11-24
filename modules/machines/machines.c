/* MACHINES -- the machine list's shared code, once for every client.
 *
 * An added machine is a track whose stored machine is its `base` (FLEX) and
 * whose three signature bytes, in NEIGHBOR's unused PLAYBACK column, are its
 * client's. The tables (mc_count, mc_sigs, ...) are the remix's: manifest.py
 * writes them into remix.inc, one entry per client present, row 5 + index.
 *
 * Derived from ANALOG BD's registration (modules/analog-bassdrum, repeat98),
 * which DRUMMER, OCTA303 and WAVE CF each carried a copy of.
 */
#include <stdint.h>

#define U8(a)  (*(volatile uint8_t *)(uintptr_t)(a))
#define U32(a) (*(volatile uint32_t *)(uintptr_t)(a))
#define ADDR(a) ((volatile uint8_t *)(uintptr_t)(a))

enum {
    BANK_PTR = 0x46c82456u,     /* the bank in DRAM */
    PART_OFF = 0x8ed80u,        /* the working Parts in a bank */
    PART_IDX = 0x100b14cfu,     /* the Part playing (low two bits) */
    PART_STRIDE = 6322u,
    SRAM_PART = 0x100a4eceu,    /* the battery copy of the working Parts */
    CUR_TRACK = 0x100b14ccu,    /* the UI track */
    SRC_WIN = 0x460d175cu,      /* SRC SETUP's window while it is open, else 0 (measured under the port) */
    PB_TABLE = 0x400d5f38u,     /* the PLAYBACK page of each machine row */
    FLEX_DEFAULTS = 0x400d320cu,
    MACHINE = 0x22u,            /* a track's stored machine byte: Part + 0x22 + track */
    SIG = 0x2au + 18u,          /* NEIGHBOR's PLAYBACK column: Part + 0x3c + 30 * track */
    KNOBS1 = 0x2au + 6u,        /* FLEX's PLAYBACK bytes: page 1, then page 2 */
    KNOBS2 = 0x1dau + 6u,
    TRACKS = 8u,
    ROW0 = 5u,                  /* the first row after stock's five */
};

/* The remix's clients (remix.inc). mc_flags: bits 0-7 the base machine,
 * MC_SLOT when the client plays the base's sample slot (RIGHT on its row in
 * SRC SETUP opens the base's slot list). */
#define MC_SLOT 0x100u
typedef uint32_t (*mc_page_fn)(const volatile uint8_t *type_ptr);
typedef void (*mc_tick_fn)(void);
typedef void (*mc_keep_fn)(uint8_t *part, unsigned track, int restore);
extern const uint32_t mc_count;
extern const uint32_t mc_sigs[];            /* 'A' 'B' version 0 */
extern const uint8_t *const mc_defaults[];  /* 12 knob bytes: page 1, then page 2 */
extern const uint32_t mc_flags[];
extern const mc_page_fn mc_pages[];
extern const mc_tick_fn mc_ticks[];         /* 0: none */
extern const mc_keep_fn mc_keeps[];         /* 0: none */

/* The row a pick of the base's slot list came from (0: no pick), and the
 * base's page it displaced from PB_TABLE meanwhile. DRAM .bss is not zeroed. */
__attribute__((section(".data"))) uint8_t mc_pick;
__attribute__((section(".data"))) uint32_t mc_pick_win;   /* SRC_WIN when the pick began (machines.s) */
__attribute__((section(".data"))) uint8_t mc_pb_held;      /* base + 1 while its page is displaced */
__attribute__((section(".data"))) uint32_t mc_pb_saved;

static unsigned bank_ok(void)
{
    uint32_t b = U32(BANK_PTR);
    return b >= 0x40000000u && b < 0x48000000u;
}

static volatile uint8_t *part_base(void)
{
    return ADDR(U32(BANK_PTR) + PART_OFF + (U8(PART_IDX) & 3u) * PART_STRIDE);
}

static unsigned base_of(unsigned i)
{
    return mc_flags[i] & 0xffu;
}

static uint32_t sig_at(const volatile uint8_t *s)
{
    return (uint32_t)s[0] << 24 | (uint32_t)s[1] << 16 | (uint32_t)s[2] << 8;
}

/* The client signing track t of a Part, or -1. */
int mc_client(const volatile uint8_t *part, unsigned t)
{
    unsigned i;
    uint32_t s;
    if (t >= TRACKS)
        return -1;
    s = sig_at(part + SIG + 30u * t);
    for (i = 0; i < mc_count; ++i)
        if (mc_sigs[i] == s && part[MACHINE + t] == base_of(i))
            return (int)i;
    return -1;
}

/* A stored machine type and its byte in the playing Part: the client's row
 * for a signed track, else the type. */
unsigned mc_type(unsigned type, const volatile uint8_t *ptr)
{
    volatile uint8_t *part;
    uintptr_t t;
    int i;
    if (!bank_ok())
        return type;
    part = part_base();
    t = (uintptr_t)ptr - (uintptr_t)(part + MACHINE);
    if (t >= TRACKS)
        return type;
    i = mc_client(part, (unsigned)t);
    return i >= 0 && type == base_of((unsigned)i) ? ROW0 + (unsigned)i : type;
}

/* Both copies of a track's signature: the working Part's and its battery copy. */
static void sign_one(volatile uint8_t *s, int i)
{
    unsigned k;
    if (i < 0) {
        int j;
        uint32_t cur = sig_at(s);
        for (j = 0; j < (int)mc_count; ++j)
            if (mc_sigs[j] == cur) {
                s[0] = s[1] = s[2] = 0;
                return;
            }
        return;
    }
    if (sig_at(s) != mc_sigs[i]) {          /* a first signing: the client's knob defaults */
        const uint8_t *d = mc_defaults[i];
        for (k = 0; k < 6; ++k) {
            s[KNOBS1 - SIG + k] = d[k];
            s[KNOBS2 - SIG + k] = d[6 + k];
        }
    }
    s[0] = (uint8_t)(mc_sigs[i] >> 24);
    s[1] = (uint8_t)(mc_sigs[i] >> 16);
    s[2] = (uint8_t)(mc_sigs[i] >> 8);
}

/* A commit of row `row` on track t of a Part: signs the track for a client's
 * row and returns the machine to store (the client's base), else clears a
 * client's signature and returns the row. */
unsigned mc_commit(volatile uint8_t *part, unsigned t, unsigned row)
{
    int i = row >= ROW0 && row - ROW0 < mc_count ? (int)(row - ROW0) : -1;
    uintptr_t off = (uintptr_t)part - U32(BANK_PTR) - PART_OFF;
    if (t < TRACKS) {
        sign_one(part + SIG + 30u * t, i);
        sign_one(ADDR(SRAM_PART + off + SIG + 30u * t), i);
    }
    return i >= 0 ? base_of((unsigned)i) : row;
}

/* The page of the client at row `row` for the machine byte at type_ptr. */
uint32_t mc_page(unsigned row, const volatile uint8_t *type_ptr)
{
    return mc_pages[row - ROW0](type_ptr);
}

/* While the base's slot list is open from a client's row, PB_TABLE[base] is
 * the client's page, so the SETUP knobs beside the list stay the client's. */
void mc_pick_page(void)
{
    unsigned base;
    uint32_t page;
    if (mc_pick) {
        base = base_of(mc_pick - ROW0);
        page = mc_page(mc_pick, bank_ok() ? part_base() + MACHINE + (U8(CUR_TRACK) & 7u) : 0);
        if (U32(PB_TABLE + 4u * base) != page) {
            if (!mc_pb_held) {
                mc_pb_saved = U32(PB_TABLE + 4u * base);
                mc_pb_held = (uint8_t)(base + 1u);
            }
            U32(PB_TABLE + 4u * base) = page;
        }
    } else if (mc_pb_held) {
        U32(PB_TABLE + 4u * (mc_pb_held - 1u)) = mc_pb_saved;
        mc_pb_held = 0;
    }
}

/* Each client's page for the UI track as its row's, for the stock code that
 * reads PB_TABLE by row (SETUP's editor and drawer). A client calls it when
 * its page changes between ticks. */
void mc_publish(void)
{
    const volatile uint8_t *ptr = bank_ok() ? part_base() + MACHINE + (U8(CUR_TRACK) & 7u) : 0;
    unsigned i;
    for (i = 0; i < mc_count; ++i)
        U32(PB_TABLE + 4u * (ROW0 + i)) = mc_pages[i](ptr);
}

/* The UI tick: the pages, a pick's page, then each client's own tick. A pick
 * ends when SRC SETUP's window is no longer the one it began in: NO or
 * FUNC + SRC close SRC SETUP with the slot list open, and LEFT is never seen. */
void mc_ui_tick(void)
{
    unsigned i;
    if (mc_pick && U32(SRC_WIN) != mc_pick_win)
        mc_pick = 0;
    mc_publish();
    mc_pick_page();
    for (i = 0; i < mc_count; ++i)
        if (mc_ticks[i])
            mc_ticks[i]();
}

/* The Part validator sees the base's defaults on a signed track's 12 knob
 * bytes (its ranges would clamp a client's values), then they are put back;
 * a client's keep hook saves and restores any other byte it borrows. */
extern int mc_stock_validate(void *part);
int mc_validate(uint8_t *part)
{
    uint8_t saved[TRACKS][12];
    const volatile uint8_t *stock = ADDR(FLEX_DEFAULTS);
    unsigned t, k;
    int who[TRACKS], result;
    for (t = 0; t < TRACKS; ++t) {
        who[t] = mc_client(part, t);
        if (who[t] < 0)
            continue;
        for (k = 0; k < 12; ++k) {
            unsigned at = (k < 6 ? KNOBS1 : KNOBS2) + 30u * t + k % 6u;
            saved[t][k] = part[at];
            part[at] = stock[k];
        }
        if (mc_keeps[who[t]])
            mc_keeps[who[t]](part, t, 0);
    }
    result = mc_stock_validate(part);
    for (t = 0; t < TRACKS; ++t) {
        if (who[t] < 0)
            continue;
        for (k = 0; k < 12; ++k)
            part[(k < 6 ? KNOBS1 : KNOBS2) + 30u * t + k % 6u] = saved[t][k];
        if (mc_keeps[who[t]])
            mc_keeps[who[t]](part, t, 1);
    }
    return result;
}
