/* Host tests for the FREE LOOP engine (run by verify.py). No firmware. */
#include <stdio.h>
#include <string.h>
#include "freeloop.h"

static int failures, checks;
#define CHECK(cond, ...) do { ++checks; if (!(cond)) { ++failures; \
    printf("FAIL %s:%d: ", __FILE__, __LINE__); printf(__VA_ARGS__); printf("\n"); } } while (0)

static const unsigned ticks_of[7] = {3, 4, 6, 8, 12, 24, 48};

static void rig(FlConfig *c, FlState *s) {
    memset(c, 0, sizeof *c);
    memset(s, 0, sizeof *s);
    c->role[0] = FL_ROLE_FREE;      /* T1 guitar loop */
    c->role[1] = FL_ROLE_GRID;      /* T2 guitar layer */
    c->role[2] = FL_ROLE_FREE;      /* T3 synth loop */
    c->role[3] = FL_ROLE_GRID;      /* T4 synth layer */
}

/* RLEN PLEN's cave (modules/rlen-plen/plen_cave.s): round(T x 2,646,000 / tempo24). */
static void test_loop_len(void) {
    CHECK(fl_loop_len(96, 2880) == 88200, "16 steps 1X at 120 BPM = one 2 s bar: %u", fl_loop_len(96, 2880));
    CHECK(fl_loop_len(384, 2880) == 352800, "64 steps at 120 = 8 s");
    CHECK(fl_loop_len(3072, 720) == 11289600, "64 steps 1/8X at 30 BPM = 256 s");
    for (unsigned t24 = 720; t24 <= 7200; t24 += 7)
        for (unsigned T = 12; T <= 3072; T += 61) {
            unsigned long long exact2 = 2ull * T * 2646000ull;    /* 2 x T x 2,646,000 */
            unsigned want = (unsigned)((exact2 + t24) / (2ull * t24));
            if (fl_loop_len(T, t24) != want) {
                CHECK(0, "T %u tempo24 %u: %u, rounded %u", T, t24, fl_loop_len(T, t24), want);
                return;
            }
        }
}

static void test_tempo_exact(void) {
    FlConfig c; FlState s; rig(&c, &s);
    FlTempo t;
    CHECK(fl_tempo(&c, 0, 352800, &t), "4 bars at 120");
    CHECK(t.tempo24 == 2880 && t.bars == 4 && t.len == 64 && t.scale == 2 && t.loop == 352800,
          "AUTO 70-160: 4 bars, 120.0, 64 steps 1X, L = D: %u %u %u %u %u",
          t.tempo24, t.bars, t.len, t.scale, t.loop);
    CHECK(fl_tempo(&c, 0, 352850, &t) && t.tempo24 == 2880 && t.loop == 352800,
          "50 samples long: still 120.0, cut by 50");
    CHECK(fl_tempo(&c, 0, 352799, &t) && t.tempo24 == 2881 && t.loop <= 352799,
          "one sample short: tempo24 2881 (%u), L %u", t.tempo24, t.loop);
    c.bars[0] = 2;
    CHECK(fl_tempo(&c, 0, 352800, &t) && t.tempo24 == 1440 && t.len == 32,
          "fixed 2 bars: 60.0, out of AUTO's range but in 30-300");
    c.bars[0] = 16;
    CHECK(fl_tempo(&c, 0, 1411200, &t) && t.tempo24 == 2880 && t.len == 64 && t.scale == 5,
          "16 bars of 4/4 at 120: 64 steps 1/4X (%u %u)", t.len, t.scale);
    c.bars[0] = 8;
    CHECK(fl_tempo(&c, 0, 705600, &t) && t.len == 64 && t.scale == 4, "8 bars: 64 steps 1/2X");
    c.bars[0] = 0;
    c.sig[0] = 1;                                                   /* 3/4 */
    CHECK(fl_tempo(&c, 0, 352800, &t) && t.tempo24 == 2160 && t.bars == 4 && t.len == 48 && t.scale == 2,
          "3/4, 8 s: 4 bars at 90.0, 48 steps (%u %u %u)", t.tempo24, t.bars, t.len);
    c.sig[0] = 4;                                                   /* 7/8 */
    c.bars[0] = 16;
    CHECK(fl_tempo(&c, 0, 16u * 14u * 661500u / 120u, &t) && t.len == 56 && t.scale == 5,
          "7/8 16 bars: 56 steps 1/4X (%u %u)", t.len, t.scale);
}

static void test_tempo_limits(void) {
    FlConfig c; FlState s; rig(&c, &s);
    FlTempo t;
    CHECK(!fl_tempo(&c, 0, 0, &t), "empty take");
    CHECK(!fl_tempo(&c, 0, 1000, &t), "23 ms: no N gives 70-160");
    c.bars[0] = 1;
    CHECK(!fl_tempo(&c, 0, 88200u * 120u / 301u, &t), "1 bar faster than 300 BPM");
    CHECK(fl_tempo(&c, 0, 88200u * 120u / 300u, &t) && t.tempo24 == 7200, "1 bar at exactly 300");
    CHECK(fl_tempo(&c, 0, 88200u * 4u, &t) && t.tempo24 == 720, "1 bar at exactly 30");
    CHECK(!fl_tempo(&c, 0, 88200u * 4u + 2000u, &t), "1 bar slower than 30 BPM");
    c.bars[0] = 0;
    c.bpm_lo[0] = 100; c.bpm_hi[0] = 140;
    CHECK(!fl_tempo(&c, 0, 88200u * 120u / 90u * 4u, &t),
          "range 100-140, 4 bars at 90: 90 too slow, 8 bars (180) too fast: refused");
    CHECK(fl_tempo(&c, 0, 88200u * 120u / 120u * 4u, &t) && t.bars == 4 && t.tempo24 == 2880,
          "range 100-140, 4 bars at 120: 120.0");
}

/* Every take from 0.5 s to 60 s, every signature: the tempo is the slowest
 * tempo24 whose L fits, AUTO lands in range, the pattern is N bars, and
 * the cut is under 1/tempo24 of the take. */
static void test_tempo_sweep(void) {
    static const unsigned spbs[4] = {16, 12, 14, 20};
    static const uint8_t sigs[4] = {0, 1, 4, 3};
    FlConfig c; FlState s; rig(&c, &s);
    unsigned n = 0, worst_ppm = 0;
    for (unsigned k = 0; k < 4; ++k) {
        c.sig[0] = sigs[k];
        for (unsigned take = 22050; take < 2646000; take = take * 1009 / 1000 + 7) {
            FlTempo t;
            if (!fl_tempo(&c, 0, take, &t)) continue;
            ++n;
            unsigned T = t.len * ticks_of[t.scale];
            if (T != t.bars * spbs[k] * 6u || t.len < 2 || t.len > 64) {
                CHECK(0, "spb %u take %u: %u x scale %u is not %u bars", spbs[k], take, t.len, t.scale, t.bars);
                return;
            }
            if (t.loop != fl_loop_len(T, t.tempo24) || t.loop > take) {
                CHECK(0, "spb %u take %u: tempo24 %u L %u", spbs[k], take, t.tempo24, t.loop);
                return;
            }
            unsigned below = t.tempo24 - 1u;
            if (below >= 720 && fl_loop_len(T, below) <= take) {
                CHECK(0, "spb %u take %u: %u fits too, slower than %u", spbs[k], take, below, t.tempo24);
                return;
            }
            if (t.tempo24 < 70 * 24 || t.tempo24 > 160 * 24) {
                CHECK(0, "spb %u take %u: %u out of AUTO's 70-160", spbs[k], take, t.tempo24);
                return;
            }
            unsigned ppm = (unsigned)((unsigned long long)(take - t.loop) * 1000000ull / take);
            if (ppm > 1000000u / t.tempo24 + 20u) {
                CHECK(0, "spb %u take %u: cut %u ppm at tempo24 %u", spbs[k], take, ppm, t.tempo24);
                return;
            }
            if (ppm > worst_ppm) worst_ppm = ppm;
        }
    }
    CHECK(n > 1500, "the sweep found tempos (%u)", n);
    CHECK(worst_ppm <= 1000000u / (70u * 24u) + 20u, "the cut is at most 0.06%% of the take at 70 BPM (%u ppm)", worst_ppm);
    printf("  tempo sweep: %u takes, worst cut %u ppm\n", n, worst_ppm);
}

static void test_session(void) {
    FlConfig c; FlState s; rig(&c, &s);
    FlAction a;
    char buf[20];
    a = fl_rec(&s, &c, 1, 0, 0, 0, 0);
    CHECK(a.toast == FL_T_ARMED && s.st[1] == FL_ARMED, "REC on T2 (GRID), stopped, nothing anywhere: armed");
    a = fl_rec(&s, &c, 1, 0, 0, 0, 0);
    CHECK(s.st[1] == FL_IDLE && a.toast == FL_T_OVERDUB_OFF, "REC again: cancelled");

    a = fl_rec(&s, &c, 0, 0, 1, 0, 0);
    CHECK(a.kind == FL_DO_TOAST && a.toast == FL_T_SLAVE && s.st[0] == FL_IDLE, "slave: refused");
    a = fl_rec(&s, &c, 0, 0, 0, 0, 0);
    CHECK(a.kind == FL_DO_TAKE && a.track == 0 && s.st[0] == FL_TAKE, "REC on T1 FREE, stopped, empty: a free take");
    CHECK(strcmp(fl_label(&a, buf), "T1 FREE LOOP") == 0, "label %s", buf);
    a = fl_rec(&s, &c, 2, 0, 0, 0, 0);
    CHECK(a.toast == FL_T_BUSY && s.st[2] == FL_IDLE, "REC on T3 during T1's take: busy");
    a = fl_play(&s, &c, 2, 10, 0, 0, 0);
    CHECK(a.toast == FL_T_BUSY, "PLAY on T3 during T1's take: busy");
    CHECK(fl_hold(&s, &c, 2, 10 + 2 * FL_LONG, 0, 0).kind == FL_DO_NOTHING, "held long after: no clear");
    a = fl_rec(&s, &c, 0, 0, 0, 500, 0);
    CHECK(a.kind == FL_DO_TOAST && a.toast == FL_T_RANGE && s.st[0] == FL_TAKE, "too short to end: still taking");
    a = fl_rec(&s, &c, 0, 0, 0, 352800, 0);
    CHECK(a.kind == FL_DO_LAUNCH && a.tempo.tempo24 == 2880 && s.st[0] == FL_IDLE && s.has[0],
          "REC again: launch at 120.0, T1 loops");
    CHECK(strcmp(fl_label(&a, buf), "120.0 BPM 4 BARS") == 0, "label %s", buf);

    CHECK(!fl_gate(&s, &c, 0) && !fl_gate(&s, &c, 1), "playing, nothing armed: recorder trigs dropped");
    CHECK(fl_gate(&s, &c, 5), "T6 (OFF) keeps stock recorder trigs");
    a = fl_rec(&s, &c, 1, 1, 0, 0, 0);
    CHECK(a.toast == FL_T_ARMED && s.st[1] == FL_ARMED, "T2: armed");
    CHECK(strcmp(fl_label(&a, buf), "T2 OVERDUB ARMED") == 0, "label %s", buf);
    CHECK(fl_gate(&s, &c, 1) && s.st[1] == FL_OVERDUB && s.has[1], "T2's next recorder trig fires: overdub");
    CHECK(fl_gate(&s, &c, 1), "and the next pass");
    a = fl_rec(&s, &c, 1, 1, 0, 0, 0);
    CHECK(s.st[1] == FL_IDLE && a.toast == FL_T_OVERDUB_OFF && !fl_gate(&s, &c, 1), "T2 cut");
    a = fl_rec(&s, &c, 2, 1, 0, 0, 0);
    CHECK(s.st[2] == FL_ARMED, "T3 FREE once a tempo exists: overdub like GRID");

    const uint32_t T0 = 0xfffff000u;                                 /* the count wraps during the hold */
    a = fl_play(&s, &c, 1, T0, 1, 0, 0);
    CHECK(a.kind == FL_DO_NOTHING && a.mute == FL_MUTE && a.toast == FL_T_MUTED, "PLAY/STOP on T2 playing, MUTE NOW: mute at the press");
    CHECK(strcmp(fl_label(&a, buf), "T2 MUTED") == 0, "label %s", buf);
    CHECK(fl_hold(&s, &c, 1, T0 + FL_LONG - 1, 1, 1).kind == FL_DO_NOTHING, "held just under 1 s: nothing more");
    fl_release(&s, 1, FL_HELD_PLAY);
    CHECK(!s.held[1] && fl_hold(&s, &c, 1, T0 + 2 * FL_LONG, 1, 1).kind == FL_DO_NOTHING, "released: nothing more");
    a = fl_play(&s, &c, 1, T0 + 2 * FL_LONG, 1, 1, 0);
    CHECK(a.mute == FL_UNMUTE && a.toast == FL_T_UNMUTED, "again, muted: unmute at the press");
    a = fl_hold(&s, &c, 1, T0 + 3 * FL_LONG, 1, 0);
    CHECK(a.toast == FL_T_END_PLAY && a.mute == FL_MUTE && s.qpend[1] == FL_UNMUTE,
          "held 1 s across the wrap: the unmute undone, END (back at its loop start)");
    CHECK(fl_hold(&s, &c, 1, T0 + 4 * FL_LONG, 1, 1).kind == FL_DO_NOTHING, "held on: once only");
    fl_release(&s, 1, FL_HELD_REC);
    CHECK(s.held[1], "the other pedal's release: still held");
    fl_release(&s, 1, FL_HELD_PLAY);
    CHECK(!s.held[1], "its release");
    s.qpend[1] = 0;
    c.endmute = 2;                                                   /* T2 MUTE END */
    a = fl_play(&s, &c, 1, 100, 1, 0, 0);
    CHECK(a.toast == FL_T_END_STOP && !a.mute && s.qpend[1] == FL_MUTE, "MUTE END: the press is END, at once");
    CHECK(fl_hold(&s, &c, 1, 100 + FL_LONG, 1, 0).kind == FL_DO_NOTHING && s.qpend[1] == FL_MUTE,
          "held: the same END, nothing more");
    fl_release(&s, 1, FL_HELD_PLAY);
    c.endmute = 0;
    s.qpend[1] = 0;

    s.has[1] = 1;                                                    /* REC's long press */
    s.st[1] = FL_IDLE;
    a = fl_rec(&s, &c, 1, 1, 0, 0, 500);
    CHECK(a.toast == FL_T_ARMED && s.held[1] == FL_HELD_REC, "REC: armed at once, held");
    CHECK(fl_hold(&s, &c, 1, 500 + FL_LONG - 1, 1, 0).kind == FL_DO_NOTHING, "under 1 s: armed still");
    CHECK(fl_gate(&s, &c, 1) && s.st[1] == FL_OVERDUB, "its pass records");
    a = fl_hold(&s, &c, 1, 500 + FL_LONG, 1, 0);
    CHECK(a.toast == FL_T_NO_BUFFER && !a.mute && s.st[1] == FL_IDLE && s.has[1],
          "T2 heard, no UNDO buffer: REC held = NO UNDO BUFFER, the arm undone, nothing cleared");
    fl_release(&s, 1, FL_HELD_REC);
    a = fl_rec(&s, &c, 1, 1, 0, 0, 700);
    CHECK(s.st[1] == FL_ARMED, "armed again");
    a = fl_hold(&s, &c, 1, 700 + FL_LONG, 1, 1);
    CHECK(a.kind == FL_DO_CLEAR && !a.mute && s.st[1] == FL_IDLE && !s.has[1] && !fl_gate(&s, &c, 1),
          "T2 muted: REC held = its loop cleared, no mute change");
    fl_release(&s, 1, FL_HELD_REC);
    s.has[1] = 1;
    a = fl_rec(&s, &c, 1, 1, 0, 0, 900);
    fl_release(&s, 1, FL_HELD_REC);
    CHECK(fl_hold(&s, &c, 1, 900 + 2 * FL_LONG, 1, 0).kind == FL_DO_NOTHING && s.st[1] == FL_ARMED && s.has[1],
          "REC released at once: armed, nothing cleared");
    fl_stopped(&s);
    CHECK(s.st[2] == FL_IDLE, "the stop disarms T3");

    a = fl_play(&s, &c, 0, 3000, 0, 1, 0);
    CHECK(a.kind == FL_DO_PLAY && a.mute == FL_UNMUTE && s.started[0] == 1, "PLAY/STOP stopped: play at the press, T1 heard");
    CHECK(fl_hold(&s, &c, 0, 3000 + FL_LONG, 1, 0).kind == FL_DO_NOTHING && s.has[0], "held: nothing more");
    fl_release(&s, 0, FL_HELD_PLAY);
    a = fl_rec(&s, &c, 0, 0, 0, 0, 9000);
    CHECK(a.toast == FL_T_ARMED, "stopped, T1 has its loop: REC arms");
    a = fl_hold(&s, &c, 0, 9000 + FL_LONG, 0, 0);
    CHECK(a.kind == FL_DO_CLEAR && !s.has[0] && s.st[0] == FL_IDLE, "the sequencer stopped (nothing plays): REC held clears");
    CHECK(strcmp(fl_label(&a, buf), "T1 CLEARED") == 0, "label %s", buf);
    fl_release(&s, 0, FL_HELD_REC);

    fl_reset(&s);
    a = fl_rec(&s, &c, 0, 0, 0, 0, 0);
    CHECK(a.kind == FL_DO_TAKE, "nothing anywhere: a free take");
    a = fl_play(&s, &c, 0, 4000, 0, 0, 352800);
    CHECK(a.kind == FL_DO_LAUNCH && s.started[0] == 3, "PLAY/STOP during the take ends it too");
    a = fl_hold(&s, &c, 0, 4000 + 3 * FL_LONG, 1, 0);
    CHECK(a.kind == FL_DO_NOTHING && s.has[0], "the launch press held long: nothing");

    fl_reset(&s);
    a = fl_rec(&s, &c, 0, 0, 0, 0, 7000);
    CHECK(a.kind == FL_DO_TAKE && s.held[0] == FL_HELD_REC, "a free take, REC held");
    a = fl_hold(&s, &c, 0, 7000 + FL_LONG, 0, 0);
    CHECK(a.kind == FL_DO_CLEAR && s.st[0] == FL_IDLE && !s.has[0], "held 1 s: the take dropped");
    a = fl_rec(&s, &c, 0, 0, 0, 0, 9000);
    CHECK(a.kind == FL_DO_TAKE, "and the next press takes again");
    fl_release(&s, 0, FL_HELD_REC);
    a = fl_rec(&s, &c, 0, 0, 0, 352800, 20000);
    CHECK(a.kind == FL_DO_LAUNCH && !s.held[0], "the take's end: not held");
    CHECK(fl_hold(&s, &c, 0, 20000 + 3 * FL_LONG, 1, 0).kind == FL_DO_NOTHING && s.has[0], "so never a clear");
}

static void test_off_and_patterns(void) {
    FlConfig c; FlState s;
    memset(&c, 0, sizeof c); memset(&s, 0, sizeof s);
    CHECK(fl_rec(&s, &c, 0, 0, 0, 0, 0).kind == FL_DO_NOTHING, "zeroed config: REC does nothing");
    CHECK(fl_play(&s, &c, 0, 1, 0, 0, 0).kind == FL_DO_NOTHING, "zeroed config: PLAY/STOP does nothing");
    for (unsigned t = 0; t < FL_TRACKS; ++t) CHECK(fl_gate(&s, &c, t), "zeroed config: stock recorder trigs");
    CHECK(fl_rec(&s, &c, 9, 0, 0, 0, 0).kind == FL_DO_NOTHING, "out of range");

    rig(&c, &s);
    c.mode[0x11] = FL_MODE_OFF | FL_MODE_ARM << 2 | FL_MODE_ARM << 6;   /* B2: T1 OFF, T2 ARM, T4 ARM */
    c.mode[0x12] = FL_MODE_OFF << 2;                                     /* B3: T2 OFF */
    s.st[0] = FL_OVERDUB;
    CHECK(fl_pattern(&s, &c, 0x10) == 1, "first sight of B1");
    CHECK(s.st[0] == FL_OVERDUB, "B1 is KEEP");
    CHECK(fl_pattern(&s, &c, 0x10) == 0, "the same pattern: no change");
    fl_pattern(&s, &c, 0x11);
    CHECK(s.st[0] == FL_IDLE && s.st[1] == FL_ARMED && s.st[3] == FL_ARMED && s.st[2] == FL_IDLE,
          "B2 lands: T1 cut, T2 and T4 armed from step 1");
    fl_pattern(&s, &c, 0x12);
    CHECK(s.st[1] == FL_IDLE && s.st[3] == FL_ARMED, "B3: T2 cut, T4 kept");
    s.st[0] = FL_TAKE;
    c.mode[0x13] = FL_MODE_OFF;
    fl_pattern(&s, &c, 0x13);
    CHECK(s.st[0] == FL_TAKE, "a free take is not touched by a pattern change");
    c.role[3] = FL_ROLE_OFF;
    c.mode[0x14] = FL_MODE_OFF << 6;
    fl_pattern(&s, &c, 0x14);
    CHECK(s.st[3] == FL_ARMED, "a track with no role is not touched");
}

static void test_panel(void) {
    FlConfig c; memset(&c, 0, sizeof c);
    char v[8];
    CHECK(strcmp(fl_row_value(&c, 0, FL_ROW_ROLE, 0, v), "OFF") == 0, "%s", v);
    CHECK(strcmp(fl_row_value(&c, 0, FL_ROW_SIGN, 0, v), "4/4") == 0, "%s", v);
    CHECK(strcmp(fl_row_value(&c, 0, FL_ROW_BARS, 0, v), "AUTO") == 0, "%s", v);
    CHECK(strcmp(fl_row_value(&c, 0, FL_ROW_MIN, 0, v), "70") == 0, "%s", v);
    CHECK(strcmp(fl_row_value(&c, 0, FL_ROW_MAX, 0, v), "160") == 0, "%s", v);
    CHECK(strcmp(fl_row_value(&c, 0, FL_ROW_ENTRY, 5, v), "KEEP") == 0, "%s", v);
    CHECK(strcmp(fl_row_value(&c, 0, FL_ROW_UNDO, 0, v), "OFF") == 0, "%s", v);
    CHECK(fl_row_edit(&c, 0, FL_ROW_UNDO, 0, 1) && c.ubuf[0] == 2, "T1 UNDO OFF +1 = R2 (R1 skipped)");
    CHECK(fl_row_edit(&c, 0, FL_ROW_UNDO, 0, 3) && strcmp(fl_row_value(&c, 0, FL_ROW_UNDO, 0, v), "R5") == 0, "%s", v);
    CHECK(fl_row_edit(&c, 1, FL_ROW_UNDO, 0, 2) && c.ubuf[1] == 3, "T2 OFF +2 = R3 (R2 skipped)");
    CHECK(fl_row_edit(&c, 1, FL_ROW_UNDO, 0, -2) && c.ubuf[1] == 0, "T2 R3 -2 = OFF");
    CHECK(fl_row_edit(&c, 7, FL_ROW_UNDO, 0, 20) && c.ubuf[7] == 7, "T8 clamps at R7");
    CHECK(strcmp(fl_row_value(&c, 2, FL_ROW_POPUP, 0, v), "OFF") == 0, "%s", v);
    CHECK(fl_row_edit(&c, 2, FL_ROW_POPUP, 0, 1) && c.popup == 4 && !fl_row_edit(&c, 2, FL_ROW_POPUP, 0, 1),
          "T3 POPUP ON (bit 2), clamps");
    CHECK(strcmp(fl_row_value(&c, 2, FL_ROW_POPUP, 0, v), "ON") == 0, "%s", v);
    {
        FlState s; memset(&s, 0, sizeof s);
        c.role[2] = FL_ROLE_GRID;
        CHECK(fl_pop_state(&s, &c, 2, 0) == FL_POP_NONE, "idle: no popup");
        s.st[2] = FL_ARMED;
        CHECK(fl_pop_state(&s, &c, 2, 0) == FL_POP_ARMED, "armed");
        s.st[2] = FL_OVERDUB;
        CHECK(fl_pop_state(&s, &c, 2, 1) == FL_POP_OVERDUB, "overdub");
        s.st[2] = FL_IDLE;
        CHECK(fl_pop_state(&s, &c, 2, 1) == FL_POP_ENDING, "cut, the pass still recording: ending");
        s.st[2] = FL_TAKE;
        CHECK(fl_pop_state(&s, &c, 2, 1) == FL_POP_TAKE, "the free take");
        CHECK(fl_pop_state(&s, &c, 1, 1) == FL_POP_NONE, "POPUP OFF: none");
        CHECK(fl_row_edit(&c, 2, FL_ROW_POPUP, 0, -1) && c.popup == 0, "T3 POPUP OFF");
    }
    c.ubuf[7] = 0;
    CHECK(fl_row_edit(&c, 0, FL_ROW_ROLE, 0, 5) && c.role[0] == FL_ROLE_FREE, "ROLE clamps at FREE");
    CHECK(!fl_row_edit(&c, 0, FL_ROW_ROLE, 0, 1), "no change past the end");
    CHECK(fl_row_edit(&c, 2, FL_ROW_SIGN, 0, 2) && strcmp(fl_row_value(&c, 2, FL_ROW_SIGN, 0, v), "6/8") == 0
          && fl_spb(c.sig[2]) == 12, "SIGN 6/8: 12 steps a bar");
    CHECK(fl_row_edit(&c, 0, FL_ROW_BARS, 0, 3) && c.bars[0] == 4, "BARS AUTO +3 = 4");
    CHECK(fl_row_edit(&c, 0, FL_ROW_BARS, 0, -9) && c.bars[0] == 0, "back to AUTO");
    CHECK(fl_row_edit(&c, 0, FL_ROW_MIN, 0, 200) && c.bpm_lo[0] == 160, "MIN stops at MAX");
    CHECK(!fl_row_edit(&c, 0, FL_ROW_MAX, 0, -200) && strcmp(fl_row_value(&c, 0, FL_ROW_MAX, 0, v), "160") == 0,
          "MAX cannot go under MIN");
    CHECK(fl_row_edit(&c, 0, FL_ROW_MIN, 0, -500) && c.bpm_lo[0] == 30, "MIN floor 30");
    CHECK(fl_row_edit(&c, 0, FL_ROW_MAX, 0, 500) && c.bpm_hi[0] == 300, "MAX ceiling 300");
    CHECK(fl_row_edit(&c, 3, FL_ROW_ENTRY, 0x21, 1) && strcmp(fl_row_value(&c, 3, FL_ROW_ENTRY, 0x21, v), "ARM") == 0,
          "ENTRY of C2 for T4: ARM");
    CHECK(((c.mode[0x21] >> 6) & 3) == FL_MODE_ARM && (c.mode[0x21] & 0x3f) == 0, "only T4's bits");
    CHECK(fl_row_edit(&c, 3, FL_ROW_ENTRY, 0x21, 1) && ((c.mode[0x21] >> 6) & 3) == FL_MODE_OFF, "then OFF");
    CHECK(strcmp(fl_row_name(FL_ROW_MAX), "MAX BPM") == 0, "row name");
    CHECK(strcmp(fl_row_value(&c, 1, FL_ROW_PLAY, 0x21, v), "KEEP") == 0, "%s", v);
    CHECK(fl_row_edit(&c, 1, FL_ROW_PLAY, 0x21, 2) && fl_play_entry(&c, 1, 0x21) == FL_PLAY_STOP
          && strcmp(fl_row_value(&c, 1, FL_ROW_PLAY, 0x21, v), "STOP") == 0, "PLAY of C2 for T2: STOP");
    CHECK(fl_row_edit(&c, 1, FL_ROW_PLAY, 0x21, 5) && fl_play_entry(&c, 1, 0x21) == FL_PLAY_PLAY
          && !fl_row_edit(&c, 1, FL_ROW_PLAY, 0x21, 1), "then PLAY, clamped");
    CHECK(((c.mode[0x21] >> 6) & 3) == FL_MODE_OFF && fl_play_entry(&c, 3, 0x21) == FL_PLAY_KEEP
          && fl_play_entry(&c, 1, 0x22) == FL_PLAY_KEEP, "ENTRY, other tracks and patterns untouched");
    CHECK(strcmp(fl_row_name(FL_ROW_PLAY), "PLAY") == 0, "row name PLAY");
    CHECK(fl_row_edit(&c, 3, FL_ROW_ENTRY, 0x21, 1) && strcmp(fl_row_value(&c, 3, FL_ROW_ENTRY, 0x21, v), "REPLACE") == 0
          && !fl_row_edit(&c, 3, FL_ROW_ENTRY, 0x21, 1), "ENTRY: OFF then REPLACE, clamped");
    CHECK(strcmp(fl_row_name(FL_ROW_UNDOTO), "UNDO TO") == 0 && strcmp(fl_row_value(&c, 0, FL_ROW_UNDOTO, 0, v), "LAST") == 0,
          "UNDO TO: LAST by default (%s)", v);
    CHECK(fl_row_edit(&c, 0, FL_ROW_UNDOTO, 0, 1) && c.undoto[0] == 1 && strcmp(fl_row_value(&c, 0, FL_ROW_UNDOTO, 0, v), "1") == 0,
          "UNDO TO 1 (%s)", v);
    CHECK(fl_row_edit(&c, 0, FL_ROW_UNDOTO, 0, 40) && c.undoto[0] == FL_UNDO_TO_MAX && !fl_row_edit(&c, 0, FL_ROW_UNDOTO, 0, 1)
          && fl_row_edit(&c, 0, FL_ROW_UNDOTO, 0, -40) && c.undoto[0] == 0, "UNDO TO clamps at 16 and LAST");
}

static void test_end(void) {
    FlConfig c; FlState s; rig(&c, &s);
    FlAction a;
    char buf[20];
    a = fl_end(&s, &c, 0, 1, 0);
    CHECK(a.toast == FL_T_END_STOP && a.mute == 0 && s.qpend[0] == FL_MUTE && fl_end_pending(&s),
          "END playing, heard: the mute waits for the loop start");
    CHECK(strcmp(fl_label(&a, buf), "T1 STOPS AT END") == 0, "label %s", buf);
    CHECK(fl_loop_start(&s, 1) == 0, "another track's loop start: nothing");
    CHECK(fl_loop_start(&s, 0) == FL_MUTE && !fl_end_pending(&s), "T1's loop start: muted, taken once");
    CHECK(fl_loop_start(&s, 0) == 0, "the next one: nothing");
    a = fl_end(&s, &c, 0, 1, 1);
    CHECK(a.toast == FL_T_END_PLAY && s.qpend[0] == FL_UNMUTE, "END muted: back at the next loop start");
    CHECK(strcmp(fl_label(&a, buf), "T1 PLAYS AT START") == 0, "label %s", buf);
    a = fl_end(&s, &c, 0, 1, 1);
    CHECK(a.toast == FL_T_END_CANCEL && !s.qpend[0] && !fl_end_pending(&s), "pressed again: cancelled");
    a = fl_end(&s, &c, 0, 0, 0);
    CHECK(a.mute == FL_MUTE && !s.qpend[0], "stopped: at once");
    fl_end(&s, &c, 2, 1, 0);
    fl_stopped(&s);
    CHECK(!fl_end_pending(&s), "a stop drops a pending END");
    CHECK(fl_end(&s, &c, 6, 1, 0).kind == FL_DO_NOTHING, "OFF track: nothing");
}


/* UNDO: T1 on R1 with R5 as its UNDO buffer; the passes ping-pong. */
static void test_undo(void) {
    FlConfig c; FlState s; rig(&c, &s);
    c.ubuf[0] = 5;
    s.has[0] = 1;
    CHECK(fl_undo_buffer(&c, 0) == 5 && fl_undo_buffer(&c, 1) == 0, "T1 R5, T2 none");
    c.ubuf[1] = 2;
    CHECK(fl_undo_buffer(&c, 1) == 0, "a track's own buffer is no UNDO buffer");
    c.ubuf[1] = 0;
    CHECK(fl_undo(&s, &c, 1).toast == FL_T_NO_BUFFER, "T2: no UNDO buffer");
    CHECK(fl_undo(&s, &c, 0).toast == FL_T_NO_UNDO, "nothing recorded yet");

    fl_rec(&s, &c, 0, 1, 0, 0, 0);                                       /* armed */
    CHECK(fl_gate(&s, &c, 0) == 0, "pass 1 on R1: T1's own trig does not fire");
    CHECK(s.rec[0] == 2 && s.swap[0] && s.inj[4] == 1, "R5's recorder takes the pass");
    CHECK(fl_inject(&s, 4) == 1 && fl_inject(&s, 4) == 0, "T5's gate takes it once");
    CHECK(s.cur[0] == 0, "still on R1 until the recorder runs");
    fl_rec_running(&s, 0);
    CHECK(s.cur[0] == 1 && !s.swap[0], "switched to R5 for the next pass");
    CHECK(fl_undo(&s, &c, 0).kind == FL_DO_CUT && s.cur[0] == 0 && s.st[0] == FL_IDLE && !s.rec[0],
          "UNDO during the pass: dropped, back on R1, overdub off");
    CHECK(fl_undo(&s, &c, 0).toast == FL_T_NO_UNDO, "and no redo");

    fl_rec(&s, &c, 0, 1, 0, 0, 0);
    fl_gate(&s, &c, 0); fl_inject(&s, 4); fl_rec_running(&s, 0);     /* pass 1 into R5 */
    fl_rec(&s, &c, 0, 1, 0, 0, 0);                                       /* cut: the pass finishes */
    CHECK(s.st[0] == FL_IDLE && s.rec[0] == 2, "the cut lets the pass finish");
    CHECK(fl_gate(&s, &c, 0) == 0 && !s.rec[0] && s.valid[0] && s.cur[0] == 1, "pass over: on R5, R1 the undo");
    FlAction a = fl_undo(&s, &c, 0);
    CHECK(a.toast == FL_T_UNDO && s.cur[0] == 0, "UNDO: back on R1");
    a = fl_undo(&s, &c, 0);
    CHECK(a.toast == FL_T_REDO && s.cur[0] == 1, "REDO: R5");

    fl_release(&s, 0, FL_HELD_REC);                                   /* REC held: UNDO */
    a = fl_rec(&s, &c, 0, 1, 0, 0, 100);
    CHECK(a.toast == FL_T_ARMED && s.st[0] == FL_ARMED, "REC at rest: armed at the press");
    CHECK(fl_hold(&s, &c, 0, 100 + FL_LONG - 1, 1, 0).kind == FL_DO_NOTHING, "under 1 s: nothing");
    a = fl_hold(&s, &c, 0, 100 + FL_LONG, 1, 0);
    CHECK(a.toast == FL_T_UNDO && s.cur[0] == 0 && s.st[0] == FL_IDLE && s.has[0],
          "held 1 s: the arm undone, UNDO (R1), nothing cleared");
    fl_release(&s, 0, FL_HELD_REC);
    a = fl_rec(&s, &c, 0, 1, 0, 0, 200);
    a = fl_hold(&s, &c, 0, 200 + FL_LONG, 1, 0);
    CHECK(a.toast == FL_T_REDO && s.cur[0] == 1 && s.st[0] == FL_IDLE, "again: REDO (R5)");
    fl_release(&s, 0, FL_HELD_REC);

    fl_rec(&s, &c, 0, 1, 0, 0, 0);                                       /* on R5: pass 2 into R1 */
    CHECK(fl_gate(&s, &c, 0) == 1 && s.rec[0] == 1 && !s.inj[4], "T1's own recorder, into R1");
    fl_rec_running(&s, 0);
    CHECK(s.cur[0] == 0, "switched to R1");
    CHECK(fl_gate(&s, &c, 0) == 0 && s.rec[0] == 2 && s.inj[4] == 1 && s.cur[0] == 0 && !s.valid[0],
          "overdub goes on: pass 3 into R5, no undo while it records");
    fl_release(&s, 0, FL_HELD_REC);
    a = fl_rec(&s, &c, 0, 1, 0, 0, 300);                               /* cut, held: the pass dropped */
    CHECK(a.toast == FL_T_OVERDUB_OFF, "REC during the pass: cut");
    a = fl_hold(&s, &c, 0, 300 + FL_LONG, 1, 0);
    CHECK(a.kind == FL_DO_CUT && a.toast == FL_T_UNDO_CUT && s.st[0] == FL_IDLE && !s.rec[0] && s.cur[0] == 0,
          "held 1 s: the pass dropped (its recorder cut), on R1");
    fl_release(&s, 0, FL_HELD_REC);
    fl_rec(&s, &c, 0, 1, 0, 0, 0);
    fl_gate(&s, &c, 0);                                               /* pass into R5 */
    fl_stopped(&s);
    CHECK(s.cur[0] == 0 && !s.rec[0] && !s.inj[4], "a stop drops the pass (not yet switched): on R1");

    s.cur[0] = 1; s.valid[0] = 1;
    fl_cleared(&s, 0);
    CHECK(!s.cur[0] && !s.valid[0] && !s.has[0], "a clear: back on its own buffer");
}

/* One pass of T1 (R1, UNDO buffer R5) at a loop start: the gate, the
 * injected trig, the recorder running, then the pass over at the next gate. */
static unsigned pass(FlState *s, const FlConfig *c) {
    unsigned own = fl_gate(s, c, 0);
    if (!own) fl_inject(s, 4);
    fl_rec_running(s, 0);
    return own;
}

/* UNDO TO 1: a take and four passes, UNDO goes back to the take. */
static void test_undo_to(void) {
    FlConfig c; FlState s; rig(&c, &s);
    c.ubuf[0] = 5;
    c.undoto[0] = 1;
    fl_rec(&s, &c, 0, 0, 0, 0, 0);                                       /* the take into R1 */
    FlAction a = fl_rec(&s, &c, 0, 0, 0, 352800, 0);
    CHECK(a.kind == FL_DO_LAUNCH && s.npass[0] == 1 && s.anchor[0] == (2 | 0), "the take: recording 1, UNDO TO's (R1)");
    fl_rec(&s, &c, 0, 1, 0, 0, 0);                                       /* overdub on */
    CHECK(pass(&s, &c) == 0 && s.rec[0] == 2 && !s.inplace[0], "pass 2: from R1, UNDO TO's, into R5 (ping-pong)");
    CHECK(pass(&s, &c) == 0 && s.npass[0] == 2 && s.cur[0] == 1, "pass 2 over: on R5");
    CHECK(s.rec[0] == 2 && s.inplace[0] && !s.swap[0] && s.inj[4] == 0, "pass 3: R5 in place, R5's recorder (injected)");
    CHECK(s.cur[0] == 1 && s.valid[0], "still on R5, R1 the undo");
    pass(&s, &c); pass(&s, &c);                                          /* passes 4, 5 */
    CHECK(s.cur[0] == 1 && s.inplace[0] && s.npass[0] == 4, "pass 5 in place on R5 (4 over)");
    a = fl_undo(&s, &c, 0);
    CHECK(a.kind == FL_DO_CUT && a.toast == FL_T_UNDO && s.cur[0] == 0 && s.st[0] == FL_IDLE && !s.rec[0],
          "UNDO during pass 5: stopped, back on R1 (the take)");
    a = fl_undo(&s, &c, 0);
    CHECK(a.toast == FL_T_REDO && s.cur[0] == 1, "REDO: R5, the passes");
    a = fl_undo(&s, &c, 0);
    CHECK(a.toast == FL_T_UNDO && s.cur[0] == 0, "UNDO again: the take");
    fl_rec(&s, &c, 0, 1, 0, 0, 0);
    CHECK(pass(&s, &c) == 0 && s.rec[0] == 2 && !s.inplace[0], "a pass from the take: into R5 (the latest is gone)");
    pass(&s, &c);
    CHECK(s.cur[0] == 1 && s.inplace[0] && s.anchor[0] == 2, "then in place again, R1 still UNDO TO's");
    fl_rec(&s, &c, 0, 1, 0, 0, 0);                                       /* cut: the pass finishes */
    fl_gate(&s, &c, 0);
    a = fl_undo(&s, &c, 0);
    CHECK(a.toast == FL_T_UNDO && s.cur[0] == 0, "at rest: UNDO, the take");

    rig(&c, &s);                                                         /* UNDO TO 2 on a GRID start */
    c.ubuf[0] = 5;
    c.undoto[0] = 2;
    s.has[0] = 1;
    fl_rec(&s, &c, 0, 1, 0, 0, 0);
    pass(&s, &c);                                                        /* 1: R1 -> R5 */
    pass(&s, &c);                                                        /* 2: R5 -> R1 */
    CHECK(s.npass[0] == 1 && !s.inplace[0] && s.rec[0] == 1, "UNDO TO 2: the 2nd pass ping-pongs too");
    pass(&s, &c);                                                        /* 3: from R1, into R5 */
    CHECK(s.npass[0] == 2 && s.anchor[0] == (4 | 0) && !s.inplace[0] && s.cur[0] == 1 && s.rec[0] == 2,
          "recording 2 on R1, UNDO TO's; pass 3 from it into R5");
    pass(&s, &c);
    CHECK(s.inplace[0] && s.rec[0] == 2 && s.cur[0] == 1, "pass 4: R5 in place");
    fl_stopped(&s);
    CHECK(!s.rec[0] && s.cur[0] == 1 && s.valid[0], "a stop during it: on R5, R1 still the undo");
    CHECK(fl_undo(&s, &c, 0).toast == FL_T_UNDO && s.cur[0] == 0, "UNDO: recording 2");
    fl_cleared(&s, 0);
    CHECK(!s.npass[0] && !s.anchor[0], "a clear forgets the count");

    rig(&c, &s);                                                         /* UNDO TO 1 on a GRID start */
    c.ubuf[0] = 5;
    c.undoto[0] = 1;
    s.has[0] = 1;
    fl_rec(&s, &c, 0, 1, 0, 0, 0);
    pass(&s, &c);                                                        /* 1: into R5 */
    CHECK(pass(&s, &c) == 1 && s.anchor[0] == (2 | 1) && s.rec[0] == 1, "recording 1 on R5; pass 2 into R1 (T1's own)");
    CHECK(pass(&s, &c) == 1 && s.inplace[0] && s.rec[0] == 1 && s.cur[0] == 0, "pass 3: R1 in place, T1's own trig");
    CHECK(fl_undo(&s, &c, 0).kind == FL_DO_CUT && s.cur[0] == 1, "UNDO: recording 1 (R5)");
    c.undoto[0] = 3;
    fl_rec(&s, &c, 0, 1, 0, 0, 0);
    CHECK(pass(&s, &c) == 1 && !s.inplace[0], "UNDO TO changed (3): ping-pong until its recording comes");
}

/* ENTRY REPLACE: one pass, inputs only, the track muted while it records. */
static void test_replace(void) {
    FlConfig c; FlState s; rig(&c, &s);
    c.ubuf[0] = 5;
    c.undoto[0] = 1;
    s.has[0] = 1;
    s.npass[0] = 3;
    s.anchor[0] = 2;
    c.mode[1] = FL_MODE_REPLACE;                                         /* A02: T1 REPLACE */
    fl_pattern(&s, &c, 0);
    fl_pattern(&s, &c, 1);
    CHECK(s.st[0] == FL_ARMED && s.repl[0], "A02: T1 armed to replace");
    CHECK(fl_pop_state(&s, &c, 0, 0) == FL_POP_NONE, "popup OFF: nothing");
    c.popup = 1;
    CHECK(fl_pop_state(&s, &c, 0, 0) == FL_POP_ARMED, "popup: armed");
    s.qpend[0] = FL_MUTE;                                                /* an END pending: the REPLACE's */
    CHECK(fl_gate(&s, &c, 0) == 0 && s.rpass[0] == FL_RP_MUTE && s.st[0] == FL_IDLE && !s.repl[0],
          "the pass: one, replacing (R5's, ping-pong), then idle");
    CHECK(!s.inplace[0] && s.rec[0] == 2 && !s.qpend[0] && s.npass[0] == 0 && !s.anchor[0], "never in place; the count anew");
    CHECK(fl_end_pending(&s), "a loop start is due");
    fl_inject(&s, 4); fl_rec_running(&s, 0);
    CHECK(fl_replace_start(&s, 0) == FL_MUTE && s.rpass[0] == FL_RP_UNMUTE, "muted at its loop start");
    CHECK(fl_pop_state(&s, &c, 0, 1) == FL_POP_REPLACE && fl_pop_state(&s, &c, 0, 0) == FL_POP_NONE, "popup: REPLACE while it records");
    CHECK(fl_gate(&s, &c, 0) == 0 && !s.rec[0] && s.npass[0] == 1 && s.anchor[0] == (2 | 1), "over: recording 1 (R5), UNDO TO's");
    CHECK(fl_replace_start(&s, 0) == FL_UNMUTE && s.rpass[0] == FL_RP_NONE && !fl_end_pending(&s), "heard at the next loop start");
    CHECK(fl_replace_start(&s, 0) == 0, "once");
    CHECK(fl_undo(&s, &c, 0).toast == FL_T_UNDO && s.cur[0] == 0, "UNDO: the loop before the REPLACE (R1)");

    rig(&c, &s);                                                         /* no UNDO buffer */
    s.has[0] = 1;
    c.mode[1] = FL_MODE_REPLACE;
    fl_pattern(&s, &c, 1);
    CHECK(fl_gate(&s, &c, 0) == 1 && s.rpass[0] == FL_RP_MUTE && !s.rec[0], "no UNDO buffer: T1's own trig, replacing");
    CHECK(fl_gate(&s, &c, 0) == 0, "one pass only");
    fl_replace_start(&s, 0);
    fl_stopped(&s);
    CHECK(s.rpass[0] == FL_RP_NOW && !fl_end_pending(&s), "stopped while muted by it: heard again at once");

    rig(&c, &s);                                                         /* REC cuts the armed REPLACE */
    s.has[0] = 1;
    c.mode[1] = FL_MODE_REPLACE;
    fl_pattern(&s, &c, 1);
    fl_rec(&s, &c, 0, 1, 0, 0, 0);
    CHECK(s.st[0] == FL_IDLE && !s.repl[0], "REC: cut");
    fl_rec(&s, &c, 0, 1, 0, 0, 0);
    CHECK(fl_gate(&s, &c, 0) == 1 && s.rpass[0] == FL_RP_NONE && s.st[0] == FL_OVERDUB, "armed again: an overdub");

    rig(&c, &s);                                                         /* UNDO during a REPLACE pass */
    c.ubuf[0] = 5;
    s.has[0] = 1;
    c.mode[1] = FL_MODE_REPLACE;
    fl_pattern(&s, &c, 1);
    fl_gate(&s, &c, 0); fl_inject(&s, 4); fl_rec_running(&s, 0);
    fl_replace_start(&s, 0);
    FlAction a = fl_undo(&s, &c, 0);
    CHECK(a.kind == FL_DO_CUT && s.cur[0] == 0 && s.rpass[0] == FL_RP_UNMUTE, "UNDO: dropped, the old loop heard at the loop start");
}

static void test_labels(void) {
    FlAction a; memset(&a, 0, sizeof a);
    char buf[20];
    a.toast = FL_T_TEMPO; a.tempo.tempo24 = 2883; a.tempo.bars = 1;
    CHECK(strcmp(fl_label(&a, buf), "120.1 BPM 1 BAR") == 0, "%s", buf);
    a.tempo.tempo24 = 24 * 99 + 22; a.tempo.bars = 16;
    CHECK(strcmp(fl_label(&a, buf), "99.9 BPM 16 BARS") == 0, "%s", buf);
    a.tempo.tempo24 = 24 * 99 + 23;
    CHECK(strcmp(fl_label(&a, buf), "100.0 BPM 16 BARS") == 0, "99.96 rounds to %s", buf);
    a.toast = FL_T_RANGE;
    CHECK(strcmp(fl_label(&a, buf), "TEMPO OUT OF RANGE") == 0, "%s", buf);
    a.toast = FL_T_SLAVE;
    CHECK(strlen(fl_label(&a, buf)) < 20, "fits");
    a.toast = FL_T_NO_UNDO; a.track = 0;
    CHECK(strcmp(fl_label(&a, buf), "T1 NOTHING TO UNDO") == 0, "%s", buf);
    a.toast = FL_T_NONE;
    CHECK(fl_label(&a, buf) == 0, "no toast");
}

int main(void) {
    test_loop_len();
    test_tempo_exact();
    test_tempo_limits();
    test_tempo_sweep();
    test_session();
    test_off_and_patterns();
    test_panel();
    test_end();
    test_undo();
    test_undo_to();
    test_replace();
    test_labels();
    printf("  freeloop engine: %d checks, %d failed\n", checks, failures);
    return failures != 0;
}
