// OT Gate logic ([js], ES5): matching and show/hide only. Every control is a native object in the patch;
// this script hears what they say, keeps the lit cells (saved through [pattr otmatrix]), decides, and shows
// either the slot column or the matrix (by the objects' scripting names, build.py).
// Columns: slots (col 0 = All). Rows: CC filters (row 0 = All CCs). A lit cell (c, r) = slot c AND CC row r;
// lit cells are OR'ed. Nothing lit: every note opens the gate. Slots are 0-based (the note); menus show +1.
//
// in:  note P VEL | cc NUM VAL | learn 0/1 | mode 0/1 | ncols N | nrows N | col C SLOT | row R CC LO HI
//      cell C R V (a matrix led or a slot toggle) | restore <c r c r ...> (pattr)
// out: 0 gate 0/1 | 1 to the patch: slot C SLOT, count N, cell C R V, tog C V, head C TEXT
//      2 lit cells (to pattr) | 3 0 switches Learn off | 4 readout: last P OPEN | 5 [thispatcher] show/hide
inlets = 1;
outlets = 6;

var MAXC = 8, MAXR = 8;
var LEFT = 13;                        // left1..left13: the controls on the left (the slot column's view only)
var ncol = 1, nrow = 6, matrix = 0;   // slot columns beyond All, CC rows beyond All, which view
var slots = [], ccr = [], lit = {}, ccv = [], learning = 0, i;
for (i = 0; i < 128; i++) ccv.push(0);
for (i = 0; i < MAXC; i++) slots.push(i === 0 ? -1 : 0);
for (i = 0; i < MAXR; i++) ccr.push([i >= 1 && i <= 6 ? 15 + i : 22, 0, 127]);   // 16 PTCH .. 21 RTIM

function key(c, r) { return c + "," + r; }
function clamp(v, lo, hi) { v = v | 0; return v < lo ? lo : (v > hi ? hi : v); }

function saved() {
    var a = [];
    for (var s in lit) if (lit[s]) { var cr = s.split(","); a.push(cr[0] | 0, cr[1] | 0); }
    return a;
}

function setcell(c, r, v) {
    var k = key(c, r), was = lit[k] ? 1 : 0;
    v = v ? 1 : 0;
    if (was === v) return 0;
    lit[k] = v;
    outlet(1, "cell", c, r, v);
    if (r === 0) outlet(1, "tog", c, v);
    return 1;
}

function cell(c, r, v) {
    c = c | 0; r = r | 0;
    if (c < 0 || c >= MAXC || r < 0 || r >= MAXR) return;
    if (setcell(c, r, v)) { var a = saved(); outlet(2, a.length ? a : [-1]); }
}

function restore() {
    var a = arrayfromargs(arguments), want = {}, k, s, cr;
    for (k = 0; k + 1 < a.length; k += 2) if (a[k] >= 0) want[key(a[k] | 0, a[k + 1] | 0)] = 1;
    for (s in lit) if (lit[s] && !want[s]) { cr = s.split(","); setcell(cr[0] | 0, cr[1] | 0, 0); }
    for (s in want) { cr = s.split(","); setcell(cr[0] | 0, cr[1] | 0, 1); }
}

// ---- the view
function show(name, on) { outlet(5, "script", on ? "show" : "hide", name); }

function layout() {
    var c, r, k;
    for (k = 1; k <= LEFT; k++) show("left" + k, !matrix);
    show("slottogall", !matrix); show("allcomp", !matrix);
    for (c = 1; c < MAXC; c++) { show("slottog" + c, !matrix && c <= ncol); show("slotmenu" + c, !matrix && c <= ncol); }
    show("ccrowslabel", matrix); show("rowcount", matrix); show("rowall", matrix);
    for (c = 0; c < MAXC; c++) show("colhead" + c, matrix && c <= ncol);
    for (r = 1; r < MAXR; r++) {
        show("rowcc" + r, matrix && r <= nrow); show("rowlo" + r, matrix && r <= nrow); show("rowhi" + r, matrix && r <= nrow);
    }
    for (c = 0; c < MAXC; c++) for (r = 0; r < MAXR; r++) show("cell" + c + "_" + r, matrix && c <= ncol && r <= nrow);
}

function mode(m) { matrix = m ? 1 : 0; layout(); }
function ncols(n) { ncol = clamp(n, 0, MAXC - 1); layout(); }
function nrows(n) { nrow = clamp(n, 0, MAXR - 1); layout(); }

function col(c, v) {
    c = c | 0;
    if (c < 1 || c >= MAXC) return;
    slots[c] = clamp(v, 0, 127);
    outlet(1, "head", c, slots[c] + 1);
}

function row(r, n, lo, hi) {
    r = r | 0;
    if (r < 1 || r >= MAXR) return;
    lo = clamp(lo, 0, 127); hi = clamp(hi, 0, 127);
    ccr[r] = [clamp(n, 0, 127), Math.min(lo, hi), Math.max(lo, hi)];
}

function learn(on) { learning = on ? 1 : 0; }

function cc(n, v) { n = n | 0; if (n >= 0 && n < 128) ccv[n] = v | 0; }

function matches(p) {
    var any = 0;
    for (var s in lit) {
        if (!lit[s]) continue;
        var cr = s.split(","), c = cr[0] | 0, r = cr[1] | 0;
        if (c > ncol || r > nrow) continue;      // hidden columns and rows do not count
        any = 1;
        var cm = c === 0 || slots[c] === p;
        var rm = r === 0 || (ccv[ccr[r][0]] >= ccr[r][1] && ccv[ccr[r][0]] <= ccr[r][2]);
        if (cm && rm) return 1;
    }
    return any ? 0 : 1;
}

function note(p, v) {
    p = p | 0;
    if ((v | 0) <= 0) return;
    if (learning) {
        var c = 0;
        for (var k = 1; k <= ncol; k++) if (slots[k] === p) c = k;
        if (!c && ncol < MAXC - 1) {
            c = ncol + 1;
            outlet(1, "count", c);               // the Slots box: ncols comes back from it
            outlet(1, "slot", c, p);             // the menu: col comes back from it
        }
        if (c) cell(c, 0, 1);
        learning = 0;
        outlet(3, 0);
    }
    var open = matches(p);
    outlet(0, open);
    outlet(4, "last", p, open);
}

function anything() { post("otgate: unknown message " + messagename + "\n"); }
