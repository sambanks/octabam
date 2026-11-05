/* CHORDS FACTORY: the firmware side of the engine, the atelier page. hooks.s
 * calls in; PAGES opens it (SRC again on MIDI NOTE, after TURING's). */
#include "chords.h"

#define U8(a)  (*(volatile uint8_t *)(uintptr_t)(a))
#define U32(a) (*(volatile uint32_t *)(uintptr_t)(a))
#define FN(addr, ...) ((uint32_t (*)(__VA_ARGS__))(uintptr_t)(addr))
/* The platform leaves a unit's .bss as the boot left it, nonzero on the unit
 * (TRAPS trap-dram-bss): state read before the unit first writes it lives in
 * .data; verify.py checks the symbols' sections. */
#define DATA __attribute__((section(".data")))

enum {
    UI_TRACK  = 0x100b14ccu,    /* byte: the MIDI track the pages edit (MIDI_TRACKS.md) */
    BANK      = 0x80000002u,    /* byte: the current bank (MIDI_TRACKS.md) */
    FUNC_HELD = 0x46c7dd26u,    /* long: nonzero while [FUNCTION] is down */
    MIDI_MODE = 0x80000012u,    /* long: nonzero in MIDI mode */
    PAGE      = 0x460d1684u,    /* long: the page shown, 0 = SRC */
    SETUP     = 0x400bcd14u,    /* -> the setup window's record, +8 nonzero while open */
    SCRDIRTY  = 0x46c7c72cu,    /* long 1: the screen is drawn again */
    WCREATE   = 0x4005829cu,    /* (w, h, dx, dy, class, closed) -> handle, centred + (dx, dy) */
    WDESTROY  = 0x40055db4u,    /* (&handle) */
    LPUSH     = 0x40031494u,    /* (layer) */
    LPOP      = 0x4003146cu,
    CLEAR     = 0x40035624u,    /* (surface) */
    TEXT      = 0x40012bd8u,    /* (font, surface, x, y, limit, text); y = the bottom row, from the bottom */
    TWIDTH    = 0x40012f30u,    /* (font, limit, text) -> pixels */
    FILL      = 0x40012254u,    /* (surface, x1, y1, x2, y2, mode): 1 set, 0 clear, -1 toggle */
    FONT      = 0x400ba876u,    /* the small UI font: labels */
    FONT5     = 0x400ba84eu,    /* the values */
    MIDI_SEND = 0x40010bc8u,    /* (len, bytes): the MIDI OUT queue (MIDI_TRACKS.md section 4) */
    F_COPY    = 0x40016388u,    /* (dst, src, 0) -> < 0 error */
    NOTE_EVT  = 0x4009e9a8u,    /* (track, note, velocity, post): a MIDI track's note on (velocity 0: off), the
                                 * call stock's CHROMATIC note 0x40043664 makes once it has kept the note; post
                                 * 1 also posts the note's event (0x46 / 0x4a) from ONE static record 0x46c77bea */
    POST      = 0x40000c3cu,    /* (queue, record): an event to a task's queue */
    SYS_QUEUE = 0x460d17aeu,    /* the queue 0x4009e9a8 posts its note events to (the sys task: live recording) */
    EV_TIME   = 0x46104cf4u,    /* long: the time a note event carries (where live recording puts it) */
    NOW       = 0x46c7a19cu,    /* long: the clock a note-off event's length is counted on */
    BANK_RAM  = 0x46c82456u,    /* -> the bank's RAM (MIDI_TRACKS.md: B) */
    UI_PART   = 0x100b14cfu,    /* byte: the Part the pages edit */
    HELD      = 0x460d174au,    /* u16: the trig keys held in GRID RECORDING, bit k = trig k + 1 */
    STEP_PAGE = 0x460d174cu,    /* long: the step of trig key 1 on the page shown (STEP_LOCKS.md) */
    UI_PATTERN = 0x100b14d0u,   /* byte: the pattern edited */
    CS1_PATTERNS = 0x1001614eu, /* the battery-backed copy of the current bank's patterns, same offsets */
    EDITED    = 0x100f8598u,    /* long 1: the project edited (the lock editor's, 0x40050ea0) */
    LOCKS_DONE = 0x40027e00u,   /* (): after a lock is written (the lock editor's call) */
    TRACK_DONE = 0x4009da20u,   /* (track): its step records again; a MIDI track is 8 + t (0x40051eb2) */
    NOTIFY    = 0x4005a2b8u,    /* (text, ticks): stock's toast; 0x30, about 0.8 s (QUANTIZE_LIVE_REC_TOGGLE) */
    PAGE_DRAW = 0x4004d948u,    /* (-1): the page's values drawn again (the lock editor's, 0x40050efe) */
    SCREEN    = 0x400bf10au,    /* the main screen's surface (the trig mode's box draws on it) */
    TEXTF     = 0x40013904u,    /* (font, surface, x, y, align, inverse, widest, format, ...): the box's numbers */
    TRIG_MODE = 0x460d16f0u,    /* long: the trig keys' mode, 2 = CHORDS on a MIDI track */
    LEDS      = 0x4007e998u,    /* (0): the trig LEDs drawn again (the pass, then ch_leds) */
    SET_LEVEL = 0x400135b0u,    /* (led, level): 2k red, 2k + 1 green of trig key k (SCALES' kl_chromatic) */
    LED_ON    = 0x400131a0u,    /* (led) */
};

/* The whole screen; class 6 gives way to every stock popup. y from the bottom. */
enum { PAGE_W = 128, PAGE_H = 64, PAGE_DX = -1, PAGE_CLASS = 6, CELL_W = 21, BAND = 8 };
/* Centred, a 128-wide window landed one column right, leaving stock's track
 * tab in column 0 (under the port); 130 wide, WCREATE made none. PAGE_DX
 * moves it back. X0: the drawings' left margin. */
enum { X0 = 0 };
/* Ticks of the display loop an edit sounds for (calibrated under the port:
 * INVESTIGATION.md), and the velocity. */
enum { HOLD_TICKS = 60, VELOCITY = 100 };

ChSlot   ch_bank[CH_BANKS][CH_SLOTS];
DATA uint8_t ch_ready;

int32_t ch_scale(unsigned t);           /* hooks.s: SCALES' scale of track t, or -1 */
int32_t ch_keyboard(unsigned t, unsigned first, unsigned green);   /* hooks.s: SCALES' sc_keyboard, 0 none drawn */
int32_t ch_channel(unsigned t);         /* hooks.s: the edited Part's CHAN of MIDI track t (0 off, else ch + 1), -1 */

static void ready(void) {
    if (ch_ready) return;
    for (unsigned b = 0; b < CH_BANKS; b++)
        for (unsigned i = 0; i < CH_SLOTS; i++) ch_slot_clear(&ch_bank[b][i]);
    ch_ready = 1;
}

/* ---- what sounds: the notes on, their channel, the ticks left ---- */

DATA uint8_t ch_on_n, ch_on_ch, ch_on_held;
DATA uint8_t ch_on_note[CH_VOICES];
DATA uint16_t ch_on_left;
uint8_t ch_msg[4];

static void send(uint8_t status, uint8_t a, uint8_t b) {
    ch_msg[0] = status;
    ch_msg[1] = a;
    ch_msg[2] = b;
    FN(MIDI_SEND, uint32_t, const uint8_t *)(3, ch_msg);
}

static void silence(void) {
    for (unsigned k = 0; k < ch_on_n; k++) send((uint8_t)(0x80 | ch_on_ch), ch_on_note[k], 0);
    ch_on_n = 0;
    ch_on_held = 0;
    ch_on_left = 0;
}

/* The chord on the UI track's channel: held (until the key is let go) or
 * for HOLD_TICKS. */
static void sound(const ChVoicing *v, unsigned held) {
    silence();
    int32_t ch = ch_channel(U8(UI_TRACK) & 7);
    if (ch <= 0 || !v->n) return;
    ch_on_ch = (uint8_t)((ch - 1) & 15);
    for (unsigned k = 0; k < v->n; k++) {
        ch_on_note[k] = v->note[k];
        send((uint8_t)(0x90 | ch_on_ch), v->note[k], VELOCITY);
    }
    ch_on_n = v->n;
    ch_on_held = (uint8_t)held;
    ch_on_left = held ? 0 : HOLD_TICKS;
}

/* ---- CHORDS, the trig mode: a key plays its slot's chord through the call
 * stock's CHROMATIC note makes (one per voice), so the arpeggiator and the
 * KEY take it as keys held. Not stock's CHROMATIC note itself: it keeps a
 * held note in one of 16 cells, note % 16, so two voices 16 apart (F#3 and
 * A#4) shared a cell and the first never got its note-off (image 36, D#m7).
 * The notes a key turned on are kept here and turned off on its release,
 * whatever the slot became since. ---- */

DATA uint8_t ch_held_n[CH_SLOTS], ch_held_t[CH_SLOTS];
DATA uint8_t ch_held[CH_SLOTS][CH_VOICES];
DATA uint8_t ch_current[8];     /* the slot each MIDI track last played + 1, 0 none (TURING, later) */
DATA uint32_t ch_held_at[CH_SLOTS];

/* The note events stock's 0x4009e9a8 posts, one record each: {0x46 on /
 * 0x4a off, 8, note, velocity, time, length}. Posted from its one static
 * record, a chord's four were one note four times by the time the sys task
 * read them (live recording kept the last voice only, 4 Nov 2026 under the
 * port); a ring of records keeps each voice. */
enum { EV_RING = 16, EV_B = 12 };
DATA uint8_t ch_ev[EV_RING][EV_B];
DATA uint8_t ch_ev_next;

static void post(unsigned code, unsigned note, unsigned vel, uint32_t length) {
    uint8_t *r = ch_ev[ch_ev_next];
    ch_ev_next = (uint8_t)((ch_ev_next + 1) % EV_RING);
    uint32_t t = U32(EV_TIME);
    r[0] = (uint8_t)code; r[1] = 8; r[2] = (uint8_t)note; r[3] = (uint8_t)vel;
    r[4] = (uint8_t)(t >> 24); r[5] = (uint8_t)(t >> 16); r[6] = (uint8_t)(t >> 8); r[7] = (uint8_t)t;
    r[8] = (uint8_t)(length >> 24); r[9] = (uint8_t)(length >> 16); r[10] = (uint8_t)(length >> 8); r[11] = (uint8_t)length;
    FN(POST, uint32_t, const uint8_t *)(SYS_QUEUE, r);
}

void ch_chord_key(unsigned key, unsigned edge) {
    ready();
    key &= 15;
    if (edge) {
        const ChVoicing *v = &ch_bank[U8(BANK) & 15][key].v;
        unsigned t = U8(UI_TRACK) & 7;
        if (ch_held_n[key] || !v->n) return;
        /* the track's VEL, as stock's CHROMATIC note reads it (0x400436ac) */
        unsigned vel = U8(U32(BANK_RAM) + U8(UI_PART) * 0x18b2u + t * 0x20u + 0x8f163u);
        for (unsigned k = 0; k < v->n; k++) {      /* the lowest first: live recording's NOTE, the rest NOT2-4 */
            ch_held[key][k] = v->note[k];
            FN(NOTE_EVT, unsigned, unsigned, unsigned, unsigned)(t, v->note[k], vel, 0);
            post(0x46, v->note[k], vel, 0);
        }
        ch_held_at[key] = U32(NOW);
        ch_held_n[key] = v->n;
        ch_held_t[key] = (uint8_t)t;
        ch_current[t] = (uint8_t)(key + 1);
        return;
    }
    uint32_t length = U32(NOW) - ch_held_at[key];
    for (unsigned k = 0; k < ch_held_n[key]; k++) {
        FN(NOTE_EVT, unsigned, unsigned, unsigned, unsigned)(ch_held_t[key], ch_held[key][k], 0, 0);
        post(0x4a, ch_held[key][k], 0, length);
    }
    ch_held_n[key] = 0;
}

/* The trig LEDs in CHORDS: a slot that holds a chord green, a key held
 * yellow, an empty slot dark. */
void ch_leds(void) {
    ready();
    const ChSlot *bank = ch_bank[U8(BANK) & 15];
    for (unsigned k = 0; k < CH_SLOTS; k++) {
        unsigned held = ch_held_n[k] != 0, full = bank[k].v.n != 0;
        FN(SET_LEVEL, unsigned, unsigned)(2 * k, held ? 15 : 0);
        FN(LED_ON, unsigned)(2 * k);
        FN(SET_LEVEL, unsigned, unsigned)(2 * k + 1, held || full ? 15 : 0);
        FN(LED_ON, unsigned)(2 * k + 1);
    }
}

/* ---- chords.work, through STORE (modules/store/README.md), client 8 ----
 * 'CHRD', version 1, payload length CH_FILE_B, CRC-32; then ch_pack's
 * payload: every bank's sixteen slots. Written at the bank writer and before
 * the project store when it changed; chords.strd is its copy at the project
 * store, copied back at a reload. As TURING's turing.work. */

enum { MAGIC = 0x43485244u, VERSION = 1u };
static const char WORK[] = "%s/chords.work", STRD[] = "%s/chords.strd", BAK[] = "%s/chords.bak";

int32_t  ch_file_path(const char *format, char *out);
int32_t  ch_file_open(const char *path, const char *mode);
int32_t  ch_file_read(void *buffer, uint32_t length);
int32_t  ch_file_write(const void *buffer, uint32_t length);
void     ch_file_close(void);
uint32_t ch_file_crc(const void *buffer, uint32_t length);
void     ch_file_refuse(void);
extern char    ch_path[260], ch_path2[260];
extern uint8_t ch_fbuf[CH_FILE_B], ch_fsaved[CH_FILE_B];       /* hooks.s, in the image: zero at boot */
DATA uint8_t ch_nowrite, ch_backup;
_Static_assert(CH_FILE_B == 3584, "hooks.s reserves 3584 bytes for ch_fbuf and ch_fsaved");

static unsigned same(const void *a, const void *b, uint32_t n) {
    const uint8_t *x = a, *y = b;
    while (n--) if (*x++ != *y++) return 0;
    return 1;
}

static void copy_bytes(void *dst, const void *src, uint32_t n) {
    uint8_t *d = dst;
    const uint8_t *s = src;
    while (n--) *d++ = *s++;
}

static int32_t file_copy(const char *to, const char *from) {
    ch_file_path(to, ch_path);
    ch_file_path(from, ch_path2);
    return (int32_t)FN(F_COPY, const char *, const char *, uint32_t)(ch_path, ch_path2, 0);
}

static void fresh(void) {
    ch_ready = 0;
    ready();
    ch_pack(ch_bank, ch_fsaved);
}

static void save(void) {
    if (ch_nowrite) return;
    ready();
    ch_pack(ch_bank, ch_fbuf);
    if (same(ch_fbuf, ch_fsaved, CH_FILE_B)) return;
    if (ch_backup) {
        ch_backup = 0;
        file_copy(BAK, WORK);
    }
    uint32_t head[4] = {MAGIC, VERSION, CH_FILE_B, ch_file_crc(ch_fbuf, CH_FILE_B)};
    ch_file_path(WORK, ch_path);
    if (ch_file_open(ch_path, "w") < 0) return;
    int32_t ok = ch_file_write(head, sizeof head) == 1 && ch_file_write(ch_fbuf, CH_FILE_B) == 1;
    ch_file_close();
    if (ok) copy_bytes(ch_fsaved, ch_fbuf, CH_FILE_B);
}

static void load(void) {
    uint32_t head[4];
    ch_nowrite = 0;
    ch_backup = 0;
    fresh();
    ch_file_path(WORK, ch_path);
    if (ch_file_open(ch_path, "r") < 0) return;
    unsigned good = ch_file_read(head, sizeof head) == 1 && head[0] == MAGIC && head[1] == VERSION
                 && head[2] == CH_FILE_B && ch_file_read(ch_fbuf, CH_FILE_B) == 1;
    ch_file_close();
    if (!good || ch_file_crc(ch_fbuf, CH_FILE_B) != head[3]) {
        ch_nowrite = 1;
        ch_file_refuse();
        return;
    }
    ch_unpack(ch_fbuf, ch_bank);
    ch_pack(ch_bank, ch_fsaved);
}

void ch_st_loadall_post(void)  { load(); }
void ch_st_loadmask_post(void) { load(); }
void ch_st_newproj(void) {
    ch_nowrite = 0;
    ch_backup = 0;
    fresh();
}
void ch_st_bankw_post(void) { save(); }
void ch_st_pstore_pre(void) { save(); }
void ch_st_pstore_post(void) {
    if (!ch_nowrite) file_copy(STRD, WORK);
}
void ch_st_preload_post(void) {
    if (file_copy(WORK, STRD) >= 0) load();
    else ch_st_newproj();
}
void ch_answer(unsigned answer) {
    if (!answer) return;
    if (answer == 2) ch_backup = 1;
    ch_nowrite = 0;
    ch_fsaved[0] = 0xff;                        /* an n of 255: matches nothing, the next save writes */
}

/* ---- the atelier ---- */

extern const uint8_t ch_layer[];
DATA uint32_t ch_win;
DATA uint8_t  ch_pushed;
DATA uint8_t  ch_slot;          /* the slot edited, 0..15 */
DATA uint8_t  ch_func;          /* FUNC as last drawn */
DATA uint8_t  ch_answers;       /* LEAD's answers for the slot edited, 0 when not LEAD */
uint8_t  ch_win_t, ch_win_b;    /* the track and bank the page shows */
char     ch_text[12];

static void text(uint32_t font, uint32_t s, int x, int y, const char *t) {
    FN(TEXT, uint32_t, uint32_t, int, int, int, const char *)(font, s, x, y, -1, t);
}

static int width(uint32_t font, const char *t) {
    return (int)FN(TWIDTH, uint32_t, int, const char *)(font, -1, t);
}

static void centred(uint32_t font, uint32_t s, int cx, int y, const char *t) {
    int w = width(font, t), x = cx - w / 2;
    if (x + w > PAGE_W) x = PAGE_W - w;
    if (x < 0) x = 0;
    text(font, s, x, y, t);
}

static void fill(uint32_t s, int x1, int y1, int x2, int y2, int mode) {
    FN(FILL, uint32_t, int, int, int, int, int)(s, x1, y1, x2, y2, mode);
}

static ChSlot *slot(void) {
    return &ch_bank[ch_win_b][ch_slot];
}

static const ChVoicing *before(void) {
    return ch_slot ? &ch_bank[ch_win_b][ch_slot - 1].v : 0;
}

static const char *const note_names[12] = {"C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"};
static const char *const degrees[7] = {"I", "II", "III", "IV", "V", "VI", "VII"};

static char *put_s(char *p, const char *s) {
    while (*s) *p++ = *s++;
    return p;
}

static char *put_u(char *p, unsigned v) {
    char d[4];
    unsigned n = 0;
    do { d[n++] = (char)('0' + v % 10); v /= 10; } while (v);
    while (n) *p++ = d[--n];
    return p;
}

/* As stock's NOTE page and its locks: 60 is C4 (a MIDI track's default
 * NOTE, 60, reads C 4; a step locked to 50 reads D 3 -- under the port,
 * 4 Nov 2026; images 35-40 named 48 C4, an octave high), so OCT n builds
 * on C(n - 1). */
static const char *note_name(unsigned n) {
    char *p = put_s(ch_text, note_names[n % 12]);
    p = n < 12 ? put_s(p, "-1") : put_u(p, n / 12 - 1);
    *p = 0;
    return ch_text;
}

/* The value font has no lower case: the types in four capitals, in
 * ch_types' order (the band's FONT names them as written). */
static const char *const type_cells[] = {
    "MAJ", "MIN", "7", "MAJ7", "MIN7", "HDIM", "DIM", "DIM7", "AUG", "SUS2", "SUS4",
    "7SU4", "6", "MIN6", "ADD9", "MAD9", "MMA7", "9", "MIN9", "MAJ9", "5",
};
static const char *const spread_cells[CH_SPREADS] = {"CLS", "DRP2", "DRP3", "OPEN", "BASS", "10E", "WIDE"};

static const char *const labels[6] = {"ROOT", "TYPE", "INV", "SPRD", "OCT", "VOIX"};
static const char *const func_labels[6] = {"VX1", "VX2", "VX3", "VX4", "BASS", "GAMME"};

static const char *value(const ChSlot *c, unsigned k) {
    char *p = ch_text;
    if (k >= 2 && k <= 4 && c->mode != CH_MODE_BUILT) return "";   /* INV, SPRD, OCT: only a built chord's */
    switch (k) {
    case 0: return note_names[c->root];
    case 1: return c->type < sizeof type_cells / sizeof type_cells[0] ? type_cells[c->type] : "?";
    case 2: p = put_u(p, c->inv); break;
    case 3: return spread_cells[c->spread];
    case 4: p = put_u(p, c->oct - 1u); break;      /* the octave of its C, as note_name */
    case 5:
        if (c->mode == CH_MODE_EDIT) return "EDIT";
        if (!ch_answers) return "-";
        p = put_u(p, c->lead + 1u);
        *p++ = '/';
        p = put_u(p, ch_answers);
        break;
    }
    *p = 0;
    return ch_text;
}

static const char *func_value(const ChSlot *c, unsigned k) {
    if (k < CH_VOICES) return k < c->v.n ? note_name(c->v.note[k]) : "-";
    if (k == 4) return c->flags & CH_BASS_ROOT ? "ROOT" : "FREE";
    return c->degree < 7 ? degrees[c->degree] : "-";
}

static void page_draw(void) {
    if (!ch_win) return;
    ready();
    uint32_t s = ch_win + 36;
    const ChSlot *c = slot();
    unsigned func = U32(FUNC_HELD) != 0;
    ch_func = (uint8_t)func;
    FN(CLEAR, uint32_t)(s);
    fill(s, 0, 0, PAGE_W - 1, PAGE_H - 1, 0);
    /* The notes, lowest left, on screen rows 2..10. */
    for (unsigned k = 0; k < CH_VOICES; k++)
        centred(FONT5, s, X0 + 16 + 32 * (int)k, 53, k < c->v.n ? note_name(c->v.note[k]) : "");
    /* The sixteen slots: a box each, filled when it holds a chord, the one
     * edited outlined twice; screen rows 15..20. */
    for (unsigned i = 0; i < CH_SLOTS; i++) {
        int x = X0 + (int)i * 8;
        fill(s, x + 1, 43, x + 6, 48, 1);
        if (!ch_bank[ch_win_b][i].v.n) fill(s, x + 2, 44, x + 5, 47, 0);
        if (i == ch_slot) {
            fill(s, x, 42, x + 7, 42, 1);
            fill(s, x, 49, x + 7, 49, 1);
        }
    }
    /* Labels and values: screen rows 30 and 43. */
    for (unsigned k = 0; k < 6; k++) {
        int cx = X0 + (int)k * CELL_W + CELL_W / 2;
        centred(FONT, s, cx, 33, func ? func_labels[k] : labels[k]);
        centred(FONT5, s, cx, 20, func ? func_value(c, k) : value(c, k));
    }
    for (int x = X0 + CELL_W; x < PAGE_W - 4; x += CELL_W)
        for (int y = BAND + 1; y < 36; y += 2) fill(s, x - 1, y, x - 1, y, 1);
    /* The band: CHORDS n/16 and the chord's name, white on black. */
    fill(s, 0, 0, PAGE_W - 1, BAND - 1, 0);
    char *p = put_s(ch_text, "CHORDS ");
    p = put_u(p, ch_slot + 1u);
    p = put_s(p, "/16");
    *p = 0;
    text(FONT, s, X0 + 2, 1, ch_text);
    ch_name(&c->v, ch_text);
    text(FONT, s, PAGE_W - 3 - width(FONT, ch_text), 1, ch_text);
    fill(s, 0, 0, PAGE_W - 1, BAND - 1, -1);
    U32(SCRDIRTY) = 1;
    FN(LEDS, unsigned)(0);      /* the keys again: CHORDS' slots (trig mode 2), or the keyboard while FUNC is held */
}

/* The slot's notes again, the answers counted, and heard. */
static void apply(unsigned heard) {
    ChSlot *c = slot();
    ch_answers = (uint8_t)ch_slot_apply(c, before());
    if (heard) sound(&c->v, 0);
    page_draw();
}

/* A slot chosen: its LEAD answers counted again (the slot before may have
 * changed); its notes kept as they were. */
static void select_slot(unsigned i) {
    ch_slot = (uint8_t)i;
    ChSlot *c = slot();
    ch_answers = 0;
    if (c->v.n && c->mode == CH_MODE_LEAD && before() && before()->n) {
        ChVoicing out[CH_LEAD_MAX];
        ch_answers = (uint8_t)ch_lead(before(), c->root, c->type, c->flags & CH_BASS_ROOT, out, CH_LEAD_MAX);
    }
}

void ch_win_closed(void) {
    silence();
    ch_win = 0;
    if (ch_pushed) {
        ch_pushed = 0;
        FN(LPOP, const void *)(ch_layer);
    }
}

static void page_close(void) {
    if (ch_win) FN(WDESTROY, uint32_t *)(&ch_win);
    ch_win_closed();
}

/* PAGES' calls. */
unsigned ch_page_shown(void) {
    return ch_win != 0;
}

void ch_page_close(void) {
    page_close();
}

void ch_page_open(void) {
    if (ch_win) return;
    ready();
    ch_win_t = U8(UI_TRACK) & 7;
    ch_win_b = U8(BANK) & 15;
    ch_win = FN(WCREATE, int, int, int, int, int, void (*)(void))(PAGE_W, PAGE_H, PAGE_DX, 0, PAGE_CLASS, ch_win_closed);
    if (!ch_win) return;
    FN(LPUSH, const void *)(ch_layer);
    ch_pushed = 1;
    select_slot(ch_slot < CH_SLOTS ? ch_slot : 0);
    page_draw();
}

static void up_layer_tick(void);

void ch_page_tick(void) {
    up_layer_tick();
    if (ch_on_left && !--ch_on_left && !ch_on_held) silence();
    /* A chord key still held when the keys leave CHORDS (another trig mode,
     * audio mode): its release goes elsewhere, so its notes end here. */
    if (U32(TRIG_MODE) != 2 || !U32(MIDI_MODE))
        for (unsigned k = 0; k < CH_SLOTS; k++)
            if (ch_held_n[k]) ch_chord_key(k, 0);
    if (!ch_win) return;
    if (U32(PAGE) != 0 || !U32(MIDI_MODE) || U32(U32(SETUP) + 8)) { page_close(); return; }
    unsigned t = U8(UI_TRACK) & 7, b = U8(BANK) & 15;
    if (t != ch_win_t || b != ch_win_b) {
        silence();
        ch_win_t = (uint8_t)t;
        ch_win_b = (uint8_t)b;
        select_slot(ch_slot);
        page_draw();
    } else if ((U32(FUNC_HELD) != 0) != ch_func) {
        page_draw();
    }
}

/* An encoder turned. A ROOT, B TYPE: the chord; after a slot that holds
 * one, LEAD (the smoothest voicing from it), else built. C INV, D SPREAD,
 * E OCT: built. F VOIX: the next or previous LEAD answer, from any chord when
 * the slot before holds one. With FUNC held:
 * A-D move voice 1-4 by a semitone (EDIT), E the bass free or the root, F
 * the scale's chord on the next degree (SCALES; 3 or 4 notes as the type). */
static int wrap(int v, int delta, int n) {
    v = (v + delta) % n;
    return v < 0 ? v + n : v;
}

static int clampi(int v, int lo, int hi) {
    return v < lo ? lo : v > hi ? hi : v;
}

void ch_page_enc(unsigned index, int delta) {
    if (!ch_win) { ch_win_closed(); return; }
    ready();
    ChSlot *c = slot();
    unsigned lead_ok = before() && before()->n;
    if (U32(FUNC_HELD)) {
        if (index < CH_VOICES) {
            if (!c->v.n || !ch_move_voice(&c->v, index, delta)) return;
            c->mode = CH_MODE_EDIT;
            ch_answers = 0;
            sound(&c->v, 0);
            page_draw();
        } else if (index == 4) {
            c->flags ^= CH_BASS_ROOT;
            if (c->v.n) apply(c->mode == CH_MODE_LEAD);
            else page_draw();
        } else if (index == 5) {
            unsigned r, t, d = c->degree < 7 ? (unsigned)wrap(c->degree, delta, 7) : 0;
            unsigned four = ch_types[c->type].n == 4;
            if (!ch_diatonic(ch_scale(ch_win_t), d, four, &r, &t)) return;
            c->degree = (uint8_t)d;
            c->root = (uint8_t)r;
            c->type = (uint8_t)t;
            c->lead = 0;
            c->mode = lead_ok ? CH_MODE_LEAD : CH_MODE_BUILT;
            apply(1);
        }
        return;
    }
    switch (index) {
    case 0: c->root = (uint8_t)wrap(c->root, delta, 12); break;
    case 1: c->type = (uint8_t)wrap(c->type, delta, (int)ch_ntypes); break;
    case 2: c->inv = (uint8_t)clampi(c->inv + delta, 0, ch_types[c->type].n - 1); break;
    case 3: c->spread = (uint8_t)clampi(c->spread + delta, 0, CH_SPREADS - 1); break;
    case 4: c->oct = (uint8_t)clampi(c->oct + delta, 1, CH_OCT_MAX - 1); break;
    case 5:
        /* VOIX: whatever made the chord (built, LEAD, edited), the next or
         * previous LEAD answer when the slot before holds one; from built or
         * edited, the smoothest first (an edited chord led as what it is,
         * when ch_identify names it). */
        if (!c->v.n) return;
        if (!lead_ok) {
            FN(NOTIFY, const char *, unsigned)("NO CHORD BEFORE", 0x30);
            return;
        }
        if (c->mode != CH_MODE_LEAD || !ch_answers) {
            unsigned r, t;
            if (c->mode == CH_MODE_EDIT && ch_identify(&c->v, &r, &t)) { c->root = (uint8_t)r; c->type = (uint8_t)t; }
            c->mode = CH_MODE_LEAD;
            c->lead = 0;
        } else {
            c->lead = (uint8_t)clampi(c->lead + delta, 0, ch_answers - 1);
        }
        apply(1);
        return;
    default: return;
    }
    if (index <= 1) {
        c->degree = CH_NONE;
        c->lead = 0;
        c->mode = lead_ok ? CH_MODE_LEAD : CH_MODE_BUILT;
    } else {
        c->mode = CH_MODE_BUILT;
    }
    apply(1);
}

/* A trig key: alone, slot k chosen and heard while held; with FUNC held, the
 * key of the slot's octave (trig 1 = C) in or out of the chord (EDIT). */
void ch_key_down(unsigned code) {
    if (!ch_win) { ch_win_closed(); return; }
    unsigned k = code & 15;
    ready();
    if (U32(FUNC_HELD)) {
        ChSlot *c = slot();
        if (!ch_toggle(&c->v, c->oct * 12u + k)) return;
        c->mode = CH_MODE_EDIT;
        ch_answers = 0;
        unsigned r, t;
        if (ch_identify(&c->v, &r, &t)) { c->root = (uint8_t)r; c->type = (uint8_t)t; }
        sound(&c->v, 0);
        page_draw();
        return;
    }
    select_slot(k);
    sound(&slot()->v, 1);
    page_draw();
}

void ch_key_up(unsigned code) {
    if (ch_on_held && (code & 15) == ch_slot) silence();
}

/* An encoder pushed: nothing (a push nudges the knob). */
void ch_page_push(unsigned code, unsigned event) {
    (void)code;
    (void)event;
    if (!ch_win) ch_win_closed();
}

/* ---- CHORDS' box on the main screen (the trig mode's: SLOTS' in audio) ----
 * Its header, where SLOTS shows its page (1-16): the slots holding a chord,
 * n/16. Its picture, under it (x 61..117, y 7..24 from the bottom): the
 * chord the UI track played last -- its name and bass, under them its spread
 * (built), VOIX n (LEAD) or EDIT -- and the sixteen slots, a box each,
 * filled when it holds a chord, the one last played taller. */

static unsigned filled(const ChSlot *bank) {
    unsigned n = 0;
    for (unsigned k = 0; k < CH_SLOTS; k++) n += bank[k].v.n != 0;
    return n;
}

void ch_box_header(void) {
    ready();
    FN(TEXTF, uint32_t, uint32_t, int, int, int, int, const char *, const char *, unsigned)(
        FONT, SCREEN, 0x75, 0x1a, 2, 1, "00/16", "%d/16", filled(ch_bank[U8(BANK) & 15]));
}

void ch_box_picture(void) {
    ready();
    const ChSlot *bank = ch_bank[U8(BANK) & 15];
    unsigned cur = ch_current[U8(UI_TRACK) & 7];
    fill(SCREEN, 61, 7, 117, 24, 0);                /* down to y 7: no sample bar in MIDI mode (ch_box_bar) */
    for (unsigned k = 0; k < CH_SLOTS; k++) {
        int x = 63 + 3 * (int)k;
        if (cur == k + 1) fill(SCREEN, x, 7, x + 1, 11, 1);        /* the one last played: taller */
        else if (bank[k].v.n) fill(SCREEN, x, 8, x + 1, 10, 1);
        else fill(SCREEN, x, 8, x + 1, 8, 1);
    }
    if (!cur || !bank[cur - 1].v.n) return;
    const ChSlot *c = &bank[cur - 1];
    char line[24], name[CH_NAME];
    ch_name(&c->v, name);
    char *p = put_s(line, name);
    *p++ = ' ';
    p = put_s(p, note_name(c->v.note[0]));          /* the bass */
    *p = 0;
    text(FONT, SCREEN, 62, 19, line);
    /* Under it, how the chord was made: a built one's spread, LEAD's answer
     * (VOIX n, the page's n/m without the count: ch_lead is too slow for
     * the box's refresh), or EDIT. */
    if (c->mode == CH_MODE_BUILT) p = put_s(line, spread_cells[c->spread]);
    else if (c->mode == CH_MODE_LEAD) p = put_u(put_s(line, "VOIX "), c->lead + 1u);
    else p = put_s(line, "EDIT");
    *p = 0;
    text(FONT, SCREEN, 62, 13, line);
}

/* With the page open and FUNC held the trig keys type notes (ch_key_down:
 * key k = the slot's octave's C + k), so the LED pass shows them as a
 * keyboard (hooks.s ch_kbd_pass), the chord's notes green: SCALES draws it
 * (sc_keyboard: the track's scale in the CHROMATIC keys' colours, tonic
 * yellow, scale red). Without SCALES in the remix, or on KEY OFF, CHORDS
 * draws the same colours for C major (stock's CHROMATIC keyboard). */
void ch_kbd_leds(void) {
    ready();
    const ChSlot *c = slot();
    unsigned first = c->oct * 12u, green = 0;
    for (unsigned k = 0; k < CH_SLOTS; k++)
        for (unsigned v = 0; v < c->v.n; v++)
            if (c->v.note[v] == first + k) green |= 1u << k;
    if (ch_keyboard(ch_win_t, first, green)) return;
    for (unsigned k = 0; k < CH_SLOTS; k++) {
        unsigned deg = (first + k) % 12u, in = green >> k & 1;
        unsigned red = !in && (0xab5u >> deg & 1), grn = in || (red && deg == 0);
        FN(SET_LEVEL, unsigned, unsigned)(2 * k, red ? 15 : 0);
        FN(LED_ON, unsigned)(2 * k);
        FN(SET_LEVEL, unsigned, unsigned)(2 * k + 1, grn ? 15 : 0);
        FN(LED_ON, unsigned)(2 * k + 1);
    }
}

/* ---- TRIG + UP in GRID RECORDING: the chord chooser ----
 * While trig keys are held on a MIDI track, a layer of ours takes UP (its
 * press only: everything else goes on to stock's). UP opens a window of MAIN
 * MENU's size, drawn as SCALES' chooser (SYSTEM > PERSONALIZE's recipe): the
 * band, CHORDS at the right with an icon, a rule, five rows -- the bank's
 * slots that hold a chord, their number and name, the bass and a built
 * chord's spread at the right -- and the scroll arrows. UP / DOWN move the cursor and sound the
 * chord (HOLD_TICKS); YES copies it on the steps held when the window opened
 * and closes it; NO closes it. The chord already on the first held step is
 * marked with a ticked box, and the cursor starts there.
 *
 * A chord on a step: NOTE its bass, NOT2-4 64 + the other voices' intervals
 * (64, none, for a voice it lacks); VEL and LEN stay. Written as stock's lock
 * editor writes a lock (0x40050e60): the bank's RAM and its battery-backed
 * copy, the edited flags, 0x40027e00; then the track's records again. */

enum {
    WTITLE    = 0x40057c84u,    /* (window, title, 0): its frame and title band (SCALES') */
    WINSIDE   = 0x400356a8u,    /* (surface): the inside cleared */
    TEXTFIT   = 0x40012f88u,    /* (font, width, text) -> the characters that fit */
    ICON      = 0x400128a8u,    /* (icon, surface, x, y) */
    RULE      = 0x40011910u,    /* (surface, x, y, w, h) */
    ARROW_UP  = 0x400b4315u,    /* PERSONALIZE's scroll arrows */
    ARROW_DOWN = 0x400b4317u,
};
/* SCALES' chooser: MAIN MENU's 118 x 64 at x -1, STEMS's class 5; five rows
 * 7 apart, the first's bar at 34; the bar from 3 to 107; the mark at 77. */
enum { PK_W = 118, PK_H = 64, PK_DX = -1, PK_CLASS = 5, PK_ROWS = 5, PK_PITCH = 7, PK_ROW0 = 34,
       PK_BAR1 = 3, PK_BAR2 = 107, PK_MARK = 77, PK_RIGHT = 102 };

extern const uint8_t ch_up_layer[], ch_pk_layer[], ch_pk_icon[];
DATA uint8_t  ch_up_pushed;     /* ch_up_layer pushed: trigs held */
DATA uint32_t ch_pk_win;
DATA uint8_t  ch_pk_pushed;
DATA uint8_t  ch_pick;          /* the slot last placed + 1, 0 none */
uint8_t  ch_pk_rows[CH_SLOTS], ch_pk_n, ch_pk_sel, ch_pk_top, ch_pk_mark, ch_pk_t, ch_pk_b;
uint16_t ch_pk_held;
uint32_t ch_pk_page;
char ch_band[24];

static volatile uint8_t *step_locks(uint32_t base, unsigned t, unsigned step) {
    return (volatile uint8_t *)(uintptr_t)(base + U8(UI_PATTERN) * 0x8ed8u + 0x48d0u + t * 0x8b0u + 0x30u
                                           + step * 32u);
}

static unsigned chord_lock(const ChVoicing *v, unsigned k) {
    unsigned x = k < v->n ? 64u + v->note[k] - v->note[0] : 64u;
    return x > 127 ? 127 : x;
}

static void lock_step(unsigned t, unsigned step, const ChVoicing *v) {
    volatile uint8_t *ram = step_locks(U32(BANK_RAM), t, step), *cs1 = step_locks(CS1_PATTERNS, t, step);
    ram[0] = cs1[0] = v->note[0];
    for (unsigned k = 1; k < CH_VOICES; k++) ram[2 + k] = cs1[2 + k] = (uint8_t)chord_lock(v, k);
}

/* The slot whose chord the step holds + 1, 0 none. */
static unsigned step_chord(unsigned t, unsigned step, const ChSlot *bank) {
    volatile uint8_t *l = step_locks(U32(BANK_RAM), t, step);
    for (unsigned i = 0; i < CH_SLOTS; i++) {
        const ChVoicing *v = &bank[i].v;
        if (!v->n || l[0] != v->note[0]) continue;
        unsigned k = 1;
        while (k < CH_VOICES && l[2 + k] == chord_lock(v, k)) k++;
        if (k == CH_VOICES) return i + 1;
    }
    return 0;
}

static void pk_scroll(void) {
    if (ch_pk_sel < ch_pk_top) ch_pk_top = ch_pk_sel;
    else if (ch_pk_sel >= ch_pk_top + PK_ROWS) ch_pk_top = (uint8_t)(ch_pk_sel - (PK_ROWS - 1));
}

static void pk_draw(void) {
    if (!ch_pk_win) return;
    uint32_t s = ch_pk_win + 36;
    const ChSlot *bank = ch_bank[ch_pk_b];
    /* The band: the steps the chord goes on. */
    unsigned n = 0;
    for (unsigned k = 0; k < 16; k++) n += ch_pk_held >> k & 1;
    char *p = put_s(ch_band, "CHORD ON ");
    p = put_u(p, n);
    p = put_s(p, n == 1 ? " STEP" : " STEPS");
    *p = 0;
    FN(WTITLE, uint32_t, const char *, int)(ch_pk_win, ch_band, 0);
    FN(WINSIDE, uint32_t)(s);
    int w = (int)U32(s), top = (int)U32(s + 4) - 20;
    text(FONT, s, w - 6 - width(FONT, "CHORDS"), top + 2, "CHORDS");
    FN(ICON, const void *, uint32_t, int, int)(ch_pk_icon, s, 6, top);
    FN(RULE, uint32_t, int, int, int, int)(s, 4, top - 1, w - 6, 1);
    if (ch_pk_top > 0) text(FONT, s, w - 8, PK_ROW0 + 1, (const char *)ARROW_UP);
    if (ch_pk_top + PK_ROWS < ch_pk_n)
        text(FONT, s, w - 8, PK_ROW0 + 1 - (PK_ROWS - 1) * PK_PITCH, (const char *)ARROW_DOWN);
    for (unsigned r = 0; r < PK_ROWS && ch_pk_top + r < ch_pk_n; r++) {
        unsigned row = ch_pk_top + r, i = ch_pk_rows[row];
        int y = PK_ROW0 - (int)r * PK_PITCH;
        const ChSlot *c = &bank[i];
        char name[CH_NAME], line[24];
        ch_name(&c->v, name);
        p = put_u(line, i + 1);
        *p++ = ' ';
        p = put_s(p, name);
        *p = 0;
        text(FONT, s, 4, y + 1, line);
        if (ch_pk_mark == i + 1) text(FONT, s, PK_MARK - 9, y + 1, "\x16");     /* PERSONALIZE's ticked box */
        p = put_s(line, note_name(c->v.note[0]));                                /* the bass, the spread */
        if (c->mode == CH_MODE_BUILT) {
            *p++ = ' ';
            p = put_s(p, spread_cells[c->spread]);
        }
        *p = 0;
        text(FONT, s, PK_RIGHT - width(FONT, line), y + 1, line);
        if (row == ch_pk_sel) fill(s, PK_BAR1, y, PK_BAR2, y + 6, -1);
    }
    U32(SCRDIRTY) = 1;
}

void ch_pk_closed(void) {
    silence();
    ch_pk_win = 0;
    if (ch_pk_pushed) {
        ch_pk_pushed = 0;
        FN(LPOP, const void *)(ch_pk_layer);
    }
}

void ch_pk_close(void) {
    if (ch_pk_win) FN(WDESTROY, uint32_t *)(&ch_pk_win);
    ch_pk_closed();
}

/* UP with trigs held: the chooser on the bank's chords. */
void ch_trig_up(void) {
    ready();
    unsigned held = U8(HELD) << 8 | U8(HELD + 1);
    if (!held || ch_pk_win || !U32(MIDI_MODE)) return;
    const ChSlot *bank = ch_bank[U8(BANK) & 15];
    ch_pk_n = 0;
    for (unsigned i = 0; i < CH_SLOTS; i++)
        if (bank[i].v.n) ch_pk_rows[ch_pk_n++] = (uint8_t)i;
    if (!ch_pk_n) {
        FN(NOTIFY, const char *, unsigned)("NO CHORD IN THIS BANK", 0x30);
        return;
    }
    ch_pk_t = U8(UI_TRACK) & 7;
    ch_pk_b = U8(BANK) & 15;
    ch_pk_held = (uint16_t)held;
    ch_pk_page = U32(STEP_PAGE);
    unsigned first = 0;
    while (!(held >> first & 1)) first++;
    ch_pk_mark = (uint8_t)(ch_pk_page + first < 64 ? step_chord(ch_pk_t, ch_pk_page + first, bank) : 0);
    unsigned want = ch_pk_mark ? ch_pk_mark : ch_pick;
    ch_pk_sel = 0;
    for (unsigned r = 0; r < ch_pk_n; r++)
        if (ch_pk_rows[r] + 1u == want) ch_pk_sel = (uint8_t)r;
    ch_pk_top = 0;
    pk_scroll();
    ch_pk_win = FN(WCREATE, int, int, int, int, int, void (*)(void))(PK_W, PK_H, PK_DX, 0, PK_CLASS, ch_pk_closed);
    if (!ch_pk_win) return;
    FN(LPUSH, const void *)(ch_pk_layer);
    ch_pk_pushed = 1;
    pk_draw();
}

/* UP and DOWN in the chooser (with their repeats): one row, the chord heard. */
void ch_pk_ud(unsigned key) {
    if (!ch_pk_win) { ch_pk_closed(); return; }
    if (key == 0x33) {
        if (!ch_pk_sel) return;
        ch_pk_sel--;
    } else {
        if (ch_pk_sel + 1u >= ch_pk_n) return;
        ch_pk_sel++;
    }
    pk_scroll();
    sound(&ch_bank[ch_pk_b][ch_pk_rows[ch_pk_sel]].v, 0);
    pk_draw();
}

/* YES: the chord on the steps held when the window opened. */
void ch_pk_yes(void) {
    if (!ch_pk_win) { ch_pk_closed(); return; }
    unsigned i = ch_pk_rows[ch_pk_sel], t = ch_pk_t;
    const ChVoicing *v = &ch_bank[ch_pk_b][i].v;
    for (unsigned k = 0; k < 16; k++)
        if (ch_pk_held >> k & 1 && ch_pk_page + k < 64) lock_step(t, ch_pk_page + k, v);
    U32(U32(BANK_RAM) + 0x9b332u) = 1;
    U32(EDITED) = 1;
    FN(LOCKS_DONE, void)();
    FN(TRACK_DONE, unsigned)(8 + t);
    ch_pick = (uint8_t)(i + 1);
    ch_current[t] = (uint8_t)(i + 1);
    ch_pk_close();
    FN(PAGE_DRAW, int)(-1);
}

/* Each display tick (ch_page_tick): ch_up_layer pushed while trig keys are
 * held on a MIDI track with no window of ours, popped when they are let go;
 * the chooser closed when the unit leaves MIDI mode or the bank changes. */
static void up_layer_tick(void) {
    if (ch_pk_win && (!U32(MIDI_MODE) || ch_pk_b != (U8(BANK) & 15))) ch_pk_close();
    unsigned want = U32(MIDI_MODE) && (U8(HELD) | U8(HELD + 1)) && !ch_win && !ch_pk_win
                    && !U32(U32(SETUP) + 8);
    if (want && !ch_up_pushed) {
        FN(LPUSH, const void *)(ch_up_layer);
        ch_up_pushed = 1;
    } else if (!want && ch_up_pushed) {
        FN(LPOP, const void *)(ch_up_layer);
        ch_up_pushed = 0;
    }
}
