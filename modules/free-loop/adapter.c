/* FREE LOOP -- the firmware side: the pedal CC, the recorder-trig gate, the
 * UI task's tick, the TRACK + UP window and freeloop.work. Reads and writes
 * the firmware's own state; every address is cited here or in
 * INVESTIGATION.md. The state lives in hooks.s (loader-owned DRAM). */
#include "freeloop.h"

#define U8(a)  (*(volatile uint8_t *)(uintptr_t)(a))
#define U16(a) (*(volatile uint16_t *)(uintptr_t)(a))
#define U32(a) (*(volatile uint32_t *)(uintptr_t)(a))
#define FN(addr, ...) ((uint32_t (*)(__VA_ARGS__))(uintptr_t)(addr))

/* --- the sequencer and the project (INVESTIGATION.md, modules/trackpatterns) --- */
enum {
    TRANSPORT    = 0x800065b8u, /* long: 1 playing                                   */
    SEQ_BANK     = 0x800065bdu, /* the playing bank and pattern                      */
    SEQ_PATTERN  = 0x800065beu,
    UI_BANK      = 0x80000002u, /* the bank and pattern the UI shows                 */
    UI_PATTERN   = 0x80000004u,
    UI_TRACK     = 0x80000000u, /* the current audio track                           */
    CLOCK_RX     = 0x80000028u, /* bit 0: CLOCK RECEIVE (MIDI.md)                    */
    TRANSPORT_RX = 0x80000029u, /* TRANSPORT RECEIVE                                 */
    CHAN_MAP     = 0x46c7febeu, /* [channel]: bits 0-7 audio tracks, 8 the auto channel */
    TRACK_CHAN   = 0x8000003fu, /* + t: the track's MIDI channel, -1 off             */
    MUTES        = 0x80000008u, /* long: bit 8 + t the track muted (MIDI.md, CC 49)   */
    MUTES_CS1    = 0x100b14d4u, /* its CS1 mirror (0x4000ed60, the MIXER's 0x4003d3d8) */
    STEP_COUNT   = 0x800064d0u, /* + t: the track's step counter; the step handler runs one step
                                   ahead (port: a step's handler 5,514 samples before its trig at 120) */
    BANK_BLOB    = 0x400e21e0u, /* bank 0 in RAM                                     */
    BANK_STRIDE  = 0x9b340u,
    PAT_STRIDE   = 0x8ed8u,
    PAT_LENGTH   = 0x8e53u,     /* pattern length, scale, scale mode (0 NORMAL)      */
    PAT_SCALE    = 0x8e54u,
    PAT_PART     = 0x8e57u,     /* the pattern's Part, 0..3                          */
    PART_SLOTS   = 0x8ed80u + 0x2cau, /* + part * 0x18b2 + 5 t; Flex at +1, 0x80+r = recorder buffer r */
    PART_STRIDE  = 0x18b2u,
    PART_DB      = 0x46c82456u, /* long: the current bank's Part DB                  */
    PART_NOW     = 0x80000003u, /* the current Part                                  */
    REC_SETUP    = 0x8f382u,    /* DB + part * 6322 + 12 t: INAB INCD RLEN TRIG SRC3 */
    REC_POS      = 0x46c802c8u, /* [track]: the recorder's write position, samples   */
    LIMIT        = 0x46c7fe24u, /* [track]: the recorder's pass length, written at its stop */
    SLOT_REC     = 0x100b14f0u + 0x448u * 128u, /* + 0x448 r: recorder buffer r's settings */
    SLOT_STRIDE  = 0x448u,
    SLOT_END     = 0x130u,      /* its trim end, re-read at every trig (INVESTIGATION.md 3) */
    SLOT_TEMPO   = 0x114u,      /* the sample's tempo24: FLEX stretches by project / this    */
    SLOT_TEMPOQ  = 0x118u,      /* 2^31 / that tempo24 (0x400043e6)                          */
    SLOT_BARS    = 0x11cu,      /* LOOP_BARS x 100 of the region, and of the loop (0x40099074) */
    SLOT_BARS2   = 0x120u,
    VOICE        = 0x800049d8u, /* + 0xa8 t: byte 1 nonzero while the track's recorder runs */
    LANE_SLOT    = 0x8000082fu, /* + 72 t: the live lane's sample slot (lock slot 31), the one a trig
                                   plays (0x4000d492 -> 0x4000f450); a Part apply rewrites it from the Part */
    LANE_STRIDE  = 72u,
    PART_MACHINE = 0x8eda2u,    /* DB + part * 6322 + t: the machine, 1 FLEX */
    PART_CS1     = 0x100a4eceu, /* the current bank's working Parts in CS1 (PARTS.md 1) */
    PART_FLEX    = 0x2cbu,      /* + part * 0x18b2 + 5 t: the Flex slot byte */
    VOICE_STRIDE = 0xa8u,
};

/* --- stock routines --- */
enum {
    REC_POST   = 0x40005178u,   /* (track, word, 1): the recorder mailbox, as the REC keys */
    TEMPO_SET  = 0x4009c708u,   /* (tempo24): project or pattern tempo, 0x80001814 */
    MIDI_START = 0x4000a274u,   /* (slot): stock's MIDI Start, TRANSPORT RECEIVE on */
    MIDI_STOP  = 0x4000a1e0u,
    CLEAR_SLOT = 0x4002557cu,   /* (id): "RECORDING CLEARED!", ids 128-135 */
    NOTIFY     = 0x4005a2b8u,   /* (text, ticks): the stock toast */
    CC_SEND    = 0x40033e3cu,   /* (track, cc, value): AUDIO CC OUT's enqueue (REC_TRIG_MUTE's) */
    RELEASE    = 0x40008f84u,   /* (track): note-off, its AMP RELEASE (0x8000184a bit t; OTFX-T's call) */
    POST       = 0x400053d8u,   /* (kind, 0, 0, 0, 0, 0): the event CC 49 posts after a mute (0x4000f26a) */
    CLEARED    = 0x400b373eu,   /* "RECORDING CLEARED!" */
    F_COPY     = 0x40016388u,   /* (dst, src, 0) -> < 0 error */
};

/* --- the window (modules/tuner, modules/tempo-bus) --- */
enum {
    WCREATE  = 0x4005829cu,     /* (w, h, 0, 0, class, closed) -> handle */
    WFRAME   = 0x40056f4cu,     /* (handle) */
    WDESTROY = 0x40055db4u,     /* (&handle): handle = 0, the screen redrawn */
    LPUSH    = 0x40031494u,     /* (layer) */
    LPOP     = 0x4003146cu,
    CLEAR    = 0x40035624u,     /* (surface) */
    FONT     = 0x400ba876u,
    TEXT     = 0x40012bd8u,     /* (font, surface, x, y, limit, text); y = the bottom row */
    TWIDTH   = 0x40012f30u,     /* (font, limit, text) -> pixels */
    RULE     = 0x40011910u,     /* (surface, x, y, x2, 1) */
    INVERT   = 0x40012254u,     /* (surface, x1, y1, x2, y2, -1) */
    SCRDIRTY = 0x46c7c72cu,
    HELD     = 0x460fab40u,     /* the held track keys, bit t (modules/morph) */
    TIMER    = 0xfc07c00cu,     /* DTIM3's count: 132 MHz, free-running (modules/trackpatterns) */
    BOLD     = 0x400ba83au,     /* the bold 5x8 font (window titles, TEMPO): +8 widths[256], +12 u16
                                   offsets[256], +16 columns, a byte each, bit 0 the top row */
    TEMPO24  = 0x80001814u,     /* long: the project tempo, 24 x BPM */
    POP_W    = 128,
    POP_H    = 64,
    POP_LINGER = 30,            /* UI ticks the popup stays once nothing records (0.5 s) */
    WIN_W    = 118,
    WIN_H    = 64,
};

enum { FL_SETTLE = 4 };                /* UI ticks, ~67 ms */

enum { KEY_YES = 0x31, KEY_NO = 0x32, KEY_UP = 0x33, KEY_DOWN = 0x20, KEY_LEFT = 0x34, KEY_RIGHT = 0x21 };

/* hooks.s: the state, zeroed by the loader, and the file glue. */
extern FlConfig fl_cfg;
extern FlState  fl_st;
extern FlConfig fl_saved;              /* the payload last read or written */
extern uint32_t fl_now;                /* UI ticks */
extern uint8_t  fl_playing_was, fl_clear_all, fl_bank_seen, fl_nowrite, fl_backup, fl_win_row, fl_win_t;
extern uint8_t  fl_clear[FL_TRACKS];
extern uint8_t  fl_settle[FL_TRACKS];  /* ticks the cut end has held */
extern uint32_t fl_trim[FL_TRACKS];    /* a loop end to write once the take has stopped */
extern uint32_t fl_trim_t24[FL_TRACKS], fl_trim_bars[FL_TRACKS];   /* and its tempo, its bars x 100 */
extern uint32_t fl_keep[FL_TRACKS][6]; /* recorder r's buffer kept whole through a cut (keep_buffer) */
extern uint8_t  fl_keep_n[FL_TRACKS];  /* 0 none; 1 its stop awaited; then 1 + the ticks it has held */
extern FlAction fl_toast_act;
extern uint8_t  fl_toast_up, fl_win_pushed;
extern uint32_t fl_win;
extern char     fl_text[24], fl_path[260], fl_path2[260];
extern const uint8_t fl_layer[];
extern uint8_t  fl_msg[4];             /* a CC 49 handed to the stock handler */
extern uint8_t  fl_qany, fl_qrefresh;  /* an END toggle pending (hooks.s tests it); one applied */
extern uint8_t  fl_qinj;               /* a recorder trig to inject pending (hooks.s tests it) */
extern uint32_t fl_pop, fl_pop_key;     /* the REC popup's window, 0 none; what it shows */
extern uint8_t  fl_pop_t, fl_pop_idle, fl_pop_last;   /* its track; ticks with nothing to show; the last REC */
extern uint8_t  fl_armed, fl_odub;     /* the edge mark (hooks.s fl_glyph): bit t armed (blink on), overdubbing */
extern uint8_t  fl_qplay;              /* some pattern has a PLAY entry: the step handler calls fl_step_track */
extern uint8_t  fl_pat_t[FL_TRACKS];   /* the pattern each track last entered (PLAY), 0xff none */
extern uint8_t  fl_stopm;              /* bit t: PLAY STOP, the track's new trigs dropped */
extern uint8_t  fl_bpat[FL_TRACKS];    /* the pattern the record builder last built a trig of, per track */
extern uint8_t  fl_pop_msg, fl_pop_mt, fl_pop_mticks;   /* an UNDO-family toast the popup shows instead */
extern uint8_t  fl_src[FL_TRACKS];     /* [recorder r]: track + 1 whose setup r records with (hooks.s), 0 its own */
extern uint32_t fl_injd3[FL_TRACKS];   /* [recorder r]: the trig word it takes */
void     fl_stock_cc(const uint8_t *message);
extern uint32_t fl_takes[FL_TRACKS];   /* recorder trigs let through, per track (the port's gate) */
int32_t  fl_file_path(const char *format, char *out);
int32_t  fl_file_open(const char *path, const char *mode);
int32_t  fl_file_read(void *buffer, uint32_t length);
int32_t  fl_file_write(const void *buffer, uint32_t length);
void     fl_file_close(void);
uint32_t fl_file_crc(const void *buffer, uint32_t length);
void     fl_file_refuse(void);

#ifdef __mcoldfire__
_Static_assert(sizeof(FlConfig) == 1098, "hooks.s reserves 1098 bytes for fl_cfg and fl_saved");
_Static_assert(sizeof(FlState) <= 176, "hooks.s reserves 176 bytes for fl_st");
_Static_assert(sizeof(FlAction) == 16, "hooks.s reserves 16 bytes for fl_toast_act");
#endif

static unsigned playing(void) { return U32(TRANSPORT) == 1; }

/* The pattern record the UI shows (stopped) or the sequencer plays. */
static uint32_t pattern_record(unsigned *id) {
    unsigned bank = playing() ? U8(SEQ_BANK) : U8(UI_BANK);
    unsigned pattern = playing() ? U8(SEQ_PATTERN) : U8(UI_PATTERN);
    bank &= 15;
    pattern &= 15;
    if (id) *id = bank * 16 + pattern;
    return BANK_BLOB + bank * BANK_STRIDE + pattern * PAT_STRIDE;
}

/* The recorder buffer (0..7) track t plays in the pattern's Part, else its own. */
static unsigned buffer_of(unsigned t) {
    unsigned id;
    uint32_t pattern = pattern_record(&id);
    uint32_t blob = BANK_BLOB + (id >> 4) * BANK_STRIDE;
    unsigned part = U8(pattern + PAT_PART) & 3;
    unsigned flex = U8(blob + PART_SLOTS + part * PART_STRIDE + 5 * t + 1);
    return (flex & 0xf8) == 0x80 ? (flex & 7) : t;
}

static uint32_t slot_end(unsigned r) { return SLOT_REC + r * SLOT_STRIDE + SLOT_END; }

static void transport(unsigned start) {
    uint8_t rx = U8(TRANSPORT_RX);
    U8(TRANSPORT_RX) = 1;
    FN(start ? MIDI_START : MIDI_STOP, uint32_t)(0);   /* the handler's writable argument slot */
    U8(TRANSPORT_RX) = rx;
}

/* The start word of a take: the REC keys' (keys + 0x8000) | 0x10, the keys
 * the track's recorder setup has sources for (AB 0x1000, CD 0x2000, SRC3
 * 0x4000; INVESTIGATION.md 1). */
static uint32_t take_word(unsigned t) {
    uint32_t setup = U32(PART_DB) + REC_SETUP + U8(PART_NOW) * 6322u + 12u * t;
    uint32_t keys = (U8(setup + 0) ? 0x1000u : 0) | (U8(setup + 1) ? 0x2000u : 0) | (U8(setup + 4) ? 0x4000u : 0);
    return ((keys ? keys : 0x1000u) + 0x8000u) | 0x10u;
}

/* ---- the fade: a stock mute ramps its gain in 16 samples (0.36 ms, payload
 * A P:0x22e's asr #4; measured under the port), a click on a sustained loop.
 * FREE LOOP's mutes fade instead, through the track's LEVEL byte, which the
 * ColdFire smooths by 1/16 a frame (0x4000d6ce: ~15 ms to silence): LEVEL 0,
 * the mute FADE_TICKS later, LEVEL back (unless moved meanwhile). An unmute
 * sets the smoothed copy to 0 first: the sound rises over ~20-30 ms. MUTE
 * MODE OT only (0x800000dc = 0): the other modes fade on the AMP or keep the
 * FX tails, which a post-FX level cut would kill. */
enum {
    LEVEL      = 0x80000c50u,   /* + 2 t: the track's LEVEL byte */
    LEVEL_SM   = 0x80000c60u,   /* + 4 t: its smoothed copy (half word), what the frame builder sends */
    MUTE_MODE  = 0x800000dcu,   /* MUTE_MODES' PERSONALIZE word: 0 OT (stock) */
    FADE_TICKS = 3,             /* UI ticks (~50 ms) from LEVEL 0 to the mute */
};
extern uint8_t fl_fade[FL_TRACKS], fl_fade_lv[FL_TRACKS];   /* ticks to the mute, 0 none; LEVEL to restore */

static unsigned muted(unsigned t) { return ((U32(MUTES) >> (8 + t)) & 1) || fl_fade[t]; }

static unsigned fades(void) { return U32(MUTE_MODE) == 0 && playing(); }

static void fade_out(unsigned t) {
    if (fl_fade[t]) return;
    fl_fade_lv[t] = U8(LEVEL + 2 * t);
    U8(LEVEL + 2 * t) = 0;
    fl_fade[t] = FADE_TICKS;
}

/* A fade-out cancelled before its mute: LEVEL back, the smoothing brings the
 * sound up again (the track was never muted). Returns 1 if one was. */
static unsigned fade_cancel(unsigned t) {
    if (!fl_fade[t]) return 0;
    fl_fade[t] = 0;
    if (U8(LEVEL + 2 * t) == 0) U8(LEVEL + 2 * t) = fl_fade_lv[t];
    return 1;
}

/* The mute word's two stores (the MIXER's, 0x4003d3d2..d8), the screen
 * posted by the UI tick: the step handler's mutes and the fade's end. */
static void mute_bit(unsigned t, unsigned on) {
    uint32_t bit = 1u << (8 + t), word = U32(MUTES);
    word = on ? (word | bit) : (word & ~bit);
    U32(MUTES) = word;
    U32(MUTES_CS1) = word;
    fl_qrefresh = 1;
}

/* Mute or unmute track t as a CC 49 on its channel does (0x4000ec98), so
 * the screen, the LEDs and MUTE MODES follow. */
static void mute(unsigned t, unsigned how) {
    int8_t channel = (int8_t)U8(TRACK_CHAN + t);
    if (!how || channel < 0) return;
    if (how == FL_UNMUTE && fade_cancel(t)) return;                  /* never muted yet */
    if (fades()) {
        if (how == FL_MUTE) { fade_out(t); return; }                 /* the mute itself at the fade's end */
        U16(LEVEL_SM + 4 * t) = 0;                                   /* the unmute rises from 0 */
    }
    fl_msg[0] = (uint8_t)(0xB0 | (channel & 15));
    fl_msg[1] = 49;
    fl_msg[2] = how == FL_MUTE ? 127 : 0;
    fl_stock_cc(fl_msg);
}

static void toast(const FlAction *a) {
    if (a->toast == FL_T_NONE) return;
    if (a->track < FL_TRACKS && ((fl_cfg.popup >> a->track) & 1) && a->toast >= FL_T_UNDO
        && a->toast <= FL_T_NO_BUFFER) {                             /* the popup says it, big */
        fl_pop_msg = a->toast;
        fl_pop_mt = a->track;
        fl_pop_mticks = 60;
        return;
    }
    fl_toast_act = *a;
    fl_toast_up = 1;
}

/* Carry out what the engine asked for. The MIDI thread (a press) or the UI
 * task (a long press). */
static void perform(FlAction a) {
    unsigned t = a.track;
    switch (a.kind) {
    case FL_DO_TAKE:
        FN(REC_POST, uint32_t, uint32_t, uint32_t)(t, take_word(t), 1);
        break;
    case FL_DO_LAUNCH: {
        uint32_t pattern = pattern_record(0);
        FN(REC_POST, uint32_t, uint32_t, uint32_t)(t, 0x80, 1);       /* stop the take */
        U8(pattern + PAT_LENGTH) = a.tempo.len;
        U8(pattern + PAT_SCALE) = a.tempo.scale;
        FN(TEMPO_SET, uint32_t)(a.tempo.tempo24);
        static const uint8_t ticks[7] = {3, 4, 6, 8, 12, 24, 48};
        fl_trim[t] = a.tempo.loop;
        fl_trim_t24[t] = a.tempo.tempo24;
        fl_trim_bars[t] = ((uint32_t)a.tempo.len * ticks[a.tempo.scale & 7] * 100u + 48u) / 96u;   /* in 4/4 bars */
        transport(1);
        break;
    }
    case FL_DO_PLAY:       transport(1); break;
    case FL_DO_STOP:       transport(0); break;
    case FL_DO_STOP_CLEAR: transport(0); fl_clear[t] = 1; break;
    case FL_DO_CLEAR:      fl_clear[t] = 1; break;
    default:               break;
    }
    mute(t, a.mute);
    toast(&a);
}

/* An END toggle at a loop start, from the step handler (fl_gate_stub): the
 * two stores stock's own mute makes (the MIXER's, 0x4003d3d2..d8), no call;
 * the UI tick posts CC 49's event for the screen. The handler prepares a
 * step one step ahead, so the one for step 2 (counter 1) runs as step 1
 * sounds: the toggle lands at the loop's start, not a step before it. */
void fl_step_track(unsigned t) {
    if (t >= FL_TRACKS || U8(STEP_COUNT + t) != 1) return;
    unsigned q = fl_loop_start(&fl_st, t);
    unsigned id = (U8(SEQ_BANK) & 15) * 16 + (U8(SEQ_PATTERN) & 15);
    if (fl_qplay && fl_pat_t[t] != id) {                             /* the track's first step of a pattern: */
        fl_pat_t[t] = (uint8_t)id;                                   /* its PLAY entry, over a pending END */
        unsigned m = fl_play_entry(&fl_cfg, t, id), bit = 1u << t;
        if (m == FL_PLAY_STOP) {                                     /* no new trig (fl_trig_entry), the */
            fl_st.qpend[t] = 0;                                      /* note released on its amp envelope: */
            FN(RELEASE, uint32_t)(t);                                /* the FX tails ring out */
            fl_stopm = (uint8_t)(fl_stopm | bit);
        } else if (m != FL_PLAY_KEEP) {
            fl_st.qpend[t] = 0;
            q = m == FL_PLAY_PLAY ? FL_UNMUTE : FL_MUTE;
            fl_stopm = (uint8_t)(fl_stopm & ~bit);
        }
    }
    unsigned r = fl_replace_start(&fl_st, t);                       /* a REPLACE pass's, over the rest */
    if (r) q = r;
    fl_qany = (uint8_t)fl_end_pending(&fl_st);
    if (!q) return;
    if (q == FL_UNMUTE) {
        if (fade_cancel(t)) return;
        if (fades()) U16(LEVEL_SM + 4 * t) = 0;
        mute_bit(t, 0);
    } else if (fades()) {
        fade_out(t);
    } else {
        mute_bit(t, 1);
    }
}

/* The record builder about to build track t's trig of pattern p (0..15 in
 * the playing bank; hooks.s fl_trig_stub, a PLAY entry somewhere): its first
 * trig of a pattern takes the pattern's PLAY entry for STOP, so the entered
 * pattern's first step never sounds (fl_step_track then releases the note
 * before and applies the other entries at its first step). */
void fl_trig_entry(unsigned t, unsigned p) {
    if (t >= FL_TRACKS) return;
    unsigned id = (U8(SEQ_BANK) & 15) * 16 + (p & 15), bit = 1u << t;
    if (fl_bpat[t] == id) return;
    fl_bpat[t] = (uint8_t)id;
    unsigned m = fl_play_entry(&fl_cfg, t, id);
    if (m == FL_PLAY_STOP) fl_stopm = (uint8_t)(fl_stopm | bit);
    else if (m != FL_PLAY_KEEP) fl_stopm = (uint8_t)(fl_stopm & ~bit);
}

/* The recorder of track t's pass into the other buffer (FlState rec). */
static unsigned pass_recorder(unsigned t) {
    unsigned u = fl_undo_buffer(&fl_cfg, t);
    return fl_st.rec[t] == 2 && u ? u - 1 : t;
}

static unsigned recording(unsigned r) { return U8(VOICE + VOICE_STRIDE * r + 1) != 0; }

/* A recorder stopped as its key does (TRIG ONE2's 0x80); only a running one:
 * the stop writes LIMIT. */
static void stop_recorder(unsigned r) {
    if (recording(r)) FN(REC_POST, uint32_t, uint32_t, uint32_t)(r, 0x80, 1);
}

/* An UNDO in an in-place pass (UNDO TO) stops its recorder, and the stop
 * writes LIMIT and the slot's end at the cut (port: R5's end 353,022 ->
 * 88,717, bars 400 -> 100): REDO then played a quarter of the loop. The
 * buffer is the loop REDO gives back, so its end, tempo and bars are kept
 * and written again once the recorder is done (fl_ui_tick). */
static const uint16_t KEEP_AT[5] = {SLOT_END, SLOT_TEMPO, SLOT_TEMPOQ, SLOT_BARS, SLOT_BARS2};

static void keep_buffer(unsigned r) {
    uint32_t slot = SLOT_REC + r * SLOT_STRIDE;
    for (unsigned k = 0; k < 5; ++k) fl_keep[r][k] = U32(slot + KEEP_AT[k]);
    fl_keep[r][5] = U32(LIMIT + 4 * r);
    fl_keep_n[r] = 1;
}

static void keep_tick(unsigned r) {
    if (!fl_keep_n[r]) return;
    if (recording(r)) {                                              /* its stop not yet done, or */
        if (fl_keep_n[r] > 1) fl_keep_n[r] = 0;                      /* a new pass into it */
        return;
    }
    uint32_t slot = SLOT_REC + r * SLOT_STRIDE;
    unsigned moved = U32(LIMIT + 4 * r) != fl_keep[r][5];
    for (unsigned k = 0; k < 5; ++k) moved |= U32(slot + KEEP_AT[k]) != fl_keep[r][k];
    if (moved) {
        for (unsigned k = 0; k < 5; ++k) U32(slot + KEEP_AT[k]) = fl_keep[r][k];
        U32(LIMIT + 4 * r) = fl_keep[r][5];
        fl_keep_n[r] = 2;
    } else if (++fl_keep_n[r] > FL_SETTLE) {
        fl_keep_n[r] = 0;
    }
}

static FlAction act_toast(unsigned t, unsigned toast) {
    FlAction a = {0};
    a.kind = FL_DO_TOAST;
    a.track = (uint8_t)t;
    a.toast = (uint8_t)toast;
    return a;
}

/* CC 90 (REC), 91 (PLAY/STOP), 92 (UNDO) or 93 (END) on a track's channel (hooks.s,
 * the MIDI thread): value > 0 a press, 0 the release, for every audio track
 * the channel reaches (the auto channel: the current track). */
void fl_pedal(unsigned channel, unsigned cc, unsigned value) {
    uint32_t map = U32(CHAN_MAP + 4 * (channel & 15));
    unsigned tracks = map & 0xff;
    if (map & 0x100) tracks |= 1u << (U8(UI_TRACK) & 7);
    for (unsigned t = 0; t < FL_TRACKS; ++t) {
        if (!(tracks & (1u << t))) continue;
        if (cc == 90) {
            if (value) fl_pop_last = (uint8_t)t;
            if (!value) fl_release(&fl_st, t, FL_HELD_REC);
            else perform(fl_rec(&fl_st, &fl_cfg, t, playing(), U8(CLOCK_RX) & 1, U32(REC_POS + 4 * t), U32(TIMER)));
        } else if (cc == 92) {
            if (!value) continue;
            unsigned r = pass_recorder(t);
            FlAction a = fl_undo(&fl_st, &fl_cfg, t);
            if (a.kind == FL_DO_CUT && a.toast == FL_T_UNDO) keep_buffer(r);
            if (a.kind == FL_DO_CUT) stop_recorder(r);
            perform(a);
        } else if (cc == 93) {
            if (value) perform(fl_end(&fl_st, &fl_cfg, t, playing(), muted(t)));
            fl_qany = (uint8_t)fl_end_pending(&fl_st);
        } else if (!value) {
            fl_release(&fl_st, t, FL_HELD_PLAY);
        } else if (fl_stopm & (1u << t)) {                              /* STOPped (PLAY entry): back at */
            fl_stopm = (uint8_t)(fl_stopm & ~(1u << t));               /* its next trig */
            perform(act_toast(t, FL_T_UNMUTED));
        } else {
            perform(fl_play(&fl_st, &fl_cfg, t, U32(TIMER), playing(), muted(t), U32(REC_POS + 4 * t)));
            fl_qany = (uint8_t)fl_end_pending(&fl_st);                /* MUTE END: the press's END */
        }
    }
}

static unsigned injecting(void) {
    for (unsigned r = 0; r < FL_TRACKS; ++r)
        if (fl_st.inj[r]) return 1;
    return 0;
}

/* The step handler's recorder-trig test (hooks.s, the record builder
 * 0x4009d1e8 for track t, the step's recorder trig word `trig`, 0 none):
 * the word the step keeps (0: no recorder trig). A pass into a track's UNDO
 * buffer is that buffer's recorder's: its track's next call (the same step:
 * the builder runs T1..T8 in order) takes the looping track's word, and its
 * recorder the looping track's setup (fl_src, hooks.s fl_rec_stub). */
enum { KEY_AB = 0x1000u, KEY_CD = 0x2000u, KEY_SRC3 = 0x4000u };   /* a recorder trig word's sources */

uint32_t fl_gate_track(unsigned t, uint32_t trig) {
    if (t >= FL_TRACKS) return trig;
    unsigned src = fl_inject(&fl_st, t);
    if (src) {
        fl_src[t] = (uint8_t)src;
        fl_qinj = (uint8_t)injecting();
        ++fl_takes[t];
        return fl_injd3[t];
    }
    if (!trig) return 0;
    unsigned go = fl_gate(&fl_st, &fl_cfg, t);
    if (fl_st.rpass[t] == FL_RP_MUTE) {                              /* REPLACE: the inputs, not the */
        if (trig & (KEY_AB | KEY_CD)) trig &= ~KEY_SRC3;             /* track itself (0x5000 = AB + SRC3, */
        fl_qany = 1;                                                 /* port); muted from its loop start */
    }
    unsigned u = fl_undo_buffer(&fl_cfg, t);
    if (u && fl_st.inj[u - 1] == t + 1) {
        fl_injd3[u - 1] = trig;
        fl_qinj = 1;
    }
    if (go && fl_cfg.role[t] != FL_ROLE_OFF) ++fl_takes[t];   /* stock's own trigs not counted */
    return go ? trig : 0;
}

/* ---- the window: TRACK + UP ---- */

static void wtext(uint32_t surface, int x, int y, const char *text) {
    FN(TEXT, uint32_t, uint32_t, int, int, int, const char *)(FONT, surface, x, y, -1, text);
}

static int width(const char *text) { return (int)FN(TWIDTH, uint32_t, int, const char *)(FONT, -1, text); }

static void draw(void) {
    if (!fl_win) return;
    uint32_t surface = fl_win + 36;
    int h = (int)U32(surface + 4), top = h - 14;
    unsigned id;
    pattern_record(&id);
    FN(CLEAR, uint32_t)(surface);
    char *p = fl_text;
    *p++ = 'T'; *p++ = (char)('1' + fl_win_t);
    const char *title = " FREE LOOP";
    while (*title) *p++ = *title++;
    *p = 0;
    wtext(surface, 4, top + 2, fl_text);
    fl_text[0] = (char)('A' + (id >> 4));
    fl_text[1] = (char)('0' + ((id & 15) + 1) / 10);
    fl_text[2] = (char)('0' + ((id & 15) + 1) % 10);
    fl_text[3] = 0;
    wtext(surface, WIN_W - 6 - width(fl_text), top + 2, fl_text);
    FN(RULE, uint32_t, int, int, int, int)(surface, 4, top - 1, WIN_W - 6, 1);
    enum { SHOWN = 6 };                               /* rows that fit; the list scrolls */
    unsigned first = fl_win_row >= SHOWN ? fl_win_row - SHOWN + 1 : 0;
    for (unsigned row = first; row < FL_ROWS && row < first + SHOWN; ++row) {
        int y = top - 9 - 7 * (int)(row - first);
        wtext(surface, 6, y, fl_row_name(row));
        fl_row_value(&fl_cfg, fl_win_t, row, id, fl_text);
        wtext(surface, WIN_W - 8 - width(fl_text), y, fl_text);
        if (row == fl_win_row)
            FN(INVERT, uint32_t, int, int, int, int, int)(surface, 4, y - 1, WIN_W - 6, y + 5, -1);
    }
    U32(SCRDIRTY) = 1;
}

void fl_win_closed(void) {
    fl_win = 0;
    if (fl_win_pushed) {
        fl_win_pushed = 0;
        FN(LPOP, const void *)(fl_layer);
    }
}

void fl_win_close(void) {
    if (fl_win) FN(WDESTROY, uint32_t *)(&fl_win);
    fl_win_closed();
}

/* ---- the REC popup (POPUP ON): big, for reading from across the room ----
 * The state in the bold 5x8 font drawn 2x on a black band, the track 3x, an
 * icon that blinks (a disc for the free take, a ring and a beat-flash for an
 * overdub, a blinking ring while armed, a stop square while the cut pass
 * finishes), the role, and the pass's progress by bars or the take's time and
 * tempo. Opened by the UI tick as a track starts recording, closed
 * POP_LINGER ticks after nothing does; it takes no keys. Drawn again only
 * when what it shows changes. */

static void fill(uint32_t s, int x1, int y1, int x2, int y2, int mode) {   /* y from the top; 1 set, 0 clear */
    int h = (int)U32(s + 4);
    FN(INVERT, uint32_t, int, int, int, int, int)(s, x1, h - 1 - y2, x2, h - 1 - y1, mode);
}

static unsigned glyph_w(unsigned c) { return U8(U32(BOLD + 8) + c); }

static int big_width(const char *t, int k) {
    int w = 0;
    for (; *t; ++t) w += ((int)glyph_w((uint8_t)*t) + 1) * k;
    return w ? w - k : 0;
}

/* `t` in the bold font, k x k pixels a dot, its top row at y. */
static void big_text(uint32_t s, int x, int y, const char *t, int k, int mode) {
    uint32_t cols = U32(BOLD + 16), offs = U32(BOLD + 12);
    for (; *t; ++t) {
        unsigned c = (uint8_t)*t, w = glyph_w(c);
        uint32_t g = cols + U16(offs + 2 * c);
        for (unsigned i = 0; i < w; ++i) {
            unsigned bits = U8(g + i);
            for (int r = 0; r < 8;) {
                if (!((bits >> r) & 1)) { ++r; continue; }
                int r0 = r;
                while (r < 8 && ((bits >> r) & 1)) ++r;
                fill(s, x + (int)i * k, y + r0 * k, x + (int)i * k + k - 1, y + r * k - 1, mode);
            }
        }
        x += ((int)w + 1) * k;
    }
}

static void centred(uint32_t s, int y, const char *t, int k, int mode) {
    big_text(s, (POP_W - big_width(t, k)) / 2, y, t, k, mode);
}

static int isqrt(int v) {
    int r = 0;
    while ((r + 1) * (r + 1) <= v) ++r;
    return r;
}

static void disc(uint32_t s, int cx, int cy, int r, int mode) {
    for (int dy = -r; dy <= r; ++dy) {
        int dx = isqrt(r * r - dy * dy + r);
        fill(s, cx - dx, cy + dy, cx + dx, cy + dy, mode);
    }
}

static void ring(uint32_t s, int cx, int cy, int r) {
    disc(s, cx, cy, r, 1);
    disc(s, cx, cy, r - 3, 0);
}

static char *put_s(char *p, const char *t) {
    while (*t) *p++ = *t++;
    return p;
}

static char *put_u(char *p, unsigned v) {
    char d[10];
    unsigned n = 0;
    do { d[n++] = (char)('0' + v % 10); v /= 10; } while (v);
    while (n) *p++ = d[--n];
    return p;
}

static unsigned pop_state(unsigned t) {
    return fl_pop_state(&fl_st, &fl_cfg, t, recording(pass_recorder(t)) || recording(t));
}

void fl_pop_closed(void) { fl_pop = 0; }

static void pop_close(void) {
    if (fl_pop) FN(WDESTROY, uint32_t *)(&fl_pop);
    fl_pop = 0;
}

static void pop_draw(unsigned t, unsigned state) {
    static const char *const titles[6] = {"", "FIRST LOOP", "ARMED", "OVERDUB", "FINISHING", "REPLACE"};
    unsigned blink = (fl_now / 15) & 1;                              /* 2 Hz */
    unsigned bar = 0, bars = 0, prog = 0, tenths = 0;
    FlAction tempo = {0};
    if (state == FL_POP_TAKE) {
        uint32_t take = U32(REC_POS + 4 * t);
        tenths = take / 4410;
        if (fl_tempo(&fl_cfg, t, take, &tempo.tempo)) tempo.toast = FL_T_TEMPO;
    } else if (state == FL_POP_OVERDUB || state == FL_POP_ENDING || state == FL_POP_REPLACE) {
        unsigned pr = pass_recorder(t);
        uint32_t pos = recording(pr) ? U32(REC_POS + 4 * pr) : 0, len = U32(slot_end(buffer_of(t)));
        uint32_t t24 = U32(TEMPO24), step = t24 ? 15876000u / t24 : 0;   /* samples a 16th: 44100 x 60 x 24 / 4 */
        unsigned spb = fl_spb(fl_cfg.sig[t]);
        if (step && len) {
            uint32_t steps = pos / step;
            bar = steps / spb + 1;
            bars = (len / step + spb / 2) / spb;
            if (bars && bar > bars) bar = bars;
            prog = len >= 120 ? pos / (len / 120) : 0;
            if (prog > 120) prog = 120;
            if (state != FL_POP_ENDING) blink = (steps & 3) == 0;   /* the beat's first 16th */
        }
    }
    uint32_t key = state | t << 3 | blink << 6 | bar << 7 | bars << 12 | prog << 17 | (tenths & 0xff) << 24;
    if (key == fl_pop_key && fl_pop_t == t) return;
    fl_pop_key = key;
    fl_pop_t = (uint8_t)t;

    uint32_t s = fl_pop + 36;
    FN(CLEAR, uint32_t)(s);
    fill(s, 0, 0, POP_W - 1, 19, 1);
    centred(s, 2, titles[state], 2, 0);
    char badge[3] = {'T', (char)('1' + t), 0};
    big_text(s, 3, 24, badge, 3, 1);
    int cx = 55, cy = 35;
    switch (state) {
    case FL_POP_TAKE:    disc(s, cx, cy, blink ? 11 : 7, 1); break;
    case FL_POP_ARMED:   if (blink) ring(s, cx, cy, 11); else disc(s, cx, cy, 2, 1); break;
    case FL_POP_OVERDUB: ring(s, cx, cy, 11); if (blink) disc(s, cx, cy, 6, 1); break;
    case FL_POP_REPLACE: disc(s, cx, cy, blink ? 11 : 9, 1); disc(s, cx, cy, 4, 0); break;
    default:             fill(s, cx - 8, cy - 8, cx + 8, cy + 8, 1); if (!blink) fill(s, cx - 5, cy - 5, cx + 5, cy + 5, 0); break;
    }
    big_text(s, 72, 24, fl_cfg.role[t] == FL_ROLE_FREE ? "FREE" : "GRID", 2, 1);
    char *p = fl_text;
    if (state == FL_POP_TAKE) {
        p = put_u(p, tenths / 10); *p++ = '.'; *p++ = (char)('0' + tenths % 10); p = put_s(p, " S");
    } else if (state == FL_POP_ARMED) {
        p = put_s(p, "WAITING");
    } else if (bars) {
        p = put_s(p, "BAR "); p = put_u(p, bar); *p++ = '/'; p = put_u(p, bars);
    }
    *p = 0;
    big_text(s, 72, 42, fl_text, 1, 1);
    if (state == FL_POP_TAKE) {
        if (tempo.toast && fl_label(&tempo, fl_text)) centred(s, 53, fl_text, 1, 1);
    } else if (state == FL_POP_ARMED) {
        centred(s, 53, fl_st.repl[t] ? "REPLACES AT THE LOOP" : "STARTS AT THE LOOP", 1, 1);
    } else {
        fill(s, 2, 52, 125, 61, 1);
        fill(s, 3, 53, 124, 60, 0);
        if (prog) fill(s, 4, 54, 3 + (int)prog, 59, 1);
        for (unsigned i = 1; bars > 1 && i < bars && bars <= 16; ++i) {
            int x = 4 + (int)(i * 120 / bars);
            fill(s, x, 52, x, 61, -1);
        }
    }
    U32(SCRDIRTY) = 1;
}

/* An UNDO-family toast, big, for a second (toast() keeps it from stock's):
 * UNDO / REDO with an arrow back / on, UNDONE (a pass dropped) with a cross,
 * NO UNDO when there is nothing to undo or no UNDO buffer. */
static void pop_msg_draw(unsigned t, unsigned msg) {
    uint32_t key = 0x80000000u | msg << 8 | t;
    if (key == fl_pop_key) return;
    fl_pop_key = key;
    fl_pop_t = (uint8_t)t;
    uint32_t s = fl_pop + 36;
    FN(CLEAR, uint32_t)(s);
    fill(s, 0, 0, POP_W - 1, 19, 1);
    const char *title = msg == FL_T_UNDO ? "UNDO" : msg == FL_T_REDO ? "REDO" : msg == FL_T_UNDO_CUT ? "UNDONE" : "NO UNDO";
    centred(s, 2, title, 2, 0);
    char badge[3] = {'T', (char)('1' + t), 0};
    big_text(s, 3, 24, badge, 3, 1);
    int cx = 55, cy = 35;
    if (msg == FL_T_UNDO || msg == FL_T_REDO) {                      /* an arrow: back for UNDO, on for REDO */
        int dir = msg == FL_T_UNDO ? -1 : 1;
        for (int dy = -8; dy <= 8; ++dy) {
            int a = dy < 0 ? -dy : dy, tip = cx + dir * 11, base = cx + dir * 3;
            int x1 = tip - dir * a;
            fill(s, x1 < base ? x1 : base, cy + dy, x1 < base ? base : x1, cy + dy, 1);
        }
        fill(s, dir < 0 ? cx - 3 : cx - 10, cy - 3, dir < 0 ? cx + 10 : cx + 3, cy + 3, 1);   /* the shaft, joined */
    } else if (msg == FL_T_UNDO_CUT) {                               /* a cross */
        for (int i = -9; i <= 9; ++i) {
            fill(s, cx + i - 1, cy + i, cx + i + 1, cy + i, 1);
            fill(s, cx - i - 1, cy + i, cx - i + 1, cy + i, 1);
        }
    } else {
        fill(s, cx - 10, cy - 2, cx + 10, cy + 2, 1);               /* a dash */
    }
    big_text(s, 72, 24, fl_cfg.role[t] == FL_ROLE_FREE ? "FREE" : "GRID", 2, 1);
    const char *info = msg == FL_T_UNDO || msg == FL_T_REDO ? "NEXT LOOP"
                     : msg == FL_T_UNDO_CUT ? "PASS DROPPED" : msg == FL_T_NO_UNDO ? "NOTHING YET" : "NO BUFFER";
    big_text(s, 72, 42, info, 1, 1);
    unsigned n = fl_cfg.undoto[t], back = n && fl_st.anchor[t] >> 1 == n && (fl_st.anchor[t] & 1) == fl_st.cur[t];
    if (msg == FL_T_UNDO && back) {
        char *p = put_u(put_s(fl_text, "BACK TO PASS "), n);
        *p = 0;
    }
    centred(s, 53, msg == FL_T_UNDO ? (back ? fl_text : "THE LOOP BEFORE") : msg == FL_T_REDO ? "THE LAST PASS BACK"
                 : msg == FL_T_UNDO_CUT ? "THE LOOP KEPT" : "TRACK + UP: UNDO", 1, 1);
    U32(SCRDIRTY) = 1;
}

static void pop_open(void) {
    if (fl_pop) return;
    fl_pop = FN(WCREATE, int, int, int, int, int, void (*)(void))(POP_W, POP_H, 0, 0, 5, fl_pop_closed);
    fl_pop_key = 0xffffffffu;                                        /* no frame: the whole screen */
}

static void pop_tick(void) {
    if (fl_win) { pop_close(); fl_pop_mticks = 0; return; }        /* the panel wins */
    if (fl_pop_mticks) {
        --fl_pop_mticks;
        fl_pop_idle = 0;
        pop_open();
        if (fl_pop) pop_msg_draw(fl_pop_mt, fl_pop_msg);
        return;
    }
    unsigned t = fl_pop_last < FL_TRACKS ? fl_pop_last : 0, state = pop_state(t);
    for (unsigned k = 0; !state && k < FL_TRACKS; ++k) state = pop_state(t = k);
    if (!state) {
        if (fl_pop && ++fl_pop_idle >= POP_LINGER) pop_close();
        return;
    }
    fl_pop_idle = 0;
    pop_open();
    if (fl_pop) pop_draw(t, state);
}

/* UP while a TRACK key is held (the [TRACK]-held layer, hooks.s). */
void fl_key_up(unsigned code, unsigned event) {
    (void)code;
    if (event != 1) return;
    if (fl_win) { fl_win_close(); return; }
    pop_close();
    unsigned held = U32(HELD) & 0xff;
    if (!held) return;
    unsigned t = 0;
    while (!(held & (1u << t))) ++t;
    fl_win_t = (uint8_t)t;
    fl_win = FN(WCREATE, int, int, int, int, int, void (*)(void))(WIN_W, WIN_H, 0, 0, 5, fl_win_closed);
    if (!fl_win) return;
    FN(WFRAME, uint32_t)(fl_win);
    FN(LPUSH, const void *)(fl_layer);
    fl_win_pushed = 1;
    draw();
}

static void any_play(void) {
    unsigned any = 0;
    for (unsigned k = 0; k < FL_PATTERNS; ++k) any |= fl_cfg.pmode[k];
    fl_qplay = any != 0;
}

static void edit(int delta) {
    unsigned id;
    pattern_record(&id);
    if (fl_row_edit(&fl_cfg, fl_win_t, fl_win_row, id, delta)) {
        any_play();
        draw();
    }
}

/* The window's keys: UP / DOWN the row, LEFT / RIGHT the value, YES / NO close. */
void fl_key_win(unsigned code, unsigned event) {
    (void)event;
    if (!fl_win) { fl_win_closed(); return; }
    if (code == KEY_UP && fl_win_row > 0) { --fl_win_row; draw(); }
    else if (code == KEY_DOWN && fl_win_row < FL_ROWS - 1) { ++fl_win_row; draw(); }
    else if (code == KEY_LEFT) edit(-1);
    else if (code == KEY_RIGHT) edit(1);
    else if (code == KEY_YES || code == KEY_NO) fl_win_close();
}

/* The encoders A-F and LEVEL turn the selected value. */
void fl_enc_win(unsigned index, int delta) {
    (void)index;
    if (!fl_win) { fl_win_closed(); return; }
    edit(delta);
}

/* ---- the UI task's tick (hooks.s), 1/60 s. Returns 1 when it showed a toast. ---- */

static void clear_buffer(unsigned r) {
    FN(CLEAR_SLOT, uint32_t)(128 + r);
}

/* Track t plays recorder buffer r from its next trig: the Flex slot byte of
 * the current bank's four Parts (RAM and CS1, so a pattern change or the
 * transport's Part apply keeps it) and, on a FLEX track, the live lane. */
static void follow(unsigned t, unsigned r) {
    uint32_t db = U32(PART_DB);
    unsigned part = U8(PART_NOW) & 3;
    uint8_t slot = (uint8_t)(0x80 + r);
    if (U8(db + PART_SLOTS + part * PART_STRIDE + 5 * t + 1) == slot && U8(LANE_SLOT + LANE_STRIDE * t) == slot)
        return;
    for (unsigned p = 0; p < 4; ++p) {
        U8(db + PART_SLOTS + p * PART_STRIDE + 5 * t + 1) = slot;
        U8(PART_CS1 + PART_FLEX + p * PART_STRIDE + 5 * t) = slot;
    }
    if (U8(db + PART_MACHINE + part * PART_STRIDE + t) == 1) U8(LANE_SLOT + LANE_STRIDE * t) = slot;
}

/* Recorder r's RECORDING SETUP made track t's in the bank's four Parts (RAM
 * and CS1): stock reads some of it from the Part, not from the setup pointer
 * hooks.s lends (a pass into R5 with T5's RLEN MAX never posted its end,
 * port), so an UNDO buffer's track records as its loop's track. */
static void lend_setup(unsigned t, unsigned r) {
    uint32_t db = U32(PART_DB);
    for (unsigned p = 0; p < 4; ++p) {
        uint32_t from = db + REC_SETUP + p * PART_STRIDE + 12u * t, to = db + REC_SETUP + p * PART_STRIDE + 12u * r;
        uint32_t cs1 = PART_CS1 + (REC_SETUP - 0x8ed80u) + p * PART_STRIDE;
        for (unsigned k = 0; k < 12; ++k) {
            if (U8(to + k) != U8(from + k)) U8(to + k) = U8(from + k);
            if (U8(cs1 + 12u * r + k) != U8(from + k)) U8(cs1 + 12u * r + k) = U8(from + k);
        }
    }
}

unsigned fl_ui_tick(void) {
    ++fl_now;
    unsigned run = playing();
    if (fl_playing_was && !run) {
        for (unsigned t = 0; t < FL_TRACKS; ++t)
            if (fl_st.rec[t]) stop_recorder(pass_recorder(t));
        fl_stopped(&fl_st);
        fl_qany = 0;
        for (unsigned t = 0; t < FL_TRACKS; ++t) fl_pat_t[t] = fl_bpat[t] = 0xff;   /* PLAY: entered again */
    }
    for (unsigned t = 0; t < FL_TRACKS; ++t) {                       /* a fade-out's end: the mute */
        if (!fl_fade[t] || --fl_fade[t]) continue;
        mute_bit(t, 1);
        if (U8(LEVEL + 2 * t) == 0) U8(LEVEL + 2 * t) = fl_fade_lv[t];
    }
    {
        unsigned armed = 0, odub = 0, on = (fl_now / 15) & 1;       /* the edge mark, 2 Hz */
        for (unsigned t = 0; t < FL_TRACKS; ++t) {
            if (fl_cfg.role[t] == FL_ROLE_OFF) continue;
            if (fl_st.st[t] == FL_ARMED && on) armed |= 1u << t;
            if (fl_st.st[t] == FL_OVERDUB) odub |= 1u << t;
        }
        fl_armed = (uint8_t)armed;
        fl_odub = (uint8_t)odub;
    }
    if (fl_qrefresh) {
        fl_qrefresh = 0;
        FN(POST, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t)(0x1a, 0, 0, 0, 0, 0);
    }
    fl_playing_was = (uint8_t)run;

    unsigned shown = 0;
    unsigned bank = U8(SEQ_BANK);
    if (fl_bank_seen != 0xff && bank != fl_bank_seen && run) fl_clear_all = 1;   /* a bank change */
    fl_bank_seen = (uint8_t)bank;
    if (fl_clear_all) {
        fl_clear_all = 0;
        for (unsigned t = 0; t < FL_TRACKS; ++t)
            if (fl_st.st[t] == FL_TAKE) FN(REC_POST, uint32_t, uint32_t, uint32_t)(t, 0x80, 1);
        for (unsigned r = 0; r < 8; ++r) clear_buffer(r), fl_keep_n[r] = 0;
        fl_reset(&fl_st);
        FN(NOTIFY, uint32_t, uint32_t)(CLEARED, 0x30);
        shown = 1;
    }
    if (run) fl_pattern(&fl_st, &fl_cfg, (bank & 15) * 16 + (U8(SEQ_PATTERN) & 15));

    for (unsigned t = 0; t < FL_TRACKS; ++t) {
        unsigned r = buffer_of(t);
        /* The take has stopped: cut it to L and stamp it with its own tempo
         * and bars, so FLEX plays it at rate 1 (its stretch is project tempo
         * / the slot's). Stock (0x400043ba, every frame the recorder writes,
         * the fade-out included, then the sanitiser 0x400994b4) rewrites
         * these from the tempo latched as it records, until the recorder
         * is done: they are written again until they have held FL_SETTLE ticks. */
        if (fl_trim[t] && !U8(VOICE + VOICE_STRIDE * t + 1) && U32(slot_end(r))) {
            uint32_t slot = slot_end(r) - SLOT_END;
            if (U32(slot + SLOT_END) != fl_trim[t] || U32(slot + SLOT_TEMPO) != fl_trim_t24[t]
                || U32(slot + SLOT_BARS) != fl_trim_bars[t]) {
                U32(slot + SLOT_END) = fl_trim[t];
                U32(slot + SLOT_TEMPO) = fl_trim_t24[t];
                U32(slot + SLOT_TEMPOQ) = 0x80000000u / fl_trim_t24[t];
                U32(slot + SLOT_BARS) = fl_trim_bars[t];
                U32(slot + SLOT_BARS2) = fl_trim_bars[t];
                fl_settle[t] = 0;
            } else if (++fl_settle[t] >= FL_SETTLE) {
                fl_trim[t] = 0;
            }
        }
        unsigned pr = pass_recorder(t);                              /* before fl_hold: REC's UNDO */
        FlAction h = fl_hold(&fl_st, &fl_cfg, t, U32(TIMER), run, muted(t));
        if (h.kind == FL_DO_CUT && h.toast == FL_T_UNDO) keep_buffer(pr);
        if (h.kind == FL_DO_CUT) stop_recorder(pr);
        perform(h);
        if (h.toast >= FL_T_END_STOP && h.toast <= FL_T_END_CANCEL) fl_qany = (uint8_t)fl_end_pending(&fl_st);
        unsigned u = fl_undo_buffer(&fl_cfg, t);
        if (fl_st.rpass[t] == FL_RP_NOW) {                           /* a REPLACE pass ended by a stop */
            fl_st.rpass[t] = FL_RP_NONE;                             /* or a clear: heard again */
            mute(t, FL_UNMUTE);
        }
        if (fl_clear[t]) {
            /* A take or a pass still recording is stopped first, and the
             * buffers cleared once its recorder is done: the stop writes
             * LIMIT, and a clear before it would leave the cut take. */
            unsigned p = fl_st.rec[t] ? pass_recorder(t) : t, busy = recording(p) || (!fl_src[t] && recording(t));
            if (fl_clear[t] == 1) {
                stop_recorder(p);
                if (!fl_src[t] && p != t) stop_recorder(t);
                fl_clear[t] = 2;
            }
            if (!busy) {
                fl_clear[t] = 0;
                if (u) {
                    clear_buffer(t);
                    clear_buffer(u - 1);
                    fl_keep_n[u - 1] = 0;
                    fl_keep_n[t] = 0;
                } else {
                    clear_buffer(r);
                }
                fl_cleared(&fl_st, t);
            }
        }
        if (fl_st.swap[t] && recording(pass_recorder(t))) fl_rec_running(&fl_st, t);
        if (u) {
            follow(t, fl_st.cur[t] ? u - 1 : t);
            lend_setup(t, u - 1);
        }
        if (!run && fl_st.st[t] == FL_IDLE && !fl_trim[t])
            fl_st.has[t] = U32(slot_end(r)) != 0;
    }
    for (unsigned r = 0; r < FL_TRACKS; ++r) keep_tick(r);
    for (unsigned r = 0; r < FL_TRACKS; ++r) {        /* a borrowed setup, until its pass is over */
        if (!fl_src[r] || fl_st.inj[r] || recording(r)) continue;
        unsigned t = fl_src[r] - 1;
        if (!(fl_st.rec[t] == 2 && fl_undo_buffer(&fl_cfg, t) == r + 1)) fl_src[r] = 0;
    }
    pop_tick();
    if (fl_toast_up && !shown) {
        fl_toast_up = 0;
        if (fl_label(&fl_toast_act, fl_text)) {
            FN(NOTIFY, const char *, uint32_t)(fl_text, 0x30);
            shown = 1;
        }
    }
    return shown;
}

/* ---- freeloop.work, through STORE (modules/store/README.md) ----
 * 'FLPW', version 4, payload length 1098, CRC-32 of the payload; then the
 * payload, fl_cfg. Versions 3 (1090 bytes, no UNDO TO), 2 (578, no PLAY entries) and 1 (570, no UNDO
 * buffers) are read too. A file that is not that is never written over: STORE
 * lists it (client 5) and asks. No file: every track OFF. */

enum { MAGIC = 0x464c5057u, VERSION = 4u, V1_SIZE = 570u, V2_SIZE = 578u, V3_SIZE = 1090u };
static const char WORK[] = "%s/freeloop.work", STRD[] = "%s/freeloop.strd", BAK[] = "%s/freeloop.bak";

static void copy_bytes(void *dst, const void *src, uint32_t n) {
    uint8_t *d = dst;
    const uint8_t *s = src;
    while (n--) *d++ = *s++;
}

static unsigned same(const void *a, const void *b, uint32_t n) {
    const uint8_t *x = a, *y = b;
    while (n--) if (*x++ != *y++) return 0;
    return 1;
}

static void zero(void *p, uint32_t n) {
    uint8_t *d = p;
    while (n--) *d++ = 0;
}

static void file_copy(const char *to, const char *from) {
    fl_file_path(to, fl_path);
    fl_file_path(from, fl_path2);
    FN(F_COPY, const char *, const char *, uint32_t)(fl_path, fl_path2, 0);
}

static void save(void) {
    if (fl_nowrite || same(&fl_cfg, &fl_saved, sizeof fl_cfg)) return;
    if (fl_backup) {
        fl_backup = 0;
        file_copy(BAK, WORK);
    }
    uint32_t head[4] = {MAGIC, VERSION, sizeof fl_cfg, fl_file_crc(&fl_cfg, sizeof fl_cfg)};
    fl_file_path(WORK, fl_path);
    if (fl_file_open(fl_path, "w") < 0) return;
    int32_t ok = fl_file_write(head, sizeof head) == 1 && fl_file_write(&fl_cfg, sizeof fl_cfg) == 1;
    fl_file_close();
    if (ok) copy_bytes(&fl_saved, &fl_cfg, sizeof fl_cfg);
}

static void load(void) {
    uint32_t head[4];
    fl_nowrite = 0;
    fl_backup = 0;
    fl_reset(&fl_st);
    zero(&fl_cfg, sizeof fl_cfg);
    fl_file_path(WORK, fl_path);
    if (fl_file_open(fl_path, "r") >= 0) {
        unsigned good = fl_file_read(head, sizeof head) == 1 && head[0] == MAGIC
                     && ((head[1] == VERSION && head[2] == sizeof fl_cfg) || (head[1] == 3 && head[2] == V3_SIZE)
                         || (head[1] == 2 && head[2] == V2_SIZE)
                         || (head[1] == 1 && head[2] == V1_SIZE))
                     && fl_file_read(&fl_cfg, head[2]) == 1;
        fl_file_close();
        if (!good || fl_file_crc(&fl_cfg, head[2]) != head[3]) {
            zero(&fl_cfg, sizeof fl_cfg);
            fl_nowrite = 1;
            fl_file_refuse();
        }
    }
    copy_bytes(&fl_saved, &fl_cfg, sizeof fl_cfg);
    any_play();
    fl_stopm = 0;
    for (unsigned t = 0; t < FL_TRACKS; ++t) fl_pat_t[t] = fl_bpat[t] = 0xff;
}

void fl_st_loadall_post(void)  { load(); }
void fl_st_loadmask_post(void) { load(); }
void fl_st_newproj(void) {
    fl_nowrite = 0;
    fl_backup = 0;
    fl_reset(&fl_st);
    zero(&fl_cfg, sizeof fl_cfg);
    copy_bytes(&fl_saved, &fl_cfg, sizeof fl_cfg);
    any_play();
}
void fl_st_bankw_post(void) { save(); }
void fl_st_pstore_pre(void) { save(); }
void fl_st_pstore_post(void) {
    if (!fl_nowrite) file_copy(STRD, WORK);
}
void fl_st_preload_post(void) {
    fl_file_path(WORK, fl_path);
    fl_file_path(STRD, fl_path2);
    if ((int32_t)FN(F_COPY, const char *, const char *, uint32_t)(fl_path, fl_path2, 0) >= 0) load();
}
/* A refused freeloop.work: IGNORE (0) / OVERWRITE (1) / BACKUP (2); the
 * writes happen at the next save. */
void fl_answer(unsigned answer) {
    if (!answer) return;
    if (answer == 2) fl_backup = 1;
    fl_nowrite = 0;
    zero(&fl_saved, sizeof fl_saved);
    fl_saved.role[0] = 0xff;                     /* no role: matches nothing, the next save writes */
}
