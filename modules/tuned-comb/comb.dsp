declare name "tuned-comb";
declare description "TUNED COMB's listening prototype: a feedback comb with a one-pole lowpass in the loop, whose loop length is shortened by the lowpass's phase delay at the sounding fundamental, so PTCH stays in tune at any LP.";

import("stdfaust.lib");

// ---------------------------------------------------------------------------
// The knobs (stock COMB's page: PTCH FINE LP FB --- MIX)
// ---------------------------------------------------------------------------
ptchk = hslider("[0]PTCH", 26, 0, 95, 1);      // A#0..A8, 26 = C3
tunek = hslider("[1]FINE", 64, 0, 127, 1);     // +-1 semitone, 64 = 0
lpk   = hslider("[2]LP", 127, 0, 127, 1);      // 127 = open
fbk   = hslider("[3]FB", 96, 0, 127, 1);       // a decay time; below 64 the octave down; 64 = none
mixk  = hslider("[5]MIX", 127, 0, 127, 1);
comp  = nentry("[9]COMP", 2, 0, 2, 1);          // test only: 0 none (stock-like), 1 on-circle phase delay, 2 pole

// ---------------------------------------------------------------------------
// The laws
// ---------------------------------------------------------------------------
semis(pk, tk) = (pk + 22 - 69) + (tk - 64)/64;               // re A4
f0(pk, tk)    = 440 * 2^(semis(pk, tk)/12);
fc(lk)        = 20000 * 2^((lk - 127)/16);                  // 16 steps an octave, ~81 Hz at 0
coef(lk)      = select2(lk >= 127, exp(-2*ma.PI*fc(lk)/ma.SR), 0);
// FB is a decay time: T60 = 0.05 s next to 64, 30 s at +-63; the gain a pass
// is that T60's at the open loop's length P, at most 0.998 (the module also
// takes the Hermite read's loss out of it).
t60(fk)       = 0.05 * 600^min(1, abs(fk - 64)/63);
sgn(fk)       = (fk > 64) - (fk < 64);
fb(fk, P)     = sgn(fk) * min(0.998, 10^(-3*P/(ma.SR*t60(fk))));
mix(mk)       = select2(mk >= 127, mk/128, 1);

// The one-pole y = (1-a)x + a y' lags by phi(w) = atan(a sin w / (1 - a cos w)).
// The loop resonates where w*L + phi(w) = 2 pi k (FB > 0) or pi (2k+1) (FB < 0):
// the sounding fundamental is f0 for FB > 0 and f0/2 for FB < 0, and in both
// cases (COMP 1) L = SR/f0 - phi(ws)/ws with ws the sounding fundamental.
phi(a, w) = atan2(a*sin(w), 1 - a*cos(w));

// COMP 2 puts the loop's POLE at the sounding fundamental: z = r e^{jw} with
// z^L (1 - a/z) = g(1 - a). Phase: L = (2 pi - psi)/w (FB > 0, w = w0) or
// (pi - psi)/w (FB < 0, w = w0/2), psi = arg(1 - (a/r) e^{-jw}); both are
// SR/f0 - psi/w. Magnitude: r = (|g|(1-a) / |1 - (a/r) e^{-jw}|)^(1/L).
// A damped pole (r < 1) lags more than the on-circle phase delay, so COMP 1
// leaves a heavily damped note flat. Fixed-point iteration from r = 1.
poleL(a, g, w, P) = len(it(it(it(it(it(it(1)))))))
with {
  psi(r)   = atan2((a/r)*sin(w), 1 - (a/r)*cos(w));
  len(r)   = P - psi(r)/w;
  mag(r)   = sqrt((1 - (a/r)*cos(w))^2 + ((a/r)*sin(w))^2);
  it(r)    = max(0.05, min(1, (max(abs(g), 1e-4)*(1 - a)/mag(r))^(1/len(r))));
};

loopLen(pk, tk, lk, fk, c) = ba.selectn(3, c, P, P - phi(a, ws)/ws, poleL(a, fb(fk, P), ws, P))
with {
  a  = coef(lk);
  P  = ma.SR/f0(pk, tk);
  w0 = 2*ma.PI*f0(pk, tk)/ma.SR;
  ws = select2(fk < 64, w0, w0/2);
};

// ---------------------------------------------------------------------------
// 4-point Hermite read at a fractional delay d >= 1 (the DSP's mo_herm form)
// ---------------------------------------------------------------------------
maxd = 2048;
herm(d) = _ <: (de.delay(maxd, hi - 1), de.delay(maxd, hi),
                de.delay(maxd, hi + 1), de.delay(maxd, hi + 2)) : hcr(hf)
with {
  hi = int(floor(d));
  hf = d - hi;
};
hcr(t, ym, y0, y1, y2) = ((h3*t + h2)*t + h1)*t + y0
with {
  h1 = 0.5*(y1 - ym);
  h2 = ym - 2.5*y0 + 2*y1 - 0.5*y2;
  h3 = 0.5*(y2 - ym) + 1.5*(y0 - y1);
};

lp(a) = *(1 - a) : + ~ *(a);

// The loop: ~ supplies one sample, the Hermite read the other L - 1.
comb(pk, tk, lk, fk, mk, c, x) = x <: *(1 - m), (loop : *(m)) :> _
with {
  L    = loopLen(pk, tk, lk, fk, c) : si.smoo;
  m    = mix(mk);
  a    = coef(lk) : si.smoo;
  g    = fb(fk, ma.SR/f0(pk, tk)) : si.smoo;
  loop = + ~ (herm(L - 1) : lp(a) : *(g));
};

process = par(i, 2, comb(ptchk, tunek, lpk, fbk, mixk, comp));
