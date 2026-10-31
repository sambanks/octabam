/* FREE LOOP -- the loop-pedal engine (freeloop.h). */
#include "freeloop.h"

#define SAMPLES_PER_TICK_X24 2646000u   /* 44,100 x 60 / 24 ticks per beat, times tempo24's 24 */
#define TEMPO24_MIN 720u                /* 30 BPM */
#define TEMPO24_MAX 7200u               /* 300 BPM */
#define DEF_LO 70u
#define DEF_HI 160u

/* Ticks per step of the pattern scales 2X, 3/2X, 1X, 3/4X, 1/2X, 1/4X, 1/8X (0x400aba50). */
static const uint8_t scale_ticks[7] = {3, 4, 6, 8, 12, 24, 48};
/* The scales a loop may take, in order of preference: 1X, 1/2X, 1/4X, 1/8X. */
static const uint8_t scale_pref[4] = {2, 4, 5, 6};
static const uint8_t auto_bars[5] = {1, 2, 4, 8, 16};
static const uint8_t sig_spb[FL_SIGS] = {16, 12, 12, 20, 14, 18, 24, 8};
static const char *const sig_names[FL_SIGS] = {"4/4", "3/4", "6/8", "5/4", "7/8", "9/8", "12/8", "2/4"};

unsigned fl_spb(unsigned sig) { return sig_spb[sig < FL_SIGS ? sig : 0]; }
const char *fl_sig_name(unsigned sig) { return sig_names[sig < FL_SIGS ? sig : 0]; }

uint32_t fl_loop_len(uint32_t ticks, uint32_t tempo24) {
    uint32_t q = SAMPLES_PER_TICK_X24 / tempo24, r = SAMPLES_PER_TICK_X24 % tempo24;
    return ticks * q + (ticks * r + tempo24 / 2) / tempo24;
}

/* The pattern for `steps` sequencer steps: its length (2..64) and scale. */
static unsigned pattern_for(uint32_t steps, FlTempo *out) {
    for (unsigned i = 0; i < 4; ++i) {
        uint32_t ticks = scale_ticks[scale_pref[i]], all = steps * 6u;
        if (all % ticks == 0 && all / ticks >= 2 && all / ticks <= 64) {
            out->len = (uint8_t)(all / ticks);
            out->scale = scale_pref[i];
            return 1;
        }
    }
    return 0;
}

/* The tempo for N bars of `spb` steps over a take of `take` samples. */
static unsigned tempo_for(uint32_t take, unsigned spb, unsigned bars, FlTempo *out) {
    if (!pattern_for((uint32_t)spb * bars, out)) return 0;
    uint32_t ticks = (uint32_t)out->len * scale_ticks[out->scale];
    if (fl_loop_len(ticks, TEMPO24_MAX) > take) return 0;            /* faster than 300 BPM */
    uint32_t lo = TEMPO24_MIN, hi = TEMPO24_MAX;                     /* L(hi) <= take */
    if (fl_loop_len(ticks, lo) <= take) {
        if (take - fl_loop_len(ticks, lo) > fl_loop_len(ticks, lo) / 1000) return 0;   /* slower than 30 BPM */
        hi = lo;
    }
    while (hi - lo > 1) {                                            /* L(lo) > take >= L(hi) */
        uint32_t mid = lo + (hi - lo) / 2;
        if (fl_loop_len(ticks, mid) <= take) hi = mid; else lo = mid;
    }
    out->tempo24 = (uint16_t)hi;
    out->bars = (uint8_t)bars;
    out->loop = fl_loop_len(ticks, hi);
    return 1;
}

unsigned fl_tempo(const FlConfig *c, unsigned t, uint32_t take, FlTempo *out) {
    if (t >= FL_TRACKS || take == 0) return 0;
    unsigned spb = fl_spb(c->sig[t]);
    if (c->bars[t]) return tempo_for(take, spb, c->bars[t], out);
    uint32_t lo = 24u * (c->bpm_lo[t] ? c->bpm_lo[t] : DEF_LO);
    uint32_t hi = 24u * (c->bpm_hi[t] ? c->bpm_hi[t] : DEF_HI);
    for (unsigned i = 0; i < 5; ++i) {
        FlTempo got;
        if (!tempo_for(take, spb, auto_bars[i], &got)) continue;
        if (got.tempo24 < lo) continue;                              /* too slow: more bars */
        if (got.tempo24 > hi) return 0;                              /* the range was skipped */
        *out = got;
        return 1;
    }
    return 0;
}

static FlAction act(unsigned kind, unsigned t, unsigned toast) {
    FlAction a = {0};
    a.kind = (uint8_t)kind;
    a.track = (uint8_t)t;
    a.toast = (uint8_t)toast;
    return a;
}

static unsigned any_loop(const FlState *s) {
    for (unsigned t = 0; t < FL_TRACKS; ++t)
        if (s->has[t]) return 1;
    return 0;
}

static unsigned taking(const FlState *s) {
    for (unsigned t = 0; t < FL_TRACKS; ++t)
        if (s->st[t] == FL_TAKE) return t + 1;
    return 0;
}

/* The end of track t's free take: the tempo, or a refusal (the take goes on). */
static FlAction launch(FlState *s, const FlConfig *c, unsigned t, uint32_t take) {
    FlAction a = act(FL_DO_LAUNCH, t, FL_T_TEMPO);
    if (!fl_tempo(c, t, take, &a.tempo)) return act(FL_DO_TOAST, t, FL_T_RANGE);
    s->st[t] = FL_IDLE;
    s->has[t] = 1;
    s->npass[t] = 1;
    s->anchor[t] = c->undoto[t] == 1 ? (uint8_t)(2 | s->cur[t]) : 0;
    return a;
}

/* A press held from `now`: its long press (fl_hold) clears the track, or
 * for REC on a track with an UNDO buffer, undoes. */
static void hold(FlState *s, unsigned t, unsigned pedal, uint32_t now) {
    s->held[t] = (uint8_t)pedal;
    s->down[t] = now;
    s->undo[t] = 0;
    s->started[t] = 0;
}

static FlAction rec(FlState *s, const FlConfig *c, unsigned t, unsigned playing, unsigned slave, uint32_t take) {
    if (s->st[t] == FL_TAKE) return launch(s, c, t, take);
    if (taking(s)) return act(FL_DO_TOAST, t, FL_T_BUSY);
    if (!playing && c->role[t] == FL_ROLE_FREE && !any_loop(s) && s->st[t] == FL_IDLE) {
        if (slave) return act(FL_DO_TOAST, t, FL_T_SLAVE);
        s->st[t] = FL_TAKE;
        return act(FL_DO_TAKE, t, FL_T_FREE);
    }
    if (s->st[t] == FL_IDLE) {                                       /* armed: playing, the next */
        s->st[t] = FL_ARMED;                                         /* recorder trig; stopped, the */
        return act(FL_DO_TOAST, t, FL_T_ARMED);                      /* first one after PLAY */
    }
    s->st[t] = FL_IDLE;                                              /* ARMED or OVERDUB: cut */
    s->repl[t] = 0;
    return act(FL_DO_TOAST, t, FL_T_OVERDUB_OFF);
}

FlAction fl_rec(FlState *s, const FlConfig *c, unsigned t, unsigned playing, unsigned slave, uint32_t take,
                uint32_t now) {
    if (t >= FL_TRACKS || c->role[t] == FL_ROLE_OFF) return act(FL_DO_NOTHING, t, FL_T_NONE);
    uint8_t was = s->st[t];
    FlAction a = rec(s, c, t, playing, slave, take);
    if (a.kind == FL_DO_TAKE || a.toast == FL_T_ARMED || a.toast == FL_T_OVERDUB_OFF) {
        hold(s, t, FL_HELD_REC, now);
        s->undo[t] = was;                                            /* REC: the state before the press */
        if (a.kind == FL_DO_TAKE) s->started[t] = 2;
    }
    return a;
}

FlAction fl_play(FlState *s, const FlConfig *c, unsigned t, uint32_t now, unsigned playing, unsigned muted,
                 uint32_t take) {
    if (t >= FL_TRACKS || c->role[t] == FL_ROLE_OFF) return act(FL_DO_NOTHING, t, FL_T_NONE);
    if (s->st[t] != FL_TAKE && taking(s)) return act(FL_DO_TOAST, t, FL_T_BUSY);   /* no press held: no clear */
    hold(s, t, FL_HELD_PLAY, now);
    if (s->st[t] == FL_TAKE) {
        FlAction a = launch(s, c, t, take);
        if (a.kind == FL_DO_LAUNCH) s->started[t] = 3;
        return a;
    }
    if (!playing) {
        FlAction a = act(FL_DO_PLAY, t, FL_T_PLAY);
        s->started[t] = 1;
        if (muted) {
            a.mute = FL_UNMUTE;
            s->undo[t] = FL_MUTE;
        }
        return a;
    }
    if ((c->endmute >> t) & 1) {                                     /* MUTE END: the press is END */
        s->started[t] = 4;
        return fl_end(s, c, t, playing, muted);
    }
    s->started[t] = 5;                                               /* MUTE NOW: at the press */
    FlAction a = act(FL_DO_NOTHING, t, muted ? FL_T_UNMUTED : FL_T_MUTED);
    a.mute = muted ? FL_UNMUTE : FL_MUTE;
    s->undo[t] = muted ? FL_MUTE : FL_UNMUTE;                        /* held: undone, then END */
    return a;
}

FlAction fl_hold(FlState *s, const FlConfig *c, unsigned t, uint32_t now, unsigned playing, unsigned muted) {
    if (t >= FL_TRACKS || !s->held[t] || (s->held[t] & FL_HELD_DONE)) return act(FL_DO_NOTHING, t, FL_T_NONE);
    if (c->role[t] == FL_ROLE_OFF || now - s->down[t] < FL_LONG) return act(FL_DO_NOTHING, t, FL_T_NONE);
    s->held[t] |= FL_HELD_DONE;
    if (s->held[t] & FL_HELD_PLAY) {                                 /* MUTE NOW: the press's mute */
        if (s->started[t] != 5) return act(FL_DO_NOTHING, t, FL_T_NONE);   /* undone, then END from */
        FlAction a = fl_end(s, c, t, playing, s->undo[t] == FL_MUTE);    /* the state before it */
        a.mute = s->undo[t];
        return a;
    }
    if (s->started[t] != 2 && playing && !muted) {                   /* REC, the track heard */
        if (!s->rec[t]) s->st[t] = s->undo[t];                       /* the press's arm / cut undone */
        return fl_undo(s, c, t);                                     /* then UNDO, as CC 92 */
    }
    s->st[t] = FL_IDLE;                                              /* REC, nothing heard (or the take's */
    s->has[t] = 0;                                                   /* start): the track's loop cleared */
    return act(FL_DO_CLEAR, t, FL_T_CLEARED);
}

void fl_release(FlState *s, unsigned t, unsigned pedal) {
    if (t < FL_TRACKS && (s->held[t] & pedal)) s->held[t] = 0;
}

unsigned fl_undo_buffer(const FlConfig *c, unsigned t) {
    if (t >= FL_TRACKS) return 0;
    unsigned u = c->ubuf[t];
    return u >= 1 && u <= FL_TRACKS && u != t + 1 ? u : 0;
}

/* The pass in progress, if any, is over (its recorder stopped by RLEN, a
 * cut or a stop): the other buffer holds the loop before it (in place: UNDO
 * TO's loop). The loop's recordings counted: the n-th is UNDO TO n's. */
static void pass_over(FlState *s, const FlConfig *c, unsigned t) {
    if (!s->rec[t]) return;
    if (s->swap[t]) s->cur[t] ^= 1;                                  /* never seen running: switch now */
    s->rec[t] = 0;
    s->swap[t] = 0;
    s->valid[t] = 1;
    s->inplace[t] = 0;
    if (s->npass[t] < 255) ++s->npass[t];
    if (c->undoto[t] && s->npass[t] == c->undoto[t]) s->anchor[t] = (uint8_t)(c->undoto[t] << 1 | s->cur[t]);
}

/* The pass in progress, if any, is dropped: the track back on what it played
 * (in place: it stays, the pass's start in it; the other is UNDO TO's loop). */
static void pass_drop(FlState *s, unsigned t) {
    if (!s->rec[t]) return;
    if (s->inplace[t]) {
        s->valid[t] = 1;
    } else {
        if (!s->swap[t]) s->cur[t] ^= 1;                             /* already switched: back */
        s->valid[t] = 0;
    }
    s->rec[t] = 0;
    s->swap[t] = 0;
    s->inplace[t] = 0;
}

/* A REPLACE pass over before its loop start: its mute undone, or not made. */
static void replace_off(FlState *s, unsigned t) {
    s->repl[t] = 0;
    if (s->rpass[t] == FL_RP_UNMUTE) s->rpass[t] = FL_RP_NOW;
    else if (s->rpass[t] == FL_RP_MUTE) s->rpass[t] = FL_RP_NONE;
}

unsigned fl_gate(FlState *s, const FlConfig *c, unsigned t) {
    if (t >= FL_TRACKS || c->role[t] == FL_ROLE_OFF) return 1;
    pass_over(s, c, t);
    unsigned go, replace = 0;
    if (s->st[t] == FL_ARMED) {
        replace = s->repl[t];                                        /* REPLACE: one pass, as a take */
        s->repl[t] = 0;
        s->st[t] = replace ? FL_IDLE : FL_OVERDUB;
        s->has[t] = 1;
        go = 1;
    } else {
        go = s->st[t] == FL_OVERDUB;
    }
    if (replace) {
        s->rpass[t] = FL_RP_MUTE;                                    /* muted from its loop start */
        s->qpend[t] = 0;
        s->npass[t] = 0;                                             /* the loop's first recording */
        s->anchor[t] = 0;
    }
    unsigned u = fl_undo_buffer(c, t);
    if (!go || !u) return go;
    s->undone[t] = 0;
    unsigned n = c->undoto[t];
    if (!replace && n && s->anchor[t] >> 1 == n && (s->anchor[t] & 1) != s->cur[t]) {
        s->rec[t] = s->cur[t] ? 2 : 1;                               /* UNDO TO's loop in the other: */
        s->swap[t] = 0;                                              /* overdub the one played, in place */
        s->inplace[t] = 1;
        s->valid[t] = 1;
        if (!s->cur[t]) return 1;                                    /* on X: the track's recorder */
        s->inj[u - 1] = (uint8_t)(t + 1);                            /* on Y: Y's recorder */
        return 0;
    }
    s->rec[t] = s->cur[t] ? 1 : 2;                                   /* into the buffer not played */
    s->swap[t] = 1;
    s->valid[t] = 0;
    s->inplace[t] = 0;
    if (s->cur[t]) return 1;                                         /* on Y: the track's recorder, into X */
    s->inj[u - 1] = (uint8_t)(t + 1);                                /* on X: Y's recorder */
    return 0;
}

unsigned fl_inject(FlState *s, unsigned r) {
    if (r >= FL_TRACKS) return 0;
    unsigned t = s->inj[r];
    s->inj[r] = 0;
    return t;
}

void fl_rec_running(FlState *s, unsigned t) {
    if (t >= FL_TRACKS || !s->swap[t]) return;
    s->swap[t] = 0;
    s->cur[t] ^= 1;
}

FlAction fl_undo(FlState *s, const FlConfig *c, unsigned t) {
    if (t >= FL_TRACKS || c->role[t] == FL_ROLE_OFF) return act(FL_DO_NOTHING, t, FL_T_NONE);
    if (!fl_undo_buffer(c, t)) return act(FL_DO_TOAST, t, FL_T_NO_BUFFER);
    if (s->rec[t] && s->inplace[t]) {                                /* in place: stopped, and back on */
        s->rec[t] = 0;                                               /* UNDO TO's loop (REDO: the pass's */
        s->inplace[t] = 0;                                           /* start in the other) */
        s->valid[t] = 1;
        s->cur[t] ^= 1;
        s->undone[t] = 1;
        s->st[t] = FL_IDLE;
        return act(FL_DO_CUT, t, FL_T_UNDO);
    }
    if (s->rec[t]) {                                                 /* a pass records: drop it */
        pass_drop(s, t);
        s->st[t] = FL_IDLE;
        if (s->rpass[t] == FL_RP_MUTE) s->rpass[t] = FL_RP_NONE;     /* a REPLACE's: heard at the loop start */
        return act(FL_DO_CUT, t, FL_T_UNDO_CUT);
    }
    if (!s->valid[t]) return act(FL_DO_TOAST, t, FL_T_NO_UNDO);
    s->cur[t] ^= 1;
    s->undone[t] ^= 1;
    return act(FL_DO_TOAST, t, s->undone[t] ? FL_T_UNDO : FL_T_REDO);
}

unsigned fl_pattern(FlState *s, const FlConfig *c, unsigned id) {
    if (s->seen && s->pattern == id) return 0;
    s->seen = 1;
    s->pattern = (uint8_t)id;
    unsigned modes = c->mode[id & (FL_PATTERNS - 1)];
    for (unsigned t = 0; t < FL_TRACKS; ++t) {
        unsigned m = (modes >> (2 * t)) & 3;
        if (c->role[t] == FL_ROLE_OFF || s->st[t] == FL_TAKE) continue;
        if (m == FL_MODE_KEEP) continue;
        s->repl[t] = m == FL_MODE_REPLACE;
        s->st[t] = m == FL_MODE_OFF ? FL_IDLE : FL_ARMED;
    }
    return 1;
}

void fl_stopped(FlState *s) {
    for (unsigned t = 0; t < FL_TRACKS; ++t) {
        if (s->st[t] == FL_ARMED || s->st[t] == FL_OVERDUB) s->st[t] = FL_IDLE;
        s->qpend[t] = 0;                                             /* no loop start will come */
        replace_off(s, t);
        pass_drop(s, t);
        s->inj[t] = 0;
    }
}

FlAction fl_end(FlState *s, const FlConfig *c, unsigned t, unsigned playing, unsigned muted) {
    if (t >= FL_TRACKS || c->role[t] == FL_ROLE_OFF) return act(FL_DO_NOTHING, t, FL_T_NONE);
    if (!playing) {                                                  /* nothing plays: at once */
        FlAction a = act(FL_DO_NOTHING, t, muted ? FL_T_UNMUTED : FL_T_MUTED);
        a.mute = muted ? FL_UNMUTE : FL_MUTE;
        return a;
    }
    if (s->qpend[t]) {
        s->qpend[t] = 0;
        return act(FL_DO_TOAST, t, FL_T_END_CANCEL);
    }
    s->qpend[t] = muted ? FL_UNMUTE : FL_MUTE;
    return act(FL_DO_TOAST, t, muted ? FL_T_END_PLAY : FL_T_END_STOP);
}

unsigned fl_loop_start(FlState *s, unsigned t) {
    if (t >= FL_TRACKS) return 0;
    unsigned q = s->qpend[t];
    s->qpend[t] = 0;
    return q;
}

unsigned fl_replace_start(FlState *s, unsigned t) {
    if (t >= FL_TRACKS) return 0;
    if (s->rpass[t] == FL_RP_MUTE) {
        s->rpass[t] = FL_RP_UNMUTE;
        return FL_MUTE;
    }
    if (s->rpass[t] != FL_RP_UNMUTE) return 0;
    s->rpass[t] = FL_RP_NONE;
    return FL_UNMUTE;
}

unsigned fl_end_pending(const FlState *s) {
    for (unsigned t = 0; t < FL_TRACKS; ++t)
        if (s->qpend[t] || s->rpass[t] == FL_RP_MUTE || s->rpass[t] == FL_RP_UNMUTE) return 1;
    return 0;
}

void fl_cleared(FlState *s, unsigned t) {
    if (t >= FL_TRACKS) return;
    s->has[t] = 0;
    s->cur[t] = 0;
    s->rec[t] = 0;
    s->swap[t] = 0;
    s->valid[t] = 0;
    s->undone[t] = 0;
    s->npass[t] = 0;
    s->anchor[t] = 0;
    s->inplace[t] = 0;
    replace_off(s, t);
}

void fl_reset(FlState *s) {
    for (unsigned t = 0; t < FL_TRACKS; ++t) {
        s->st[t] = FL_IDLE;
        s->has[t] = 0;
        s->held[t] = 0;
        s->qpend[t] = 0;
        s->inj[t] = 0;
        fl_cleared(s, t);
    }
}

unsigned fl_play_entry(const FlConfig *c, unsigned t, unsigned id) {
    return t < FL_TRACKS ? (c->pmode[id & (FL_PATTERNS - 1)] >> (2 * t)) & 3 : FL_PLAY_KEEP;
}

unsigned fl_pop_state(const FlState *s, const FlConfig *c, unsigned t, unsigned recording) {
    if (t >= FL_TRACKS || c->role[t] == FL_ROLE_OFF || !((c->popup >> t) & 1)) return FL_POP_NONE;
    if (s->rpass[t] == FL_RP_UNMUTE && recording) return FL_POP_REPLACE;
    switch (s->st[t]) {
    case FL_TAKE:    return FL_POP_TAKE;
    case FL_ARMED:   return FL_POP_ARMED;
    case FL_OVERDUB: return FL_POP_OVERDUB;
    default:         return recording ? FL_POP_ENDING : FL_POP_NONE;   /* cut: the pass finishes */
    }
}

static char *put(char *p, const char *text) {
    while (*text) *p++ = *text++;
    return p;
}

static char *put_uint(char *p, unsigned v) {
    char digits[6];
    unsigned n = 0;
    do { digits[n++] = (char)('0' + v % 10); v /= 10; } while (v && n < 6);
    while (n) *p++ = digits[--n];
    return p;
}

static char *put_track(char *p, unsigned t) {
    *p++ = 'T';
    *p++ = (char)('1' + t);
    *p++ = ' ';
    return p;
}

/* ---- the panel ---- */

static const char *const row_names[FL_ROWS] = {"ROLE", "SIGN", "BARS", "MIN BPM", "MAX BPM", "ENTRY", "PLAY", "UNDO", "UNDO TO",
                                               "MUTE", "POPUP"};
static const char *const role_names[3] = {"OFF", "GRID", "FREE"};
static const char *const mode_names[4] = {"KEEP", "ARM", "OFF", "REPLACE"};
static const char *const play_names[4] = {"KEEP", "MUTE", "STOP", "PLAY"};
static const uint8_t bar_values[6] = {0, 1, 2, 4, 8, 16};

const char *fl_row_name(unsigned row) { return row < FL_ROWS ? row_names[row] : ""; }

static unsigned eff_lo(const FlConfig *c, unsigned t) { return c->bpm_lo[t] ? c->bpm_lo[t] : DEF_LO; }
static unsigned eff_hi(const FlConfig *c, unsigned t) { return c->bpm_hi[t] ? c->bpm_hi[t] : DEF_HI; }
static unsigned mode_of(const FlConfig *c, unsigned t, unsigned id) {
    return (c->mode[id & (FL_PATTERNS - 1)] >> (2 * t)) & 3;
}

char *fl_row_value(const FlConfig *c, unsigned t, unsigned row, unsigned id, char *out) {
    char *p = out;
    if (t >= FL_TRACKS) t = 0;
    switch (row) {
    case FL_ROW_ROLE:  p = put(p, role_names[c->role[t] < 3 ? c->role[t] : 0]); break;
    case FL_ROW_SIGN:  p = put(p, fl_sig_name(c->sig[t])); break;
    case FL_ROW_BARS:  p = c->bars[t] ? put_uint(p, c->bars[t]) : put(p, "AUTO"); break;
    case FL_ROW_MIN:   p = put_uint(p, eff_lo(c, t)); break;
    case FL_ROW_MAX:   p = put_uint(p, eff_hi(c, t)); break;
    case FL_ROW_ENTRY: p = put(p, mode_names[mode_of(c, t, id)]); break;
    case FL_ROW_PLAY:  p = put(p, play_names[fl_play_entry(c, t, id)]); break;
    case FL_ROW_UNDO:
        if (fl_undo_buffer(c, t)) { *p++ = 'R'; *p++ = (char)('0' + c->ubuf[t]); }
        else p = put(p, "OFF");
        break;
    case FL_ROW_UNDOTO: p = c->undoto[t] ? put_uint(p, c->undoto[t]) : put(p, "LAST"); break;
    case FL_ROW_POPUP: p = put(p, (c->popup >> t) & 1 ? "ON" : "OFF"); break;
    case FL_ROW_MUTE:  p = put(p, (c->endmute >> t) & 1 ? "END" : "NOW"); break;
    default:           break;
    }
    *p = 0;
    return out;
}

static int clamp(int v, int lo, int hi) { return v < lo ? lo : v > hi ? hi : v; }

unsigned fl_row_edit(FlConfig *c, unsigned t, unsigned row, unsigned id, int delta) {
    if (t >= FL_TRACKS) return 0;
    int was, now;
    switch (row) {
    case FL_ROW_ROLE:
        was = c->role[t] < 3 ? c->role[t] : 0;
        now = clamp(was + delta, 0, 2);
        c->role[t] = (uint8_t)now;
        break;
    case FL_ROW_SIGN:
        was = c->sig[t] < FL_SIGS ? c->sig[t] : 0;
        now = clamp(was + delta, 0, FL_SIGS - 1);
        c->sig[t] = (uint8_t)now;
        break;
    case FL_ROW_BARS: {
        int i = 0;
        for (int k = 0; k < 6; ++k)
            if (bar_values[k] == c->bars[t]) i = k;
        was = i;
        now = clamp(i + delta, 0, 5);
        c->bars[t] = bar_values[now];
        break;
    }
    case FL_ROW_MIN:
        was = (int)eff_lo(c, t);
        now = clamp(was + delta, 30, (int)eff_hi(c, t));
        c->bpm_lo[t] = (uint16_t)now;
        break;
    case FL_ROW_MAX:
        was = (int)eff_hi(c, t);
        now = clamp(was + delta, (int)eff_lo(c, t), 300);
        c->bpm_hi[t] = (uint16_t)now;
        break;
    case FL_ROW_ENTRY: {
        unsigned k = id & (FL_PATTERNS - 1);
        was = (int)mode_of(c, t, k);
        now = clamp(was + delta, 0, 3);
        c->mode[k] = (uint16_t)((c->mode[k] & ~(3u << (2 * t))) | ((unsigned)now << (2 * t)));
        break;
    }
    case FL_ROW_PLAY: {
        unsigned k = id & (FL_PATTERNS - 1);
        was = (int)fl_play_entry(c, t, k);
        now = clamp(was + delta, 0, 3);
        c->pmode[k] = (uint16_t)((c->pmode[k] & ~(3u << (2 * t))) | ((unsigned)now << (2 * t)));
        break;
    }
    case FL_ROW_UNDOTO:
        was = c->undoto[t] <= FL_UNDO_TO_MAX ? c->undoto[t] : 0;
        now = clamp(was + delta, 0, FL_UNDO_TO_MAX);
        c->undoto[t] = (uint8_t)now;
        break;
    case FL_ROW_MUTE:
        was = (c->endmute >> t) & 1;
        now = clamp(was + delta, 0, 1);
        c->endmute = (uint8_t)((c->endmute & ~(1u << t)) | ((unsigned)now << t));
        break;
    case FL_ROW_POPUP:
        was = (c->popup >> t) & 1;
        now = clamp(was + delta, 0, 1);
        c->popup = (uint8_t)((c->popup & ~(1u << t)) | ((unsigned)now << t));
        break;
    case FL_ROW_UNDO: {                                              /* OFF, R1..R8 but the track's own */
        was = (int)fl_undo_buffer(c, t);
        now = was;
        for (int n = delta < 0 ? -delta : delta; n > 0; --n) {
            int next = now + (delta < 0 ? -1 : 1);
            if (next == (int)t + 1) next += delta < 0 ? -1 : 1;
            if (next < 0 || next > FL_TRACKS) break;
            now = next;
        }
        c->ubuf[t] = (uint8_t)now;
        break;
    }
    default:
        return 0;
    }
    return now != was;
}

char *fl_label(const FlAction *a, char *out) {
    char *p = out;
    switch (a->toast) {
    case FL_T_FREE:        p = put(put_track(p, a->track), "FREE LOOP"); break;
    case FL_T_TEMPO: {
        unsigned tenths = (a->tempo.tempo24 * 10u + 12u) / 24u;    /* BPM x 10, rounded */
        p = put_uint(p, tenths / 10);
        *p++ = '.';
        *p++ = (char)('0' + tenths % 10);
        p = put_uint(put(p, " BPM "), a->tempo.bars);
        p = put(p, a->tempo.bars == 1 ? " BAR" : " BARS");
        break;
    }
    case FL_T_ARMED:       p = put(put_track(p, a->track), "OVERDUB ARMED"); break;
    case FL_T_OVERDUB_OFF: p = put(put_track(p, a->track), "OVERDUB OFF"); break;
    case FL_T_PLAY:        p = put(p, "PLAY"); break;
    case FL_T_STOP:        p = put(p, "STOP"); break;
    case FL_T_CLEARED:     p = put(put_track(p, a->track), "CLEARED"); break;
    case FL_T_SLAVE:       p = put(p, "EXT CLOCK: NO FREE"); break;
    case FL_T_RANGE:       p = put(p, "TEMPO OUT OF RANGE"); break;
    case FL_T_BUSY:        p = put(p, "TAKE IN PROGRESS"); break;
    case FL_T_MUTED:       p = put(put_track(p, a->track), "MUTED"); break;
    case FL_T_UNMUTED:     p = put(put_track(p, a->track), "PLAYS"); break;
    case FL_T_END_STOP:    p = put(put_track(p, a->track), "STOPS AT END"); break;
    case FL_T_END_PLAY:    p = put(put_track(p, a->track), "PLAYS AT START"); break;
    case FL_T_END_CANCEL:  p = put(put_track(p, a->track), "END CANCELLED"); break;
    case FL_T_UNDO:        p = put(put_track(p, a->track), "UNDO"); break;
    case FL_T_REDO:        p = put(put_track(p, a->track), "REDO"); break;
    case FL_T_UNDO_CUT:    p = put(put_track(p, a->track), "OVERDUB UNDONE"); break;
    case FL_T_NO_UNDO:     p = put(put_track(p, a->track), "NOTHING TO UNDO"); break;
    case FL_T_NO_BUFFER:   p = put(put_track(p, a->track), "NO UNDO BUFFER"); break;
    default:               return 0;
    }
    *p = 0;
    return out;
}
