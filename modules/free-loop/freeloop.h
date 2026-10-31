/* FREE LOOP -- the loop-pedal engine.
 *
 Two pedals (MIDI CCs on a track's channel) per looping track, REC and
 * PLAY/STOP. A track's role says what REC does:
 *   FREE  with the sequencer stopped and no loop anywhere, the first press
 *         starts a free take, the second ends it: its length sets the
 *         tempo, the pattern's length and the loop's end, and the sequencer
 *         starts. Afterwards the track behaves as GRID.
 *   GRID  each press arms or cuts the overdub: the track's recorder trigs
 *         fire only while it is armed (the first one that fires turns ARMED
 *         into OVERDUB; a cut lets the pass in progress finish).
 *   OFF   (zero) the module leaves the track to stock.
 * PLAY/STOP: the sequencer stopped, PLAY at the press (the track heard);
 * during the track's free take, its end (as REC); playing, per the track's
 * MUTE: NOW, mute / unmute at the press; END, END at the press.
 * A long press: REC or PLAY/STOP still held FL_LONG after the press (no
 * release, value 0, before then), at once, the pedal still down. A track
 * "plays" when the sequencer runs and it is heard. REC, the track playing:
 * what the press did (arm, cut) undone, then UNDO as CC 92 (a pass
 * recording: dropped; no UNDO buffer: NO UNDO BUFFER). REC, the track not
 * playing (muted, or the sequencer stopped), or the press that started a
 * free take: the track's loop cleared (a take dropped). PLAY/STOP, MUTE NOW:
 * the press's mute undone, then END from the state before it (the track was
 * cut, or let through, for that second); MUTE END: the press's own END. The
 * press that ended a free take does nothing more. A pedal that sends no release (127
 * only) clears 1 s after each such press: it needs 127 / 0.
 * END (CC 93): mute / unmute the track at its loop's start -- playing and
 * heard, it stops when the pass in progress ends; muted, it comes back at
 * the next pass's first step. Pressed again before that: cancelled.
 * Stopped: at once.
 * UNDO (CC 92), for a track given an UNDO buffer (another recorder buffer,
 * R5-R8 in the template): an overdub never writes the loop it plays. The track
 * plays X; the pass records X + the new layer into the other buffer Y (Y's
 * own recorder, the track's recording setup), and once it records the track
 * is switched to Y, heard from the next loop start. UNDO at rest switches
 * back to X (pressed again: REDO, Y); during a pass, it stops that pass and
 * the track stays on X (the redo is gone). A clear empties both buffers.
 * UNDO TO n (the window; 0 LAST, the above): UNDO goes back to the loop as
 * it was after its n-th recording (the take, or a first pass, is the 1st).
 * Once it is held in one buffer, every later pass overdubs the other in
 * place, so that one stays: UNDO switches to it, REDO back to the latest; a
 * pass started from it records into the other (the latest is gone). UNDO
 * during an in-place pass stops it and switches to that loop.
 *
 * Each pattern can set, per track, how the track enters it: ENTRY, its
 * overdub: ARM (recorder trigs on from step 1), OFF (cut), KEEP (zero: as
 * before), REPLACE (one pass from step 1 that records the inputs only, not
 * the track itself -- SRC3 dropped from its recorder trig -- the track
 * muted while it records and heard again, the new loop, at the next loop
 * start; with an UNDO buffer the old loop is UNDO's); PLAY, its sound, at its first step of the pattern: MUTE, STOP
 * (muted and its new trigs dropped, so its tails ring out), PLAY (heard),
 * KEEP (zero).
 *
 * The tempo of a free take: a bar of the track's signature is `spb`
 * sequencer steps (16th notes: 4/4 16, 3/4 and 6/8 12, 7/8 14 ...; the
 * tempo counts quarter notes, as the Octatrack's); the loop is N bars, N fixed or AUTO (the smallest
 * of 1, 2, 4, 8, 16 whose tempo is in the track's range). The tempo is the
 * slowest tempo24 (1/24 BPM steps, what the firmware keeps) whose recorded
 * loop -- RLEN PLEN's L = round(T x 2,646,000 / tempo24), T the pattern's
 * ticks -- is not longer than the take, so the take is only ever cut, never
 * padded: by under 1/tempo24 of its length (0.06 % at 70 BPM).
 *
 * Every field is zero in the stock state. Freestanding: no floating point,
 * no library calls, 32-bit arithmetic only. Tested on the host by verify.py. */
#ifndef FREELOOP_H
#define FREELOOP_H
#include <stdint.h>

#define FL_TRACKS 8          /* audio tracks T1..T8 */
#define FL_PATTERNS 256      /* bank * 16 + pattern */
#define FL_LONG 132000000u   /* a long press: 1 s of the unit's DTIM3 count (132 MHz, free-running) */

enum { FL_ROLE_OFF = 0, FL_ROLE_GRID = 1, FL_ROLE_FREE = 2 };
enum { FL_MODE_KEEP = 0, FL_MODE_ARM = 1, FL_MODE_OFF = 2, FL_MODE_REPLACE = 3 };
enum { FL_IDLE = 0, FL_TAKE, FL_ARMED, FL_OVERDUB };   /* a track's recording state */
enum { FL_MUTE = 1, FL_UNMUTE = 2 };
enum { FL_PLAY_KEEP = 0, FL_PLAY_MUTE, FL_PLAY_STOP, FL_PLAY_PLAY };   /* how a track's sound enters a pattern */
enum { FL_HELD_PLAY = 1, FL_HELD_REC = 2, FL_HELD_DONE = 4 };   /* FlState held: the pedal; its long press taken */
/* FlState rpass, a REPLACE pass: its mute due at the coming loop start; the
 * track muted, heard at the next; heard again at once (the pass is over by a
 * stop or a clear). */
enum { FL_RP_NONE = 0, FL_RP_MUTE, FL_RP_UNMUTE, FL_RP_NOW };
#define FL_UNDO_TO_MAX 16

/* What the adapter does after an event (fl_rec, fl_play, fl_hold). */
enum {
    FL_DO_NOTHING = 0,
    FL_DO_TAKE,          /* start a free take on `track` */
    FL_DO_LAUNCH,        /* end the take, write tempo24 / pattern / loop end, start the sequencer */
    FL_DO_PLAY,          /* start the sequencer */
    FL_DO_STOP,          /* stop the sequencer */
    FL_DO_CLEAR,         /* clear `track`'s buffer (a free take in progress is ended first) */
    FL_DO_STOP_CLEAR,    /* stop the sequencer, then clear `track`'s buffer */
    FL_DO_TOAST,         /* only the toast */
    FL_DO_CUT,           /* stop the recorder of `track`'s pass (UNDO; the adapter read which before) */
};

/* Toasts (fl_label). */
enum {
    FL_T_NONE = 0, FL_T_FREE, FL_T_TEMPO, FL_T_ARMED, FL_T_OVERDUB_OFF, FL_T_PLAY, FL_T_STOP,
    FL_T_CLEARED, FL_T_SLAVE, FL_T_RANGE, FL_T_BUSY, FL_T_MUTED, FL_T_UNMUTED,
    FL_T_END_STOP, FL_T_END_PLAY, FL_T_END_CANCEL, FL_T_UNDO, FL_T_REDO, FL_T_UNDO_CUT, FL_T_NO_UNDO,
    FL_T_NO_BUFFER,
};

typedef struct {
    uint8_t  role[FL_TRACKS];
    uint8_t  sig[FL_TRACKS];       /* signature: an index into fl_sig_name (0 = 4/4) */
    uint8_t  bars[FL_TRACKS];      /* 1, 2, 4, 8, 16; 0 = AUTO */
    uint8_t  popup;                /* bit t: the REC popup opens for track t (was reserved: 0 in version 1) */
    uint8_t  endmute;              /* bit t: PLAY/STOP's press is END (MUTE END), else a mute (NOW) */
    uint16_t bpm_lo[FL_TRACKS];    /* AUTO's range, whole BPM; 0 = 70 / 160 */
    uint16_t bpm_hi[FL_TRACKS];
    uint16_t mode[FL_PATTERNS];    /* 2 bits per track, T1 in bits 0-1 */
    uint8_t  ubuf[FL_TRACKS];      /* UNDO: 0 OFF, else the other buffer, recorder 1..8 (not the track's) */
    uint16_t pmode[FL_PATTERNS];   /* PLAY entry, 2 bits per track (FL_PLAY_*), T1 in bits 0-1 */
    uint8_t  undoto[FL_TRACKS];    /* UNDO TO: 0 LAST, else the recording UNDO goes back to, 1..FL_UNDO_TO_MAX */
} FlConfig;                        /* 1098 bytes, the payload of freeloop.work (big-endian); version 3 ended
                                      before undoto (1090), version 2 before pmode (578), version 1 before
                                      ubuf (570) */

typedef struct {
    uint16_t tempo24;              /* 24 x BPM */
    uint8_t  bars;                 /* N */
    uint8_t  len;                  /* pattern length, 2..64 steps */
    uint8_t  scale;                /* the pattern's scale index: 2 = 1X, 4 = 1/2X, 5 = 1/4X, 6 = 1/8X */
    uint8_t  reserved[3];
    uint32_t loop;                 /* L, samples (<= the take) */
} FlTempo;

typedef struct {
    uint8_t  kind;                 /* FL_DO_* */
    uint8_t  track;
    uint8_t  toast;                /* FL_T_* */
    uint8_t  mute;                 /* FL_MUTE / FL_UNMUTE the track, after `kind`; 0 none */
    FlTempo  tempo;                /* FL_DO_LAUNCH, FL_T_TEMPO */
} FlAction;

typedef struct {
    uint8_t  st[FL_TRACKS];        /* FL_IDLE .. FL_OVERDUB */
    uint8_t  has[FL_TRACKS];       /* the track's buffer holds a loop */
    uint8_t  held[FL_TRACKS];      /* the pedal down (FL_HELD_*), 0 none */
    uint8_t  undo[FL_TRACKS];      /* the held press's mute, to undo (FL_MUTE / FL_UNMUTE), 0 none */
    uint8_t  started[FL_TRACKS];   /* the held press: 1 started the sequencer, 3 launched a take */
    uint8_t  qpend[FL_TRACKS];     /* END: FL_MUTE / FL_UNMUTE at the track's next loop start, 0 none */
    uint8_t  pattern;              /* the playing pattern last seen */
    uint8_t  seen;
    uint32_t down[FL_TRACKS];      /* DTIM3 count at the held press */
    uint8_t  cur[FL_TRACKS];       /* UNDO: 1 the track plays its UNDO buffer, 0 its own */
    uint8_t  rec[FL_TRACKS];       /* a pass records into the other buffer: 1 the track's recorder, 2 the UNDO buffer's */
    uint8_t  valid[FL_TRACKS];     /* the other buffer holds the loop before the last pass */
    uint8_t  swap[FL_TRACKS];      /* `cur` flips once the pass's recorder runs (fl_rec_running) */
    uint8_t  undone[FL_TRACKS];    /* the last switch was an UNDO: the next is a REDO */
    uint8_t  inj[FL_TRACKS];       /* [recorder r]: track + 1 whose pass r's next gate takes, 0 none */
    uint8_t  npass[FL_TRACKS];     /* UNDO TO: the loop's recordings so far (the take or first pass 1) */
    uint8_t  anchor[FL_TRACKS];    /* UNDO TO n's loop: n << 1 | the cur that plays it; 0 none yet */
    uint8_t  inplace[FL_TRACKS];   /* the pass in progress overdubs the buffer played (UNDO TO) */
    uint8_t  repl[FL_TRACKS];      /* ARMED by a REPLACE entry: the next pass replaces */
    uint8_t  rpass[FL_TRACKS];     /* a REPLACE pass's mute (FL_RP_*) */
} FlState;

/* The signatures, their steps per bar and names. */
#define FL_SIGS 8
unsigned    fl_spb(unsigned sig);
const char *fl_sig_name(unsigned sig);

/* The panel (TRACK + UP): one row per setting of track `t`; ENTRY is the
 * entry mode in pattern `id` (bank * 16 + pattern). */
enum { FL_ROW_ROLE = 0, FL_ROW_SIGN, FL_ROW_BARS, FL_ROW_MIN, FL_ROW_MAX, FL_ROW_ENTRY, FL_ROW_PLAY, FL_ROW_UNDO, FL_ROW_UNDOTO,
       FL_ROW_MUTE, FL_ROW_POPUP, FL_ROWS };
const char *fl_row_name(unsigned row);
/* The value as the panel prints it; `out` must hold 8 bytes. */
char       *fl_row_value(const FlConfig *c, unsigned t, unsigned row, unsigned id, char *out);
/* Turn the row's value by `delta` steps, clamped. Returns 1 when it changed. */
unsigned    fl_row_edit(FlConfig *c, unsigned t, unsigned row, unsigned id, int delta);

/* END (CC 93) pressed on track `t`; `muted` = the track is muted now. */
FlAction fl_end(FlState *s, const FlConfig *c, unsigned t, unsigned playing, unsigned muted);

/* Track `t` is on its loop's first step: the END toggle due there
 * (FL_MUTE / FL_UNMUTE), taken; 0 none. */
unsigned fl_loop_start(FlState *s, unsigned t);

/* Track `t` is on its loop's first step: a REPLACE pass's mute due there
 * (FL_MUTE as it starts, FL_UNMUTE as the next starts), taken; 0 none. */
unsigned fl_replace_start(FlState *s, unsigned t);

/* 1 while some track has an END toggle or a REPLACE mute pending. */
unsigned fl_end_pending(const FlState *s);

/* Every track idle and empty (a clear of every buffer, a project load). */
void        fl_reset(FlState *s);

/* The tempo of a take of `take` samples for track `t` (its spb, bars and
 * range). Returns 1 and fills `out`, or 0 when no N gives a tempo in range
 * (AUTO) or the tempo is outside 30..300 BPM. */
unsigned fl_tempo(const FlConfig *c, unsigned t, uint32_t take, FlTempo *out);

/* RLEN PLEN's recorded length for `ticks` (len x ticks per step) at tempo24. */
uint32_t fl_loop_len(uint32_t ticks, uint32_t tempo24);

/* REC pressed on track `t` at `now` (DTIM3 counts). `playing` = the
 * sequencer runs; `slave` = CLOCK RECEIVE on; `take` = the length so far of
 * the free take in progress (read off the recorder), for its end. */
FlAction fl_rec(FlState *s, const FlConfig *c, unsigned t, unsigned playing, unsigned slave, uint32_t take,
                uint32_t now);

/* PLAY/STOP pressed on track `t` at `now`; `muted` = the track is muted now. */
FlAction fl_play(FlState *s, const FlConfig *c, unsigned t, uint32_t now, unsigned playing, unsigned muted,
                 uint32_t take);

/* Every UI tick, per track: the held press's long press, once it is
 * FL_LONG old (REC: the loop cleared, or UNDO: FL_DO_CUT as fl_undo's, the
 * adapter reads the pass's recorder before; PLAY/STOP: END); else nothing.
 * `muted` = the track is muted now. */
FlAction fl_hold(FlState *s, const FlConfig *c, unsigned t, uint32_t now, unsigned playing, unsigned muted);

/* The pedal (FL_HELD_PLAY / FL_HELD_REC) released: its press no longer held. */
void     fl_release(FlState *s, unsigned t, unsigned pedal);

/* The step handler's recorder-trig test for track `t`: 1 = let it fire.
 * With an UNDO buffer, a pass that records into it is not the track's trig
 * but its recorder's: inj[] is set, the track's own trig does not fire.
 * rpass FL_RP_MUTE after the call: the pass replaces (its trig without SRC3). */
unsigned fl_gate(FlState *s, const FlConfig *c, unsigned t);

/* The step handler on recorder `r`'s track: the track + 1 whose pass r
 * records now (r takes that track's trig and setup), taken; 0 none. */
unsigned fl_inject(FlState *s, unsigned r);

/* The track's UNDO buffer, recorder 1..8, or 0 none. */
unsigned fl_undo_buffer(const FlConfig *c, unsigned t);

/* The recorder of track `t`'s pass runs: its `cur` switches now. */
void     fl_rec_running(FlState *s, unsigned t);

/* UNDO (CC 92) pressed on track `t`. FL_DO_CUT: the adapter stops the
 * recorder rec[] named before the call. */
FlAction fl_undo(FlState *s, const FlConfig *c, unsigned t);

/* The PLAY entry (FL_PLAY_*) of track `t` in pattern `id`. */
unsigned fl_play_entry(const FlConfig *c, unsigned t, unsigned id);

/* The playing pattern is `id` (bank * 16 + pattern). On a change, each
 * track takes the new pattern's entry mode. Returns 1 on a change. */
unsigned fl_pattern(FlState *s, const FlConfig *c, unsigned id);

/* The sequencer stopped (by any means): armed and overdubbing tracks stop
 * recording; a pass into the UNDO buffer is dropped (the track stays on
 * what it played). */
void     fl_stopped(FlState *s);

/* The track's buffer was cleared (its own and its UNDO buffer: back on its own). */
void     fl_cleared(FlState *s, unsigned t);

/* The REC popup (POPUP ON): what track `t` shows. `recording` = the
 * recorder of its pass (or its take) runs now. */
enum { FL_POP_NONE = 0, FL_POP_TAKE, FL_POP_ARMED, FL_POP_OVERDUB, FL_POP_ENDING, FL_POP_REPLACE };
unsigned fl_pop_state(const FlState *s, const FlConfig *c, unsigned t, unsigned recording);

/* The toast for an action, e.g. "FREE LOOP T1", "120.3 BPM", "T2 ARMED".
 * `out` must hold 20 bytes. Returns `out`, or 0 for no toast. */
char    *fl_label(const FlAction *a, char *out);

#endif
