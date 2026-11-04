declare name "vibrato";
declare description "VIBRATO's listening prototype: continuous-time, per sample. vibrato_ref.py (block-based, the DSP's arithmetic) is what the DSP is proven against.";

import("stdfaust.lib");

// ---------------------------------------------------------------------------
// The knobs, on the module's laws (k = 0..127)
// ---------------------------------------------------------------------------
spdk = hslider("[0]SPD", 94, 0, 127, 1);
depk = hslider("[1]DEP", 70, 0, 127, 1);
slwk = hslider("[2]SLEW", 0, 0, 127, 1);
widk = hslider("[3]WID", 0, 0, 127, 1);
mixk = hslider("[5]MIX", 127, 0, 127, 1);
shp  = nentry("[6]SHP [style:menu{'SINE':0;'TRI':1;'SQR':2;'RND':3}]", 0, 0, 3, 1);

spd  = 0.25 * 2^(3*spdk/64);                   // Hz
c    = 100 * (depk/127)^2;                     // cents
mix  = select2(mixk >= 127, mixk/128, 1);
wid  = widk / 256;                             // R's lead, cycles
w    = widk / 128;                             // RND's decorrelation

// ---------------------------------------------------------------------------
// Each shape is a pitch trajectory; the delay its integral, normalised to
// +-1 and scaled by H. dev = tanh(c ln2/1200): the extremes are 2c apart.
// ---------------------------------------------------------------------------
maxd = 1024;
lim  = 500;
dev  = ma.tanh(c * log(2) / 1200);
per  = ma.SR / spd;
fac  = ba.selectn(4, shp, 1/(2*ma.PI), 1/8, 1/4, 1/4);
hc   = min(lim, dev * per * fac) : si.smoo;
cen  = 2 + hc;

tau = slwk / 128 * 0.25 / spd * ma.SR;         // SLEW: s/4 of a cycle
s   = exp(-1 / max(tau, 1e-3));

ph   = os.lf_sawpos(spd);
half = ph >= 0.5;
step = half != half';                          // each half cycle

fsin(x) = sin(2*ma.PI*x);
ftri(x) = select2(x < 0.5, -g(x - 0.5), g(x)) with { g(y) = 8*(y - 2*y*y); };
fsqr(x) = 1 - 4*abs(ma.frac(x + 0.25) - 0.5);
periodic(x) = ba.selectn(3, min(shp, 2), fsin(x), ftri(x), fsqr(x));

// RND: on each half-cycle step u = (x + n)/2, then x -= 4 u dphi a sample:
// the half cycle ends near x = -n, so |x| <= 1 with no leak.
dphi = spd / ma.SR;
rnd(n) = x
letrec {
  'u = select2(step, u, (x + n)/2);
  'x = max(-1, min(1, x - 4*u*dphi));
};

n1 = no.multinoise(2) : _, !;
n2 = no.multinoise(2) : !, _;
nR = n1 + w*(n2 - n1);

offset(x, n) = select2(shp == 3, hc*periodic(x), hc*rnd(n)) : si.smooth(s);
dly(x, n) = max(2, min(1016, cen + offset(x, n)));

chan(d) = _ <: *(1 - mix), (de.fdelay(maxd, d) : *(mix)) :> _;

process = chan(dly(ph, n1)), chan(dly(ma.frac(ph + wid), nR));
