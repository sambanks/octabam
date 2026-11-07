/* BRAIN -- the brain's run-time layers on the unit (git show 76fd8466:docs/proposals/BRAIN.md).
 *
 * This increment: card-layer FX page defaults, read-only. At each project
 * load (and the power-up's bank load) brain_load() puts every effect's
 * twelve descriptor defaults back to the image's values, reads
 * /BRAIN/card.work (or card.strd, by the pair rule of section 6.2) and
 * writes each valid default record over its effect's descriptor bytes
 * (P+0x5e). The choosers and the new-part initialiser read those bytes when
 * they run (tools/verify/verify_desc_defaults.py).
 *
 * A record with a mode writes into MODE DEFAULTS' view table (its
 * MODEDEF_TABLE, 0 when that module is not in the remix): the values of the
 * slots the mode's view already re-defaults. The table is sparse and keeps
 * its size, so a slot the view does not list is skipped and counted.
 *
 * The table brain_fx[] (one entry per effect in the image: store id, fx id,
 * twelve keys, layout hash) is generated per remix (manifest.py fx_inc).
 */

typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;

struct fx_ent {			/* 40 bytes, as fx_inc() emits it */
	u32 layout;
	const char *id;
	u16 keys[12];
	u8 fx_id;
	u8 id_len;
	u16 pad;
	const char *name;		/* the module's key, the TEMPLATES heading */
};

extern const struct fx_ent brain_fx[];
extern const u32 brain_fx_n;
/* id, mode slot, nviews, then per view: mode, npairs, (slot, value)*;
 * 0xff ends it (modules/mode-defaults/manifest.py table_inc) */
extern u8 *const brain_modedef;		/* MODEDEF_TABLE or 0 (hooks.s) */
#define MODEDEF_TABLE brain_modedef
extern u8 *const brain_cs1_early;	/* CS1_EARLY_BASE (hooks.s) */
#define CS1_EARLY_BASE brain_cs1_early

#define F_OPEN   ((int (*)(void *, const char *, const char *, void *, u32))0x40016864)
#define F_READ   ((int (*)(void *, void *, u32))0x40016564)
#define F_CLOSE  ((int (*)(void *))0x4001677c)
extern u8 *const brain_fx2_ids[];	/* remix.inc: the FX2 descriptor table (0x400d5fdc; moves in a 64-id image) */
#define FX2_IDS  ((u8 **)brain_fx2_ids)
#define FX1_IDS  ((u8 **)0x400d5f58)

#define MAX_FX    32
#define BUF_LEN   65536			/* card.work: ten PART templates (6.4 KB each) and the rest */
#define HDR       32
#define REC_HDR   20
#define K_DEFAULT 2
#define T_BLOB    4
#define T_BYTE    5
#define NO_MODE   0xffff

/* The platform loads a unit's image and leaves its .bss as the boot left
 * it (tools/remix/platform_build.py): state read before BRAIN first writes
 * it lives in .data. */
#define DATA __attribute__((section(".data")))
/* the stock soft timer (about 0.5 s a period of 60) */
#define TIMER      ((int (*)(u32, void (*)(void)))0x40031a0c)
#define UNTIMER    ((void (*)(int))0x40031abc)
#define TIMERS     0x460d5a28			/* 32 slots, 16 bytes: {period, due, fn, next} */

/* counters, read by the gates (tools/verify/verify_brain.py); all but
 * C_LOADS describe the last brain_load() */
enum { C_LOADS, C_STATE, C_RECORDS, C_APPLIED, C_VALUES, C_SKIP_ID, C_SKIP_LAYOUT,
       C_SKIP_MODE, C_SKIP_CRC, C_SKIP_DUP, C_SKIP_VALUE, C_SKIP_SLOT, C_N };
/* C_SKIP_MODE: a mode record with no MODE DEFAULTS or no view for the mode;
 * C_SKIP_SLOT: a mode value for a slot the view does not list */
/* C_STATE: 0 fresh, 1 card.work, 2 recovered from card.strd, 3 damaged */
u32 brain_counts[C_N] DATA;

static u8 shadow[MAX_FX][2][12];
#define MAX_TABLE 1024
static u8 table_shadow[MAX_TABLE];
static u32 table_len DATA;
static u8 *desc[MAX_FX][2];
static u32 snapped DATA;

static u8 fobj[24];
static u8 iob[4096];
static u8 buf[BUF_LEN];

static u32 be32(const u8 *p) { return ((u32)p[0] << 24) | ((u32)p[1] << 16) | ((u32)p[2] << 8) | p[3]; }
static u32 be16(const u8 *p) { return ((u32)p[0] << 8) | p[1]; }
static u32 align4(u32 n) { return (n + 3) & ~3u; }

static u32 crc32(const u8 *p, u32 n)
{
	u32 c = 0xffffffffu;
	while (n--) {
		c ^= *p++;
		for (int k = 0; k < 8; k++)
			c = (c >> 1) ^ (0xedb88320u & -(c & 1));
	}
	return ~c;
}

/* The descriptor of entry i in one id table, or 0: a table slot whose
 * descriptor carries another id (NONE, or an effect on one chooser only). */
static u8 *find(const u8 *const *table, u32 id)
{
	u8 *p = (u8 *)table[id];
	return (p && be32(p) == id) ? p : 0;
}

static void snapshot(void)
{
	for (u32 i = 0; i < brain_fx_n && i < MAX_FX; i++) {
		desc[i][0] = find((const u8 *const *)FX2_IDS, brain_fx[i].fx_id);
		desc[i][1] = find((const u8 *const *)FX1_IDS, brain_fx[i].fx_id);
		if (desc[i][1] == desc[i][0])
			desc[i][1] = 0;
		for (int t = 0; t < 2; t++)
			if (desc[i][t])
				for (int s = 0; s < 12; s++)
					shadow[i][t][s] = desc[i][t][0x5e + s];
	}
	if (MODEDEF_TABLE) {
		u32 at = 0;
		while (at < MAX_TABLE && MODEDEF_TABLE[at] != 0xff) {
			u32 nviews = MODEDEF_TABLE[at + 2];
			at += 3;
			for (u32 v = 0; v < nviews; v++)
				at += 2 + 2 * MODEDEF_TABLE[at + 1];
		}
		table_len = at < MAX_TABLE ? at : 0;
		for (u32 k = 0; k < table_len; k++)
			table_shadow[k] = MODEDEF_TABLE[k];
	}
	snapped = 1;
}

/* The (slot, value) pairs of MODE DEFAULTS' view for (fx id, mode): a
 * pointer to the first pair and its count, or 0. */
static u8 *view_of(u32 fx_id, u32 mode, u32 *npairs)
{
	if (!MODEDEF_TABLE || !table_len)
		return 0;
	for (u32 at = 0; at < table_len;) {
		u32 id = MODEDEF_TABLE[at], nviews = MODEDEF_TABLE[at + 2];
		at += 3;
		for (u32 v = 0; v < nviews; v++) {
			u32 n = MODEDEF_TABLE[at + 1];
			if (id == fx_id && MODEDEF_TABLE[at] == mode) {
				*npairs = n;
				return MODEDEF_TABLE + at + 2;
			}
			at += 2 + 2 * n;
		}
	}
	return 0;
}

static void restore(void)
{
	for (u32 i = 0; i < brain_fx_n && i < MAX_FX; i++)
		for (int t = 0; t < 2; t++)
			if (desc[i][t])
				for (int s = 0; s < 12; s++)
					desc[i][t][0x5e + s] = shadow[i][t][s];
	for (u32 k = 0; k < table_len; k++)
		MODEDEF_TABLE[k] = table_shadow[k];
}

/* Read one file whole into buf: its length; 0 when absent; 1 (never a
 * valid length) when present but too long or short to read. */
static u32 slurp(const char *path)
{
	u32 n = 1;
	if (F_OPEN(fobj, path, "r", iob, sizeof iob) < 0)
		return 0;
	if (F_READ(fobj, buf, HDR) == 1) {
		u32 total = be32(buf + 12);
		if (total >= HDR && total <= BUF_LEN
		    && (total == HDR || F_READ(fobj, buf + HDR, total - HDR) == 1))
			n = total;
	}
	F_CLOSE(fobj);
	return n;
}

/* BRAIN.md section 7.1/7.2: 1 when buf[0..n) is a valid file. */
static int valid(u32 n)
{
	if (n < HDR || be32(buf) != 0x4252414eu || be16(buf + 4) != HDR || buf[6] != 1
	    || be32(buf + 12) != n || crc32(buf + 20, n - 20) != be32(buf + 16))
		return 0;
	u32 at = HDR, count = be16(buf + 10);
	for (u32 r = 0; r < count; r++) {
		if (at + REC_HDR > n)
			return 0;
		u32 idlen = buf[at + 1], plen = be32(buf + at + 8), size = be32(buf + at + 16);
		if (idlen < 1 || idlen > 63 || size != REC_HDR + align4(idlen) + align4(plen) || at + size > n)
			return 0;
		at += size;
	}
	return at == n;
}

static int same_id(const u8 *a, u32 alen, const char *b, u32 blen)
{
	if (alen != blen)
		return 0;
	for (u32 k = 0; k < alen; k++)
		if (a[k] != (u8)b[k])
			return 0;
	return 1;
}

/* A default record for target 0: its entry index, or -1. */
static int entry_of(const u8 *rec)
{
	u32 idlen = rec[1];
	for (u32 i = 0; i < brain_fx_n && i < MAX_FX; i++)
		if (same_id(rec + REC_HDR, idlen, brain_fx[i].id, brain_fx[i].id_len))
			return (int)i;
	return -1;
}

static void apply_record(const u8 *rec, int e)
{
	const struct fx_ent *f = &brain_fx[e];
	u32 idlen = rec[1], plen = be32(rec + 8);
	const u8 *pay = rec + REC_HDR + align4(idlen);
	if (be16(rec + 2) != 1 || plen < 8)		/* schema major 1 */
		return;
	u32 mode = be16(pay + 2), npairs = 0;
	u8 *view = 0;
	if (be16(pay) != 0) {
		brain_counts[C_SKIP_MODE]++;
		return;
	}
	if (be32(pay + 4) != f->layout) {
		brain_counts[C_SKIP_LAYOUT]++;
		return;
	}
	if (mode != NO_MODE && !(view = view_of(f->fx_id, mode, &npairs))) {
		brain_counts[C_SKIP_MODE]++;
		return;
	}
	brain_counts[C_APPLIED]++;
	for (u32 at = 8; at + 4 <= plen;) {
		u32 key = be16(pay + at), type = pay[at + 2], n = pay[at + 3], head = 4;
		if (n == 255) {
			if (at + 8 > plen)
				break;
			n = be32(pay + at + 4);
			head = 8;
		}
		if (at + head + align4(n) > plen)
			break;
		if (type == T_BYTE && n == 1 && key && view) {
			u8 v = pay[at + head];
			for (int s = 0; s < 12; s++) {
				if (f->keys[s] != key)
					continue;
				u8 *p = desc[e][0] ? desc[e][0] : desc[e][1];
				u32 k = 0;
				while (k < npairs && view[2 * k] != s)
					k++;
				if (k == npairs)
					brain_counts[C_SKIP_SLOT]++;
				else if (!p || v >= be32(p + 0x9a + 4 * s))
					brain_counts[C_SKIP_VALUE]++;
				else {
					view[2 * k + 1] = v;
					brain_counts[C_VALUES]++;
				}
			}
		} else if (type == T_BYTE && n == 1 && key) {
			u8 v = pay[at + head];
			for (int s = 0; s < 12; s++)
				if (f->keys[s] == key)
					for (int t = 0; t < 2; t++) {
						u8 *p = desc[e][t];
						if (!p)
							continue;
						if (v < be32(p + 0x9a + 4 * s)) {
							p[0x5e + s] = v;
							brain_counts[C_VALUES]++;
						} else {
							brain_counts[C_SKIP_VALUE]++;
						}
					}
		}
		at += head + align4(n);
	}
}

static void apply(u32 n)
{
	u32 count = be16(buf + 10);
	const u8 *rec[64];
	int ent[64];
	u32 m = 0;
	for (u32 r = 0, at = HDR; r < count; r++, at += be32(buf + at + 16)) {
		const u8 *p = buf + at;
		brain_counts[C_RECORDS]++;
		if (p[0] != K_DEFAULT)
			continue;
		u32 plen = be32(p + 8);
		if (crc32(p + REC_HDR + align4(p[1]), plen) != be32(p + 12)) {
			brain_counts[C_SKIP_CRC]++;
			continue;
		}
		int e = entry_of(p);
		if (e < 0) {
			brain_counts[C_SKIP_ID]++;
			continue;
		}
		if (m < 64) {
			rec[m] = p;
			ent[m++] = e;
		}
	}
	(void)n;
	/* BRAIN.md section 7.7 rule 5: two records with one store id and
	 * prefix are neither applied. */
	for (u32 i = 0; i < m; i++) {
		const u8 *pi = rec[i] + REC_HDR + align4(rec[i][1]);
		int dup = 0;
		for (u32 j = 0; j < m; j++) {
			const u8 *pj = rec[j] + REC_HDR + align4(rec[j][1]);
			if (j != i && ent[j] == ent[i] && be32(pi) == be32(pj))
				dup = 1;
		}
		if (dup)
			brain_counts[C_SKIP_DUP]++;
		else
			apply_record(rec[i], ent[i]);
	}
}

/* ---- settings: the run-time value table (BRAIN.md sections 5, 7.7) -------- */

/* One per setting the unit holds (manifest.py settings_inc), in the
 * SETTINGS list's order. brain_values[i] is its value, a long other units
 * read by symbol (remix.brain.value_symbol). */
struct set_ent {
	const char *id;
	u8 id_len, type, apply, nlabels;	/* type 1 Binary, 2 Option, 3 Number */
	u16 key, step;
	int min, max, def;
	u32 cs1_off;				/* the value's CS1 address when early, 0 otherwise (settings_inc) */
	const char *const *labels;
	const char *name, *group;
	u32 scope;				/* 0 CARD (card.work), 1 PROJECT (the project's brain.work) */
};
extern const struct set_ent brain_set[];
extern const u32 brain_set_n;
extern int brain_values[];

#define K_SETTINGS 1
#define MAX_SET    48

enum { C_SET_RECORDS = 0, C_SET_VALUES, C_SET_SKIP, C_SET_DUP, C_SET_N };
/* C_SET_SKIP: a value whose type, bounds or step does not fit (the layer
 * below stays); C_SET_DUP: two settings records for one store (neither) */
u32 brain_set_counts[C_SET_N] DATA;

static int value_ok(const struct set_ent *e, int v)
{
	return v >= e->min && v <= e->max && (e->step <= 1 || (v - e->min) % e->step == 0);
}

/* One settings record's values into the table: the known keys of its
 * store whose type and bounds fit. */
static void apply_settings(const u8 *rec, u32 scope)
{
	u32 idlen = rec[1], plen = be32(rec + 8);
	const u8 *pay = rec + REC_HDR + align4(idlen);
	if (be16(rec + 2) != 1)				/* schema major 1 */
		return;
	brain_set_counts[C_SET_RECORDS]++;
	for (u32 at = 0; at + 4 <= plen;) {
		u32 key = be16(pay + at), type = pay[at + 2], n = pay[at + 3], head = 4;
		if (n == 255) {
			if (at + 8 > plen)
				break;
			n = be32(pay + at + 4);
			head = 8;
		}
		if (at + head + align4(n) > plen)
			break;
		const u8 *d = pay + at + head;
		for (u32 i = 0; i < brain_set_n && i < MAX_SET; i++) {
			const struct set_ent *e = &brain_set[i];
			if (e->scope != scope || e->key != key || !same_id(rec + REC_HDR, idlen, e->id, e->id_len))
				continue;
			int v;
			if (type != e->type || (type == 3 ? n != 2 : n != 1)) {
				brain_set_counts[C_SET_SKIP]++;
				continue;
			}
			v = type == 3 ? (int)(short)be16(d) : d[0];
			if (!value_ok(e, v)) {
				brain_set_counts[C_SET_SKIP]++;
				continue;
			}
			brain_values[i] = v;
			brain_set_counts[C_SET_VALUES]++;
		}
		at += head + align4(n);
	}
}

/* The table back to the layers below, the counters to zero (brain_load). */
static void reset_settings(void)
{
	for (u32 i = 0; i < brain_set_n && i < MAX_SET; i++)
		brain_values[i] = brain_set[i].def;
	for (int k = 0; k < C_SET_N; k++)
		brain_set_counts[k] = 0;
}

/* Every settings record of the file in buf, applied to the entries of
 * `scope`: a store with two records is skipped (rule 5). */
static void load_settings(int have, u32 scope)
{
	if (!have)
		return;
	u32 count = be16(buf + 10);
	for (u32 r = 0, at = HDR; r < count; r++, at += be32(buf + at + 16)) {
		const u8 *p = buf + at;
		if (p[0] != K_SETTINGS || crc32(p + REC_HDR + align4(p[1]), be32(p + 8)) != be32(p + 12))
			continue;
		int dup = 0;
		for (u32 r2 = 0, at2 = HDR; r2 < count; r2++, at2 += be32(buf + at2 + 16)) {
			const u8 *q = buf + at2;
			if (q != p && q[0] == K_SETTINGS && same_id(q + REC_HDR, q[1], (const char *)p + REC_HDR, p[1]))
				dup = 1;
		}
		if (dup)
			brain_set_counts[C_SET_DUP]++;
		else
			apply_settings(p, scope);
	}
}

/* ---- templates: the copy brain_load keeps (more below the menu) ---------- */

#define K_TEMPLATE  3
#define TPL_CACHE   BUF_LEN			/* card.work's whole size: every template fits */
#define TPL_MAX     64
#define TPL_NAME    8

static u8 tpl_cache[TPL_CACHE];
static u32 tpl_len DATA;			/* bytes of records in tpl_cache */
/* what ABOUT > CARD shows of card.work: its length, its templates and its defaults (set by every
 * load and write, the file being in buf) */
static u32 card_len DATA, card_tpls DATA, card_defs DATA;

/* the copy: every template record of the file in buf (called by brain_load
 * and after each template write) */
static void cache_templates(int have)
{
	tpl_len = 0;
	card_tpls = card_len = 0;
	if (!have)
		return;
	card_len = be32(buf + 12);
	u32 count = be16(buf + 10);
	for (u32 r = 0, at = HDR; r < count; r++, at += be32(buf + at + 16)) {
		const u8 *p = buf + at;
		u32 size = be32(p + 16);
		if (p[0] != K_TEMPLATE || tpl_len + size > TPL_CACHE)
			continue;
		if (crc32(p + REC_HDR + align4(p[1]), be32(p + 8)) != be32(p + 12))
			continue;
		card_tpls++;
		for (u32 k = 0; k < size; k++)
			tpl_cache[tpl_len + k] = p[k];
		tpl_len += size;
	}
}

/* BRAIN's own settings (manifest.py: store octabam.brain) */
extern int brain_v_octabam_brain_1;		/* MIDI LOG: 1 = the debug log records */
extern int brain_v_octabam_brain_3;		/* EVENT LOG: 1 = LOG > EVENTS notes events */
extern int brain_v_octabam_brain_2;		/* CARD DEFAULTS: 1 = card defaults apply */

/* ---- the project pair and the project record (BRAIN.md sections 6.1, 7.5, 8) ---- */

#define SET_PATH   ((const char *)0x100f8480)	/* the current set's path: "/SETNAME" */
#define PROJ_NAME  ((const char *)0x100f8378)	/* the current project's folder name */
#define PATH_HALF  0x100
#define K_PROJECT  4
#define OWN_STORE  "octabam.brain"		/* the store id the project record is filed under */

static char pw[PATH_HALF * 2 + 16], ps[PATH_HALF * 2 + 16];	/* <set>/<project>/brain.work, .strd */

/* Both paths of the current project's pair; 0 when no set or project is
 * named (nothing loaded yet). */
static int proj_paths(void)
{
	const char *set = SET_PATH, *proj = PROJ_NAME;
	u32 n = 0, k;
	for (k = 0; set[k] && k < PATH_HALF; k++)
		pw[n++] = set[k];
	if (!n || !proj[0])
		return 0;
	if (proj[0] != '/')
		pw[n++] = '/';
	for (k = 0; proj[k] && k < PATH_HALF; k++)
		pw[n++] = proj[k];
	pw[n++] = '/';
	for (k = 0; k < n; k++)
		ps[k] = pw[k];
	const char *w = "brain.work", *s = "brain.strd";
	for (k = 0; k < 11; k++) {
		pw[n + k] = w[k];
		ps[n + k] = s[k];
	}
	return 1;
}

/* ---- MIDI knob names (BRAIN.md section 3) -------------------------------- */

/* A name per bank, Part, MIDI track and assignable CC (CC1..CC10): four
 * characters and a NUL in a Name value's six bytes. In the project's
 * brain.work as field blocks (kind 5) of store stock.midi, one per Part
 * that has a name: target bank * 4 + Part, instance 0, a Name value keyed
 * track * 10 + cc + 1. Cleared and read at each project load; drawn on
 * the CTRL1/CTRL2 pages by brain_klabel. */
#define K_FIELD   5
#define T_NAME    6
#define KN_PARTS  64
#define KN_LEN    6
#define KN_CHARS  4
#define KN_STORE  "stock.midi"
static char knames[KN_PARTS][8][10][KN_LEN];

/* bank * 4 + Part of the current Part */
static u32 kn_part(void)
{
	return ((u32)(*(volatile u8 *)0x80000002 & 15) << 2) | (*(volatile u8 *)0x80000003 & 3);
}

static void kn_clear(void)
{
	char *p = &knames[0][0][0][0];
	for (u32 k = 0; k < sizeof knames; k++)
		p[k] = 0;
}

/* the field blocks of the project file in buf */
static void kn_load(void)
{
	u32 count = be16(buf + 10);
	for (u32 r = 0, at = HDR; r < count; r++, at += be32(buf + at + 16)) {
		const u8 *p = buf + at;
		if (p[0] != K_FIELD || !same_id(p + REC_HDR, p[1], KN_STORE, 10))
			continue;
		const u8 *pay = p + REC_HDR + align4(p[1]);
		u32 plen = be32(p + 8);
		if (plen < 4 || crc32(pay, plen) != be32(p + 12) || be16(pay) >= KN_PARTS)
			continue;
		char (*part)[10][KN_LEN] = knames[be16(pay)];
		for (u32 v = 4; v + 4 <= plen && pay[v + 3] != 0xff; v += 4 + align4(pay[v + 3])) {
			u32 key = be16(pay + v);
			if (pay[v + 2] != T_NAME || pay[v + 3] != KN_LEN || key < 1 || key > 80)
				continue;
			char *o = part[(key - 1) / 10][(key - 1) % 10];
			for (u32 c = 0; c < KN_CHARS; c++)
				o[c] = (char)pay[v + 4 + c];
			o[KN_CHARS] = 0;
		}
	}
}

/* The Name values keyed 129..138 of template record p onto MIDI track t's
 * names in the current Part; 1 when it had any. */
static int kn_take(const u8 *p, u32 t)
{
	const u8 *pay = p + REC_HDR + align4(p[1]);
	u32 plen = be32(p + 8);
	int any = 0;
	char (*kn)[KN_LEN] = knames[kn_part()][t & 7];
	for (u32 v = 16; v + 4 <= plen && pay[v + 3] != 0xff; v += 4 + align4(pay[v + 3])) {
		u32 key = be16(pay + v);
		if (pay[v + 2] != T_NAME || pay[v + 3] != KN_LEN || key < 129 || key > 138)
			continue;
		for (u32 c = 0; c < KN_CHARS; c++)
			kn[key - 129][c] = (char)pay[v + 4 + c];
		kn[key - 129][KN_CHARS] = 0;
		any = 1;
	}
	return any;
}

/* The label the CTRL page drawer pushes for slot s of descriptor P (the
 * detour at 0x4004e474, hooks.s brain_klabel_hook): the current MIDI
 * track's name for that CC when it has one, else dflt. CTL1 (P
 * 0x400d42f4): slots 2-5 are CC1-CC4; CTL2 (P 0x400d4486): slots 0-5 are
 * CC5-CC10. Bank, Part and track as the UI's writers read them. */
const char *brain_klabel(u32 P, u32 s, const char *dflt)
{
	int cc = P == 0x400d42f4 ? (int)s - 2 : P == 0x400d4486 ? 4 + (int)s : -1;
	if (cc < 0 || cc > 9 || s > 5)
		return dflt;
	const char *n = knames[kn_part()][*(volatile u8 *)0x80000000 & 7][cc];
	return n[0] ? n : dflt;
}

/* Counters of the last project load, read by the gates. */
enum { PC_LOADS, PC_STATE, PC_RECORD, PC_ENTRIES, PC_SAME, PC_MOVED, PC_LAYOUT, PC_GONE, PC_SKIP,
       PC_N };
/* PC_STATE: as C_STATE (0 no files or no project, 1 brain.work, 2 recovered from
 * brain.strd, 3 damaged); PC_RECORD: 1 when one project record was compared;
 * PC_ENTRIES: its entries. Per entry, one of: PC_SAME (its FX id names the same
 * store and layout), PC_MOVED (its FX id names another store, or none, and the
 * image still has the store), PC_LAYOUT (same store, another layout hash),
 * PC_GONE (the image has no such store). PC_SKIP: project records not
 * compared (CRC, schema major, a second record). */
u32 brain_pcounts[PC_N] DATA;
/* the entries that changed, for IMAGE: name (a store id when the image no longer has it) and why */
#define PC_NAMES 12
static char pc_nm[PC_NAMES][16];
static u8 pc_why[PC_NAMES];			/* 0 moved, 1 layout, 2 gone */
static u32 pc_nn DATA;

static void pc_note(const u8 *src, u32 len, u32 why)
{
	if (pc_nn >= PC_NAMES)
		return;
	u32 k = 0;
	for (; k < len && k < 15 && src[k]; k++)
		pc_nm[pc_nn][k] = (char)src[k];
	pc_nm[pc_nn][k] = 0;
	pc_why[pc_nn++] = (u8)why;
}

/* One pair by the rule of section 6.2: 0 neither file, 1 .work valid, 2
 * .strd valid (the .work absent or damaged), 3 damaged; buf holds the file
 * for 1 and 2. */
static int pair_load(const char *w, const char *s, u32 *len)
{
	u32 n = slurp(w);
	if (n && valid(n)) {
		*len = n;
		return 1;
	}
	int work_present = n != 0;
	n = slurp(s);
	if (n && valid(n)) {
		*len = n;
		return 2;
	}
	return (work_present || n) ? 3 : 0;
}

/* The project record of the file in buf against brain_fx[]. */
static void check_project(void)
{
	u32 count = be16(buf + 10), found = 0;
	const u8 *rec = 0;
	for (u32 r = 0, at = HDR; r < count; r++, at += be32(buf + at + 16)) {
		const u8 *p = buf + at;
		if (p[0] != K_PROJECT || !same_id(p + REC_HDR, p[1], OWN_STORE, 13))
			continue;
		if (be16(p + 2) != 1 || crc32(p + REC_HDR + align4(p[1]), be32(p + 8)) != be32(p + 12)) {
			brain_pcounts[PC_SKIP]++;
			continue;
		}
		found++;
		rec = p;
	}
	if (found > 1) {			/* rule 5: neither */
		brain_pcounts[PC_SKIP] += found;
		return;
	}
	if (!rec)
		return;
	brain_pcounts[PC_RECORD] = 1;
	const u8 *pay = rec + REC_HDR + align4(rec[1]);
	u32 plen = be32(rec + 8);
	for (u32 at = 0; at + 8 <= plen;) {
		u32 fx = pay[at], idlen = pay[at + 1], layout = be32(pay + at + 4);
		if (idlen < 1 || idlen > 63 || at + 8 + align4(idlen) > plen)
			break;
		const u8 *id = pay + at + 8;
		at += 8 + align4(idlen);
		brain_pcounts[PC_ENTRIES]++;
		int e = -1, at_fx = -1;
		for (u32 i = 0; i < brain_fx_n && i < MAX_FX; i++) {
			if (same_id(id, idlen, brain_fx[i].id, brain_fx[i].id_len))
				e = (int)i;
			if (brain_fx[i].fx_id == fx)
				at_fx = (int)i;
		}
		if (e < 0) {
			brain_pcounts[PC_GONE]++;
			pc_note(id, idlen, 2);
		} else if (at_fx != e) {
			brain_pcounts[PC_MOVED]++;
			pc_note((const u8 *)brain_fx[e].name, 15, 0);
		} else if (brain_fx[e].layout != layout) {
			brain_pcounts[PC_LAYOUT]++;
			pc_note((const u8 *)brain_fx[e].name, 15, 1);
		} else
			brain_pcounts[PC_SAME]++;
	}
}

/* The project pair: its PROJECT-scope settings onto the table, its project
 * record against the image. */
static void load_project(void)
{
	for (int k = PC_STATE; k < PC_N; k++)
		brain_pcounts[k] = 0;
	pc_nn = 0;
	brain_pcounts[PC_LOADS]++;
	u32 n;
	if (!proj_paths())
		return;
	kn_clear();
	int st = pair_load(pw, ps, &n);
	brain_pcounts[PC_STATE] = (u32)st;
	if (st == 1 || st == 2) {
		load_settings(1, 1);
		check_project();
		kn_load();
	}
}

/* which stored defaults the card file holds, with a signature of each one's values */
static u8 def_have[MAX_FX];
static u8 pset_have;
static u32 def_sig[MAX_FX], pset_sig;
static u32 pairs_sig(const u8 *pay, u32 from, u32 plen);
static void cache_defaults(int have);
static void write_early_block(void);

static void load_card(void)
{
	u32 n;
	int st = pair_load("/BRAIN/card.work", "/BRAIN/card.strd", &n);
	brain_counts[C_STATE] = (u32)st;
	load_settings(st == 1 || st == 2, 0);
	write_early_block();		/* CS1 mirrors the table after every load */
	cache_templates(st == 1 || st == 2);
	cache_defaults(st == 1 || st == 2);
	if ((st == 1 || st == 2) && brain_v_octabam_brain_2)
		apply(n);
}

static void samp_start(void);

void brain_load(void)
{
	samp_start();
	/* the counters after C_LOADS describe the last load */
	for (int k = C_STATE; k < C_N; k++)
		brain_counts[k] = 0;
	brain_counts[C_LOADS]++;
	if (!snapped)
		snapshot();
	restore();
	reset_settings();
	load_card();
	load_project();
}

/* ---- writing the card store ------------------------------------------------ */

#define MKDIR    (*(int (**)(const char *))0x46c8240a)	/* FS vtable: create a directory */
#define F_WRITE  ((int (*)(void *, const void *, u32))0x400166b8)
#define DBPTR    (*(u8 **)0x46c82456)			/* the current bank */
#define CUR_PART (*(volatile u8 *)0x80000003)
#define PART_LEN 6322
#define WORKING  0x8ed80
/* the card's PART default: a copy of its Part image (the engine task reads card.work, Part Clear
 * runs in the UI task) and a signature of it */
static u8 part_def[PART_LEN];
static u8 part_def_have DATA;
static u32 part_def_sig DATA;
#define ST_BASE  0x40				/* the stock targets' entries follow the effects' */
#define E_PROJECT (ST_BASE + 8)
#define E_PART    (ST_BASE + 9)
#define PART_STORE "stock.part2"
#define PART_LAYOUT 0x50525432u

enum { S_SAVES, S_SAVE_ERR, S_STRD, S_STRD_ERR, S_N };
/* S_SAVE_ERR: last error of brain_save_default (0 none, 1 no effect, 2 card
 * store damaged, 3 too large, 4 write, 5 a template of that name is on the
 * card); S_STRD: card.strd copies written */
u32 brain_save_counts[S_N] DATA;

static u8 out[BUF_LEN];

static void put32(u8 *p, u32 v) { p[0] = v >> 24; p[1] = v >> 16; p[2] = v >> 8; p[3] = v; }
static void put16(u8 *p, u32 v) { p[0] = v >> 8; p[1] = v; }

static int write_file(const char *path, const u8 *data, u32 n)
{
	int ok = 0;
	if (F_OPEN(fobj, path, "w", iob, sizeof iob) < 0) {
		if (path[1] != 'B')			/* a project's file: its folder exists */
			return -1;
		MKDIR("/BRAIN");			/* the first write on this card */
		if (F_OPEN(fobj, path, "w", iob, sizeof iob) < 0)
			return -1;
	}
	ok = F_WRITE(fobj, data, n) == 1;
	F_CLOSE(fobj);
	return ok ? 0 : -1;
}

/* The content of a pair in buf (BRAIN.md section 6.2): its length, 0 when
 * there is none, -1 when both copies are damaged (no automatic write). */
static int cur(const char *w, const char *s)
{
	u32 n = slurp(w);
	if (n && valid(n))
		return (int)n;
	u32 work_present = n != 0;
	n = slurp(s);
	if (n && valid(n))
		return (int)n;
	return (work_present || n) ? -1 : 0;
}

static int current_store(void)
{
	return cur("/BRAIN/card.work", "/BRAIN/card.strd");
}

/* SAVE FX DEFAULT: track t's FX1 (fx 0) or FX2 (fx 1) page in the current
 * Part becomes that effect's card-layer default. The record replaces the
 * effect's default record (no mode) in card.work; every other record keeps
 * its bytes. The descriptor takes the values at once. 0, or an error code
 * (also in brain_save_counts[S_SAVE_ERR]). */
static int write_default(u32 t, u32 fx, int clear);
static void cache_defaults(int have);

/* out[HDR..at) holds `kept` records: the header (file kind 0 card .work, 2
 * project .work), then the file at path. */
static int write_store(const char *path, u32 kind, u32 at, u32 kept)
{
	for (u32 k = 0; k < HDR; k++)
		out[k] = 0;
	put32(out, 0x4252414eu);			/* "BRAN": a brain file */
	put16(out + 4, HDR);
	out[6] = 1;					/* container 1.0 */
	out[8] = (u8)kind;
	put16(out + 10, kept);
	put32(out + 12, at);
	for (u32 k = 0; k < 8 && "BRAIN"[k]; k++)
		out[20 + k] = "BRAIN"[k];
	put32(out + 16, crc32(out + 20, at - 20));
	return write_file(path, out, at);
}

static int write_card(u32 at, u32 kept)
{
	return write_store("/BRAIN/card.work", 0, at, kept);
}

/* REMIX SWITCH's CARD setting, key 1: a bounded filename, or empty for
 * FLASHED. It is a Blob (no scalar SETTINGS row). The switcher calls this
 * after the sync has drained, or before the boot posts any engine work. */
#define RMX_STORE "octabam.remix-switch"
#define RMX_IDLEN (sizeof RMX_STORE - 1)
#define RMX_NLEN 24

static int remix_name_ok(const char *s)
{
	u32 n = 0;
	while (n < RMX_NLEN && s[n]) {
		char c = s[n];
		if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
		      (c >= '0' && c <= '9') || c == ' ' || c == '.' || c == '_' || c == '-'))
			return 0;
		n++;
	}
	return n == 0 || (n >= 5 && n < RMX_NLEN && s[0] != '.' && s[n - 4] == '.' &&
		(s[n - 3] & ~32) == 'R' && (s[n - 2] & ~32) == 'M' && (s[n - 1] & ~32) == 'X');
}

/* The sole record, with a supported schema and intact payload. Duplicates
 * or an unreadable record make a write fail as well as a read stay home. */
static const u8 *remix_record(int n, int *bad)
{
	const u8 *found = 0;
	for (u32 r = 0, at = HDR; n > 0 && r < be16(buf + 10); r++, at += be32(buf + at + 16)) {
		const u8 *p = buf + at;
		if (p[0] != K_SETTINGS || !same_id(p + REC_HDR, p[1], RMX_STORE, RMX_IDLEN))
			continue;
		const u8 *pay = p + REC_HDR + align4(p[1]);
		if (found || be16(p + 2) != 1 || crc32(pay, be32(p + 8)) != be32(p + 12))
			*bad = 1;
		found = p;
	}
	return found;
}

/* Return the size of a bounded TLV, or zero for a malformed payload. */
static u32 remix_tlv(const u8 *v, u32 left)
{
	if (left < 4)
		return 0;
	u32 len = v[3], head = 4;
	if (len == 255) {
		if (left < 8 || v[2] != T_BLOB)
			return 0;
		len = be32(v + 4);
		head = 8;
	}
	if (len > left - head || align4(len) > left - head)
		return 0;
	return head + align4(len);
}

int brain_remix_get(char *name)
{
	name[0] = 0;
	int n = current_store(), bad = 0, seen = 0;
	const u8 *r = remix_record(n, &bad);
	if (n <= 0 || bad || !r)
		return 0;
	const u8 *p = r + REC_HDR + align4(r[1]);
	for (u32 at = 0, plen = be32(r + 8); at < plen;) {
		u32 size = remix_tlv(p + at, plen - at);
		if (!size)
			return name[0] = 0;
		if (be16(p + at) == 1) {
			if (seen++ || p[at + 2] != T_BLOB || p[at + 3] != RMX_NLEN)
				return name[0] = 0;
			for (u32 k = 0; k < RMX_NLEN; k++)
				name[k] = p[at + 4 + k];
		}
		at += size;
	}
	if (!remix_name_ok(name))
		name[0] = 0;
	return name[0] != 0;
}

/* Keep every other record and every unknown key of our own record. */
int brain_remix_save(const char *name)
{
	if (!remix_name_ok(name))
		return 2;
	int n = current_store(), bad = 0;
	const u8 *old = remix_record(n, &bad);
	if (n < 0 || bad)
		return 2;
	u32 at = HDR, kept = 0;
	for (u32 i = HDR, k = 0; n > 0 && k < be16(buf + 10); k++, i += be32(buf + i + 16)) {
		const u8 *p = buf + i;
		if (p == old)
			continue;
		u32 size = be32(p + 16);
		if (size > BUF_LEN - at)
			return 3;
		for (u32 j = 0; j < size; j++)
			out[at + j] = p[j];
		at += size;
		kept++;
	}
	u32 prefix = REC_HDR + align4(RMX_IDLEN);
	if (prefix + 4 + RMX_NLEN > BUF_LEN - at)
		return 3;
	u8 *r = out + at, *pay = r + prefix;
	for (u32 k = 0; k < prefix + 4 + RMX_NLEN; k++)
		r[k] = 0;
	r[0] = K_SETTINGS; r[1] = RMX_IDLEN;
	put16(r + 2, 1);
	for (u32 k = 0; k < RMX_IDLEN; k++)
		r[REC_HDR + k] = RMX_STORE[k];
	put16(pay, 1); pay[2] = T_BLOB; pay[3] = RMX_NLEN;
	for (u32 k = 0; k < RMX_NLEN - 1 && name[k]; k++)
		pay[4 + k] = (u8)name[k];
	u32 plen = 4 + RMX_NLEN;
	if (old) {
		const u8 *p = old + REC_HDR + align4(old[1]);
		for (u32 i = 0, len = be32(old + 8); i < len;) {
			u32 size = remix_tlv(p + i, len - i);
			if (!size)
				return 2;
			if (be16(p + i) != 1) {
				if (size > BUF_LEN - at - prefix - plen)
					return 3;
				for (u32 k = 0; k < size; k++)
					pay[plen + k] = p[i + k];
				plen += size;
			}
			i += size;
		}
	}
	put32(r + 8, plen); put32(r + 12, crc32(pay, plen)); put32(r + 16, prefix + plen);
	return write_card(at + prefix + plen, kept + 1) < 0 ? 4 : 0;
}

/* The settings records of one scope: scope 0 is card.work, scope 1 the
 * project's brain.work (pw, ps; proj_paths() first). One record per store
 * that has entries of the scope, its values the table's; keys this image
 * does not know are kept from the record it replaces (rule 2), and every
 * other record keeps its bytes. With `project`, the project record
 * (section 7.5) is rebuilt from brain_fx[] and replaces any other one.
 * 0, or an error code as write_default's (5: no project is named). */
static int in_scope(u32 f, u32 scope)
{
	return brain_set[f].scope == scope;
}

static int write_set_file(u32 scope, int project)
{
	if (scope && !proj_paths())
		return 5;
	const char *w = scope ? pw : "/BRAIN/card.work", *sd = scope ? ps : "/BRAIN/card.strd";
	int n = cur(w, sd);
	if (n < 0)
		return 2;
	u32 at = HDR, kept = 0;
	/* the kept records: everything but the settings of the stores we write
	 * and, with `project`, the project records */
	for (u32 r = 0, i = HDR; n && r < be16(buf + 10); r++, i += be32(buf + i + 16)) {
		const u8 *p = buf + i;
		u32 size = be32(p + 16), ours = 0;
		if (p[0] == K_SETTINGS)
			for (u32 e = 0; e < brain_set_n && e < MAX_SET; e++)
				ours |= in_scope(e, scope) && same_id(p + REC_HDR, p[1], brain_set[e].id, brain_set[e].id_len);
		if (p[0] == K_PROJECT && project && same_id(p + REC_HDR, p[1], OWN_STORE, 13))
			ours = 1;
		if (ours)
			continue;
		if (at + size > BUF_LEN)
			return 3;
		for (u32 k = 0; k < size; k++)
			out[at + k] = p[k];
		at += size;
		kept++;
	}
	/* one record per store, in table order */
	for (u32 e = 0; e < brain_set_n && e < MAX_SET; e++) {
		const struct set_ent *s = &brain_set[e];
		if (!in_scope(e, scope))
			continue;
		int first = 1;
		for (u32 f = 0; f < e; f++)
			if (in_scope(f, scope) && same_id((const u8 *)brain_set[f].id, brain_set[f].id_len, s->id, s->id_len))
				first = 0;
		if (!first)
			continue;
		u8 *r = out + at;
		u32 idsz = align4(s->id_len);
		if (at + REC_HDR + idsz > BUF_LEN)
			return 3;
		for (u32 k = 0; k < REC_HDR + idsz; k++)
			r[k] = 0;
		r[0] = K_SETTINGS;
		r[1] = s->id_len;
		put16(r + 2, 1);			/* schema major 1, minor 0 */
		for (u32 k = 0; k < s->id_len; k++)
			r[REC_HDR + k] = s->id[k];
		u8 *v = r + REC_HDR + idsz, *v0 = v;
		for (u32 f = e; f < brain_set_n && f < MAX_SET; f++) {
			const struct set_ent *g = &brain_set[f];
			if (!in_scope(f, scope) || !same_id((const u8 *)g->id, g->id_len, s->id, s->id_len))
				continue;
			if (v + 8 > out + BUF_LEN)
				return 3;
			put16(v, g->key);
			v[2] = g->type;
			v[3] = g->type == 3 ? 2 : 1;
			v[4] = v[5] = v[6] = v[7] = 0;
			if (g->type == 3)
				put16(v + 4, (u32)brain_values[f] & 0xffff);
			else
				v[4] = (u8)brain_values[f];
			v += 8;
		}
		/* unknown keys from the record this one replaces */
		for (u32 rr = 0, i = HDR; n && rr < be16(buf + 10); rr++, i += be32(buf + i + 16)) {
			const u8 *p = buf + i;
			if (p[0] != K_SETTINGS || !same_id(p + REC_HDR, p[1], s->id, s->id_len))
				continue;
			const u8 *pay = p + REC_HDR + align4(p[1]);
			u32 plen = be32(p + 8);
			for (u32 a = 0; a + 4 <= plen;) {
				u32 key = be16(pay + a), len = pay[a + 3], head = 4, known = 0;
				if (len == 255) {
					if (a + 8 > plen)
						break;
					len = be32(pay + a + 4);
					head = 8;
				}
				u32 sz = head + align4(len);
				if (a + sz > plen)
					break;
				for (u32 f = 0; f < brain_set_n && f < MAX_SET; f++)
					known |= in_scope(f, scope) && brain_set[f].key == key
						&& same_id((const u8 *)brain_set[f].id, brain_set[f].id_len, s->id, s->id_len);
				if (!known) {
					if (v + sz > out + BUF_LEN)
						return 3;
					for (u32 k = 0; k < sz; k++)
						v[k] = pay[a + k];
					v += sz;
				}
				a += sz;
			}
			break;
		}
		u32 plen = (u32)(v - v0), size = REC_HDR + idsz + plen;
		put32(r + 8, plen);
		put32(r + 12, crc32(v0, plen));
		put32(r + 16, size);
		at += size;
		kept++;
	}
	if (project) {
		/* the project record: one entry per effect in the image */
		u32 plen = 0;
		for (u32 i = 0; i < brain_fx_n && i < MAX_FX; i++)
			plen += 8 + align4(brain_fx[i].id_len);
		u32 size = REC_HDR + align4(13) + plen;
		if (at + size > BUF_LEN)
			return 3;
		u8 *r = out + at;
		for (u32 k = 0; k < size; k++)
			r[k] = 0;
		r[0] = K_PROJECT;
		r[1] = 13;
		put16(r + 2, 1);
		put32(r + 8, plen);
		put32(r + 16, size);
		for (u32 k = 0; k < 13; k++)
			r[REC_HDR + k] = (u8)OWN_STORE[k];
		u8 *v = r + REC_HDR + align4(13), *v0 = v;
		for (u32 i = 0; i < brain_fx_n && i < MAX_FX; i++) {
			const struct fx_ent *f = &brain_fx[i];
			v[0] = f->fx_id;
			v[1] = f->id_len;
			put32(v + 4, f->layout);
			for (u32 k = 0; k < f->id_len; k++)
				v[8 + k] = (u8)f->id[k];
			v += 8 + align4(f->id_len);
		}
		put32(r + 12, crc32(v0, plen));
		at += size;
		kept++;
	}
	return write_store(w, scope ? 2 : 0, at, kept) < 0 ? 4 : 0;
}

/* The CS1 early block (BRAIN.md section 6.4): at CS1_EARLY_BASE a 4-byte
 * header (magic 0xea, version 1, the 16-bit sum of the value bytes), then
 * each early setting's value at its cs1_off (type 1/2: one byte; type 3:
 * two, big-endian). The sum is over the value bytes of every early entry,
 * so the reader (the usb unit's cfgsel) checks the same sum over the table
 * its include emits; the order does not matter, addition is commutative. */
#define EARLY_MAGIC 0xea
#define EARLY_VER   1

static void write_early_block(void)
{
	volatile u8 *b = CS1_EARLY_BASE;
	u32 sum = 0;
	for (u32 i = 0; i < brain_set_n && i < MAX_SET; i++) {
		const struct set_ent *e = &brain_set[i];
		if (e->apply != 2 || !e->cs1_off)
			continue;
		volatile u8 *p = (volatile u8 *)e->cs1_off;
		if (e->type == 3) {
			p[0] = (u8)(brain_values[i] >> 8);
			p[1] = (u8)brain_values[i];
			sum += p[0] + p[1];
		} else {
			p[0] = (u8)brain_values[i];
			sum += p[0];
		}
	}
	b[0] = EARLY_MAGIC;
	b[1] = EARLY_VER;
	b[2] = (u8)(sum >> 8);
	b[3] = (u8)sum;
}

/* SETTINGS edit: card.work, and the project's brain.work when a PROJECT
 * setting exists and a project is named. */
static int write_settings(void)
{
	int err = write_set_file(0, 0), proj = 0;
	if (!err)
		write_early_block();		/* CS1 mirrors the table (BRAIN.md 6.4) */
	for (u32 e = 0; e < brain_set_n && e < MAX_SET; e++)
		proj |= in_scope(e, 1);
	if (proj) {
		int e2 = write_set_file(1, 0);
		if (!err)
			err = e2;
	}
	return err;
}

int brain_save_default(u32 t, u32 fx)
{
	return write_default(t, fx, 0);
}

/* CLEAR FX DEFAULT: the effect's default record (no mode) leaves card.work and
 * the descriptor goes back to the image's values. */
int brain_clear_default(u32 t, u32 fx)
{
	return write_default(t, fx, 1);
}

/* the default of the effect on track t's FX1 (fx 0) or FX2, written or cleared */
static int write_default_e(int e, u32 t, u32 fx, int clear);

static int write_default(u32 t, u32 fx, int clear)
{
	u8 *part = DBPTR + WORKING + (CUR_PART & 3) * PART_LEN;
	int e = -1;
	if (t <= 7) {
		u32 id = part[fx ? 0x8 + t : t];
		for (u32 i = 0; i < brain_fx_n && i < MAX_FX; i++)
			if (brain_fx[i].fx_id == id && (desc[i][0] || desc[i][1]))
				e = (int)i;
	}
	return write_default_e(e, t, fx, clear);
}

/* e is the effect's entry; a clear needs no page (t and fx are the values' source for a save) */
static int write_default_e(int e, u32 t, u32 fx, int clear)
{
	u8 *part = DBPTR + WORKING + (CUR_PART & 3) * PART_LEN;
	int err = 0;
	brain_save_counts[S_SAVES]++;
	if (!snapped)
		snapshot();
	if (e < 0 || e >= (int)brain_fx_n || (!clear && t > 7)) {
		err = 1;
		goto done;
	}
	const struct fx_ent *f = &brain_fx[e];
	u8 vals[12];
	for (int s = 0; s < 12; s++)
		vals[s] = 0;
	if (!clear)
		for (int s = 0; s < 6; s++) {
			vals[s] = part[0x11a + t * 24 + (fx ? 18 : 12) + s];
			vals[6 + s] = part[0x2fe + t * 30 + (fx ? 6 : 0) + s];
		}
	int n = current_store();
	if (n < 0) {
		err = 2;
		goto done;
	}
	/* the file: the kept records, then the new one */
	u32 at = HDR, kept = 0;
	for (u32 r = 0, i = HDR; n && r < be16(buf + 10); r++, i += be32(buf + i + 16)) {
		const u8 *p = buf + i;
		u32 size = be32(p + 16);
		const u8 *pay = p + REC_HDR + align4(p[1]);
		if (p[0] == K_DEFAULT && same_id(p + REC_HDR, p[1], f->id, f->id_len)
		    && be32(p + 8) >= 4 && be16(pay) == 0 && be16(pay + 2) == NO_MODE)
			continue;
		if (at + size > BUF_LEN) {
			err = 3;
			goto done;
		}
		for (u32 k = 0; k < size; k++)
			out[at + k] = p[k];
		at += size;
		kept++;
	}
	if (clear)
		goto header;
	u32 nvals = 0;
	for (int s = 0; s < 12; s++)
		nvals += f->keys[s] != 0;
	u32 plen = 8 + 8 * nvals, size = REC_HDR + align4(f->id_len) + plen;
	if (at + size > BUF_LEN) {
		err = 3;
		goto done;
	}
	u8 *r = out + at;
	for (u32 k = 0; k < size; k++)
		r[k] = 0;
	r[0] = K_DEFAULT;
	r[1] = f->id_len;
	put16(r + 2, 1);				/* schema major 1, minor 0 */
	put32(r + 8, plen);
	put32(r + 16, size);
	for (u32 k = 0; k < f->id_len; k++)
		r[REC_HDR + k] = f->id[k];
	u8 *pay = r + REC_HDR + align4(f->id_len);
	put16(pay + 2, NO_MODE);			/* target 0, no mode */
	put32(pay + 4, f->layout);
	u8 *v = pay + 8;
	for (int s = 0; s < 12; s++)
		if (f->keys[s]) {
			put16(v, f->keys[s]);
			v[2] = T_BYTE;
			v[3] = 1;
			v[4] = vals[s];
			v += 8;
		}
	put32(r + 12, crc32(pay, plen));
	at += size;
	kept++;
header:
	if (write_card(at, kept) < 0) {
		err = 4;
		goto done;
	}
	cache_defaults(current_store() > 0);
	/* the descriptor takes the values now (the next load re-applies the file) */
	if (clear) {
		for (int k = 0; k < 2; k++)
			if (desc[e][k])
				for (int s = 0; s < 12; s++)
					desc[e][k][0x5e + s] = shadow[e][k][s];
		goto done;
	}
	for (int s = 0; s < 12; s++)
		if (f->keys[s])
			for (int k = 0; k < 2; k++) {
				u8 *p = desc[e][k];
				if (p && vals[s] < be32(p + 0x9a + 4 * s))
					p[0x5e + s] = vals[s];
			}
done:
	brain_save_counts[S_SAVE_ERR] = (u32)err;
	return -err;
}

/* SAVE PROJECT (the project store), in the engine task: card.work becomes
 * card.strd, the recovery copy (BRAIN.md section 6.2; a damaged or absent
 * card.work is not copied); then the project's brain.work is written (its
 * PROJECT settings and the project record) and becomes brain.strd. */
enum { PS_SAVES, PS_ERR, PS_STRD, PS_STRD_ERR, PS_N };
/* PS_ERR: the last write_set_file error (0 none, 2 both files damaged, 3 too
 * large, 4 write, 5 no project named) */
u32 brain_proj_counts[PS_N] DATA;

void brain_card_store(void)
{
	u32 n = slurp("/BRAIN/card.work");
	if (n && valid(n)) {
		buf[8] = 1;				/* file kind: card .strd (outside the CRC) */
		if (write_file("/BRAIN/card.strd", buf, n) < 0)
			brain_save_counts[S_STRD_ERR]++;
		else
			brain_save_counts[S_STRD]++;
	}
	brain_proj_counts[PS_SAVES]++;
	int err = write_set_file(1, 1);
	brain_proj_counts[PS_ERR] = (u32)err;
	if (err)
		return;
	n = slurp(pw);
	if (!n || !valid(n))
		return;
	buf[8] = 3;					/* project .strd */
	if (write_file(ps, buf, n) < 0)
		brain_proj_counts[PS_STRD_ERR]++;
	else
		brain_proj_counts[PS_STRD]++;
}

/* ---- the engine job: SAVE FX DEFAULT off the UI task ----------------------- */

#define Q_SEND   ((int (*)(void *, void *))0x40000c3c)	/* post a message to a queue */
#define ENGINE_Q ((void *)0x460d17ce)			/* the engine task's queue */
#define JOB_SAVE 0x41					/* above stock's 0..45 */

static u32 job_msg[4];		/* type byte first, as stock's records */
static u32 job_args;

/* From any task: SAVE FX DEFAULT for track t's FX1 (0) or FX2 (1), run by
 * the engine task, where the stock writes the project's files. One job is
 * pending at a time; a second post before the engine runs replaces it. */
void brain_post_save(u32 t, u32 fx)
{
	job_args = (t & 7) | (fx ? 0x100 : 0);
	((u8 *)job_msg)[0] = JOB_SAVE;
	Q_SEND(ENGINE_Q, job_msg);
}

/* From any task: card.work copied to card.strd by the engine task (what
 * SAVE PROJECT's project store does in that task through brain_on_store). */
void brain_post_store(void)
{
	job_args = 0x10000;
	((u8 *)job_msg)[0] = JOB_SAVE;
	Q_SEND(ENGINE_Q, job_msg);
}

/* From any task: CLEAR FX DEFAULT for track t's FX1 (0) or FX2 (1). */
void brain_post_clear(u32 t, u32 fx)
{
	job_args = (t & 7) | (fx ? 0x100 : 0) | 0x200;
	((u8 *)job_msg)[0] = JOB_SAVE;
	Q_SEND(ENGINE_Q, job_msg);
}

/* From any task: the stored default of effect entry e cleared (DEFAULTS' rows). */
void brain_post_clear_e(u32 e)
{
	job_args = 0x400000 | (e & 0xff);
	((u8 *)job_msg)[0] = JOB_SAVE;
	Q_SEND(ENGINE_Q, job_msg);
}

/* The engine task, at a JOB_SAVE message (hooks.s brain_on_job). */
static void write_debug(void);

void brain_post_settings(void)
{
	job_args = 0x40000;
	((u8 *)job_msg)[0] = JOB_SAVE;
	Q_SEND(ENGINE_Q, job_msg);
}

enum { T_SAVE, T_DELETE, T_RENAME, T_EDIT, T_NEW };
static int write_template(int del, u32 t, u32 kind, u32 e, u32 i);
static int write_names(void);
static int write_pset(int clear);
static int write_default_e(int e, u32 t, u32 fx, int clear);
static int write_setdef(u32 e, u32 i);
static int write_partdef_clear(void);

void brain_job(void)
{
	if (job_args & 0x10000000)
		brain_save_counts[S_SAVE_ERR] = (u32)write_template(T_NEW, 0, 0, (job_args >> 8) & 0xff, 0);
	else if (job_args & 0x8000000)
		brain_save_counts[S_SAVE_ERR] = (u32)write_template(T_EDIT, 0, 0, (job_args >> 8) & 0xff, job_args & 0xff);
	else if (job_args & 0x4000000)
		brain_save_counts[S_SAVE_ERR] = (u32)write_setdef((job_args >> 8) & 0xff, job_args & 0xff);
	else if (job_args & 0x3000000)
		brain_save_counts[S_SAVE_ERR] = (u32)write_pset(!!(job_args & 0x2000000));
	else if (job_args & 0x800000)
		brain_save_counts[S_SAVE_ERR] = (u32)write_names();
	else if (job_args & 0x400000)
		brain_save_counts[S_SAVE_ERR] = (u32)((job_args & 0xff) == E_PART ? write_partdef_clear()
						       : write_default_e((int)(job_args & 0xff), 0, 0, 1));
	else if (job_args & 0x200000)
		brain_save_counts[S_SAVE_ERR] = (u32)write_template(T_RENAME, 0, 0, (job_args >> 8) & 0xff, job_args & 0xff);
	else if (job_args & 0x100000)
		brain_save_counts[S_SAVE_ERR] = (u32)write_template(T_DELETE, 0, 0, (job_args >> 8) & 0xff, job_args & 0xff);
	else if (job_args & 0x80000)
		brain_save_counts[S_SAVE_ERR] = (u32)write_template(T_SAVE, job_args & 7, (job_args >> 8) & 7, 0, 0);
	else if (job_args & 0x40000)
		brain_save_counts[S_SAVE_ERR] = (u32)write_settings();
	else if (job_args & 0x20000)
		write_debug();
	else if (job_args & 0x10000)
		brain_card_store();
	else
		write_default(job_args & 7, (job_args >> 8) & 1, (job_args >> 9) & 1);
}

/* ---- the BRAIN menu ------------------------------------------------------ */

#define POPUP     ((void (*)(const char *, u32, const char *const *, u32, u32))0x4006d57c)
#define CUR_TRACK (*(volatile u8 *)0x80000000)
#define MIDI_MODE (*(volatile u32 *)0x80000012)	/* nonzero: MIDI tracks (a long; the MIDI key stores 1) */
#define PAGE_KIND (*(volatile u32 *)0x460d1684)	/* 0 SRC, 1 LFO, 2 AMP, 3 FX1, 4 FX2 */

static const char *msg[2];
static char line1[16];

/* The page the menu was opened over: 0 FX1, 1 FX2, or -1 with the reason
 * in msg[1]. */
static int menu_target(void)
{
	u32 kind = PAGE_KIND;
	if (MIDI_MODE || (kind != 3 && kind != 4)) {
		msg[0] = "OPEN AN FX PAGE";
		msg[1] = "OF AN AUDIO TRACK";
		return -1;
	}
	u32 fx = kind == 4, t = CUR_TRACK & 7;
	u8 *part = DBPTR + WORKING + (CUR_PART & 3) * PART_LEN;
	u32 id = part[fx ? 0x8 + t : t];
	for (u32 i = 0; i < brain_fx_n && i < MAX_FX; i++)
		if (brain_fx[i].fx_id == id) {
			const char *s = fx ? "FX2 TRACK " : "FX1 TRACK ";
			int k = 0;
			while (s[k]) {
				line1[k] = s[k];
				k++;
			}
			line1[k++] = '1' + t;
			line1[k] = 0;
			msg[0] = line1;
			return (int)fx;
		}
	msg[0] = "THIS EFFECT HAS";
	msg[1] = "NO STORED DEFAULT";
	return -1;
}

/* Row actions, called by the menu with one argument (0). */
void brain_menu_save(u32 unused)
{
	int fx = menu_target();
	(void)unused;
	if (fx >= 0) {
		brain_post_save(CUR_TRACK & 7, (u32)fx);
		msg[1] = "SAVED AS DEFAULT";
	}
	POPUP("SAVE FX DEFAULT", 2, msg, 0, 0);
}

void brain_menu_clear(u32 unused)
{
	int fx = menu_target();
	(void)unused;
	if (fx >= 0) {
		brain_post_clear(CUR_TRACK & 7, (u32)fx);
		msg[1] = "DEFAULT CLEARED";
	}
	POPUP("CLEAR FX DEFAULT", 2, msg, 0, 0);
}

static u32 put_s(char *o, const char *s);

static u32 put_num(char *o, u32 v)
{
	char d[10];
	u32 n = 0, k = 0;
	do
		d[n++] = (char)('0' + v % 10);
	while ((v /= 10) && n < 10);
	while (n)
		o[k++] = d[--n];
	return k;
}

/* ---- the debug log: MIDI messages and what the firmware did with them ------ */

/* hooks.s brain_on_midi wraps the MIDI thread's call to its handler (table
 * 0x400d6474, docs/firmware/MIDI.md appendix B) and calls brain_midi_log
 * after the handler returns, with the message (status, data) and the state
 * it left: the sync flags (0x80000028), the playing pattern (0x800065be)
 * and the byte after it (0x800065c0). Clock and active sensing are not
 * logged. WRITE DEBUG LOG has the engine task write the ring to
 * /BRAIN/debug.txt. */

#define LOG_N    256

struct dbg_ent { u16 seq; u8 st, d1, d2, sync, pnow, pnext; };
static struct dbg_ent dbg_ring[LOG_N];
static u32 dbg_seq DATA;			/* messages logged since the boot */

/* what came in, by kind (IO): notes, controllers, program changes, pressure
 * and bend, other system messages, clock */
enum { MC_NOTE, MC_CC, MC_PGM, MC_BEND, MC_SYS, MC_CLK, MC_N };
static u32 midi_cnt[MC_N] DATA;

void brain_midi_log(const u8 *m)
{
	u32 hi = m[0] >> 4;
	if (m[0] == 0xf8)
		midi_cnt[MC_CLK]++;
	else if (m[0] != 0xfe)
		midi_cnt[hi == 8 || hi == 9 ? MC_NOTE : hi == 11 ? MC_CC : hi == 12 ? MC_PGM : hi == 15 ? MC_SYS : MC_BEND]++;
	if (!brain_v_octabam_brain_1)			/* SETTINGS > MIDI LOG off */
		return;
	u8 st = m[0];
	if (st == 0xf8 || st == 0xfe)
		return;
	struct dbg_ent *e = &dbg_ring[dbg_seq % LOG_N];
	e->seq = (u16)dbg_seq;
	e->st = st;
	e->d1 = m[1];
	e->d2 = m[2];
	e->sync = *(volatile u8 *)0x80000028;
	e->pnow = *(volatile u8 *)0x800065be;
	e->pnext = *(volatile u8 *)0x800065c0;
	dbg_seq++;
}

/* Text without stock's sprintf, which does not take %02X or field widths. Ends the text with a NUL
 * (not counted in the return value, so a following put_s overwrites it). */
static u32 put_s(char *o, const char *s) { u32 n = 0; while (s[n]) { o[n] = s[n]; n++; } o[n] = 0; return n; }
static u32 put_hex2(char *o, u32 v) { const char *h = "0123456789ABCDEF"; o[0] = h[(v >> 4) & 15]; o[1] = h[v & 15]; return 2; }
static u32 put_dec(char *o, u32 v, u32 width)
{
	char d[10];
	u32 n = 0, k = 0;
	do { d[n++] = (char)('0' + v % 10); v /= 10; } while (v && n < 10);
	while (k + n < width) o[k++] = ' ';
	while (n) o[k++] = d[--n];
	return k;
}

/* The engine task: the ring, oldest first, to /BRAIN/debug.txt. */
static void write_debug(void)
{
	u32 n = dbg_seq < LOG_N ? dbg_seq : LOG_N, at = 0;
	char *o = (char *)out;
	at += put_s(o + at, "BRAIN debug: ");
	at += put_dec(o + at, dbg_seq, 0);
	at += put_s(o + at, " MIDI messages since the boot, the last ");
	at += put_dec(o + at, n, 0);
	at += put_s(o + at, " below (clock and active sensing not logged)\r\n"
		       "  seq status d1 d2 sync pattern next\r\n");
	for (u32 k = dbg_seq - n; k < dbg_seq && at < BUF_LEN - 64; k++) {
		const struct dbg_ent *e = &dbg_ring[k % LOG_N];
		at += put_dec(o + at, e->seq, 5);
		at += put_s(o + at, "   ");
		at += put_hex2(o + at, e->st);
		at += put_s(o + at, "    ");
		at += put_hex2(o + at, e->d1);
		at += put_s(o + at, " ");
		at += put_hex2(o + at, e->d2);
		at += put_s(o + at, "  ");
		at += put_hex2(o + at, e->sync);
		at += put_dec(o + at, e->pnow, 6);
		at += put_dec(o + at, e->pnext, 7);
		at += put_s(o + at, "\r\n");
	}
	if (write_file("/BRAIN/debug.txt", out, at) < 0)
		brain_save_counts[S_SAVE_ERR] = 4;
}

void brain_post_log(void)
{
	job_args = 0x20000;
	((u8 *)job_msg)[0] = JOB_SAVE;
	Q_SEND(ENGINE_Q, job_msg);
}

/* WRITE DEBUG LOG and MIDI MONITOR read the log SETTINGS > MIDI LOG fills */
static int log_is_off(void)
{
	if (brain_v_octabam_brain_1)
		return 0;
	msg[0] = "MIDI LOG IS OFF";
	msg[1] = "SWITCH IT ON";
	POPUP("MIDI LOG", 2, msg, 0, 0);
	return 1;
}

void brain_menu_log(u32 unused)
{
	(void)unused;
	if (log_is_off())
		return;
	brain_post_log();
	msg[0] = "WRITING THE LOG TO";
	msg[1] = "/BRAIN/DEBUG.TXT";
	POPUP("DEBUG LOG", 2, msg, 0, 0);
}

/* ---- BRAIN's root pane and its screens ------------------------------------ */

/* BRAIN's pane in MAIN MENU is one list; each row opens one of BRAIN's
 * screens, or (IMAGE CHECK) a popup. A screen is a state of the menu-state
 * table (0x400cbdac), which is copied to DRAM with the screens appended as
 * states 16.. (manifest.py): a full window like the stock MIDI SYNC, drawn
 * by brain_scr_draw, keys to brain_scr_key. NO inside a screen goes back to
 * the menu, as in the stock ones. docs/firmware/MAINMENU.md sections 3, 4
 * and 9a (modules/busscreen, in history, added a 17th state the same way). */

struct mrow { const char *label; void *window; void (*action)(u32); u32 getter; void *child; u32 id; };
struct mlist { u32 count, scroll, cursor, sel, visible, count2; struct mrow *rows; };

extern struct mlist brain_list;
extern struct mrow brain_top_rows[], brain_rmx_rows[];
void brain_post_settings(void);
extern u32 brain_rmx_n;			/* REMIXES' rows (switch.s) */

#define TOP_N   6				/* IMAGE, LOG, PERFORMANCE, REMIXES, SETTINGS, TEMPLATES */
#define PANE_W  15				/* characters the list pane shows */
#define NOOP    ((void (*)(u32))0x400648f8)	/* stock's shared row action, `rts` */

enum { SC_PERF, SC_RMX, SC_SET, SC_TPL, SC_IMG, SC_LOG, SC_TED, SC_N };
static void sc_open(u32 sc);
static void sc_rebuild(void);

/* BRAIN's pane at its top row (REMIX SWITCH's osw_menu calls this when MAIN MENU opens) */
void brain_menu_top(void)
{
	brain_list.rows = brain_top_rows;
	brain_list.count = brain_list.count2 = TOP_N;
	brain_list.scroll = brain_list.cursor = brain_list.sel = 0;
}

void brain_open_perf(u32 unused) { (void)unused; sc_open(SC_PERF); }
void brain_open_about(u32 unused) { (void)unused; sc_open(SC_IMG); }
void brain_open_log(u32 unused) { (void)unused; sc_open(SC_LOG); }
void brain_open_remixes(u32 unused) { (void)unused; sc_open(SC_RMX); }
void brain_open_settings(u32 unused) { (void)unused; sc_open(SC_SET); }
void brain_open_templates(u32 unused) { (void)unused; sc_open(SC_TPL); }

/* ---- templates: lists, apply, save and delete (BRAIN.md sections 5.2, 9) ---- */

/* A template's target is one view: track t's FX1 or FX2 page (an effect of
 * brain_fx[], entry e < MAX_FX), its AMP or LFO page, a whole MIDI track
 * (the stock targets, entry ST_BASE + kind - V_AMP), or its SRC page, one
 * target per machine type (entry ST_BASE + 3 + machine). */
enum { V_FX1, V_FX2, V_AMP, V_LFO, V_MIDI, V_SRC, V_PART, V_PROJECT };
#define NSLOT    208
#define SKIP     0xfe		/* flat[]: a slot with no parameter */
#define NOFLAT   0xff		/* flat[]: a slot the page-1 writer does not reach */

struct view {
	u32 kind, t, e, n, machine;
	u16 key[NSLOT];			/* 0: the slot is not stored */
	u32 at[NSLOT];			/* Part offset from DBPTR + part * PART_LEN */
	u8 lo[NSLOT], hi[NSLOT];
	u8 flat[NSLOT];			/* page-1 writer index, NOFLAT or SKIP */
	u8 cur[NSLOT];
	u8 def[NSLOT];			/* the descriptor's default of the slot */
	u32 fmt[NSLOT];			/* the slot's display formatter (E + 0x102), or 0 */
	const u8 *name[NSLOT];		/* the slot's name in its descriptor (6 bytes), or 0 */
};

struct st_ent {
	const char *id;
	u32 id_len, layout;
};
#define ST_N     10
static const struct st_ent st_ent[ST_N] = {
	{ "stock.amp", 9, 0x414d5031 },		/* "AMP1" */
	{ "stock.lfo", 9, 0x4c464f31 },		/* "LFO1" */
	{ "stock.midi", 10, 0x4d494431 },	/* "MID1" */
	/* the SRC page by machine type (PARAM_PAGES.md section 3, entries 0-4) */
	{ "stock.static", 12, 0x53544131 },	/* "STA1" */
	{ "stock.flex", 10, 0x464c5831 },	/* "FLX1" */
	{ "stock.thru", 10, 0x54485231 },	/* "THR1" */
	{ "stock.neighbor", 14, 0x4e425231 },	/* "NBR1" */
	{ "stock.pickup", 12, 0x50434b31 },	/* "PCK1" */
	{ "stock.project", 13, 0x50524a31 },	/* "PRJ1": the stock PROJECT menu's bytes (PS_LAYOUT) */
	{ "stock.part2", 11, 0x50525432 },	/* "PRT2": the whole Part, one blob (PART templates, below) */
};
#define D_PLAYBACK 0x400d2fe4			/* PLAYBACK entry 0; entry m at + m * 0x192 */

/* The stock page descriptors (PARAM_PAGES.md section 3), entry start E:
 * minimum per slot at E + 0xa2, count at E + 0xd2, enable nibbles at
 * E + 0x1c6 (slots 0-7) and E + 0x1c2 (8-11), section 3b. */
#define D_LFO   0x400d37be
#define D_AMP   0x400d3950
#define D_NOTE  0x400d3e06
#define D_ARP   0x400d3f98
#define D_MLFO  0x400d412a
#define D_CTL1  0x400d42bc
#define D_CTL2  0x400d444e
static const u32 midi_desc[5] = { D_NOTE, D_MLFO, D_ARP, D_CTL1, D_CTL2 };

static void ent_id(u32 e, const char **id, u32 *len, u32 *layout)
{
	if (e >= ST_BASE) {
		const struct st_ent *s = &st_ent[e - ST_BASE];
		*id = s->id;
		*len = s->id_len;
		*layout = s->layout;
	} else {
		*id = brain_fx[e].id;
		*len = brain_fx[e].id_len;
		*layout = brain_fx[e].layout;
	}
}

/* One slot: its key, Part offset, page-1 index and range from descriptor
 * E's slot s (a raw byte when E is 0). A slot whose enable nibble has bit
 * 0 clear is neither stored nor written: the stock writers refuse it
 * (0x40054cd8 at 0x40054d20), and the stock MIDI pages' empty setup slots
 * and AMP's XVOL are those. */
static void slot(struct view *v, u32 key, u32 at, u32 flat, u32 E, u32 s)
{
	u32 i = v->n++;
	v->key[i] = (u16)key;
	v->at[i] = at;
	v->flat[i] = (u8)flat;
	v->lo[i] = 0;
	v->hi[i] = 255;
	if (E) {
		int min = (int)be32((const u8 *)E + 0xa2 + 4 * s), cnt = (int)be32((const u8 *)E + 0xd2 + 4 * s);
		v->lo[i] = (u8)min;
		v->hi[i] = (u8)(min + cnt - 1);
		u32 en = s < 8 ? be32((const u8 *)E + 0x1c6) >> (4 * s) : be32((const u8 *)E + 0x1c2) >> (4 * (s - 8));
		if (cnt <= 0 || !(en & 1)) {
			v->key[i] = 0;
			v->flat[i] = SKIP;
		}
	}
	v->cur[i] = (DBPTR + (CUR_PART & 3) * PART_LEN)[at];
	v->name[i] = E ? (const u8 *)E + 0x4e + 6 * s : 0;
	v->def[i] = E ? ((const u8 *)E)[0x96 + s] : 0;
	v->fmt[i] = E ? be32((const u8 *)E + 0x102 + 4 * s) : 0;
}

/* View kind of track t: 0, or 1 with msg[] set when the view cannot hold a
 * template. An FX view needs its effect in brain_fx[] and a descriptor. */
static int ps_byte(u32 off);

static int view_fill(struct view *v, u32 kind, u32 t)
{
	v->kind = kind;
	v->t = t & 7;
	v->n = 0;
	t = v->t;
	if (kind == V_PROJECT) {		/* the stock PROJECT menu's bytes: key 1 + offset, at the offset */
		v->e = E_PROJECT;
		for (u32 off = 0; off < 0x70; off++)
			if (ps_byte(off)) {
				u32 i = v->n++;
				v->key[i] = (u16)(1 + off);
				v->at[i] = off;
				v->flat[i] = NOFLAT;
				v->lo[i] = 0;
				v->hi[i] = 255;
				v->cur[i] = *(volatile u8 *)(0x80000000u + off);
				v->def[i] = 0;
				v->fmt[i] = 0;
				v->name[i] = 0;
			}
		return 1;
	}
	if (kind == V_PART) {		/* the ids (keys 1..8 FX1, 9..16 FX2), then each track's FX1 and FX2 page values */
		v->e = E_PART;
		for (u32 i = 0; i < 16; i++) {
			u32 j = v->n++;
			v->key[j] = (u16)(1 + i);
			v->at[j] = 0x8ed80 + i;
			v->flat[j] = NOFLAT;
			v->lo[j] = 0;
			v->hi[j] = 255;
			v->cur[j] = (DBPTR + (CUR_PART & 3) * PART_LEN)[0x8ed80 + i];
			v->def[j] = 0;
			v->fmt[j] = 0;
			v->name[j] = 0;
		}
		for (u32 tr = 0; tr < 8; tr++)
			for (u32 fx = 0; fx < 2; fx++)
				for (u32 sl = 0; sl < 12; sl++) {
					u32 j = v->n++;
					v->key[j] = (u16)(17 + (tr * 2 + fx) * 12 + sl);
					v->at[j] = sl < 6 ? 0x8ee9a + tr * 24 + (fx ? 18 : 12) + sl
							  : (fx ? 0x8f084 : 0x8f07e) + tr * 30 + sl - 6;
					v->flat[j] = NOFLAT;
					v->lo[j] = 0;
					v->hi[j] = 255;
					v->cur[j] = (DBPTR + (CUR_PART & 3) * PART_LEN)[v->at[j]];
					v->def[j] = 0;
					v->fmt[j] = 0;
					v->name[j] = 0;
				}
		return 1;
	}
	if (kind <= V_FX2) {
		u8 *part = DBPTR + WORKING + (CUR_PART & 3) * PART_LEN;
		u32 id = part[kind ? 0x8 + t : t];
		v->e = MAX_FX;
		for (u32 i = 0; i < brain_fx_n && i < MAX_FX; i++)
			if (brain_fx[i].fx_id == id)
				v->e = i;
		if (v->e == MAX_FX) {
			msg[0] = "THIS EFFECT HAS";
			msg[1] = "NO TEMPLATES";
			return 0;
		}
		if (!snapped)
			snapshot();
		const u8 *d = desc[v->e][kind] ? desc[v->e][kind] : desc[v->e][kind ^ 1];
		if (!d)
			return 0;
		for (u32 s = 0; s < 12; s++) {
			u32 at = s < 6 ? 0x8ee9a + t * 24 + (kind ? 18 : 12) + s
				       : (kind ? 0x8f084 : 0x8f07e) + t * 30 + s - 6;
			slot(v, brain_fx[v->e].keys[s], at, s < 6 ? (kind ? 24 : 18) + s : NOFLAT,
			     (u32)d - 0x38, s);
		}
		return 1;
	}
	if (kind == V_SRC) {
		/* the machine byte, then its six page-1 and six page-2 bytes */
		u32 m = (DBPTR + (CUR_PART & 3) * PART_LEN)[0x8eda2 + t];
		if (m > 4)
			return 0;
		v->machine = m;
		v->e = ST_BASE + 3 + m;
		for (u32 s = 0; s < 12; s++)
			slot(v, 1 + s, (s < 6 ? 0x8edaa : 0x8ef5a - 6) + t * 30 + m * 6 + s, s < 6 ? s : NOFLAT,
			     D_PLAYBACK + m * 0x192, s);
		return 1;
	}
	v->e = ST_BASE + kind - V_AMP;
	if (kind == V_AMP)
		for (u32 s = 0; s < 12; s++)
			slot(v, 1 + s, s < 6 ? 0x8eea0 + t * 24 + s : 0x8f078 + t * 30 + s - 6,
			     s < 6 ? 12 + s : NOFLAT, D_AMP, s);
	else if (kind == V_LFO)
		for (u32 s = 0; s < 18; s++)
			slot(v, 1 + s, s < 6 ? 0x8ee9a + t * 24 + s
					     : s < 12 ? 0x8f072 + t * 30 + s - 6 : 0x8f08a + t * 30 + s - 12,
			     s < 6 ? 6 + s : NOFLAT, D_LFO, s < 6 ? s : 6 + (s - 6) / 3);
	else {
		for (u32 f = 0; f < 32; f++)	/* page 1: 30 values, CTRL1/CTRL2 enable bitmaps */
			slot(v, 64 + f, 0x8f162 + t * 32 + f, f < 30 ? f : NOFLAT,
			     f < 30 ? midi_desc[f / 6] : 0, f % 6);
		for (u32 o = 0; o < 36; o++)	/* LFO PMTR x3, WAVE x3 at 6-11; MULT x3, TRIG x3 at 30-35 */
			slot(v, 1 + o, 0x8f262 + t * 36 + o, NOFLAT, o < 30 ? midi_desc[o / 6] : D_MLFO,
			     o >= 30 ? 8 + (o - 30) / 3 : o / 6 == 1 ? 6 + (o - 6) / 3 : 6 + o % 6);
	}
	return 1;
}

/* The view in front of the page shortcut: 0, or 1 with msg[] set. */
static int view_here(struct view *v)
{
	u32 kind = PAGE_KIND;
	if (MIDI_MODE)
		return view_fill(v, V_MIDI, CUR_TRACK);
	if (kind <= 4)
		return view_fill(v, kind == 0 ? V_SRC : kind == 1 ? V_LFO : kind == 2 ? V_AMP : kind - 3, CUR_TRACK);
	msg[0] = "OPEN A TRACK PAGE";
	msg[1] = "";
	return 0;
}

/* The i-th template record of entry e among the records at recs[0..len),
 * or 0. */
static const u8 *nth_in(const u8 *recs, u32 len, u32 e, u32 i)
{
	const char *id;
	u32 id_len, layout;
	ent_id(e, &id, &id_len, &layout);
	for (u32 at = 0; at < len; at += be32(recs + at + 16)) {
		const u8 *p = recs + at;
		const u8 *pay = p + REC_HDR + align4(p[1]);
		if (!same_id(p + REC_HDR, p[1], id, id_len) || be32(p + 8) < 16 || be32(pay + 4) != layout)
			continue;
		if (p[0] != K_TEMPLATE)
			continue;
		if (i-- == 0)
			return p;
	}
	return 0;
}

/* The i-th card template of entry e. */
static const u8 *card_nth(u32 e, u32 i)
{
	return nth_in(tpl_cache, tpl_len, e, i);
}

/* ---- apply: each slot through the stock paths ----------------------------- */

#define P1WRITE  ((void (*)(u32, u32, u32))0x40054cd8)	/* page-1 writer (track, flat, value) */
#define LIVEB    0x80000810				/* live lane: track*72 */
#define LIVEM    0x46c76dc0				/* MIDI live copy: track*0x44 */
#define CS1      0x1001614e				/* CS1 mirror of the bank: + Part offset */
#define MIDI_INVAL ((void (*)(void))0x4009a3e0)		/* resend bank and program */
#define MIDI_PROG  ((void (*)(u32, u32))0x4009ec70)	/* (bank, part): send bank and program */
#define CUR_BANK (*(volatile u8 *)0x80000002)

/* View v takes vals[]: page-1 slots through the stock writer, the others as
 * the editors store them (Part, CS1 mirror, live copy, the four dirty
 * flags; MIDI_TRACKS.md section 5, modules/cc-map), each value clamped to
 * its descriptor's range. A MIDI track sends its bank and program after
 * its setup, then its page-1 values. */
/* The Part takes the template's ids and page values through the stock paste (0x40029a4c(src,
 * p): src to the working Part and its CS1 copy, the unsaved and edited flags, and, for the
 * current Part, the engine's apply). */
#define PART_PASTE ((void (*)(const u8 *, u32))0x40029a4c)
static u8 part_buf[PART_LEN];

/* ---- PART templates: the whole Part, applied by section and track ----------------------- */

/* A PART template record: the 16-byte prefix, then value 1, a Blob of the Part's 6,322 bytes
 * (the long length form: 0xff, a u32 length), then value 2, a Blob of the project folder name it
 * was taken in (a NUL-ended string). A PART default (K_DEFAULT, stock.part2) is the same with an
 * 8-byte prefix. Offsets below are Part-relative (the Part's first byte is 0; WORKING is where
 * the engine keeps the working Part of a bank). */
#define PRT_NAME_MAX 32

static const u8 *part_blob_at(const u8 *pay, u32 at, u32 plen)
{
	if (at + 8 + align4(PART_LEN) > plen || be16(pay + at) != 1 || pay[at + 2] != T_BLOB
	    || pay[at + 3] != 0xff || be32(pay + at + 4) != PART_LEN)
		return 0;
	return pay + at + 8;
}

/* the Part image of a PART template record, or 0 */
static const u8 *part_blob(const u8 *rec)
{
	return part_blob_at(rec + REC_HDR + align4(rec[1]), 16, be32(rec + 8));
}

/* the project folder name a PART template was taken in, or 0 */
static const u8 *part_origin(const u8 *rec)
{
	const u8 *pay = rec + REC_HDR + align4(rec[1]);
	u32 plen = be32(rec + 8), at = 16 + 8 + align4(PART_LEN);
	if (!part_blob(rec) || at + 4 > plen || be16(pay + at) != 2 || pay[at + 2] != T_BLOB || pay[at + 3] == 0xff)
		return 0;
	return pay + at + 4;
}

/* A section is its pieces: track t's bytes at off + t * stride, len long, rep times rstride apart. */
struct piece { u16 off, len, rstride; u8 stride, rep; };
static const struct piece pc_fx[]   = { { 0x000, 1, 0, 1, 1 }, { 0x008, 1, 0, 1, 1 },	/* the FX1 and FX2 ids */
					{ 0x126, 12, 0, 24, 1 }, { 0x2fe, 12, 0, 30, 1 } };	/* FX1+FX2 page 1 and 2 */
static const struct piece pc_lfo[]  = { { 0x11a, 6, 0, 24, 1 }, { 0x2f2, 6, 0, 30, 1 }, { 0x30a, 6, 0, 30, 1 } };
/* the SRC pages of the machines that read no sample: the THRU, NEIGHBOR and PICKUP pages (types 2-4 of
 * the five a track keeps, 6 bytes each) */
static const struct piece pc_src[]  = { { 0x02a + 12, 18, 0, 30, 1 }, { 0x1da + 12, 18, 0, 30, 1 } };
static const struct piece pc_midi[] = { { 0x3e2, 32, 0, 32, 1 }, { 0x4e2, 36, 0, 36, 1 } };	/* a MIDI track's two pages */
static const struct piece pc_scn[]  = { { 0x662, 32, 256, 32, 16 } };				/* a track's lock in each of 16 scenes */
static const struct piece pc_mach[] = { { 0x022, 1, 0, 1, 1 } };
/* what a section carries beyond its tracks, when it is taken for all tracks */
static const struct piece px_scn[]  = { { 0x010, 2, 0, 0, 1 } };				/* scene A and scene B */
static const struct piece px_lfo[]  = { { 0x1702, 304, 0, 0, 1 } };				/* the LFO designer shapes, audio and MIDI */

struct sec { const struct piece *pc, *ex; u8 n, nex; };
#define SECP(a, x, b) { a, x, sizeof a / sizeof *a, b }
enum { SEC_FX, SEC_LFO, SEC_SRC, SEC_MIDI, SEC_SCN, SEC_MACH, SEC_N };
static const struct sec sec[SEC_N] = {
	SECP(pc_fx, 0, 0), SECP(pc_lfo, px_lfo, 1), SECP(pc_src, 0, 0), SECP(pc_midi, 0, 0), SECP(pc_scn, px_scn, 1),
	SECP(pc_mach, 0, 0),
};
/* what a PART template takes and applies is what means the same in any project: no sample slots,
 * no AMP page and no Flex or Static SRC page (they are shaped around a sample), no levels */
#define SEC_ALL     ((1u << SEC_N) - 1)
#define SEC_DEFAULT SEC_ALL

static void copy_piece(u8 *dst, const u8 *src, const struct piece *p, u32 ts, u32 td)
{
	for (u32 r = 0; r < p->rep; r++)
		for (u32 k = 0; k < p->len; k++)
			dst[p->off + r * p->rstride + td * p->stride + k] = src[p->off + r * p->rstride + ts * p->stride + k];
}

/* sections in mask from blob into the Part image dst: every track onto itself (from < 0, with each
 * section's extras), or track from onto track onto */
static void part_merge(u8 *dst, const u8 *blob, u32 mask, int from, int onto)
{
	for (u32 s = 0; s < SEC_N; s++) {
		if (!(mask >> s & 1))
			continue;
		for (u32 k = 0; k < sec[s].n; k++) {
			if (from < 0)
				for (u32 t = 0; t < 8; t++)
					copy_piece(dst, blob, &sec[s].pc[k], t, t);
			else
				copy_piece(dst, blob, &sec[s].pc[k], (u32)from & 7, (u32)onto & 7);
		}
		for (u32 k = 0; from < 0 && k < sec[s].nex; k++)
			copy_piece(dst, blob, &sec[s].ex[k], 0, 0);
	}
}

/* The current Part takes sections of blob. The stock Part paste writes the working Part and its
 * CS1 copy, marks it unsaved and applies it to the engine; a machine change goes on through the
 * calls Part Reload makes (PARTS.md section 2): the engine's apply of the Part, then the machine
 * transition of each track with the machine it had. */
#define PART_APPLY ((void (*)(u32, u32))0x40009848)
#define MACH_TRANS ((void (*)(u32, u32, u32))0x400972fc)
static void part_apply(const u8 *blob, u32 mask, int from, int onto)
{
	u32 part = CUR_PART & 3;
	const u8 *src = DBPTR + WORKING + part * PART_LEN;
	u8 old[8];
	for (u32 i = 0; i < PART_LEN; i++)
		part_buf[i] = src[i];
	for (u32 t = 0; t < 8; t++)
		old[t] = src[0x22 + t];
	part_merge(part_buf, blob, mask, from, onto);
	PART_PASTE(part_buf, part);
	if (mask >> SEC_MACH & 1) {
		PART_APPLY(*(volatile u8 *)0x80000002, part);
		for (u32 t = 0; t < 8; t++)
			MACH_TRANS(part, t, (u32)(int)(signed char)old[t]);
	}
}

static void apply_view(const struct view *v, const u8 *vals)
{
	u32 part = CUR_PART & 3, t = v->t, chan = 0;
	if (v->kind == V_PROJECT) {		/* as a new project's settings land (brain_new_project) */
		for (u32 i = 0; i < v->n; i++) {
			*(volatile u8 *)(0x80000000u + v->at[i]) = vals[i];
			*(volatile u8 *)(0x100b1460u + v->at[i]) = vals[i];
		}
		*(volatile u32 *)0x100f8598 = 1;
		return;
	}
	u8 *pb = DBPTR + part * PART_LEN;
	u8 c[NSLOT];
	for (u32 i = 0; i < v->n; i++) {
		u32 x = vals[i];
		c[i] = (u8)(x < v->lo[i] ? v->lo[i] : x > v->hi[i] ? v->hi[i] : x);
		if (v->flat[i] != NOFLAT)
			continue;
		u32 at = v->at[i];
		if (at == 0x8f262 + t * 36 && pb[at] != c[i])
			chan = 1;
		pb[at] = c[i];
		*(volatile u8 *)(CS1 + at + part * PART_LEN) = c[i];
		if (v->kind == V_MIDI)
			*(volatile u8 *)(LIVEM + t * 0x44 + (at - 0x8f162 - t * 32 < 32 ? at - 0x8f162 - t * 32
							  : 0x20 + at - 0x8f262 - t * 36)) = c[i];
		else
			*(volatile u8 *)(LIVEB + t * 72 + (v->kind == V_SRC ? 0x20 + at - 0x8ef5a - t * 30 - v->machine * 6
								       : 0x26 + at - 0x8f072 - t * 30)) = c[i];
	}
	DBPTR[0x95048] |= (u8)(1 << part);
	*(volatile u8 *)0x100b145e |= (u8)(1 << part);
	*(volatile u32 *)(DBPTR + 0x9b332) = 1;
	*(volatile u32 *)0x100f8598 = 1;
	if (v->kind == V_MIDI) {
		if (chan)
			MIDI_INVAL();
		MIDI_PROG(CUR_BANK, part);
	}
	for (u32 i = 0; i < v->n; i++)
		if (v->flat[i] < SKIP)
			P1WRITE(v->kind == V_MIDI ? 8 + t : t, v->flat[i], c[i]);
}

/* The values of template record p for view v: its bytes by key; a slot it
 * has no value for keeps the current byte. */
static void tpl_values(const u8 *p, const struct view *v, u8 *vals)
{
	for (u32 i = 0; i < v->n; i++)
		vals[i] = v->cur[i];
	const u8 *pay = p + REC_HDR + align4(p[1]);
	u32 plen = be32(p + 8);
	for (u32 at = 16; at + 4 <= plen && pay[at + 3] != 0xff; at += 4 + align4(pay[at + 3])) {
		u32 key = be16(pay + at);
		if (pay[at + 2] != T_BYTE || pay[at + 3] != 1 || !key)
			continue;
		for (u32 i = 0; i < v->n; i++)
			if (v->key[i] == key)
				vals[i] = pay[at + 4];
	}
}

/* ---- the engine task: a template saved, deleted, renamed or copied ------- */

/* op T_SAVE: track t's view kind becomes a new template of its target,
 * named tpl_newname (a template of that name on the target is replaced). T_DELETE: the i-th card template
 * of entry e leaves card.work. T_RENAME: it takes the name in tpl_newname.
 * keeps its bytes. The copy is read back after the write. 0, or an error
 * code as write_default's. */
static int view_meta(struct view *v, u32 e);
static struct view job_view;
static struct view ted_view;			/* the edit screen's template: its slots and values */
static u8 ted_vals[NSLOT];
static u8 ted_part[PART_LEN];			/* a PART template's Part image, as it is being edited */
static char tpl_newname[TPL_NAME + 1];

static int same_name(const u8 *rec, const u8 *nm)
{
	const u8 *a = rec + REC_HDR + align4(rec[1]) + 8;
	for (u32 k = 0; k < TPL_NAME; k++)
		if (a[k] != nm[k])
			return 0;
	return 1;
}

static int write_template(int del, u32 t, u32 kind, u32 e, u32 i)
{
	int n = current_store();
	if (n < 0)
		return 2;
	struct view *v = &job_view;
	if (del == T_SAVE) {
		if (kind > V_PROJECT || t > 7 || !view_fill(v, kind, t))
			return 1;
		e = v->e;
	}
	if (del == T_NEW) {			/* a template of target e with the descriptor's defaults */
		if (!view_meta(v, e))
			return 1;
		for (u32 q = 0; q < v->n; q++)
			v->cur[q] = v->def[q];
		del = T_SAVE;
		kind = V_AMP;			/* no knob names */
	}
	const char *id;
	u32 id_len, layout;
	ent_id(e, &id, &id_len, &layout);
	const u8 *drop = ((del == T_DELETE || del == T_RENAME || del == T_EDIT) && n) ? nth_in(buf + HDR, (u32)n - HDR, e, i) : 0;
	if ((del == T_DELETE || del == T_RENAME || del == T_EDIT) && !drop)
		return 1;
	/* a save under a name the target already has replaces that template */
	for (u32 j = 0; del == T_SAVE && n && j < TPL_MAX; j++) {
		const u8 *q = nth_in(buf + HDR, (u32)n - HDR, e, j);
		if (!q)
			break;
		if (same_name(q, (const u8 *)tpl_newname)) {
			drop = q;
			break;
		}
	}
	u32 at = HDR, kept = 0;
	for (u32 r = 0, k = HDR; n && r < be16(buf + 10); r++, k += be32(buf + k + 16)) {
		const u8 *p = buf + k;
		u32 size = be32(p + 16);
		if (p == drop && (del == T_DELETE || del == T_SAVE))
			continue;
		if (at + size > BUF_LEN)
			return 3;
		for (u32 b = 0; b < size; b++)
			out[at + b] = p[b];
		if (p == drop && del == T_EDIT) {	/* the edit screen's values, then the payload CRC */
			u8 *pay = out + at + REC_HDR + align4(p[1]);
			u32 plen = be32(p + 8);
			for (u32 a = 16; a + 4 <= plen && pay[a + 3] != 0xff; a += 4 + align4(pay[a + 3]))
				if (pay[a + 2] == T_BYTE && pay[a + 3] == 1)
					for (u32 q = 0; q < ted_view.n; q++)
						if (ted_view.key[q] == be16(pay + a))
							pay[a + 4] = ted_vals[q];
			if (e == E_PART && part_blob(out + at))
				for (u32 q = 0; q < PART_LEN; q++)
					pay[24 + q] = ted_part[q];
			put32(out + at + 12, crc32(pay, plen));
		}
		if (p == drop && del == T_RENAME) {	/* the name, then the payload CRC */
			u8 *pay = out + at + REC_HDR + align4(p[1]);
			for (u32 c = 0; c < TPL_NAME; c++)
				pay[8 + c] = (u8)tpl_newname[c];
			put32(out + at + 12, crc32(pay, be32(p + 8)));
		}
		at += size;
		kept++;
	}
	if (del == T_SAVE && kind == V_PART) {		/* the whole working Part, and the project it is from */
		const u8 *wp = DBPTR + WORKING + (CUR_PART & 3) * PART_LEN;
		u32 nlen = 0;
		while (nlen < PRT_NAME_MAX - 1 && PROJ_NAME[nlen])
			nlen++;
		nlen++;
		u32 plen = 16 + 8 + align4(PART_LEN) + 4 + align4(nlen), size = REC_HDR + align4(id_len) + plen;
		if (at + size > BUF_LEN)
			return 3;
		u8 *r = out + at;
		for (u32 b = 0; b < size; b++)
			r[b] = 0;
		r[0] = K_TEMPLATE;
		r[1] = (u8)id_len;
		put16(r + 2, 1);
		put32(r + 8, plen);
		put32(r + 16, size);
		for (u32 b = 0; b < id_len; b++)
			r[REC_HDR + b] = (u8)id[b];
		u8 *pay = r + REC_HDR + align4(id_len);
		put16(pay + 2, NO_MODE);
		put32(pay + 4, layout);
		for (u32 c = 0; c < TPL_NAME; c++)
			pay[8 + c] = (u8)tpl_newname[c];
		u8 *w = pay + 16;
		put16(w, 1);
		w[2] = T_BLOB;
		w[3] = 0xff;
		put32(w + 4, PART_LEN);
		for (u32 b = 0; b < PART_LEN; b++)
			w[8 + b] = wp[b];
		w += 8 + align4(PART_LEN);
		put16(w, 2);
		w[2] = T_BLOB;
		w[3] = (u8)nlen;
		for (u32 b = 0; b + 1 < nlen; b++)
			w[4 + b] = (u8)PROJ_NAME[b];
		put32(r + 12, crc32(pay, plen));
		at += size;
		kept++;
	} else if (del == T_SAVE) {
		u32 nvals = 0, nnames = 0;
		for (u32 s = 0; s < v->n; s++)
			nvals += v->key[s] != 0;
		/* a MIDI track carries its knob names: Name values keyed 129 + cc */
		const char (*kn)[KN_LEN] = knames[kn_part()][t & 7];
		for (u32 c = 0; kind == V_MIDI && c < 10; c++)
			nnames += kn[c][0] != 0;
		u32 plen = 16 + 8 * nvals + 12 * nnames, size = REC_HDR + align4(id_len) + plen;
		if (at + size > BUF_LEN)
			return 3;
		u8 *r = out + at;
		for (u32 b = 0; b < size; b++)
			r[b] = 0;
		r[0] = K_TEMPLATE;
		r[1] = (u8)id_len;
		put16(r + 2, 1);			/* schema major 1, minor 0 */
		put32(r + 8, plen);
		put32(r + 16, size);
		for (u32 b = 0; b < id_len; b++)
			r[REC_HDR + b] = (u8)id[b];
		u8 *pay = r + REC_HDR + align4(id_len);
		put16(pay + 2, NO_MODE);		/* target 0, no mode */
		put32(pay + 4, layout);
		for (u32 c = 0; c < TPL_NAME; c++)
			pay[8 + c] = (u8)tpl_newname[c];
		u8 *w = pay + 16;
		for (u32 s = 0; s < v->n; s++)
			if (v->key[s]) {
				put16(w, v->key[s]);
				w[2] = T_BYTE;
				w[3] = 1;
				w[4] = v->cur[s];
				w += 8;
			}
		for (u32 c = 0; nnames && c < 10; c++)
			if (kn[c][0]) {
				put16(w, 129 + c);
				w[2] = T_NAME;
				w[3] = KN_LEN;
				for (u32 k = 0; k < KN_LEN; k++)
					w[4 + k] = (u8)kn[c][k];
				w += 12;
			}
		put32(r + 12, crc32(pay, plen));
		at += size;
		kept++;
	}
	if (write_card(at, kept) < 0)
		return 4;
	n = current_store();
	cache_templates(n > 0);
	return 0;
}

void brain_post_template(u32 args)
{
	job_args = args;
	((u8 *)job_msg)[0] = JOB_SAVE;
	Q_SEND(ENGINE_Q, job_msg);
}

/* ---- the page shortcut and the template lists ---------------------------- */

/* Hold a page key (SRC, AMP, LFO, FX1, FX2) and press FUNC: the record
 * manifest.py adds to the page-held key layer (0x400bab6e's keys) calls
 * brain_page_func, which opens the stock list popup (0x4006d94c(count,
 * sel, &sel_out, labels, handlers); YES stores the row in sel_out, closes
 * it and calls that row's handler, no argument). */
#define LISTPOP ((void (*)(u32, u32, u32 *, const char *const *, void *))0x4006d94c)

void brain_tpl_save(u32 unused);
void brain_tpl_load(u32 unused);
void brain_tpl_delete(u32 unused);

static u32 pop_sel;
void brain_kn_list(u32 unused);
static const char *const page_lbl[6] = { "SAVE FX DEFAULT", "CLEAR FX DEFAULT", "SAVE TEMPLATE",
					 "LOAD TEMPLATE", "DELETE TEMPLATE", "NAME KNOB" };
static void (*const page_fn[6])(u32) = { brain_menu_save, brain_menu_clear, brain_tpl_save,
					 brain_tpl_load, brain_tpl_delete, brain_kn_list };

/* NAME KNOB: on a MIDI track only */
void brain_page_func(void)
{
	pop_sel = 0;
	LISTPOP(MIDI_MODE ? 6 : 5, 0, &pop_sel, page_lbl, (void *)page_fn);
}

static char tpl_lbl[TPL_MAX][TPL_NAME + 1];
static const char *tpl_lp[TPL_MAX];
static void (*tpl_fp[TPL_MAX])(u32);
static u32 tpl_sel;
static struct view tpl_view;		/* the view the lists were opened over */

/* The names of the templates of the view in front (the image's and the
 * card's, or the card's alone), each row calling fn; their count (0: msg[]
 * says why, the popup shown). */
static u32 tpl_list(const char *title, void (*fn)(u32), int card)
{
	if (!view_here(&tpl_view)) {
		POPUP(title, 2, msg, 0, 0);
		return 0;
	}
	u32 n = 0;
	for (; n < TPL_MAX; n++) {
		const u8 *p = card_nth(tpl_view.e, n);
		if (!p)
			break;
		const u8 *nm = p + REC_HDR + align4(p[1]) + 8;
		for (u32 k = 0; k < TPL_NAME; k++)
			tpl_lbl[n][k] = (char)nm[k];
		tpl_lbl[n][TPL_NAME] = 0;
		tpl_lp[n] = tpl_lbl[n];
		tpl_fp[n] = fn;
	}
	if (!n) {
		msg[0] = "NO TEMPLATES";
		msg[1] = "FOR THIS PAGE";
		POPUP(title, 2, msg, 0, 0);
	}
	return n;
}

static void tpl_apply_sel(u32 unused)
{
	(void)unused;
	const u8 *p = card_nth(tpl_view.e, tpl_sel);
	if (!p)
		return;
	u8 vals[NSLOT];
	tpl_values(p, &tpl_view, vals);
	apply_view(&tpl_view, vals);
	if (tpl_view.kind == V_MIDI && kn_take(p, tpl_view.t))
		brain_post_template(0x800000);
}

static void tpl_delete_sel(u32 unused)
{
	(void)unused;
	brain_post_template(0x100000 | (tpl_view.e << 8) | (tpl_sel & 0xff));
	msg[0] = tpl_lbl[tpl_sel < TPL_MAX ? tpl_sel : 0];
	msg[1] = "DELETED";
	POPUP("DELETE TEMPLATE", 2, msg, 0, 0);
}

void brain_tpl_load(u32 unused)
{
	(void)unused;
	u32 n = tpl_list("LOAD TEMPLATE", tpl_apply_sel, 0);
	if (n) {
		tpl_sel = 0;
		LISTPOP(n, 0, &tpl_sel, tpl_lp, (void *)tpl_fp);
	}
}

void brain_tpl_delete(u32 unused)
{
	(void)unused;
	u32 n = tpl_list("DELETE TEMPLATE", tpl_delete_sel, 1);
	if (n) {
		tpl_sel = 0;
		LISTPOP(n, 0, &tpl_sel, tpl_lp, (void *)tpl_fp);
	}
}

#define NAMEED   ((void (*)(u32, const char *, char *, u32, void (*)(u32)))0x4007e664)

static char tname[16];
static u32 save_kind, save_t;		/* the view the name editor was opened over */

/* "TPL nn" with the lowest nn no card template of entry e carries, into
 * tname */
static int str_lt(const char *a, const char *b);

/* a new template's name: the target's abbreviation and the lowest free number, "CHAR 01", "AMP 01",
 * "FLEX 01" (an effect's abbreviation is its descriptor's, P + 4) */
static u32 tpl_prefix(u32 e, char *o)
{
	static const char *const st_abbr[ST_N] = { "AMP", "LFO", "MIDI", "STAT", "FLEX", "THRU", "NBR", "PICK",
						   "PROJ", "PART" };
	const char *a = "TPL";
	if (e >= ST_BASE)
		a = st_abbr[e - ST_BASE];
	else if (e < brain_fx_n && (desc[e][0] || desc[e][1]))
		a = (const char *)(desc[e][0] ? desc[e][0] : desc[e][1]) + 4;
	u32 n = 0;
	for (; n < 4 && a[n] && a[n] != ' '; n++)
		o[n] = a[n] >= 'a' && a[n] <= 'z' ? (char)(a[n] - 32) : a[n];
	if (!n)
		n = put_s(o, "TPL");
	return n;
}

static void default_name(u32 e)
{
	char pre[5];
	u32 pn = tpl_prefix(e, pre), num = 1;
	for (int again = 1; again && num < 100;) {
		again = 0;
		for (u32 j = 0; j < TPL_MAX; j++) {
			const u8 *q = card_nth(e, j);
			if (!q)
				break;
			const u8 *nm = q + REC_HDR + align4(q[1]) + 8;
			u32 k = 0;
			while (k < pn && nm[k] == (u8)pre[k])
				k++;
			if (k == pn && nm[pn] == ' ' && (u32)((nm[pn + 1] - '0') * 10 + (nm[pn + 2] - '0')) == num) {
				num++;
				again = 1;
			}
		}
	}
	for (u32 k = 0; k < sizeof tname; k++)
		tname[k] = 0;
	for (u32 k = 0; k < pn; k++)
		tname[k] = pre[k];
	tname[pn] = ' ';
	tname[pn + 1] = (char)('0' + num / 10);
	tname[pn + 2] = (char)('0' + num % 10);
}

/* the name editor's answer: the engine task saves the page under the name */
static void tpl_named(u32 confirmed)
{
	if (!confirmed)
		return;
	for (u32 k = 0; k <= TPL_NAME; k++)
		tpl_newname[k] = 0;
	for (u32 k = 0; k < TPL_NAME && tname[k]; k++)
		tpl_newname[k] = tname[k];
	if (!tpl_newname[0])
		return;
	brain_post_template(0x80000 | save_t | (save_kind << 8));
	static const char *const kname[8] = { "FX1 TRACK ", "FX2 TRACK ", "AMP TRACK ", "LFO TRACK ",
					      "MIDI TRACK ", "SRC TRACK ", "PART", "PROJECT" };
	int k = 0;
	for (const char *c = kname[save_kind]; *c; c++)
		line1[k++] = *c;
	if (save_kind < V_PART)
		line1[k++] = (char)('1' + save_t);
	line1[k] = 0;
	msg[0] = line1;
	msg[1] = "TEMPLATE SAVED";
	POPUP("SAVE TEMPLATE", 2, msg, 0, 0);
	sc_rebuild();
}

/* SAVE PROJECT and SAVE PART FX: the stock PROJECT menu's bytes, or the FX1 and FX2 of the
 * eight tracks, as a template */
static void tpl_save_kind(u32 kind)
{
	save_t = 0;
	save_kind = kind;
	default_name(kind == V_PROJECT ? E_PROJECT : E_PART);
	NAMEED(TPL_NAME, "TEMPLATE NAME", tname, 1, tpl_named);
}
static void tpl_save_project(u32 unused) { (void)unused; tpl_save_kind(V_PROJECT); }
static void tpl_save_part(u32 unused) { (void)unused; tpl_save_kind(V_PART); }

/* NEW (the rows on TEMPLATES' tabs): the name editor opens on the next free name (CHAR 01); on
 * confirm the template is written and its edit screen opens when it is on the card, polled by a
 * soft timer. A name the target's templates already have is refused (a save under it would
 * replace that template). */
static u32 new_e, new_tries, new_job;
static int new_timer DATA = -1;
static void new_poll(void);
static void new_named(u32 confirmed)
{
	if (!confirmed)
		return;
	for (u32 k = 0; k <= TPL_NAME; k++)
		tpl_newname[k] = 0;
	for (u32 k = 0; k < TPL_NAME && tname[k]; k++)
		tpl_newname[k] = tname[k];
	if (!tpl_newname[0])
		return;
	for (u32 j = 0; j < TPL_MAX; j++) {
		const u8 *q = card_nth(new_e, j);
		if (!q)
			break;
		if (same_name(q, (const u8 *)tpl_newname)) {
			msg[0] = tname;
			msg[1] = "NAME IN USE";
			POPUP("NEW TEMPLATE", 2, msg, 0, 0);
			return;
		}
	}
	brain_post_template(new_job);
	new_tries = 0;
	if (new_timer < 0)
		new_timer = TIMER(15, new_poll);
}

/* job: the engine job that writes it (a save of view kind, or T_NEW of entry e) */
static void new_ask(u32 e, u32 job)
{
	new_e = e;
	new_job = job;
	default_name(e);
	NAMEED(TPL_NAME, "TEMPLATE NAME", tname, 1, new_named);
}
static void new_template(u32 kind, u32 t, u32 e) { new_ask(e, 0x80000 | t | (kind << 8)); }
static void tpl_new_project(u32 unused) { (void)unused; new_template(V_PROJECT, 0, E_PROJECT); }
static void tpl_new_part(u32 unused) { (void)unused; new_template(V_PART, 0, E_PART); }

/* a template of target e with the page descriptor's default values (no page need be open) */
static void new_default(u32 e) { new_ask(e, 0x10000000 | (e << 8)); }

static void tpl_new_midi(u32 unused) { (void)unused; new_default(ST_BASE + 2); }

/* NEW EFFECT and NEW SRC ask which: a list of the image's effects, alphabetical, or the five machine types */
static const char *pick_l[MAX_FX];
static u8 pick_e[MAX_FX];
static void (*pick_f[MAX_FX])(u32);
static u32 pick_sel;
static void pick_fx_cb(u32 unused)
{
	(void)unused;
	new_default(pick_e[pick_sel]);
}

static void tpl_new_fx(u32 unused)
{
	(void)unused;
	u32 n = 0;
	for (u32 e = 0; e < brain_fx_n && e < MAX_FX; e++) {
		if (!desc[e][0] && !desc[e][1])
			continue;
		u32 at = n++;
		while (at && str_lt(brain_fx[e].name, pick_l[at - 1])) {
			pick_l[at] = pick_l[at - 1];
			pick_e[at] = pick_e[at - 1];
			at--;
		}
		pick_l[at] = brain_fx[e].name;
		pick_e[at] = (u8)e;
	}
	for (u32 i = 0; i < n; i++)
		pick_f[i] = pick_fx_cb;
	pick_sel = 0;
	if (n)
		LISTPOP(n, 0, &pick_sel, pick_l, (void *)pick_f);
}


void brain_tpl_save(u32 unused)
{
	(void)unused;
	if (!view_here(&tpl_view)) {
		POPUP("SAVE TEMPLATE", 2, msg, 0, 0);
		return;
	}
	save_t = tpl_view.t;
	save_kind = tpl_view.kind;
	default_name(tpl_view.e);
	NAMEED(TPL_NAME, "TEMPLATE NAME", tname, 1, tpl_named);
}

/* ---- the TEMPLATES screen's actions ----------------------------------------- */

/* Rows: SAVE TEMPLATE (the page in view, asking for a name), then a section
 * per target with card templates (the effect's name or the stock page's),
 * sections and names alphabetical. YES on a template opens the stock list
 * popup: LOAD (onto the page in view, when it is that target's), RENAME (the
 * name editor) and DELETE. Each posts an engine job and rebuilds the rows. */

static u32 trow_ref_sel;			/* e << 8 | i of the template the popup is about */

static const char *const st_name[ST_N] = { "AMP", "LFO", "MIDI TRACK", "SRC STATIC", "SRC FLEX",
					   "SRC THRU", "SRC NEIGHBOR", "SRC PICKUP", "PROJECT", "PART" };

static const char *ent_name(u32 e)
{
	return e >= ST_BASE ? st_name[e - ST_BASE] : brain_fx[e].name;
}

static int str_lt(const char *a, const char *b)
{
	while (*a && *a == *b)
		a++, b++;
	return (u8)*a < (u8)*b;
}

static const u8 *tname_of(const u8 *rec)
{
	return rec + REC_HDR + align4(rec[1]) + 8;
}

static int name_lt(const u8 *a, const u8 *b)
{
	for (u32 k = 0; k < TPL_NAME; k++) {
		if (a[k] != b[k])
			return a[k] < b[k];
		if (!a[k])
			break;
	}
	return 0;
}

static void trow_name(char *o, const u8 *rec)
{
	const u8 *nm = tname_of(rec);
	u32 k = 0;
	for (; k < TPL_NAME && nm[k]; k++)
		o[k] = (char)nm[k];
	o[k] = 0;
}

static void tpl_job(u32 args, const char *done)
{
	brain_post_template(args);
	msg[0] = tname;
	msg[1] = done;
	POPUP("TEMPLATES", 2, msg, 0, 0);
	sc_rebuild();
}

static void tpl_renamed(u32 confirmed)
{
	if (!confirmed)
		return;
	for (u32 k = 0; k <= TPL_NAME; k++)
		tpl_newname[k] = 0;
	for (u32 k = 0; k < TPL_NAME && tname[k]; k++)
		tpl_newname[k] = tname[k];
	if (!tpl_newname[0])
		return;
	tpl_job(0x200000 | trow_ref_sel, "RENAMED");
}

static void trow_rename(u32 unused)
{
	(void)unused;
	NAMEED(TPL_NAME, "TEMPLATE NAME", tname, 1, tpl_renamed);
}

static void trow_delete(u32 unused)
{
	(void)unused;
	tpl_job(0x100000 | trow_ref_sel, "DELETED");
}

/* the template's values onto the view in tpl_view (filled for the target) */
static void load_onto(const u8 *p)
{
	u8 vals[NSLOT];
	tpl_values(p, &tpl_view, vals);
	apply_view(&tpl_view, vals);
	if (tpl_view.kind == V_MIDI && kn_take(p, tpl_view.t))
		brain_post_template(0x800000);
	trow_name(tname, p);
	msg[0] = tname;
	msg[1] = "APPLIED";
	POPUP("APPLY TEMPLATE", 2, msg, 0, 0);
}

/* LOAD asks onto which track: an effect onto any FX1 or FX2 slot whose chooser lists it (another effect
 * there is replaced), SRC onto the tracks with its machine type, AMP, LFO and MIDI onto any track */
#define LD_MAX 16
static const char *ld_l[LD_MAX];
static char ld_lab[LD_MAX][12];
static u8 ld_kind[LD_MAX], ld_t[LD_MAX];
static void (*ld_f[LD_MAX])(u32);
static u32 ld_n, ld_ref, ld_sel;

/* LOAD of an effect template onto a slot that has another effect: the Part with that slot's id and
 * its twelve page values through the stock Part paste (as PART FX's LOAD) */
static struct view swap_view;
static void load_fx_swap(u32 t, u32 fx, u32 e, const u8 *p)
{
	if (!view_meta(&swap_view, e))
		return;
	for (u32 i = 0; i < swap_view.n; i++)
		swap_view.cur[i] = swap_view.def[i];
	u8 vals[NSLOT];
	tpl_values(p, &swap_view, vals);
	u32 part = CUR_PART & 3;
	const u8 *src = DBPTR + WORKING + part * PART_LEN;
	for (u32 i = 0; i < PART_LEN; i++)
		part_buf[i] = src[i];
	part_buf[(fx ? 8 : 0) + t] = brain_fx[e].fx_id;
	for (u32 s = 0; s < 12 && s < swap_view.n; s++) {
		u32 at = s < 6 ? 0x8ee9a + t * 24 + (fx ? 18 : 12) + s : (fx ? 0x8f084 : 0x8f07e) + t * 30 + s - 6;
		u32 v = vals[s];
		part_buf[at - WORKING] = (u8)(v < swap_view.lo[s] ? swap_view.lo[s] : v > swap_view.hi[s] ? swap_view.hi[s] : v);
	}
	PART_PASTE(part_buf, part);
	trow_name(tname, p);
	msg[0] = tname;
	msg[1] = "APPLIED";
	POPUP("APPLY TEMPLATE", 2, msg, 0, 0);
}

static void load_pick(u32 unused)
{
	(void)unused;
	if (ld_sel >= ld_n)
		return;
	u32 e = ld_ref >> 8, kind = ld_kind[ld_sel], t = ld_t[ld_sel];
	const u8 *p = card_nth(e, ld_ref & 0xff);
	if (!p)
		return;
	if (kind <= V_FX2 && (DBPTR + (CUR_PART & 3) * PART_LEN)[0x8ed80 + (kind ? 8 : 0) + t] != brain_fx[e].fx_id) {
		load_fx_swap(t, kind, e, p);
		return;
	}
	if (view_fill(&tpl_view, kind, t))
		load_onto(p);
}

static void ld_add(u32 kind, u32 t)
{
	static const char *const nm[] = { "FX1", "FX2" };
	if (ld_n >= LD_MAX)
		return;
	char *o = ld_lab[ld_n];
	u32 k = put_s(o, "T");
	k += put_dec(o + k, t + 1, 0);
	if (kind <= V_FX2) {
		o[k++] = ' ';
		k += put_s(o + k, nm[kind]);
	}
	o[k] = 0;
	ld_l[ld_n] = o;
	ld_f[ld_n] = load_pick;
	ld_kind[ld_n] = (u8)kind;
	ld_t[ld_n++] = (u8)t;
}

/* APPLY TO... on a PART template: which section (WHOLE PART or one), then, for a section, which
 * track of the template (ALL TRACKS, or one) and, for one, onto which track of the current Part */
#define AP_ROWS (SEC_N + 1)
static const char *const ap_secl[AP_ROWS] = { "WHOLE PART", "FX", "LFO", "INPUT SRC", "MIDI TRACKS", "SCENES",
					      "MACHINES" };
static const char *ap_l[9];
static char ap_lab[9][18];
static void (*ap_f[9])(u32);
static u32 ap_sel, ap_ref, ap_sec;		/* the list's row; the template (e << 8 | i); 0 whole, else section + 1 */
static int ap_from;

/* the effect ids of the tracks taken all exist in this image (0 is NONE) */
static int ap_ids_ok(const u8 *blob, int from)
{
	for (u32 i = 0; i < 16; i++) {
		if (from >= 0 && (i & 7) != (u32)from)
			continue;
		if (blob[i] && !find((const u8 *const *)(i < 8 ? FX1_IDS : FX2_IDS), blob[i]))
			return 0;
	}
	return 1;
}

static void ap_run(int from, int onto)
{
	const u8 *rec = card_nth(ap_ref >> 8, ap_ref & 0xff);
	const u8 *blob = rec ? part_blob(rec) : 0;
	if (!blob)
		return;
	u32 mask = ap_sec ? 1u << (ap_sec - 1) : SEC_ALL;
	trow_name(tname, rec);
	msg[0] = tname;
	if ((mask >> SEC_FX & 1) && !ap_ids_ok(blob, from)) {
		msg[1] = "EFFECT NOT IN IMAGE";
		POPUP("APPLY TEMPLATE", 2, msg, 0, 0);
		return;
	}
	part_apply(blob, mask, from, onto);
	msg[1] = "APPLIED";
	POPUP("APPLY TEMPLATE", 2, msg, 0, 0);
}

static void ap_onto_pick(u32 unused)
{
	(void)unused;
	ap_run(ap_from, (int)ap_sel);
}

static void ap_from_pick(u32 unused)
{
	(void)unused;
	if (ap_sel == 0) {
		ap_run(-1, -1);
		return;
	}
	ap_from = (int)ap_sel - 1;
	for (u32 t = 0; t < 8; t++) {
		u32 k = put_s(ap_lab[t], "ONTO ");
		ap_lab[t][k++] = ap_sec == SEC_MIDI + 1 ? 'M' : 'T';
		ap_lab[t][k++] = (char)('1' + t);
		ap_lab[t][k] = 0;
		ap_l[t] = ap_lab[t];
		ap_f[t] = ap_onto_pick;
	}
	ap_sel = (u32)ap_from;
	LISTPOP(8, (u32)ap_from, &ap_sel, ap_l, (void *)ap_f);
}

static void ap_sec_pick(u32 unused)
{
	(void)unused;
	ap_sec = ap_sel;
	if (ap_sec == 0) {
		ap_run(-1, -1);
		return;
	}
	u32 k = put_s(ap_lab[0], "FROM ALL TRACKS");
	ap_lab[0][k] = 0;
	ap_l[0] = ap_lab[0];
	ap_f[0] = ap_from_pick;
	for (u32 t = 0; t < 8; t++) {
		k = put_s(ap_lab[1 + t], "FROM ");
		ap_lab[1 + t][k++] = ap_sec == SEC_MIDI + 1 ? 'M' : 'T';
		ap_lab[1 + t][k++] = (char)('1' + t);
		ap_lab[1 + t][k] = 0;
		ap_l[1 + t] = ap_lab[1 + t];
		ap_f[1 + t] = ap_from_pick;
	}
	ap_sel = 0;
	LISTPOP(9, 0, &ap_sel, ap_l, (void *)ap_f);
}

static void part_apply_ask(u32 ref)
{
	ap_ref = ref;
	static const char *rows[AP_ROWS];
	static void (*fn[AP_ROWS])(u32);
	for (u32 i = 0; i < AP_ROWS; i++) {
		rows[i] = ap_secl[i];
		fn[i] = ap_sec_pick;
	}
	ap_sel = 0;
	LISTPOP(AP_ROWS, 0, &ap_sel, rows, (void *)fn);
}

static void trow_load(u32 unused)
{
	(void)unused;
	u32 e = trow_ref_sel >> 8;
	const u8 *p = card_nth(e, trow_ref_sel & 0xff);
	if (!p)
		return;
	if (e == E_PART) {
		part_apply_ask(trow_ref_sel);
		return;
	}
	if (e == E_PROJECT) {
		view_fill(&tpl_view, V_PROJECT, 0);
		load_onto(p);
		return;
	}
	ld_n = 0;
	ld_ref = trow_ref_sel;
	for (u32 t = 0; t < 8; t++) {
		if (e < brain_fx_n) {			/* every slot whose chooser lists the effect */
			for (u32 fx = 0; fx < 2; fx++)
				if (find((const u8 *const *)(fx ? FX2_IDS : FX1_IDS), brain_fx[e].fx_id))
					ld_add(V_FX1 + fx, t);
		} else if (e == ST_BASE + 2) {
			ld_add(V_MIDI, t);
		}
	}
	if (!ld_n) {
		msg[0] = ent_name(e);
		msg[1] = "IS ON NO TRACK";
		POPUP("APPLY TEMPLATE", 2, msg, 0, 0);
		return;
	}
	ld_sel = 0;
	LISTPOP(ld_n, 0, &ld_sel, ld_l, (void *)ld_f);
}

/* a template is the default of its target when the stored default's values are its values */
static u32 pairs_sig(const u8 *pay, u32 from, u32 plen)
{
	u32 sg = 0;
	for (u32 at = from; at + 4 <= plen && pay[at + 3] != 0xff; at += 4 + align4(pay[at + 3]))
		if (pay[at + 2] == T_BYTE && pay[at + 3] == 1)
			sg = sg * 131 + (u32)(be16(pay + at) << 8 | pay[at + 4]) + 1;
	return sg;
}

static int can_default(u32 e)
{
	return e < brain_fx_n || e == E_PROJECT || e == E_PART;
}

static int tpl_is_default(u32 e, const u8 *rec)
{
	if (!can_default(e))
		return 0;
	if (e == E_PART) {
		const u8 *bl = part_blob(rec);
		return bl && part_def_have && part_def_sig == crc32(bl, PART_LEN);
	}
	u32 sg = pairs_sig(rec + REC_HDR + align4(rec[1]), 16, be32(rec + 8));
	return e == E_PROJECT ? pset_have && pset_sig == sg : e < MAX_FX && def_have[e] && def_sig[e] == sg;
}

/* SET AS DEFAULT: the engine task writes the template's values as the target's stored
 * default; CLEAR DEFAULT removes it */
static void trow_setdef(u32 unused)
{
	(void)unused;
	tpl_job(0x4000000 | trow_ref_sel, "SET AS DEFAULT");
}

static void trow_cleardef(u32 unused)
{
	(void)unused;
	if ((trow_ref_sel >> 8) == E_PROJECT)
		brain_post_template(0x2000000);
	else
		brain_post_clear_e(trow_ref_sel >> 8);
	msg[0] = tname;
	msg[1] = "DEFAULT CLEARED";
	POPUP("TEMPLATES", 2, msg, 0, 0);
	sc_rebuild();
}

/* ---- the edit screen of a template: its slots by their names, the values changed in place ---- */

static u32 ted_ref;			/* e << 8 | i of the template */
static u8 ted_has[NSLOT];			/* the template stores this slot */
static char ted_lab[NSLOT][8], ted_val[NSLOT][12];
static char ted_origin[PRT_NAME_MAX];		/* a PART template: the project it was taken in */
static u8 ted_dirty;

/* the slots of target e as a page of its own (the template's, not the page in front) */
static int view_meta(struct view *v, u32 e)
{
	v->n = 0;
	v->t = 0;
	if (e < brain_fx_n) {
		const u8 *d = desc[e][0] ? desc[e][0] : desc[e][1];
		if (!d)
			return 0;
		v->kind = V_FX1;
		v->e = e;
		for (u32 s = 0; s < 12; s++)
			slot(v, brain_fx[e].keys[s], 0, NOFLAT, (u32)d - 0x38, s);
		return 1;
	}
	if (e >= ST_BASE + 3 && e < ST_BASE + 8) {
		u32 m = e - ST_BASE - 3;
		v->kind = V_SRC;
		v->e = e;
		v->machine = m;
		for (u32 s = 0; s < 12; s++)
			slot(v, 1 + s, 0, NOFLAT, D_PLAYBACK + m * 0x192, s);
		return 1;
	}
	if (e == E_PROJECT || e == E_PART)
		return view_fill(v, e == E_PROJECT ? V_PROJECT : V_PART, 0);
	return e <= ST_BASE + 2 && view_fill(v, e == ST_BASE ? V_AMP : e == ST_BASE + 1 ? V_LFO : V_MIDI, 0);
}

static void ted_row(u32 unused) { (void)unused; }

/* a value as its page shows it: the slot's formatter (PARAM_PAGES.md section 7: fmt(buf, value), a
 * sprintf), into a 16-byte buffer of which the rows show eight; without one, the number */
typedef void (*fmt_fn)(char *, int);
static char fmt_buf[16];
static void txt_slot(const struct view *vw, u32 i, u32 val, char *lab, char *vs)
{
	u32 k = 0;
	if (vw->name[i])
		for (; k < 6 && vw->name[i][k]; k++)
			lab[k] = (char)vw->name[i][k];
	if (!k)
		k = put_s(lab, "SLOT");
	lab[k] = 0;
	u32 f = vw->fmt[i];
	if (f >= 0x40000000 && f < 0x48000000) {
		for (u32 q = 0; q < 16; q++)
			fmt_buf[q] = 0;
		((fmt_fn)f)(fmt_buf, val);
		u32 n = 0;
		for (; n < 8 && fmt_buf[n]; n++)
			vs[n] = fmt_buf[n];
		vs[n] = 0;
		if (n)
			return;
	}
	u32 n = put_dec(vs, val, 0);
	vs[n] = 0;
}

static void ted_text(u32 i)
{
	txt_slot(&ted_view, i, ted_vals[i], ted_lab[i], ted_val[i]);
}

/* ---- PROJECT and PART templates: their values by group ---------------------- */

/* A PROJECT or PART template's screen lists groups; YES opens one (ted_grp) and NO goes back to
 * them. PROJECT's groups are the stock CONTROL and MIDI screens and the mixer, each with the rows
 * stock draws; PART's are the sixteen FX slots, each its effect and that effect's page values. */
#define G_TOP 0xff
static u8 ted_grp DATA = G_TOP;
static u8 grp_back DATA = G_TOP;		/* the group row the cursor returns to */
static u8 ted_sub DATA = G_TOP;			/* a PART template's second level: the FX slot or the track */
static u8 sub_back DATA = G_TOP;


enum { PG_AUDIO, PG_INPUT, PG_SEQ, PG_MSEQ, PG_MEM, PG_METRO, PG_MIXER, PG_MCTL, PG_SYNC, PG_CHAN, PG_N };
static const char *const pg_name[PG_N] = { "AUDIO", "INPUT", "SEQUENCER", "MIDI SEQUENCER", "MEMORY",
					   "METRONOME", "MIXER", "MIDI CONTROL", "MIDI SYNC", "MIDI CHANNELS" };

/* A row's kind. P_GET: a stock row, its getter (the string the screen draws) and its setter
 * (delta, wrap) called on the template's bytes swapped in (pr_call); P_MEM the same with MEMORY's
 * pending copy; P_PICK one of two words (AUDIO's pairs: get the word for 0, set the word for 1);
 * P_KNOB a mixer knob, 0..126 drawn as the byte less 64 with its sign; P_DIR the same drawn as the
 * byte; P_CLAMP a stock getter, the byte stepped within 0..arg here (AUDIO NOTE IN's setter also
 * tells the engine); P_BIT0 a stock getter, bit 0 of the byte set or cleared here (CLOCK RECEIVE's
 * setter also restarts the clock). get, set and lab are the cells that hold the stock pointers. */
enum { P_GET, P_MEM, P_PICK, P_KNOB, P_DIR, P_CLAMP, P_BIT0 };
#define P_YES0 0x80				/* arg: YES passes delta 0 (MIDI SYNC toggles), else (1, wrap) */
struct prow {
	u8 grp, kind, off, arg;
	const char *label;			/* or 0: the stock label in the cell lab */
	u32 lab, get, set;
};
#define MEMROW(i) 0x400cc834 + 24 * (i), 0x400cc834 + 24 * (i) + 12, 0x400cc834 + 24 * (i) + 8
static const struct prow prow[] = {
	{ PG_AUDIO, P_PICK, 0x34, 0, "TRACK 8", 0, 0x400b2780, 0x400b277c },
	{ PG_AUDIO, P_PICK, 0x37, 0, "CUE CFG", 0, 0x400b278c, 0x400b2790 },
	{ PG_INPUT, P_GET, 0x58, 0, 0, 0x400b27ac, 0x400b27b8, 0x400b27c4 },
	{ PG_INPUT, P_GET, 0x59, 0, 0, 0x400b27b0, 0x400b27bc, 0x400b27c8 },
	{ PG_INPUT, P_GET, 0x5a, 0, 0, 0x400b27b4, 0x400b27c0, 0x400b27cc },
	{ PG_SEQ, P_GET, 0x4e, 0, 0, 0x400b27d0, 0x400b27dc, 0x400b282c },
	{ PG_SEQ, P_GET, 0x4f, 0, 0, 0x400b27d4, 0x400b27e0, 0x400b2830 },
	{ PG_SEQ, P_GET, 0x50, 0, 0, 0x400b27d8, 0x400b27e4, 0x400b2834 },
	{ PG_MSEQ, P_GET, 0x4d, 0, 0, 0x400b2838, 0x400b283c, 0x400b2840 },
	{ PG_MEM, P_MEM, 0x51, 0, 0, MEMROW(0) },
	{ PG_MEM, P_MEM, 0x52, 0, 0, MEMROW(1) },
	{ PG_MEM, P_MEM, 0x53, 0, 0, MEMROW(2) },
	{ PG_MEM, P_MEM, 0x54, 0, 0, MEMROW(3) },
	{ PG_MEM, P_MEM, 0x56, 0, 0, MEMROW(4) },
	{ PG_METRO, P_GET, 0x60, 0, 0, 0x400b2850, 0x400b2870, 0x400b28f4 },
	{ PG_METRO, P_GET, 0x5b, 0, 0, 0x400b2854, 0x400b2874, 0x400b28f8 },
	{ PG_METRO, P_GET, 0x5c, 0, 0, 0x400b2858, 0x400b2878, 0x400b28fc },
	{ PG_METRO, P_GET, 0x5d, 0, 0, 0x400b285c, 0x400b287c, 0x400b2900 },
	{ PG_METRO, P_GET, 0x5e, 0, 0, 0x400b2860, 0x400b2880, 0x400b2904 },
	{ PG_METRO, P_GET, 0x5f, 0, 0, 0x400b2864, 0x400b2884, 0x400b2908 },
	{ PG_METRO, P_GET, 0x62, 0, 0, 0x400b2868, 0x400b2888, 0x400b290c },
	{ PG_METRO, P_GET, 0x61, 0, 0, 0x400b286c, 0x400b288c, 0x400b2910 },
	{ PG_MIXER, P_KNOB, 0x32, 0, "MIX", 0, 0, 0 },
	{ PG_MIXER, P_KNOB, 0x35, 0, "MAIN", 0, 0, 0 },
	{ PG_MIXER, P_KNOB, 0x36, 0, "CUE", 0, 0, 0 },
	{ PG_MIXER, P_DIR, 0x31, 0, "DIR AB", 0, 0, 0 },
	{ PG_MIXER, P_KNOB, 0x2f, 0, "GAIN AB", 0, 0, 0 },
	{ PG_MIXER, P_DIR, 0x30, 0, "DIR CD", 0, 0, 0 },
	{ PG_MIXER, P_KNOB, 0x2e, 0, "GAIN CD", 0, 0, 0 },
	{ PG_MCTL, P_GET, 0x49, 0, 0, 0x400b29e0, 0x400b29f0, 0x400b2a00 },
	{ PG_MCTL, P_GET, 0x4a, 0, 0, 0x400b29e4, 0x400b29f4, 0x400b2a04 },
	{ PG_MCTL, P_CLAMP, 0x4b, 3, 0, 0x400b29e8, 0x400b29f8, 0 },
	{ PG_MCTL, P_GET, 0x4c, 0, 0, 0x400b29ec, 0x400b29fc, 0x400b2a0c },
	{ PG_SYNC, P_GET, 0x2a, P_YES0, "TRANSP SEND", 0, 0x400b291c, 0x400b2954 },
	{ PG_SYNC, P_GET, 0x29, P_YES0, "TRANSP RECV", 0, 0x400b2920, 0x400b2958 },
	{ PG_SYNC, P_GET, 0x28, P_YES0, "CLOCK SEND", 0, 0x400b292c, 0x400b295c },
	{ PG_SYNC, P_BIT0, 0x28, 0, "CLOCK RECV", 0, 0x400b2930, 0 },
	{ PG_SYNC, P_GET, 0x2b, P_YES0, "PROG CH SEND", 0, 0x400b2944, 0x400b2964 },
	{ PG_SYNC, P_GET, 0x2c, P_YES0, "PROG CH SEND CH", 0, 0x400b2948, 0x400b2968 },
	{ PG_SYNC, P_GET, 0x2b, P_YES0, "PROG CH RECV", 0, 0x400b294c, 0x400b296c },
	{ PG_SYNC, P_GET, 0x2d, P_YES0, "PROG CH RECV CH", 0, 0x400b2950, 0x400b2970 },
	{ PG_CHAN, P_GET, 0x47, 0, "AUTO CH", 0, 0x400b2998, 0x400b29bc },
	{ PG_CHAN, P_GET, 0x3f, 0, "TRIG CH 1", 0, 0x400b299c, 0x400b29c0 },
	{ PG_CHAN, P_GET, 0x40, 0, "TRIG CH 2", 0, 0x400b29a0, 0x400b29c4 },
	{ PG_CHAN, P_GET, 0x41, 0, "TRIG CH 3", 0, 0x400b29a4, 0x400b29c8 },
	{ PG_CHAN, P_GET, 0x42, 0, "TRIG CH 4", 0, 0x400b29a8, 0x400b29cc },
	{ PG_CHAN, P_GET, 0x43, 0, "TRIG CH 5", 0, 0x400b29ac, 0x400b29d0 },
	{ PG_CHAN, P_GET, 0x44, 0, "TRIG CH 6", 0, 0x400b29b0, 0x400b29d4 },
	{ PG_CHAN, P_GET, 0x45, 0, "TRIG CH 7", 0, 0x400b29b4, 0x400b29d8 },
	{ PG_CHAN, P_GET, 0x46, 0, "TRIG CH 8", 0, 0x400b29b8, 0x400b29dc },
};
#define PROW_N (sizeof prow / sizeof prow[0])
#define CELL(a) (*(const u32 *)(a))

/* The project bytes: the settings from 0x80000000, their CS1 mirror, and MEMORY's pending copy of
 * 0x51..0x54 and the word at 0x56 (0x40066904; its setters and getters read and write only that,
 * and 0x460e4400, its redraw count). */
#define PS_LIVE   ((volatile u8 *)0x80000000)
#define PS_MIRROR ((volatile u8 *)0x100b1460)
#define MEM_PEND  ((volatile u8 *)0x460e4550)
#define MEM_COUNT (*(volatile u32 *)0x460e4400)
static const u8 pend_off[6] = { 0x51, 0x52, 0x53, 0x54, 0x56, 0x57 };
static u8 pslot[0x70];				/* the view slot of a project byte, or 0xff */
static u8 sw_live[0x70], sw_mir[0x70], sw_pend[6];
static u32 sw_count;

static u32 irq_off(void)
{
	u32 sr;
	__asm__ volatile("move.w %%sr,%0\n\tmove.w #0x2700,%%sr" : "=d"(sr));
	return sr;
}
static void irq_on(u32 sr) { __asm__ volatile("move.w %0,%%sr" : : "d"(sr)); }

/* the template's bytes into the live settings, their mirror and MEMORY's pending copy (interrupts
 * off: nothing else runs on them until sw_out puts them back) */
static void sw_in(void)
{
	for (u32 o = 0; o < 0x70; o++) {
		sw_live[o] = PS_LIVE[o];
		sw_mir[o] = PS_MIRROR[o];
		if (pslot[o] != 0xff && ted_has[pslot[o]])
			PS_LIVE[o] = PS_MIRROR[o] = ted_vals[pslot[o]];
	}
	for (u32 k = 0; k < 6; k++) {
		sw_pend[k] = MEM_PEND[k];
		MEM_PEND[k] = PS_LIVE[pend_off[k]];
	}
	sw_count = MEM_COUNT;
}

/* back out; with keep the bytes a setter wrote become the template's (a MEMORY row's from the
 * pending copy) */
static void sw_out(int keep, int mem)
{
	if (keep) {
		for (u32 o = 0; o < 0x70; o++)
			if (pslot[o] != 0xff && ted_has[pslot[o]]) {
				u8 v = PS_LIVE[o];
				for (u32 k = 0; mem && k < 6; k++)
					if (pend_off[k] == o)
						v = MEM_PEND[k];
				if (v != ted_vals[pslot[o]])
					ted_dirty = 1;
				ted_vals[pslot[o]] = v;
			}
	}
	for (u32 o = 0; o < 0x70; o++) {
		PS_LIVE[o] = sw_live[o];
		PS_MIRROR[o] = sw_mir[o];
	}
	for (u32 k = 0; k < 6; k++)
		MEM_PEND[k] = sw_pend[k];
	MEM_COUNT = sw_count;
}

typedef const char *(*get_fn)(void);
typedef void (*set_fn)(int, int);

static int pr_has(const struct prow *r) { return pslot[r->off] != 0xff && ted_has[pslot[r->off]]; }

/* row k's value as its screen draws it, into ted_val[k] */
static void pr_text(u32 k)
{
	const struct prow *r = &prow[k];
	char *o = ted_val[k];
	u32 n = 0;
	int v = ted_vals[pslot[r->off]];
	if (r->kind == P_PICK) {
		n = put_s(o, (const char *)CELL(v ? r->set : r->get));
	} else if (r->kind == P_KNOB || r->kind == P_DIR) {
		if (r->kind == P_KNOB) {
			o[n++] = v < 64 ? '-' : '+';
			v = v < 64 ? 64 - v : v - 64;
		}
		n += put_dec(o + n, (u32)v, 0);
	} else {
		u32 sr = irq_off();
		sw_in();
		const char *t = ((get_fn)CELL(r->get))();
		for (; t && n < 11 && t[n]; n++)
			o[n] = t[n];
		sw_out(0, 0);
		irq_on(sr);
	}
	o[n] = 0;
}

/* row k stepped by delta (wrap: YES): stock's setter on the template's bytes, or the same rule here */
static void pr_step(u32 k, int delta, int wrap)
{
	const struct prow *r = &prow[k];
	u8 *b = &ted_vals[pslot[r->off]];
	int v = (int)*b;
	if (r->kind == P_GET || r->kind == P_MEM) {
		u32 sr = irq_off();
		sw_in();
		((set_fn)CELL(r->set))(delta, wrap);
		sw_out(1, r->kind == P_MEM);
		irq_on(sr);
		return;
	}
	if (r->kind == P_PICK)
		v = wrap ? !v : v + delta < 0 ? 0 : v + delta > 1 ? 1 : v + delta;
	else if (r->kind == P_KNOB || r->kind == P_DIR)
		v = wrap ? v : v + delta < 0 ? 0 : v + delta > 126 ? 126 : v + delta;
	else if (r->kind == P_CLAMP) {
		v = (int)(signed char)*b + delta;
		v = wrap ? (v > r->arg ? 0 : v < 0 ? r->arg : v) : (v < 0 ? 0 : v > r->arg ? r->arg : v);
	} else if (r->kind == P_BIT0)
		v = wrap || !delta ? v ^ 1 : delta > 0 ? v | 1 : v & ~1;
	if ((u8)v != *b)
		ted_dirty = 1;
	*b = (u8)v;
}

static void ted_prow(u32 k) { pr_step(k, prow[k].arg & P_YES0 ? 0 : 1, 1); }

/* PART: group g is track g >> 1's FX1 (g even) or FX2; its id is view slot (g & 1) * 8 + track and
 * its twelve values slots 16 + g * 12 on (view_fill) */
static const char *fx_name(u32 fx, u32 id);
static char pg_lab[16][8];
#define PART_ID(g)  (((g) & 1) * 8 + ((g) >> 1))
#define PART_VAL(g) (16 + (g) * 12)

static void part_put(u32 i) { ted_part[ted_view.at[i] - WORKING] = ted_vals[i]; }

/* the names, ranges and formatters of group g's values from its effect's page descriptor; a slot
 * the descriptor leaves out (enable bit 0 clear, no count) is SKIP and not listed */
static void part_meta(u32 g)
{
	u32 fx = g & 1, id = ted_vals[PART_ID(g)];
	const u8 *p = find((const u8 *const *)(fx ? FX2_IDS : FX1_IDS), id);
	for (u32 s = 0; s < 12; s++) {
		u32 i = PART_VAL(g) + s;
		ted_view.name[i] = 0;
		ted_view.fmt[i] = 0;
		ted_view.def[i] = 0;
		ted_view.lo[i] = 0;
		ted_view.hi[i] = 127;
		ted_view.flat[i] = SKIP;
		if (!p || !id)
			continue;
		const u8 *E = p - 0x38;
		int min = (int)be32(E + 0xa2 + 4 * s), cnt = (int)be32(E + 0xd2 + 4 * s);
		u32 en = s < 8 ? be32(E + 0x1c6) >> (4 * s) : be32(E + 0x1c2) >> (4 * (s - 8));
		if (cnt <= 0 || !(en & 1))
			continue;
		ted_view.flat[i] = NOFLAT;
		ted_view.lo[i] = (u8)min;
		ted_view.hi[i] = (u8)(min + cnt - 1);
		ted_view.name[i] = E + 0x4e + 6 * s;
		ted_view.fmt[i] = be32(E + 0x102 + 4 * s);
		ted_view.def[i] = E[0x96 + s];
	}
}

/* LEFT and RIGHT on a slot's row: the next or previous effect its chooser lists (NONE first), its
 * values the new effect's defaults */
static void part_fx_step(u32 g, int delta)
{
	u32 fx = g & 1, id = ted_vals[PART_ID(g)];
	for (int k = delta < 0 ? -delta : delta; k > 0; k--)
		for (u32 n = 0; n < 32; n++) {
			id = delta > 0 ? (id + 1) & 31 : (id + 31) & 31;
			if (!id || find((const u8 *const *)(fx ? FX2_IDS : FX1_IDS), id))
				break;
		}
	if (id == ted_vals[PART_ID(g)])
		return;
	ted_vals[PART_ID(g)] = (u8)id;
	part_put(PART_ID(g));
	part_meta(g);
	for (u32 s = 0; s < 12; s++) {
		ted_vals[PART_VAL(g) + s] = ted_view.def[PART_VAL(g) + s];
		part_put(PART_VAL(g) + s);
	}
	ted_dirty = 1;
}

static int ted_is(u32 e) { return (ted_ref >> 8) == e; }

/* YES on a group's row: its values */
static void sc_home(void);
static void ted_open(u32 g)
{
	ted_grp = (u8)g;
	ted_sub = G_TOP;
	sc_rebuild();
	sc_home();
}

/* YES on a PART group's row for an FX slot or a track: its values */
static void ted_sub_open(u32 sb)
{
	ted_sub = (u8)sb;
	sc_rebuild();
	sc_home();
}

/* A PART template's groups: what its sections hold, edited in the Part image ted_part */
enum { PP_MACH, PP_FX, PP_LFO, PP_SRC, PP_MIDI, PP_SCN, PP_N };
static const char *const pp_name[PP_N] = { "MACHINES", "FX", "LFO", "INPUT SRC", "MIDI TRACKS", "SCENES" };
static const char *const mach_name[5] = { "STATIC", "FLEX", "THRU", "NEIGHBOR", "PICKUP" };
static const char *const pg_t[8] = { "T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8" };
static const char *const pg_m[8] = { "M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8" };
static char scn_val[2][4];
static char ted_tt[16];

/* track ted_sub's page in the group open (LFO, INPUT SRC, MIDI TRACKS): its slots from the stock page
 * descriptors; a slot's value is the byte of ted_part at its offset. An INPUT SRC page is the one of the
 * machine the template has on the track (a THRU, NEIGHBOR or PICKUP page; a sample machine's is not
 * a template's). */
static struct view pv;
static char pv_lab[NSLOT][8], pv_val[NSLOT][12];
static void pv_build(void)
{
	u32 t = ted_sub & 7;
	if (ted_grp == PP_LFO) {
		view_fill(&pv, V_LFO, t);
	} else if (ted_grp == PP_MIDI) {
		view_fill(&pv, V_MIDI, t);
	} else {
		u32 m = ted_part[0x22 + t];
		pv.n = 0;
		for (u32 sl = 0; m >= 2 && m <= 4 && sl < 12; sl++)
			slot(&pv, 1 + sl, (sl < 6 ? 0x8edaa : 0x8ef5a - 6) + t * 30 + m * 6 + sl, NOFLAT,
			     D_PLAYBACK + m * 0x192, sl);
	}
}

static void pv_row(u32 unused) { (void)unused; }
static void ted_mach(u32 unused) { (void)unused; }
static void ted_scn(u32 unused) { (void)unused; }

/* the screen's title: the target, or the group open */
static const char *ted_title(void)
{
	u32 e = ted_ref >> 8;
	if (ted_grp == G_TOP)
		return ent_name(e);
	if (e == E_PROJECT)
		return pg_name[ted_grp];
	if (ted_sub == G_TOP)
		return pp_name[ted_grp];
	if (ted_grp == PP_FX)
		return pg_lab[ted_sub];
	u32 t = ted_sub & 7, k = 0;
	ted_tt[k++] = ted_grp == PP_MIDI ? 'M' : 'T';
	ted_tt[k++] = (char)('1' + t);
	ted_tt[k++] = ' ';
	k += put_s(ted_tt + k, ted_grp == PP_LFO ? "LFO" : ted_grp == PP_MIDI ? "MIDI" : mach_name[ted_part[0x22 + t] % 5]);
	ted_tt[k] = 0;
	return ted_tt;
}

static void ted_save(u32 unused)
{
	(void)unused;
	ted_dirty = 0;
	tpl_job(0x8000000 | ted_ref, "SAVED");
}

/* the edit screen of template ref (e << 8 | i): the slots it stores by name, when its target has
 * them (an effect, AMP, LFO, SRC or MIDI template), and the actions as rows */
static u8 ted_gone;
static int ted_prepare(u32 ref)
{
	u32 e = ref >> 8;
	const u8 *rec = card_nth(e, ref & 0xff);
	if (!rec)
		return 0;
	trow_ref_sel = ref;
	ted_ref = ref;
	ted_gone = 0;
	ted_dirty = 0;
	for (u32 k = 0; k < sizeof tname; k++)
		tname[k] = 0;
	trow_name(tname, rec);
	for (u32 i = 0; i < NSLOT; i++)
		ted_has[i] = 0;
	if (view_meta(&ted_view, e)) {
		tpl_values(rec, &ted_view, ted_vals);
		const u8 *pay = rec + REC_HDR + align4(rec[1]);
		u32 plen = be32(rec + 8);
		for (u32 a = 16; a + 4 <= plen && pay[a + 3] != 0xff; a += 4 + align4(pay[a + 3]))
			for (u32 i = 0; i < ted_view.n; i++)
				if (ted_view.key[i] == be16(pay + a))
					ted_has[i] = 1;
	} else {
		ted_view.n = 0;
	}
	ted_origin[0] = 0;
	if (e == E_PART) {				/* the values are the template's Part image */
		const u8 *bl = part_blob(rec), *o = part_origin(rec);
		for (u32 q = 0; q < PART_LEN; q++)
			ted_part[q] = bl ? bl[q] : 0;
		for (u32 i = 0; i < ted_view.n; i++) {
			ted_vals[i] = ted_part[ted_view.at[i] - WORKING];
			ted_has[i] = bl != 0;
		}
		for (u32 k = 0; o && k < PRT_NAME_MAX - 1 && o[k]; k++)
			ted_origin[k] = (char)o[k];
		ted_origin[PRT_NAME_MAX - 1] = 0;
	}
	ted_grp = G_TOP;
	ted_sub = G_TOP;
	for (u32 o = 0; o < 0x70; o++)
		pslot[o] = 0xff;
	if (e == E_PROJECT)
		for (u32 i = 0; i < ted_view.n; i++)
			pslot[ted_view.at[i]] = (u8)i;
	if (e == E_PART)
		for (u32 g = 0; g < 16; g++) {
			pg_lab[g][0] = 'T';
			pg_lab[g][1] = (char)('1' + (g >> 1));
			put_s(pg_lab[g] + 2, g & 1 ? " FX2" : " FX1");
			pg_lab[g][6] = 0;
			part_meta(g);
		}
	return 1;
}

/* a one-shot timer: unlinked as the tick does (the soft timer re-links what it calls) */
static void timer_off(int *slot)
{
	if (*slot >= 0)
		*(volatile u32 *)(TIMERS + (u32)*slot * 16 + 8) = 0;
	*slot = -1;
}

static int open_timer DATA = -1;
static void open_cb(void)
{
	timer_off(&open_timer);
	sc_open(SC_TED);
}

/* YES on a template row: its edit screen, a moment later (a state opened from the key's own
 * handler took no keys under the port) */
static void tpl_item(u32 ref)
{
	if (ted_prepare(ref) && open_timer < 0)
		open_timer = TIMER(12, open_cb);
}

static void new_poll(void)
{
	for (u32 j = 0; j < TPL_MAX; j++) {
		const u8 *q = card_nth(new_e, j);
		if (!q)
			break;
		if (same_name(q, (const u8 *)tpl_newname)) {
			timer_off(&new_timer);
			if (ted_prepare(new_e << 8 | j))
				sc_open(SC_TED);
			return;
		}
	}
	if (++new_tries > 40)			/* about six seconds: it did not arrive */
		timer_off(&new_timer);
}

/* ---- NAME KNOB: the page shortcut on a MIDI track ------------------------- */

/* The current MIDI track's ten CCs, each "CCn  NAME" (---- without one); YES
 * opens the name editor (four characters) on that CC's name, and on
 * confirm the engine task rewrites the project's knob-name field blocks
 * (write_names). An empty name clears it. */
static char kn_lbl[10][16];
static const char *kn_lp[10];
static void (*kn_fp[10])(u32);
static u32 kn_sel, kn_t, kn_bp;
static char kn_buf[16];

static void kn_named(u32 confirmed)
{
	if (!confirmed || kn_sel > 9)
		return;
	char *o = knames[kn_bp][kn_t][kn_sel];
	u32 k = 0;
	for (; k < KN_CHARS && kn_buf[k]; k++)
		o[k] = kn_buf[k];
	while (k > 0 && o[k - 1] == ' ')
		k--;
	for (; k < KN_LEN; k++)
		o[k] = 0;
	brain_post_template(0x800000);
}

static void kn_pick(u32 unused)
{
	(void)unused;
	if (kn_sel > 9)
		return;
	for (u32 k = 0; k < sizeof kn_buf; k++)
		kn_buf[k] = 0;
	const char *n = knames[kn_bp][kn_t][kn_sel];
	for (u32 k = 0; k < KN_CHARS && n[k]; k++)
		kn_buf[k] = n[k];
	NAMEED(KN_CHARS, "KNOB NAME", kn_buf, 1, kn_named);
}

void brain_kn_list(u32 unused)
{
	(void)unused;
	if (!MIDI_MODE)
		return;
	kn_t = CUR_TRACK & 7;
	kn_bp = kn_part();
	for (u32 c = 0; c < 10; c++) {
		char *o = kn_lbl[c];
		u32 k = 0;
		o[k++] = 'C'; o[k++] = 'C';
		if (c == 9) {
			o[k++] = '1'; o[k++] = '0';
		} else
			o[k++] = (char)('1' + c);
		while (k < 6)
			o[k++] = ' ';
		const char *n = knames[kn_bp][kn_t][c];
		for (u32 j = 0; j < KN_CHARS; j++)
			o[k++] = n[0] ? (n[j] ? n[j] : ' ') : '-';
		o[k] = 0;
		kn_lp[c] = o;
		kn_fp[c] = kn_pick;
	}
	kn_sel = 0;
	LISTPOP(10, 0, &kn_sel, kn_lp, (void *)kn_fp);
}

/* The engine task: the project's brain.work with one stock.midi field
 * block per Part that has a name, every other record kept. 0, or an error
 * code as write_set_file's. */
static int write_names(void)
{
	if (!proj_paths())
		return 5;
	int n = cur(pw, ps);
	if (n < 0)
		return 2;
	u32 at = HDR, kept = 0;
	for (u32 r = 0, i = HDR; n && r < be16(buf + 10); r++, i += be32(buf + i + 16)) {
		const u8 *p = buf + i;
		u32 size = be32(p + 16);
		if (p[0] == K_FIELD && same_id(p + REC_HDR, p[1], KN_STORE, 10))
			continue;
		if (at + size > BUF_LEN)
			return 3;
		for (u32 b = 0; b < size; b++)
			out[at + b] = p[b];
		at += size;
		kept++;
	}
	for (u32 bp = 0; bp < KN_PARTS; bp++) {
		u32 nn = 0;
		for (u32 t = 0; t < 8; t++)
			for (u32 c = 0; c < 10; c++)
				nn += knames[bp][t][c][0] != 0;
		if (!nn)
			continue;
		u32 plen = 4 + 12 * nn, size = REC_HDR + align4(10) + plen;
		if (at + size > BUF_LEN)
			return 3;
		u8 *r = out + at;
		for (u32 b = 0; b < size; b++)
			r[b] = 0;
		r[0] = K_FIELD;
		r[1] = 10;
		put16(r + 2, 1);
		put32(r + 8, plen);
		put32(r + 16, size);
		for (u32 b = 0; b < 10; b++)
			r[REC_HDR + b] = (u8)KN_STORE[b];
		u8 *pay = r + REC_HDR + align4(10);
		put16(pay, bp);
		u8 *w = pay + 4;
		for (u32 t = 0; t < 8; t++)
			for (u32 c = 0; c < 10; c++)
				if (knames[bp][t][c][0]) {
					put16(w, t * 10 + c + 1);
					w[2] = T_NAME;
					w[3] = KN_LEN;
					for (u32 k = 0; k < KN_LEN; k++)
						w[4 + k] = (u8)knames[bp][t][c][k];
					w += 12;
				}
		put32(r + 12, crc32(pay, plen));
		at += size;
		kept++;
	}
	return write_store(pw, 2, at, kept) < 0 ? 4 : 0;
}

/* ---- project settings for new projects (BRAIN.md section 3) -------------- */

/* The stock PROJECT menu's bytes (docs/firmware/STORAGE.md section 5:
 * bytes from 0x80000000, each mirrored in CS1 at 0x100b1460 + the same
 * offset), TEMPOx24 left out: SAVE NEW PROJ stores them as a card-layer
 * default of store stock.project (keys 1 + offset, raw bytes); CREATE
 * EMPTY PROJECT applies it right after the empty project's RAM is set up
 * (0x400909d8; the detour at 0x40085176, hooks.s brain_on_newproj), so the
 * new project.work is written with them. */
#define PS_STORE   "stock.project"
#define PS_LAYOUT  0x50524a31u			/* "PRJ1" */
#define PS_RAM     0x80000000u
#define PS_CS1     0x100b1460u
static int ps_byte(u32 off)
{
	return off == 0x24 || (off >= 0x28 && off <= 0x37) || (off >= 0x3f && off <= 0x54)
	       || (off >= 0x56 && off <= 0x6a);
}

/* NP_RUNS: new projects seen; NP_VALUES: bytes the last one took */
/* SET AS DEFAULT, in the engine task: the i-th card template of entry e becomes the stored default of its
 * target (an effect's NO_MODE record, or the new-project settings), the values copied as they are, and an
 * effect's descriptor takes them at once. 0, or an error as write_default's. */
static int write_setdef(u32 e, u32 i)
{
	int n = current_store();
	if (n < 0)
		return 2;
	const u8 *tp = n ? nth_in(buf + HDR, (u32)n - HDR, e, i) : 0;
	if (!tp || !can_default(e))
		return 1;
	const char *id;
	u32 id_len, layout;
	ent_id(e, &id, &id_len, &layout);
	u32 at = HDR, kept = 0;
	for (u32 r = 0, k = HDR; r < be16(buf + 10); r++, k += be32(buf + k + 16)) {
		const u8 *p = buf + k;
		u32 size = be32(p + 16);
		const u8 *pay = p + REC_HDR + align4(p[1]);
		if (p[0] == K_DEFAULT && same_id(p + REC_HDR, p[1], id, id_len)
		    && (e == E_PROJECT || e == E_PART || (be32(p + 8) >= 4 && be16(pay) == 0 && be16(pay + 2) == NO_MODE)))
			continue;
		if (at + size > BUF_LEN)
			return 3;
		for (u32 b = 0; b < size; b++)
			out[at + b] = p[b];
		at += size;
		kept++;
	}
	if (e == E_PART) {				/* the default is the template's Part image, an 8-byte prefix */
		const u8 *bl = part_blob(tp);
		if (!bl)
			return 1;
		u32 plen = 8 + 8 + align4(PART_LEN), size = REC_HDR + align4(id_len) + plen;
		if (at + size > BUF_LEN)
			return 3;
		u8 *r = out + at;
		for (u32 b = 0; b < size; b++)
			r[b] = 0;
		r[0] = K_DEFAULT;
		r[1] = (u8)id_len;
		put16(r + 2, 1);
		put32(r + 8, plen);
		put32(r + 16, size);
		for (u32 b = 0; b < id_len; b++)
			r[REC_HDR + b] = (u8)id[b];
		u8 *pay = r + REC_HDR + align4(id_len);
		put16(pay + 2, NO_MODE);
		put32(pay + 4, layout);
		put16(pay + 8, 1);
		pay[10] = T_BLOB;
		pay[11] = 0xff;
		put32(pay + 12, PART_LEN);
		for (u32 b = 0; b < PART_LEN; b++)
			pay[16 + b] = bl[b];
		put32(r + 12, crc32(pay, plen));
		at += size;
		kept++;
		if (write_card(at, kept) < 0)
			return 4;
		cache_defaults(current_store() > 0);
		cache_templates(1);
		return 0;
	}
	const u8 *tpay = tp + REC_HDR + align4(tp[1]);
	u32 tlen = be32(tp + 8), nvals = 0;
	for (u32 a = 16; a + 4 <= tlen && tpay[a + 3] != 0xff; a += 4 + align4(tpay[a + 3]))
		nvals += tpay[a + 2] == T_BYTE && tpay[a + 3] == 1;
	u32 plen = 8 + 8 * nvals, size = REC_HDR + align4(id_len) + plen;
	if (at + size > BUF_LEN)
		return 3;
	u8 *r = out + at;
	for (u32 b = 0; b < size; b++)
		r[b] = 0;
	r[0] = K_DEFAULT;
	r[1] = (u8)id_len;
	put16(r + 2, 1);
	put32(r + 8, plen);
	put32(r + 16, size);
	for (u32 b = 0; b < id_len; b++)
		r[REC_HDR + b] = (u8)id[b];
	u8 *pay = r + REC_HDR + align4(id_len);
	put16(pay + 2, NO_MODE);
	put32(pay + 4, layout);
	u8 *w = pay + 8;
	for (u32 a = 16; a + 4 <= tlen && tpay[a + 3] != 0xff; a += 4 + align4(tpay[a + 3]))
		if (tpay[a + 2] == T_BYTE && tpay[a + 3] == 1) {
			put16(w, be16(tpay + a));
			w[2] = T_BYTE;
			w[3] = 1;
			w[4] = tpay[a + 4];
			w += 8;
		}
	put32(r + 12, crc32(pay, plen));
	at += size;
	kept++;
	if (write_card(at, kept) < 0)
		return 4;
	if (e < brain_fx_n)
		for (u32 a = 8; a + 8 <= plen; a += 8) {
			u32 key = be16(pay + a);
			for (int s = 0; s < 12; s++)
				if (brain_fx[e].keys[s] == key)
					for (int k = 0; k < 2; k++) {
						u8 *p = desc[e][k];
						if (p && pay[a + 4] < be32(p + 0x9a + 4 * s))
							p[0x5e + s] = pay[a + 4];
					}
		}
	cache_defaults(current_store() > 0);
	cache_templates(1);
	return 0;
}

static void cache_defaults(int have)
{
	for (u32 i = 0; i < MAX_FX; i++)
		def_have[i] = 0;
	pset_have = 0;
	part_def_have = 0;
	card_defs = 0;
	if (!have)
		return;
	u32 count = be16(buf + 10);
	for (u32 r = 0, at = HDR; r < count; r++, at += be32(buf + at + 16)) {
		const u8 *p = buf + at;
		if (p[0] != K_DEFAULT || crc32(p + REC_HDR + align4(p[1]), be32(p + 8)) != be32(p + 12))
			continue;
		card_defs++;
		const u8 *pay = p + REC_HDR + align4(p[1]);
		if (same_id(p + REC_HDR, p[1], PART_STORE, 11)) {
			const u8 *bl = part_blob_at(pay, 8, be32(p + 8));
			if (bl && be32(pay + 4) == PART_LAYOUT) {
				for (u32 k = 0; k < PART_LEN; k++)
					part_def[k] = bl[k];
				part_def_sig = crc32(bl, PART_LEN);
				part_def_have = 1;
			}
			continue;
		}
		if (same_id(p + REC_HDR, p[1], PS_STORE, 13)) {
			pset_have = 1;
			pset_sig = pairs_sig(pay, 8, be32(p + 8));
			continue;
		}
		int e = entry_of(p);
		if (e >= 0 && be32(p + 8) >= 4 && be16(pay) == 0 && be16(pay + 2) == NO_MODE) {
			def_have[e] = 1;
			def_sig[e] = pairs_sig(pay, 8, be32(p + 8));
		}
	}
}

enum { NP_RUNS, NP_VALUES, NP_N };
u32 brain_np_counts[NP_N] DATA;

/* engine task: CLEAR DEFAULT of the PART default: the file without its record */
static int write_partdef_clear(void)
{
	int n = current_store();
	if (n < 0)
		return 2;
	u32 at = HDR, kept = 0;
	for (u32 r = 0, i = HDR; n && r < be16(buf + 10); r++, i += be32(buf + i + 16)) {
		const u8 *p = buf + i;
		u32 size = be32(p + 16);
		if (p[0] == K_DEFAULT && same_id(p + REC_HDR, p[1], PART_STORE, 11))
			continue;
		if (at + size > BUF_LEN)
			return 3;
		for (u32 b = 0; b < size; b++)
			out[at + b] = p[b];
		at += size;
		kept++;
	}
	if (write_card(at, kept) < 0)
		return 4;
	cache_defaults(current_store() > 0);
	return 0;
}

/* engine task: SAVE NEW PROJECT (clear 0) or CLEAR NEW PROJECT (clear 1) */
static int write_pset(int clear)
{
	int n = current_store();
	if (n < 0)
		return 2;
	u32 at = HDR, kept = 0;
	for (u32 r = 0, i = HDR; n && r < be16(buf + 10); r++, i += be32(buf + i + 16)) {
		const u8 *p = buf + i;
		u32 size = be32(p + 16);
		if (p[0] == K_DEFAULT && same_id(p + REC_HDR, p[1], PS_STORE, 13))
			continue;
		if (at + size > BUF_LEN)
			return 3;
		for (u32 b = 0; b < size; b++)
			out[at + b] = p[b];
		at += size;
		kept++;
	}
	if (!clear) {
		u32 nv = 0;
		for (u32 off = 0; off < 0x70; off++)
			nv += ps_byte(off);
		u32 plen = 8 + 8 * nv, size = REC_HDR + align4(13) + plen;
		if (at + size > BUF_LEN)
			return 3;
		u8 *r = out + at;
		for (u32 b = 0; b < size; b++)
			r[b] = 0;
		r[0] = K_DEFAULT;
		r[1] = 13;
		put16(r + 2, 1);
		put32(r + 8, plen);
		put32(r + 16, size);
		for (u32 b = 0; b < 13; b++)
			r[REC_HDR + b] = (u8)PS_STORE[b];
		u8 *pay = r + REC_HDR + align4(13);
		put16(pay + 2, NO_MODE);
		put32(pay + 4, PS_LAYOUT);
		u8 *w = pay + 8;
		for (u32 off = 0; off < 0x70; off++)
			if (ps_byte(off)) {
				put16(w, 1 + off);
				w[2] = T_BYTE;
				w[3] = 1;
				w[4] = *(volatile u8 *)(PS_RAM + off);
				w += 8;
			}
		put32(r + 12, crc32(pay, plen));
		at += size;
		kept++;
	}
	if (write_card(at, kept) < 0)
		return 4;
	cache_defaults(current_store() > 0);
	return 0;
}

/* engine task, inside CREATE EMPTY PROJECT: the card's stock.project
 * default onto the settings bytes and their CS1 mirrors */
void brain_new_project(void)
{
	u32 n;
	brain_np_counts[NP_RUNS]++;
	brain_np_counts[NP_VALUES] = 0;
	int st = pair_load("/BRAIN/card.work", "/BRAIN/card.strd", &n);
	if (st != 1 && st != 2)
		return;
	u32 count = be16(buf + 10);
	for (u32 r = 0, at = HDR; r < count; r++, at += be32(buf + at + 16)) {
		const u8 *p = buf + at;
		const u8 *pay = p + REC_HDR + align4(p[1]);
		u32 plen = be32(p + 8);
		if (p[0] != K_DEFAULT || !same_id(p + REC_HDR, p[1], PS_STORE, 13) || plen < 8
		    || crc32(pay, plen) != be32(p + 12) || be32(pay + 4) != PS_LAYOUT)
			continue;
		for (u32 v = 8; v + 4 <= plen && pay[v + 3] != 0xff; v += 4 + align4(pay[v + 3])) {
			u32 key = be16(pay + v);
			if (pay[v + 2] != T_BYTE || pay[v + 3] != 1 || key < 1 || !ps_byte(key - 1))
				continue;
			*(volatile u8 *)(PS_RAM + key - 1) = pay[v + 4];
			*(volatile u8 *)(PS_CS1 + key - 1) = pay[v + 4];
			brain_np_counts[NP_VALUES]++;
		}
		return;
	}
}

/* The end of stock's Part initialiser (0x40005638(part): what a Part Clear, a new project's every
 * Part and KITS' test for a free slot start from; hooks.s brain_partinit): the card's PART default
 * onto the Part just initialised, but its sample slots. */
void brain_part_init(u8 *part)
{
	if (part_def_have)
		part_merge(part, part_def, SEC_DEFAULT, -1, -1);
}

void brain_menu_psave(u32 unused)
{
	(void)unused;
	brain_post_template(0x1000000);
	msg[0] = "PROJECT SETTINGS";
	msg[1] = "SAVED FOR NEW PROJ";
	POPUP("DEFAULTS", 2, msg, 0, 0);
}

void brain_menu_pclear(u32 unused)
{
	(void)unused;
	brain_post_template(0x2000000);
	msg[0] = "PROJECT SETTINGS";
	msg[1] = "CLEARED";
	POPUP("DEFAULTS", 2, msg, 0, 0);
}

/* One logged message as text: "CH01 CC 007=020", "CH10 NOTE 036 100",
 * "START" ... */
static u32 midi_text(char *t, const struct dbg_ent *e)
{
	u32 st = e->st, n = 0;
	static const char *const sys[16] = { "SYSEX", "MTC", "SPP", "SONG", "", "", "TUNE", "EOX",
					     "CLOCK", "", "START", "CONT", "STOP", "", "SENSE", "RESET" };
	if (st >= 0xf0)
		return put_s(t, sys[st & 15]);
	n = put_s(t, "CH");
	n += put_dec(t + n, (st & 15) + 1, 2);
	if (t[2] == ' ')
		t[2] = '0';
	switch (st >> 4) {
	case 0x8: n += put_s(t + n, " OFF "); break;
	case 0x9: n += put_s(t + n, " NOTE "); break;
	case 0xa: n += put_s(t + n, " PAT "); break;
	case 0xb: n += put_s(t + n, " CC "); break;
	case 0xc: n += put_s(t + n, " PC "); n += put_dec(t + n, e->d1, 3);
		  n += put_s(t + n, " P"); return n + put_dec(t + n, e->pnext + 1, 0);
	case 0xd: n += put_s(t + n, " CP "); return n + put_dec(t + n, e->d1, 3);
	case 0xe: n += put_s(t + n, " PB "); return n + put_dec(t + n, ((u32)e->d2 << 7) | e->d1, 5);
	default: return n;
	}
	n += put_dec(t + n, e->d1, 3);
	t[n++] = (st >> 4) == 0xb ? '=' : ' ';
	return n + put_dec(t + n, e->d2, 3);
}


/* ---- BRAIN's screens: the menu states ------------------------------------- */

/* One state of the menu-state table per screen (SC_BASE + screen; the
 * table's members {enter, exit, draw, key, encoder} are the brain_scr_*
 * functions below, which read the state index 0x400cbf40). The screen is a
 * list of rows (sr[], rebuilt on entry and after each action) drawn the way
 * the stock MIDI screens draw: the category icon at the left and the title
 * at the right of the first band, a rule under it, then rows at the stock
 * 7-pixel pitch with the stock inverted bar on the cursor row
 * (0x40012254). The stock key dispatcher (0x4006510a) calls key(code,
 * pressed) and redraws after it; NO leaves the state through the exit
 * member back to the menu (0x400650a0). LOAD and MIDI redraw every half
 * second from a soft timer (0x40031a0c). */

#define SC_BASE    16
#define STATEG     (*(volatile u32 *)0x400cbf40)
#define OPEN_STATE ((void (*)(u32))0x40064e20)	/* the id path's: sets the state, calls its enter member, redraws */
#define MENU_REDRAW ((void (*)(void))0x40064d7c)
#define FONT       ((const char *)0x400ba876)
#define TEXT_W     ((u32 (*)(const char *, u32, const char *))0x40012f30)	/* (font, max, string): pixels */
#define DRAWSTR    ((void (*)(const char *, void *, int, int, int, const char *))0x40012bd8)
#define INVERT     ((void (*)(void *, int, int, int, int, int))0x40012254)
#define ICON       ((void (*)(const void *, void *, int, int))0x400128a8)
#define RULE       ((void (*)(void *, int, int, int, int))0x40011910)
#define DOTH       ((void (*)(void *, int, int, int))0x40011a58)
#define VLINE      ((void (*)(void *, int, int, int, int))0x40011b94)
#define HLINE      ((void (*)(void *, int, int, int, int, int))0x40012004)
#define LIVE_TICKS 60				/* about 0.5 s */
#define VISIBLE    4				/* rows under the rule */
#define PITCH      8				/* pixels between rows */
#define MARGIN     6				/* the text's distance from the window's sides */

extern const u32 brain_icon[];

enum { K_HEAD, K_TEXT, K_COST, K_BAR, K_ITEM, K_TOGGLE, K_VALUE, K_LINE };	/* K_COST: text with a value; K_BAR: a processor's bar (arg 0..2); neither selectable; K_LINE: a selectable row that does nothing, its text and value like K_COST's (a log line, so the list scrolls with the cursor) */
struct srow { const char *label, *val; void (*act)(u32); u32 arg; u8 kind, on; };
#define SR_MAX 176
static struct srow sr[SR_MAX];
static u32 sn DATA, scur DATA, stop DATA;
static char slab[SR_MAX][16];			/* heading and template names */
static const char *const sc_title[SC_N] = { "PERFORMANCE", "REMIXES", "SETTINGS", "TEMPLATES", "ABOUT", "LOG", "TEMPLATE" };

static u32 sc_now(void)
{
	u32 st = STATEG;
	return st >= SC_BASE && st < SC_BASE + SC_N ? st - SC_BASE : SC_N;
}

static struct srow *add(u32 kind, const char *label, void (*act)(u32), u32 arg)
{
	struct srow *r = &sr[sn < SR_MAX ? sn++ : SR_MAX - 1];
	r->label = label;
	r->val = 0;
	r->act = act;
	r->arg = arg;
	r->kind = (u8)kind;
	r->on = 0;
	return r;
}

static int selectable(u32 i)
{
	return i < sn && sr[i].kind >= K_ITEM;
}

/* the actions of the template on its edit screen */
static void ted_name(u32 unused)
{
	trow_rename(unused);
}

/* back to TEMPLATES from the template's screen, a moment after the key's handler (a state opened
 * from it took no keys under the port): after NO (the stock path ran the exit member and opened
 * the menu's state 1) and after DELETE */
#define MENU_WIN (*(volatile u32 *)0x400cbf4c)		/* the menu's window; 0 once it is closed (0x40064bc0) */
static int back_timer DATA = -1;
static u8 back_mode;				/* 0 NO, 1 DELETE, 2 NO in a group */
static u32 back_ref DATA = 0xffffffff;		/* the template row the list's cursor returns to */

static void ask_save_cb(u32 answer)
{
	if (answer == 0)			/* YES */
		brain_post_template(0x8000000 | ted_ref);
	ted_dirty = 0;
}

static void back_cb(void)
{
	timer_off(&back_timer);
	if (back_mode == 1) {
		sc_open(SC_TPL);
		msg[0] = tname;
		msg[1] = "DELETED";
		POPUP("TEMPLATES", 2, msg, 0, 0);
		return;
	}
	if (!MENU_WIN || STATEG != 1) {		/* the menu was closed: the edits are kept */
		if (ted_dirty)
			brain_post_template(0x8000000 | ted_ref);
		ted_dirty = 0;
		ted_grp = G_TOP;
		ted_sub = G_TOP;
		return;
	}
	if (back_mode == 2) {			/* back one level, the cursor on the row left */
		if (ted_is(E_PART) && ted_sub != G_TOP) {
			sub_back = ted_sub;
			ted_sub = G_TOP;
		} else {
			grp_back = ted_grp;
			ted_grp = G_TOP;
		}
		sc_open(SC_TED);
		return;
	}
	back_ref = ted_ref;
	sc_open(SC_TPL);
	if (ted_dirty) {
		msg[0] = tname;
		msg[1] = "SAVE CHANGES?";
		POPUP("TEMPLATE", 2, msg, 3, (u32)ask_save_cb);
	}
}

/* the template a DELETE has posted and the card still holds: TEMPLATES leaves it out until the
 * engine task's write drops it (the list opens before the job is done) */
static u32 del_e DATA = 0xffff;
static u8 del_name[TPL_NAME];

static void ted_delete(u32 unused)
{
	(void)unused;
	const u8 *rec = card_nth(ted_ref >> 8, ted_ref & 0xff);
	if (rec) {
		const u8 *nm = rec + REC_HDR + align4(rec[1]) + 8;
		for (u32 k = 0; k < TPL_NAME; k++)
			del_name[k] = nm[k];
		del_e = ted_ref >> 8;
	}
	ted_gone = 1;
	ted_dirty = 0;
	brain_post_template(0x100000 | ted_ref);
	back_mode = 1;
	if (back_timer < 0)
		back_timer = TIMER(2, back_cb);
}

/* a PART template's group: MACHINES, the FX slots (and one slot's values), a track list and a track's
 * page for LFO, INPUT SRC and MIDI TRACKS, SCENES' two selections */
static void build_part_page(void)
{
	if (ted_grp == PP_MACH) {
		for (u32 t = 0; t < 8; t++)
			add(K_VALUE, pg_t[t], ted_mach, t)->val = mach_name[ted_part[0x22 + t] % 5];
		return;
	}
	if (ted_grp == PP_SCN) {
		for (u32 k = 0; k < 2; k++) {
			u32 n = put_dec(scn_val[k], (u32)(ted_part[0x10 + k] & 15) + 1, 0);
			scn_val[k][n] = 0;
			add(K_VALUE, k ? "SCENE B" : "SCENE A", ted_scn, k)->val = scn_val[k];
		}
		return;
	}
	if (ted_grp == PP_FX && ted_sub == G_TOP) {
		for (u32 g = 0; g < 16; g++)
			if (ted_has[PART_ID(g)])
				add(K_VALUE, pg_lab[g], ted_sub_open, g)->val = fx_name(g & 1, ted_vals[PART_ID(g)]);
		return;
	}
	if (ted_grp == PP_FX) {				/* a slot's values, by its effect's page */
		u32 b = PART_VAL(ted_sub);
		for (u32 i = b; i < b + 12; i++) {
			if (!ted_has[i] || ted_view.flat[i] == SKIP)
				continue;
			ted_text(i);
			if (ted_lab[i][0] == '-')
				continue;
			add(K_VALUE, ted_lab[i], ted_row, i)->val = ted_val[i];
		}
		if (sn == 0)
			add(K_TEXT, "NO VALUES", 0, 0);
		return;
	}
	if (ted_sub == G_TOP) {				/* the tracks: INPUT SRC lists the ones with a THRU, NEIGHBOR or PICKUP */
		for (u32 t = 0; t < 8; t++) {
			u32 m = ted_part[0x22 + t];
			if (ted_grp == PP_SRC) {
				if (m >= 2 && m <= 4)
					add(K_VALUE, pg_t[t], ted_sub_open, t)->val = mach_name[m];
			} else {
				add(K_ITEM, ted_grp == PP_MIDI ? pg_m[t] : pg_t[t], ted_sub_open, t);
			}
		}
		if (sn == 0)
			add(K_TEXT, "NO INPUT TRACKS", 0, 0);
		return;
	}
	pv_build();
	for (u32 i = 0; i < pv.n && sn + 2 < SR_MAX; i++) {
		if (!pv.key[i])
			continue;
		txt_slot(&pv, i, ted_part[pv.at[i] - WORKING], pv_lab[i], pv_val[i]);
		if (pv_lab[i][0] == '-')
			continue;
		add(K_VALUE, pv_lab[i], pv_row, i)->val = pv_val[i];
	}
	if (sn == 0)
		add(K_TEXT, "NO VALUES", 0, 0);
}

static void build_ted(void)
{
	u32 e = ted_ref >> 8;
	if (ted_gone) {
		add(K_TEXT, "DELETED", 0, 0);
		return;
	}
	const u8 *rec = card_nth(e, ted_ref & 0xff);
	if (!rec) {
		add(K_TEXT, "NO TEMPLATE", 0, 0);
		return;
	}
	if (ted_grp != G_TOP && e == E_PROJECT) {	/* a group's rows, as its stock screen draws them */
		for (u32 k = 0; k < PROW_N; k++)
			if (prow[k].grp == ted_grp && pr_has(&prow[k])) {
				pr_text(k);
				add(K_VALUE, prow[k].label ? prow[k].label : (const char *)CELL(prow[k].lab), ted_prow, k)->val = ted_val[k];
			}
		return;
	}
	if (ted_grp != G_TOP && e == E_PART) {		/* a group of the Part: what its section holds */
		build_part_page();
		return;
	}
	/* the actions, the same on every template's screen (SET AS DEFAULT where the target has a
	 * moment to take it: an effect's selection, a new project), then the values */
	add(K_ITEM, e == E_PROJECT ? "APPLY TO PROJECT" : e == E_PART ? "APPLY TO PART" : "APPLY TO...", trow_load, 0);
	if (can_default(e)) {
		if (tpl_is_default(e, rec))
			add(K_ITEM, "CLEAR DEFAULT", trow_cleardef, 0);
		else
			add(K_ITEM, "SET AS DEFAULT", trow_setdef, 0);
	}
	add(K_ITEM, "SAVE", ted_save, 0);
	add(K_VALUE, "RENAME", ted_name, 0)->val = tname;
	add(K_ITEM, "DELETE", ted_delete, 0);
	add(K_HEAD, "VALUES", 0, 0);
	if (e == E_PROJECT)
		for (u32 g = 0; g < PG_N; g++) {
			u32 any = 0;
			for (u32 k = 0; k < PROW_N; k++)
				any |= prow[k].grp == g && pr_has(&prow[k]);
			if (any)
				add(K_ITEM, pg_name[g], ted_open, g);
		}
	if (e == E_PART && ted_origin[0])
		add(K_COST, "TAKEN IN", 0, 0)->val = ted_origin;
	if (e == E_PART)
		for (u32 g = 0; g < PP_N; g++)
			add(K_ITEM, pp_name[g], ted_open, g);
	for (u32 i = 0; i < ted_view.n && sn + 6 < SR_MAX && e < E_PROJECT; i++) {
		if (!ted_has[i] || !ted_view.key[i])
			continue;
		ted_text(i);
		if (ted_lab[i][0] == '-')			/* an empty encoder position */
			continue;
		add(K_VALUE, ted_lab[i], ted_row, i)->val = ted_val[i];
	}
}

/* LEFT and RIGHT or the encoder: the value of the row under the cursor, within its range */
static void ted_adjust(int delta)
{
	if (!selectable(scur))
		return;
	if (sr[scur].act == ted_prow) {
		pr_step(sr[scur].arg, delta, 0);
		sc_rebuild();
		return;
	}
	if (sr[scur].act == ted_sub_open && ted_is(E_PART) && ted_grp == PP_FX) {
		part_fx_step(sr[scur].arg, delta);
		sc_rebuild();
		return;
	}
	if (sr[scur].act == pv_row || sr[scur].act == ted_mach || sr[scur].act == ted_scn) {	/* a byte of the Part image */
		u32 a = sr[scur].arg, off, lo = 0, hi = 255;
		if (sr[scur].act == pv_row) {
			off = pv.at[a] - WORKING;
			lo = pv.lo[a];
			hi = pv.hi[a];
		} else if (sr[scur].act == ted_mach) {
			off = 0x22 + a;
			hi = 4;
		} else {
			off = 0x10 + a;
			hi = 15;
		}
		int v = (int)ted_part[off] + delta;
		u8 nv = (u8)(v < (int)lo ? lo : v > (int)hi ? hi : v);
		if (nv != ted_part[off])
			ted_dirty = 1;
		ted_part[off] = nv;
		sc_rebuild();
		return;
	}
	if (sr[scur].act != ted_row)
		return;
	u32 i = sr[scur].arg;
	int v = (int)ted_vals[i] + delta;
	u8 nv = (u8)(v < ted_view.lo[i] ? ted_view.lo[i] : v > ted_view.hi[i] ? ted_view.hi[i] : v);
	if (nv != ted_vals[i])
		ted_dirty = 1;
	ted_vals[i] = nv;
	if (ted_is(E_PART))
		part_put(i);
	sc_rebuild();
}

/* ---- MIDI: the log switch, the log file, the last messages ------------------ */

#define MON_N 24
static char mon_buf[MON_N][32];
static u32 mon_n;

static void tog_log(u32 unused)
{
	(void)unused;
	brain_v_octabam_brain_1 ^= 1;
	brain_post_settings();
}

static void tog_ev(u32 unused)
{
	(void)unused;
	brain_v_octabam_brain_3 ^= 1;
	brain_post_settings();
}

static void midi_write(u32 unused)
{
	(void)unused;
	brain_menu_log(0);
}

/* the last messages, newest first, decoded */
static void mon_update(void)
{
	mon_n = 0;
	if (!brain_v_octabam_brain_1) {
		put_s(mon_buf[0], "MIDI LOG IS OFF");
		return;
	}
	if (!dbg_seq) {
		put_s(mon_buf[0], "NO MESSAGES YET");
		return;
	}
	char t[32];
	for (u32 i = 0; i < MON_N && i < dbg_seq; i++) {
		const struct dbg_ent *e = &dbg_ring[(dbg_seq - 1 - i) % LOG_N];
		u32 n = midi_text(t, e);
		t[n] = 0;
		for (u32 j = 0; j < 32; j++)
			mon_buf[i][j] = 0;
		put_s(mon_buf[i], t);
		mon_n++;
	}
}

/* ---- DEFAULTS --------------------------------------------------------------- */


static void tog_apply(u32 unused)
{
	(void)unused;
	brain_v_octabam_brain_2 ^= 1;
	brain_post_settings();
}

/* ---- REMIXES (REMIX SWITCH's rows) ------------------------------------------- */

/* osw_pick reads the selection from brain_list's scroll + cursor */
static void rmx_pick(u32 i)
{
	brain_list.scroll = 0;
	brain_list.cursor = i;
	brain_rmx_rows[i].action(0);
}

/* a name without its spaces and case, the image's against a file's */
static int same_image(const char *a, const char *b)
{
	for (;;) {
		while (*a == ' ')
			a++;
		while (*b == ' ')
			b++;
		char x = *a >= 'a' && *a <= 'z' ? (char)(*a - 32) : *a, y = *b >= 'a' && *b <= 'z' ? (char)(*b - 32) : *b;
		if (x != y)
			return 0;
		if (!x)
			return 1;
		a++;
		b++;
	}
}

static void build_rmx(void)
{
	extern const char brain_img_name[];
	for (u32 i = 0; i < brain_rmx_n && i < 36; i++) {
		const struct mrow *m = &brain_rmx_rows[i];
		struct srow *r = add(m->action == NOOP ? K_TEXT : K_ITEM, m->label, rmx_pick, i);
		if (r->kind == K_ITEM && same_image(m->label, brain_img_name)) {
			r->kind = K_VALUE;			/* the image that is running */
			r->val = "RUNNING";
		}
	}
	if (!sn)
		add(K_TEXT, "NO REMIX SWITCH", 0, 0);
}

/* ---- SETTINGS: the other modules' settings (BRAIN's own are in DEFAULTS and MIDI) ---- */

static char setval[MAX_SET][12];

static void set_value(u32 i)
{
	const struct set_ent *e = &brain_set[i];
	int v = brain_values[i];
	char *o = setval[i];
	if (e->type == 1)
		o[put_s(o, v ? "ON" : "OFF")] = 0;
	else if (e->type == 2)
		o[put_s(o, (u32)v < e->nlabels ? e->labels[v] : "?")] = 0;
	else {
		u32 n = 0;
		if (v < 0) {
			o[n++] = '-';
			v = -v;
		}
		n += put_dec(o + n, (u32)v, 0);
		o[n] = 0;
	}
}

/* The usb module's pair rule: IN needs an output stream beside it (EP3 IN
 * is its implicit-feedback source). A move of entry i to value v is
 * refused when it leaves IN not OFF while TRACKS, MAIN, CUE and MASTER are
 * all off. The check is on the labels ("OFF") and the binary values (0),
 * not the indexes, which the store's lock file owns; no usb module in the
 * remix, no rule. */
static int label_is(const struct set_ent *e, int v, const char *s)
{
	const char *l = (u32)v < e->nlabels ? e->labels[v] : 0;
	if (!l)
		return 0;
	while (*s && *l == *s) {
		l++;
		s++;
	}
	return !*s && !*l;
}

/* A usb setting is off at value v: 0 for the Binary ones (MAIN, CUE,
 * MASTER), the "OFF" label for the Options (TRACKS, IN). */
static int usb_off(const struct set_ent *e, int v)
{
	if (e->type == 1)
		return v == 0;
	return label_is(e, v, "OFF");
}

/* the setting keys of modules/usb/manifest.py */
#define USB_KEY_TRACKS 7
#define USB_KEY_MAIN 8
#define USB_KEY_CUE 9
#define USB_KEY_MASTER 10
#define USB_KEY_IN 11

static int usb_pair_ok(u32 i, int v)
{
	int tr = -1, ma = -1, cu = -1, ms = -1, in = -1;
	for (u32 k = 0; k < brain_set_n && k < MAX_SET; k++) {
		const struct set_ent *e = &brain_set[k];
		if (!same_id(e->id, e->id_len, "octabam.usb", 11))
			continue;
		if (e->key == USB_KEY_TRACKS)
			tr = (int)k;
		else if (e->key == USB_KEY_MAIN)
			ma = (int)k;
		else if (e->key == USB_KEY_CUE)
			cu = (int)k;
		else if (e->key == USB_KEY_MASTER)
			ms = (int)k;
		else if (e->key == USB_KEY_IN)
			in = (int)k;
	}
	if (in < 0)
		return 1;
	int iv = i == (u32)in ? v : brain_values[in];
	if (usb_off(&brain_set[in], iv))
		return 1;
	if (tr >= 0 && !usb_off(&brain_set[tr], i == (u32)tr ? v : brain_values[tr]))
		return 1;
	if (ma >= 0 && !usb_off(&brain_set[ma], i == (u32)ma ? v : brain_values[ma]))
		return 1;
	if (cu >= 0 && !usb_off(&brain_set[cu], i == (u32)cu ? v : brain_values[cu]))
		return 1;
	if (ms >= 0 && !usb_off(&brain_set[ms], i == (u32)ms ? v : brain_values[ms]))
		return 1;
	return 0;
}

/* TRACKS and MASTER: MASTER is track 8's L/R, which TRACKS already carries
 * (the usb module's descriptors.py and cfgsel refuse the pair too). A move
 * of entry i to value v is refused when it leaves both on. */
static int usb_master_ok(u32 i, int v)
{
	int tr = -1, ms = -1;
	for (u32 k = 0; k < brain_set_n && k < MAX_SET; k++) {
		const struct set_ent *e = &brain_set[k];
		if (!same_id(e->id, e->id_len, "octabam.usb", 11))
			continue;
		if (e->key == USB_KEY_TRACKS)
			tr = (int)k;
		else if (e->key == USB_KEY_MASTER)
			ms = (int)k;
	}
	if (tr < 0 || ms < 0)
		return 1;
	if (usb_off(&brain_set[tr], i == (u32)tr ? v : brain_values[tr]))
		return 1;
	return usb_off(&brain_set[ms], i == (u32)ms ? v : brain_values[ms]);
}

/* The usb rules for a move of entry i to v: 1 when allowed, else 0 with the
 * popup shown. */
static int usb_move_ok(u32 i, int v)
{
	if (!usb_pair_ok(i, v)) {
		msg[0] = "IN NEEDS AN";
		msg[1] = "OUTPUT STREAM";
		POPUP("USB SETTINGS", 2, msg, 0, 0);
		return 0;
	}
	if (!usb_master_ok(i, v)) {
		msg[0] = "TRACKS HAS T8:";
		msg[1] = "NO MASTER";
		POPUP("USB SETTINGS", 2, msg, 0, 0);
		return 0;
	}
	return 1;
}

/* a setting that takes effect at the next boot was changed: leaving SETTINGS says so */
static u8 boot_pend;
static int boot_timer DATA = -1;

static void boot_toast_cb(void)
{
	timer_off(&boot_timer);
	msg[0] = "REBOOT TO";
	msg[1] = "APPLY CHANGES";
	POPUP("SETTINGS", 2, msg, 0, 0);
}

/* LEFT and RIGHT: one step down or up, stopping at the ends */
static void set_move(u32 i, int dir)
{
	const struct set_ent *e = &brain_set[i];
	int v = brain_values[i] + dir * (e->type == 3 ? e->step : 1);
	if (v < e->min)
		v = e->min;
	if (v > e->max)
		v = e->max;
	if (!usb_move_ok(i, v))
		return;
	brain_values[i] = v;
	boot_pend |= e->apply == 2;
	brain_post_settings();
}

static void set_step(u32 i)
{
	const struct set_ent *e = &brain_set[i];
	int v = brain_values[i] + (e->type == 3 ? e->step : 1);
	if (v > e->max)
		v = e->min;
	if (!usb_move_ok(i, v))
		return;
	brain_values[i] = v;
	boot_pend |= e->apply == 2;
	brain_post_settings();
}

static int own_setting(const struct set_ent *e)
{
	return same_id(e->id, e->id_len, "octabam.brain", 13);
}

static void build_set(void)
{
	const char *group = 0;
	u32 head = 0;
	add(K_HEAD, "BRAIN", 0, 0);
	add(K_TOGGLE, "APPLY DEFAULTS", tog_apply, 0)->on = (u8)brain_v_octabam_brain_2;
	u32 own = sn;
	for (u32 i = 0; i < brain_set_n && i < MAX_SET; i++) {
		const struct set_ent *e = &brain_set[i];
		if (own_setting(e))
			continue;
		if (e->group != group) {
			group = e->group;
			char *h = slab[head++ & 63];
			u32 k = 0;
			for (const char *c = group; *c && k < 15; c++)
				if (*c != '\027')
					h[k++] = *c;
			h[k] = 0;
			add(K_HEAD, h, 0, 0);
		}
		set_value(i);
		struct srow *r = add(e->type == 1 ? K_TOGGLE : K_VALUE, e->name, set_step, i);
		r->val = setval[i];
		r->on = e->type == 1 && brain_values[i];
	}
	if (sn == own)
		add(K_TEXT, "NO MODULE SETTINGS", 0, 0);
}

/* ---- TEMPLATES --------------------------------------------------------------- */

/* TEMPLATES: a tab per type of target, LEFT and RIGHT between them; each opens on a row to save
 * one (the page in front when it is of that type) and lists that type's templates */
#define TPL_TABS 4
static const char *const tpl_tab_name[TPL_TABS] = { "PART", "FX", "MIDI", "PROJECT" };
static u32 tpl_tab DATA;

/* the tab a target's templates are on: PART 0, an effect 1, MIDI TRACK 2, PROJECT 3; the page
 * templates (AMP, LFO, SRC) the page shortcut saves are on none */
static u32 tab_of_entry(u32 e)
{
	return e < ST_BASE ? 1 : e == ST_BASE + 2 ? 2 : e == E_PART ? 0 : e == E_PROJECT ? 3 : 9;	/* 9: page templates, by the shortcut */
}

static void build_tpl(void)
{
	static void (*const newf[TPL_TABS])(u32) = { tpl_new_part, tpl_new_fx, tpl_new_midi, tpl_new_project };
	static const char *const newl[TPL_TABS] = { "<NEW PART TEMPLATE>", "<NEW FX TEMPLATE>", "<NEW MIDI TEMPLATE>", "<NEW PROJECT TEMPLATE>" };
	add(K_ITEM, newl[tpl_tab], newf[tpl_tab], 0);
	if (del_e != 0xffff) {			/* the deleted template gone from the card: nothing left out */
		u32 j = 0;
		while (card_nth(del_e, j) && !same_name(card_nth(del_e, j), del_name))
			j++;
		if (!card_nth(del_e, j))
			del_e = 0xffff;
	}
	u8 done[ST_BASE + ST_N];
	for (u32 e = 0; e < sizeof done; e++)
		done[e] = 0;
	u32 name = 0, first = sn;
	for (;;) {
		/* the next section: the alphabetically first target of this tab not yet listed */
		u32 pick = 0xffff;
		for (u32 e = 0; e < ST_BASE + ST_N; e++) {
			if (done[e] || (e >= brain_fx_n && e < ST_BASE) || tab_of_entry(e) != tpl_tab || !card_nth(e, 0))
				continue;
			if (pick == 0xffff || str_lt(ent_name(e), ent_name(pick)))
				pick = e;
		}
		if (pick == 0xffff || sn + 2 > SR_MAX)
			break;
		done[pick] = 1;
		{					/* a heading per target; the other tabs have one target each */
			char *h = slab[name++];
			u32 k = 0;
			for (const char *c = ent_name(pick); *c && k < 15; c++)
				h[k++] = *c;
			h[k] = 0;
			add(K_HEAD, h, 0, 0);
		}
		u8 used[TPL_MAX];
		u32 kc = 0;
		while (kc < TPL_MAX && card_nth(pick, kc))
			used[kc++] = 0;
		for (u32 r = 0; r < kc && sn < SR_MAX && name < 64 + SR_MAX - 64; r++) {
			u32 best = 0xffff;
			for (u32 j = 0; j < kc; j++)
				if (!used[j] && (best == 0xffff || name_lt(tname_of(card_nth(pick, j)),
									   tname_of(card_nth(pick, best)))))
					best = j;
			used[best] = 1;
			if (pick == del_e && same_name(card_nth(pick, best), del_name))
				continue;
			char *t = slab[64 + (sn & 127)];
			trow_name(t, card_nth(pick, best));
			if (tpl_is_default(pick, card_nth(pick, best))) {	/* the target's default */
				u32 k2 = 0;
				while (t[k2])
					k2++;
				t[k2++] = ' ';
				t[k2++] = '*';
				t[k2] = 0;
			}
			add(K_ITEM, t, tpl_item, pick << 8 | best);
		}
	}
	if (sn == first)
		add(K_TEXT, "NO TEMPLATES", 0, 0);
}

/* ---- OTOP: LOAD METER's figures, bars and the cost of each effect ------------------ */

extern volatile u32 *const brain_lm;
extern volatile u32 *const brain_lmd;
static u32 load_peak_pct DATA, load_peak_us DATA;
static u32 load_dseq DATA, load_dbad DATA, load_ticks DATA;
static int load_now[3] DATA, load_pk[3] DATA;	/* percent; -1 before a sample, -2 when the records were all bad */

/* a core's frame in timer-0 counts, from LOAD METER's last record (nominal 36,256) */
static u32 load_period(u32 core)
{
	u32 p = brain_lmd ? brain_lmd[3 + 2 * core] : 0;
	return p ? p : 36256;
}

static void load_update(void)
{
	load_now[0] = load_pk[0] = load_now[1] = load_pk[1] = load_now[2] = load_pk[2] = -1;
	if (!brain_lm)
		return;
	u32 seq = brain_lm[0], win = brain_lm[1], sum = brain_lm[2], cnt = brain_lm[3], max = brain_lm[4];
	if (seq && win && cnt) {
		u32 pct = sum / (win / 100 ? win / 100 : 1), us = max / 132;
		if (pct > load_peak_pct)
			load_peak_pct = pct;
		if (us > load_peak_us)
			load_peak_us = us;
		load_now[0] = (int)pct;
		load_pk[0] = (int)load_peak_pct;
	}
	if (!brain_lmd)
		return;
	int fresh = brain_lmd[0] != load_dseq, bad = brain_lmd[1] != load_dbad;
	for (u32 core = 0; core < 2; core++) {
		const volatile u32 *now = brain_lmd + 2 + 2 * core, *pk = brain_lmd + 6 + 2 * core;
		if (brain_lmd[0] && fresh && now[1]) {
			load_now[1 + core] = (int)(now[0] * 100 / now[1]);
			load_pk[1 + core] = pk[1] ? (int)(pk[0] * 100 / pk[1]) : 0;
		} else if (brain_lmd[0] && bad) {
			load_now[1 + core] = -2;
		}
	}
	load_dseq = brain_lmd[0];
	load_dbad = brain_lmd[1];
	load_ticks++;
}

/* OTOP: one list under the rule, scrolled by UP and DOWN: a bar per processor, the
 * worst frame and the audio drops, then the cost of each effect slot, from the DSP cores' own timer 0
 * stamps around each FX1 and FX2 call (modules/load-meter dsp_meter.asm). LOAD
 * METER's lm_ot holds, per slot (0..7 core 0's, 8..15 core 1's: FX1 then FX2
 * of position 0, 1, 2, 3), the last, summed, counted and largest cost in timer-0
 * counts (CLK/2: 2 cycles; a frame is 16 samples, so cycles a sample = counts / 8).
 * Core 0 is payload A (tracks 5-8), core 1 payload B (tracks 1-4). The rows are
 * sorted by cost, a SYSTEM row per core is what its busy time holds beyond them. */
extern volatile u32 *const brain_lmo;		/* lm_ot: 16 x {last, sum, count, max}, then the reset flag; 0 without LOAD METER */
#define FX1_LIVE 0x80000ec4			/* the live FX1 id of each track; FX2's are 8 on */
#define FRAME_US 363			/* the frame interrupt's period, 1 / 2,756 Hz = 362.8 us */
#define OT_ROWS  18			/* effect rows: 16 slots and two SYSTEM rows */

static char ot_sum[32];			/* the summary line */
static char ot_pct[3][8];			/* the bars' percent text */
static char ot_lab[OT_ROWS + 6][22], ot_val[OT_ROWS + 6][12];

static u32 ot_cost(u32 slot)
{
	const volatile u32 *e = brain_lmo + 4 * slot;
	return e[2] ? e[1] / e[2] : 0;
}

/* a track's FX name: the descriptor's 12-character name (P + 9) */
static const char *fx_name(u32 fx, u32 id)
{
	const u8 *d = find((const u8 *const *)(fx ? FX2_IDS : FX1_IDS), id);
	return d ? (const char *)d + 9 : "NONE";
}

/* "996 22%": cycles a sample and the share of the core's frame; under 10% with a tenth ("49 0.6%") */
static void ot_val_text(char *o, u32 counts, u32 period)
{
	u32 n = put_dec(o, counts / 8, 0);			/* cycles a sample */
	n += put_s(o + n, " ");
	u32 tenths = period ? counts * 1000 / period : 0;
	if (tenths < 100) {
		n += put_dec(o + n, tenths / 10, 0);
		o[n++] = '.';
		n += put_dec(o + n, tenths % 10, 0);
	} else {
		n += put_dec(o + n, tenths / 10, 0);
	}
	o[n++] = '%';
	o[n] = 0;
}

static void build_load(void)
{
	static const char *const names[3] = { "CFIRE", "DSP0", "DSP1" };
	for (u32 r = 0; r < 3; r++) {
		u32 n = 0;
		if (load_now[r] == -1)
			n = put_s(ot_pct[r], "-");
		else if (load_now[r] == -2)
			n = put_s(ot_pct[r], "?");
		else {
			n = put_dec(ot_pct[r], (u32)load_now[r], 0);
			ot_pct[r][n++] = '%';
		}
		ot_pct[r][n] = 0;
		add(K_BAR, names[r], 0, r)->val = ot_pct[r];
	}
	/* the worst single run of the frame interrupt since opening, as a share of the
	 * frame (362.8 us), "OVER" at 100% */
	u32 n = put_s(ot_sum, "WORST FRAME ");
	if (!load_peak_us)
		n += put_s(ot_sum + n, "-");
	else if (load_peak_us * 100 / FRAME_US >= 100)
		n += put_s(ot_sum + n, "OVER");
	else {
		n += put_dec(ot_sum + n, load_peak_us * 100 / FRAME_US, 0);
		ot_sum[n++] = '%';
	}
	ot_sum[n] = 0;
	add(K_TEXT, ot_sum, 0, 0);
}

static void build_procs(void)
{
	u32 n;
	if (!brain_lmo) {
		add(K_TEXT, "NO LOAD METER", 0, 0);
		return;
	}
	u32 period[2] = { load_period(0), load_period(1) };
	/* the DSP busy line, then every slot and each core's remainder, by cost */
	struct { u32 cost; u8 slot; } it[OT_ROWS];
	u32 sum[2] = { 0, 0 };
	n = 0;
	for (u32 sl = 0; sl < 16; sl++) {
		u32 c = ot_cost(sl);
		sum[sl >> 3] += c;
		if (!brain_lmo[4 * sl + 2])
			continue;
		u32 at = n++;
		while (at && it[at - 1].cost < c) {
			it[at] = it[at - 1];
			at--;
		}
		it[at].cost = c;
		it[at].slot = (u8)sl;
	}
	for (u32 core = 0; core < 2; core++) {			/* the remainder: busy - the effects */
		u32 busy = brain_lmd && brain_lmd[17] ? brain_lmd[15 + core] / brain_lmd[17] : 0;
		u32 rest = busy > sum[core] ? busy - sum[core] : 0;
		if (!busy)
			continue;
		u32 at = n++;
		while (at && it[at - 1].cost < rest) {
			it[at] = it[at - 1];
			at--;
		}
		it[at].cost = rest;
		it[at].slot = (u8)(16 + core);
	}
	for (u32 i = 0; i < n && sn < OT_ROWS + 4; i++) {
		u32 sl = it[i].slot, k = sn;
		char *l = ot_lab[k];
		u32 c = sl & 16 ? sl & 1 : sl >> 3;
		if (sl >= 16) {
			put_s(l, c ? "SYSTEM B" : "SYSTEM A");
		} else {
			u32 pos = (sl & 7) >> 1, fx = sl & 1, track = (c ? 0 : 4) + pos;
			u32 m = put_s(l, "T");
			m += put_dec(l + m, track + 1, 0);
			m += put_s(l + m, fx ? " 2 " : " 1 ");
			m += put_s(l + m, fx_name(fx, *(volatile u8 *)(FX1_LIVE + 8 * fx + track)));
			l[m] = 0;
		}
		ot_val_text(ot_val[k], it[i].cost, period[c]);
		add(K_COST, l, 0, 0)->val = ot_val[k];
	}
	if (!n)
		add(K_TEXT, "NO COSTS YET", 0, 0);
}

/* ---- the sampler: the event log, the MIDI rate ------------------------------------
 * One soft timer (about 0.5 s) started by the first load runs for good: every
 * tick samples the processors (load_update) and notes the events below. The
 * time of an event is the tick count at 0.5 s a tick, the timer's nominal
 * period. */

enum { EV_OVER, EV_FULL, EV_SLOW, EV_N };
static u32 samples DATA;
static int samp_timer DATA = -1;
static u32 midi_prev DATA, midi_rate DATA, over_flag DATA, full_flag DATA;

#define EV_N_MAX 40
struct ev_ent { u32 t; u16 arg; u8 type, pad; };
static struct ev_ent evr[EV_N_MAX];
static u32 ev_count DATA;

static void ev_add(u32 type, u32 arg)
{
	if (!brain_v_octabam_brain_3)
		return;
	struct ev_ent *e = &evr[ev_count % EV_N_MAX];
	e->t = samples / 2;
	e->arg = (u16)(arg > 0xffff ? 0xffff : arg);
	e->type = (u8)type;
	ev_count++;
}

/* the card's commands: brain_ata_begin/end wrap the ATA dispatcher (hooks.s) */
#define DTCN3 (*(volatile u32 *)0xfc07c00c)	/* DMA timer 3, 132 MHz */
static u32 ata_t0 DATA, ata_cmds[3] DATA, ata_secs[3] DATA, ata_max_us DATA, ata_slow_ms DATA;
static u32 ata_op DATA, ata_sec DATA;

void brain_ata_begin(void)
{
	ata_op = *(volatile u8 *)0x46c8656d;
	ata_sec = *(volatile u8 *)0x46c8656c;
	ata_t0 = DTCN3;
}

void brain_ata_end(void)
{
	u32 us = (DTCN3 - ata_t0) / 132;
	u32 k = ata_op == 0x20 || ata_op == 0xc8 || ata_op == 0x24 || ata_op == 0x25 ? 0
	      : ata_op == 0x30 || ata_op == 0xca || ata_op == 0x34 || ata_op == 0x35 ? 1 : 2;
	ata_cmds[k]++;
	ata_secs[k] += k == 2 ? 0 : ata_sec ? ata_sec : 256;
	if (us > ata_max_us)
		ata_max_us = us;
	if (us > 100000 && us / 1000 > ata_slow_ms)
		ata_slow_ms = us / 1000;
}

/* the ColdFire tasks: hooks.s brain_sched charges the DMA timer 3 counts between scheduler
 * entries to the task that was running; every tick turns the counts since the last into
 * a share. The frame interrupt's time lands on whichever task it interrupted: it is shown
 * on its own row, and taken off the tasks in proportion to their shares, which assumes
 * it arrives independently of the task switches (inferred, not measured). */
#define CPU_N 12
extern volatile u32 brain_ts[2 * CPU_N];		/* {TCB, counts} per task, the last slot any other */
static const char *const cpu_name[CPU_N] = { "MIDI", "STORAGE", "KEYS", "UI", "TASK 91D18", "TASK 921C4",
	"TASK 9203C", "ENGINE", "TASK 98A5C", "SYS", "IDLE", "OTHER" };
static u32 cpu_prev[CPU_N] DATA, cpu_tenths[CPU_N] DATA, cpu_seen DATA;

static void cpu_update(void)
{
	u32 d[CPU_N], total = 0;
	for (u32 i = 0; i < CPU_N; i++) {
		u32 now = brain_ts[2 * i + 1];
		d[i] = now - cpu_prev[i];
		cpu_prev[i] = now;
		total += d[i] >> 8;
	}
	if (!cpu_seen) {			/* the first tick has no baseline */
		cpu_seen = 1;
		return;
	}
	u32 irq = load_now[0] > 0 ? (u32)load_now[0] * 10 : 0;
	for (u32 i = 0; i < CPU_N; i++)
		cpu_tenths[i] = total ? (d[i] >> 8) * 1000 / total * (1000 - (irq > 1000 ? 1000 : irq)) / 1000 : 0;
}

static void put_tenths(char *o, u32 tenths, u32 *n)
{
	*n += put_dec(o + *n, tenths / 10, 0);
	if (tenths < 100) {
		o[(*n)++] = '.';
		o[(*n)++] = (char)('0' + tenths % 10);
	}
}

static void samp(void)
{
	load_update();
	cpu_update();
	for (u32 c = 0; c < 3; c++) {
		int v = load_now[c];
		if (v >= 100 && !(full_flag >> c & 1))
			ev_add(EV_FULL, c);
		full_flag = v >= 100 ? full_flag | 1u << c : full_flag & ~(1u << c);
	}
	samples++;
	if (brain_lm && brain_lm[4] / 132 >= FRAME_US) {
		if (!over_flag)
			ev_add(EV_OVER, brain_lm[4] / 132);
		over_flag = 1;
	} else {
		over_flag = 0;
	}
	u32 mt = midi_cnt[0] + midi_cnt[1] + midi_cnt[2] + midi_cnt[3] + midi_cnt[4];
	midi_rate = (mt - midi_prev) * 2;
	midi_prev = mt;
	if (ata_slow_ms) {
		ev_add(EV_SLOW, ata_slow_ms);
		ata_slow_ms = 0;
	}
}

static void samp_start(void)
{
	if (samp_timer >= 0 && *(volatile u32 *)(TIMERS + (u32)samp_timer * 16 + 8) == (u32)samp)
		return;
	samp_timer = TIMER(LIVE_TICKS, samp);
}

static void put_clock(char *o, u32 secs, u32 *n)	/* H:MM:SS, or M:SS under an hour */
{
	u32 h = secs / 3600, m = secs / 60 % 60, s = secs % 60;
	if (h) {
		*n += put_dec(o + *n, h, 0);
		o[(*n)++] = ':';
		o[(*n)++] = (char)('0' + m / 10);
		o[(*n)++] = (char)('0' + m % 10);
	} else {
		*n += put_dec(o + *n, m, 0);
	}
	o[(*n)++] = ':';
	o[(*n)++] = (char)('0' + s / 10);
	o[(*n)++] = (char)('0' + s % 10);
	o[*n] = 0;
}

/* ---- IMAGE: this image's name, the check of the project's record, its modules ---- */

extern const char brain_img_name[];
extern const u32 brain_img_n;
extern const char *const brain_img[];		/* {key, author} pairs */
static char img_chk[2][24];

/* ABOUT: tabs IMAGE (its name), PROJECT (what the last load found) and MODULES, LEFT and RIGHT
 * between them */
static u32 about_tab DATA;
#define ABOUT_TABS 4
static const char *const about_name[ABOUT_TABS] = { "IMAGE", "PROJECT", "CARD", "MODULES" };
extern const char brain_img_remix[], brain_img_os[];
static char about_c[4][12];

static void build_image(void)
{
	if (about_tab == 0) {
		add(K_COST, "IMAGE", 0, 0)->val = brain_img_name;
		add(K_COST, "REMIX", 0, 0)->val = brain_img_remix;
		add(K_COST, "STOCK OS", 0, 0)->val = brain_img_os;
		add(K_COST, "MODULES", 0, 0)->val = about_c[3];
		about_c[3][put_num(about_c[3], brain_img_n)] = 0;
		return;
	}
	if (about_tab == 2) {			/* the card store: BRAIN/card.work */
		static const char *const st_txt[4] = { "NO FILE YET", "LOADED", "FROM card.strd", "DAMAGED" };
		u32 st = brain_counts[C_STATE];
		add(K_COST, "card.work", 0, 0)->val = st_txt[st & 3];
		u32 k = put_num(about_c[0], card_len / 1024);
		k += put_s(about_c[0] + k, " KB OF ");
		k += put_num(about_c[0] + k, BUF_LEN / 1024);
		about_c[0][k] = 0;
		add(K_COST, "SIZE", 0, 0)->val = about_c[0];
		about_c[1][put_num(about_c[1], card_tpls)] = 0;
		add(K_COST, "TEMPLATES", 0, 0)->val = about_c[1];
		about_c[2][put_num(about_c[2], card_defs)] = 0;
		add(K_COST, "DEFAULTS", 0, 0)->val = about_c[2];
		return;
	}
	if (about_tab == 3) {
		for (u32 i = 0; i < brain_img_n; i++)
			add(K_COST, brain_img[2 * i], 0, 0)->val = brain_img[2 * i + 1];
		return;
	}
	u32 changed = brain_pcounts[PC_MOVED] + brain_pcounts[PC_LAYOUT] + brain_pcounts[PC_GONE];
	const char *l1, *l2 = 0;
	if (brain_pcounts[PC_STATE] == 3) {
		l1 = "BRAIN FILES BAD";
	} else if (!brain_pcounts[PC_RECORD]) {
		l1 = "NO RECORD OF A SAVE";
	} else if (!changed) {
		l1 = "SAVED WITH THIS IMAGE";
	} else {
		u32 k = put_num(img_chk[0], changed);
		k += put_s(img_chk[0] + k, changed == 1 ? " EFFECT CHANGED" : " EFFECTS CHANGED");
		img_chk[0][k] = 0;
		l1 = img_chk[0];
		l2 = "SINCE THE SAVE";
	}
	add(K_TEXT, l1, 0, 0);
	if (l2)
		add(K_TEXT, l2, 0, 0);
	for (u32 i = 0; i < pc_nn; i++)
		add(K_COST, pc_nm[i], 0, 0)->val = pc_why[i] == 0 ? "MOVED" : pc_why[i] == 1 ? "LAYOUT" : "GONE";
}

static char cpu_val[CPU_N + 1][12];

/* a share in tenths of a percent: "35%", under 10% with a tenth ("0.6%") */
static void put_share(char *o, u32 tenths)
{
	u32 n = 0;
	put_tenths(o, tenths, &n);
	o[n++] = '%';
	o[n] = 0;
}

static void build_cpu(void)
{
	for (u32 i = 0; i <= CPU_N; i++)
		for (u32 j = 0; j < 12; j++)
			cpu_val[i][j] = 0;
	if (load_now[0] >= 0) {
		put_share(cpu_val[CPU_N], (u32)load_now[0] * 10);
		add(K_COST, "FRAME IRQ", 0, 0)->val = cpu_val[CPU_N];
	}
	u8 order[CPU_N];
	u32 n = 0;
	for (u32 i = 0; i < CPU_N; i++) {
		if (!cpu_tenths[i])
			continue;
		u32 at = n++;
		while (at && cpu_tenths[order[at - 1]] < cpu_tenths[i]) {
			order[at] = order[at - 1];
			at--;
		}
		order[at] = (u8)i;
	}
	for (u32 k = 0; k < n; k++) {
		put_share(cpu_val[order[k]], cpu_tenths[order[k]]);
		add(K_COST, cpu_name[order[k]], 0, 0)->val = cpu_val[order[k]];
	}
	if (!sn)
		add(K_TEXT, "NO SAMPLE YET", 0, 0);
}

/* ---- the PERFORMANCE tabs after DSP: MEM, CARD, MIDI, USB ---- */

static char tv[8][20];

static void tv_row(u32 i, const char *label, u32 v)
{
	put_dec(tv[i], v, 0);
	add(K_COST, label, 0, 0)->val = tv[i];
}

static void tv_mb(u32 i, const char *label, u32 pages)	/* a page is 6,144 B */
{
	u32 tenths = pages * 15 / 256, n = 0;
	n += put_dec(tv[i], tenths / 10, 0);
	tv[i][n++] = '.';
	tv[i][n++] = (char)('0' + tenths % 10);
	put_s(tv[i] + n, " MB");
	add(K_COST, label, 0, 0)->val = tv[i];
}

extern const u32 brain_dram[2];		/* the arena base after the reserve, the runtime's end */
#define STOCK_ARENA 0x40a955e0

/* bytes as "12 KB" or, from a MiB up, "3.4 MB" */
static void tv_bytes(u32 i, const char *label, u32 b)
{
	u32 n = 0;
	if (b >= 1048576) {
		u32 t = (b >> 10) * 10 / 1024;
		n += put_dec(tv[i], t / 10, 0);
		tv[i][n++] = '.';
		tv[i][n++] = (char)('0' + t % 10);
		put_s(tv[i] + n, " MB");
	} else {
		n += put_dec(tv[i], (b + 1023) >> 10, 0);
		put_s(tv[i] + n, " KB");
	}
	add(K_COST, label, 0, 0)->val = tv[i];
}

/* octabam's DRAM, from the build: the platform's reserve at the bottom of the audio
 * arena, the runtime (code, data, bss) linked at its start, and the rest of the
 * reserve (the loader stage, DRAM regions, fixed claims, page rounding); then the
 * audio page arena that is left (modules/memory/README.md) */
static void build_mem(void)
{
	u32 reserve = brain_dram[0] - STOCK_ARENA, runtime = brain_dram[1] - STOCK_ARENA;
	tv_bytes(5, "DRAM RESERVE", reserve);
	tv_bytes(6, "RUNTIME", runtime);
	tv_bytes(7, "STAGE, REGIONS", reserve > runtime ? reserve - runtime : 0);
	u32 used = *(volatile u32 *)0x8000691c, held = *(volatile u32 *)0x80006920, rec = 0;
	const volatile u16 *cnt = (const volatile u16 *)0x46c75e88;
	for (u32 i = 128; i < 136; i++)
		rec += cnt[i];
	tv_mb(0, "FLEX USED", used);
	tv_mb(1, "FLEX FREE", held > used ? held - used : 0);
	tv_mb(2, "RECORDERS", rec);
	tv_mb(3, "ARENA", held + rec);
	u32 n = put_dec(tv[4], held + rec ? (used + rec) * 100 / (held + rec) : 0, 0);
	tv[4][n++] = '%';
	tv[4][n] = 0;
	add(K_COST, "IN USE", 0, 0)->val = tv[4];
}

static void tv_kb(u32 i, const char *label, u32 cmds, u32 secs)
{
	u32 n = put_dec(tv[i], cmds, 0);
	n += put_s(tv[i] + n, " / ");
	n += put_dec(tv[i] + n, secs / 2, 0);
	put_s(tv[i] + n, " KB");
	add(K_COST, label, 0, 0)->val = tv[i];
}

static void build_card(void)
{
	tv_kb(0, "READS", ata_cmds[0], ata_secs[0]);
	tv_kb(1, "WRITES", ata_cmds[1], ata_secs[1]);
	u32 n = 0;
	put_tenths(tv[2], ata_max_us / 100, &n);
	put_s(tv[2] + n, " MS");
	add(K_COST, "SLOWEST", 0, 0)->val = tv[2];
}

static void build_midi_tab(void)
{
	tv_row(0, "MSGS A SEC", midi_rate);
	tv_row(1, "NOTES", midi_cnt[MC_NOTE]);
	tv_row(2, "CONTROLLERS", midi_cnt[MC_CC]);
	tv_row(3, "PROGRAM", midi_cnt[MC_PGM]);
	tv_row(4, "BEND, PRESSURE", midi_cnt[MC_BEND]);
	tv_row(5, "SYSTEM", midi_cnt[MC_SYS]);
	tv_row(6, "CLOCK", midi_cnt[MC_CLK]);
}

extern volatile u32 *const brain_usb[4];	/* usbaudio_underruns, usbaudio_overruns, in_counters, usbmidi_tx_drops; 0 without the module */

static void tv_usb(u32 i, const char *label, const volatile u32 *p)
{
	if (p)
		tv_row(i, label, *p);
}

static void build_usb(void)
{
	tv_usb(0, "AUDIO OUT UNDER", brain_usb[0]);
	tv_usb(1, "AUDIO OUT OVER", brain_usb[1]);
	tv_usb(2, "AUDIO IN UNDER", brain_usb[2] ? brain_usb[2] + 5 : 0);
	tv_usb(3, "AUDIO IN OVER", brain_usb[2] ? brain_usb[2] + 6 : 0);
	tv_usb(4, "MIDI OUT DROPS", brain_usb[3]);
	if (!sn)
		add(K_TEXT, "NOT IN THIS IMAGE", 0, 0);
}

/* ---- LOG: what happened, newest first, with the uptime it happened at ---- */

static char log_lab[EV_N_MAX][24], log_val[EV_N_MAX][8];

static void build_events(void)
{
	static const char *const what[EV_N] = { "FRAME OVER", "CPU FULL", "CARD SLOW" };
	add(K_TOGGLE, "EVENT LOG", tog_ev, 0)->on = (u8)brain_v_octabam_brain_3;
	add(K_HEAD, "EVENTS", 0, 0);
	if (!ev_count) {
		add(K_TEXT, "NO EVENTS YET", 0, 0);
		return;
	}
	u32 n = ev_count < EV_N_MAX ? ev_count : EV_N_MAX;
	for (u32 i = 0; i < n; i++) {
		const struct ev_ent *e = &evr[(ev_count - 1 - i) % EV_N_MAX];
		u32 k = 0;
		put_clock(log_lab[i], e->t, &k);
		log_lab[i][k++] = ' ';
		put_s(log_lab[i] + k, what[e->type]);
		log_val[i][0] = 0;
		if (e->type == EV_OVER)
			put_s(log_val[i] + put_dec(log_val[i], e->arg, 0), "US");
		else if (e->type == EV_SLOW)
			put_s(log_val[i] + put_dec(log_val[i], e->arg, 0), "MS");
		else if (e->type == EV_FULL)
			put_s(log_val[i], e->arg == 0 ? "CFIRE" : e->arg == 1 ? "DSP0" : "DSP1");
		add(K_LINE, log_lab[i], 0, 0)->val = log_val[i];
	}
}

static void build_midilog(void)
{
	add(K_TOGGLE, "MIDI LOG", tog_log, 0)->on = (u8)brain_v_octabam_brain_1;
	add(K_ITEM, "WRITE DEBUG LOG", midi_write, 0);
	add(K_HEAD, "MESSAGES", 0, 0);
	mon_update();
	if (!mon_n)
		add(K_TEXT, mon_buf[0], 0, 0);
	for (u32 i = 0; i < mon_n; i++)
		add(K_LINE, mon_buf[i], 0, 0);
}

/* LOG: tabs EVENTS and MIDI, LEFT and RIGHT between them, a checkbox at the top of each */
static u32 log_tab DATA;
#define LOG_TABS 2
static const char *const log_name[LOG_TABS] = { "EVENTS", "MIDI" };

static void build_logscr(void)
{
	if (log_tab == 0)
		build_events();
	else
		build_midilog();
}

/* ---- the engine ---------------------------------------------------------------- */

static int live_timer DATA = -1;

/* the screens that only show: UP and DOWN scroll them, no cursor */
static int scroll_only(u32 sc)
{
	return sc == SC_PERF || sc == SC_IMG;
}

/* PERFORMANCE: LOAD (the processors), CPU (each ColdFire task), DSP (each effect's cost), MEM, CARD, MIDI, USB;
 * LEFT and RIGHT move between them, the title names the one in view */
static u32 perf_tab DATA;
#define PERF_TABS 7
static const char *const perf_name[PERF_TABS] = { "LOAD", "CPU", "DSP", "MEM", "CARD", "MIDI", "USB" };
static char perf_title[16];

static void build_perf(void)
{
	for (u32 i = 0; i < 8; i++)
		for (u32 j = 0; j < 20; j++)
			tv[i][j] = 0;
	switch (perf_tab) {
	case 0: build_load(); break;
	case 1: build_cpu(); break;
	case 2: build_procs(); break;
	case 3: build_mem(); break;
	case 4: build_card(); break;
	case 5: build_midi_tab(); break;
	default: build_usb(); break;
	}
}

static void sc_build(void)
{
	sn = 0;
	switch (sc_now()) {
	case SC_PERF: build_perf(); break;
	case SC_RMX: build_rmx(); break;
	case SC_SET: build_set(); break;
	case SC_TPL: build_tpl(); break;
	case SC_IMG: build_image(); break;
	case SC_LOG: build_logscr(); break;
	case SC_TED: build_ted(); break;
	default: break;
	}
}

static void sc_fix(void)
{
	if (scur >= sn)
		scur = sn ? sn - 1 : 0;
	/* a heading directly above the cursor row is shown with it */
	u32 want = scur > 0 && sr[scur - 1].kind == K_HEAD ? scur - 1 : scur;
	if (want < stop)
		stop = want;
	if (scur >= stop + VISIBLE)
		stop = scur + 1 - VISIBLE;
}

static void sc_rebuild(void)
{
	if (sc_now() == SC_N)
		return;
	sc_build();
	sc_fix();
}

/* the cursor to the next selectable row in direction d; it stops at the
 * first and the last (no wrapping) */
static u8 manual DATA;			/* the list was scrolled past its cursor row: the tick leaves it there */

static void sc_move(int d)
{
	int i = (int)scur, moved = 0;
	for (i += d; i >= 0 && i < (int)sn; i += d)
		if (selectable((u32)i)) {
			scur = (u32)i;
			moved = 1;
			break;
		}
	if (moved) {
		manual = 0;
		sc_fix();
	} else if (d < 0 && stop > 0) {		/* no row above: the rows above scroll into view */
		stop--;
		manual = 1;
	} else if (d > 0 && stop + VISIBLE < sn) {			/* none below: the rows below */
		stop++;
		manual = 1;
	}
}

/* the screens with a cursor that redraw every half second: their lists change under the
 * engine task's writes (a stored default, a template) or a log */
static int cursor_live(u32 sc)
{
	return sc == SC_LOG || sc == SC_TPL || sc == SC_TED;
}

static void sc_tick(void)
{
	if (live_timer < 0)
		return;
	u32 sc = sc_now();
	if (!cursor_live(sc) && (!scroll_only(sc) || sc == SC_IMG)) {
		*(volatile u32 *)(TIMERS + (u32)live_timer * 16 + 8) = 0;	/* not re-linked */
		live_timer = -1;
		return;
	}
	if (cursor_live(sc)) {
		sc_build();
		if (manual) {
			if (stop + VISIBLE > sn)
				stop = sn > VISIBLE ? sn - VISIBLE : 0;
		} else {
			sc_fix();
		}
	} else {
		sc_build();
		if (stop + VISIBLE > sn)
			stop = sn > VISIBLE ? sn - VISIBLE : 0;
	}
	MENU_REDRAW();
}

/* the cursor on the first selectable row, the list at its top */
static void sc_home(void)
{
	manual = 0;
	scur = 0;
	stop = 0;
	for (u32 i = 0; i < sn; i++)
		if (selectable(i)) {
			scur = i;
			break;
		}
	sc_fix();
}

static void sc_open(u32 sc)
{
	OPEN_STATE(SC_BASE + sc);
}

void brain_scr_enter(void)
{
	u32 sc = sc_now();
	if (live_timer >= 0) {
		UNTIMER(live_timer);
		live_timer = -1;
	}
	if (sc == SC_LOG)
		log_tab = 0;
	if (sc == SC_PERF)
		perf_tab = 0;
	if (sc == SC_IMG)
		about_tab = 0;
	sc_build();
	sc_home();
	if (sc == SC_TPL && back_ref != 0xffffffff) {	/* back from a template's screen: its row */
		for (u32 i = 0; i < sn; i++)
			if (sr[i].act == tpl_item && sr[i].arg == back_ref) {
				scur = i;
				sc_fix();
				break;
			}
		back_ref = 0xffffffff;
	}
	if (sc == SC_TED && grp_back != G_TOP) {	/* back from a group: its row */
		for (u32 i = 0; i < sn; i++)
			if (sr[i].act == ted_open && sr[i].arg == grp_back) {
				scur = i;
				sc_fix();
				break;
			}
		grp_back = G_TOP;
	}
	if (sc == SC_TED && sub_back != G_TOP) {	/* back from a slot or track: its row */
		for (u32 i = 0; i < sn; i++)
			if (sr[i].act == ted_sub_open && sr[i].arg == sub_back) {
				scur = i;
				sc_fix();
				break;
			}
		sub_back = G_TOP;
	}
	if (sc == SC_PERF) {
		if (brain_lmo)
			brain_lmo[64] = 1;			/* the effect costs start again */
		load_peak_pct = load_peak_us = 0;
		load_ticks = 0;
		if (brain_lmd) {
			brain_lmd[12] = 1;			/* the DSP peaks start again */
			load_dseq = brain_lmd[0];
			load_dbad = brain_lmd[1];
		}
		load_update();
	}
	if (cursor_live(sc) || (scroll_only(sc) && sc != SC_IMG))
		live_timer = TIMER(LIVE_TICKS, sc_tick);
}

void brain_scr_exit(void)
{
	if (live_timer >= 0) {
		UNTIMER(live_timer);
		live_timer = -1;
	}
	if (sc_now() == SC_SET && boot_pend && boot_timer < 0) {
		boot_pend = 0;
		boot_timer = TIMER(2, boot_toast_cb);
	}
	if (sc_now() == SC_TED && !ted_gone && back_timer < 0) {	/* NO, or the menu closing: back_cb tells */
		back_mode = ted_grp == G_TOP ? 0 : 2;
		back_timer = TIMER(2, back_cb);
	}
}

/* the screens with tabs: the tab in view, their count and names */
static u32 *tab_of(u32 sc)
{
	return sc == SC_PERF ? &perf_tab : sc == SC_LOG ? &log_tab : sc == SC_TPL ? &tpl_tab : sc == SC_IMG ? &about_tab : 0;
}
static u32 tabs_of(u32 sc)
{
	return sc == SC_PERF ? PERF_TABS : sc == SC_LOG ? LOG_TABS : sc == SC_TPL ? TPL_TABS : ABOUT_TABS;
}
static const char *tab_name(u32 sc, u32 t)
{
	return sc == SC_PERF ? perf_name[t] : sc == SC_LOG ? log_name[t] : sc == SC_TPL ? tpl_tab_name[t] : about_name[t];
}

void brain_scr_key(u32 code, u32 pressed)
{
	(void)pressed;
	u32 sc = sc_now();
	if (sc == SC_TED && (code == 0x34 || code == 0x21)) {
		ted_adjust(code == 0x21 ? 1 : -1);
		return;
	}
	if (sc == SC_SET && (code == 0x34 || code == 0x21) && selectable(scur) && sr[scur].act == set_step) {
		set_move(sr[scur].arg, code == 0x21 ? 1 : -1);
		sc_rebuild();
		return;
	}
	if (tab_of(sc) && (code == 0x34 || code == 0x21)) {
		u32 *tab = tab_of(sc), tabs = tabs_of(sc);
		if (code == 0x34 && *tab > 0)
			(*tab)--;
		else if (code == 0x21 && *tab + 1 < tabs)
			(*tab)++;
		sc_build();
		sc_home();
		return;
	}
	if (scroll_only(sc_now())) {		/* the list scrolls, no cursor */
		if (code == 0x33 && stop > 0)
			stop--;
		else if (code == 0x20 && stop + VISIBLE < sn)
			stop++;
		return;
	}
	if (code == 0x33)
		sc_move(-1);
	else if (code == 0x20)
		sc_move(1);
	else if (code == 0x31 && selectable(scur)) {
		struct srow *r = &sr[scur];
		if (r->act)
			r->act(r->arg);
		sc_rebuild();
	}
}

void brain_scr_enc(u32 index, int delta)
{
	(void)index;
	if (sc_now() == SC_TED) {			/* the encoder turns the value under the cursor */
		ted_adjust(delta > 8 ? 8 : delta < -8 ? -8 : delta);
		return;
	}
	if (scroll_only(sc_now())) {
		for (int k = delta < 0 ? -delta : delta; k > 0 && k < 8; k--) {
			if (delta < 0 && stop > 0)
				stop--;
			else if (delta > 0 && stop + VISIBLE < sn)
				stop++;
		}
		return;
	}
	for (int k = delta < 0 ? -delta : delta; k > 0 && k < 8; k--)
		sc_move(delta < 0 ? -1 : 1);
}

/* the checkbox: a 7 x 7 square, crossed when on (stock's mark) */
static void checkbox(void *ctx, int x, int y, int on)
{
	RULE(ctx, x, y - 1, x + 6, 1);
	RULE(ctx, x, y + 5, x + 6, 1);
	VLINE(ctx, x, y - 1, y + 5, 1);
	VLINE(ctx, x + 6, y - 1, y + 5, 1);
	if (on)
		for (int k = 0; k < 5; k++) {
			RULE(ctx, x + 1 + k, y + k, x + 1 + k, 1);
			RULE(ctx, x + 5 - k, y + k, x + 5 - k, 1);
		}
}

/* OTOP page 0: a bar per processor (the peak a mark on it), then two readouts */
#define BAR_X 56

static void load_bar(void *ctx, int w, int y, int now, int pk)
{
	int x0 = BAR_X, x1 = w - 6;
	RULE(ctx, x0, y, x1, 1);
	RULE(ctx, x0, y + 4, x1, 1);
	VLINE(ctx, x0, y, y + 4, 1);
	VLINE(ctx, x1, y, y + 4, 1);
	if (now < 0)
		return;
	int span = x1 - x0 - 2;
	int f = now > 100 ? 100 : now, p = pk > 100 ? 100 : pk;
	for (int x = x0 + 1; x < x0 + 1 + f * span / 100; x++)
		VLINE(ctx, x, y + 1, y + 3, 1);
	VLINE(ctx, x0 + 1 + p * span / 100, y - 1, y + 5, 1);
}

void brain_scr_draw(void *ctx)
{
	u32 sc = sc_now();
	if (!ctx || sc == SC_N)
		return;
	int w = (int)((u32 *)ctx)[0], h = (int)((u32 *)ctx)[1];
	int a2 = h - 20;
	const char *title = sc == SC_TED ? ted_title() : sc_title[sc];
	if (tab_of(sc)) {			/* the tab in view and its place */
		u32 tab = *tab_of(sc), tabs = tabs_of(sc);
		u32 n = put_s(perf_title, tab_name(sc, tab));
		perf_title[n++] = ' ';
		perf_title[n++] = (char)('1' + tab);
		perf_title[n++] = '/';
		perf_title[n++] = (char)('0' + tabs);
		perf_title[n] = 0;
		title = perf_title;
		int xr = w - 10, xl = xr - (int)TEXT_W(FONT, -1, title) - 7;
		for (int k = 0; k < 3; k++) {		/* a triangle each side: more tabs that way */
			if (tab + 1 < tabs)
				VLINE(ctx, xr + 2 + k, a2 + 2 + k, a2 + 6 - k, 1);
			if (tab > 0)
				VLINE(ctx, xl + 2 - k, a2 + 2 + k, a2 + 6 - k, 1);
		}
		DRAWSTR(FONT, ctx, xr - (int)TEXT_W(FONT, -1, title), a2 + 2, -1, title);
		title = 0;
	}
	if (title)
		DRAWSTR(FONT, ctx, w - 6 - (int)TEXT_W(FONT, -1, title), a2 + 2, -1, title);
	ICON(brain_icon, ctx, 6, a2);
	RULE(ctx, 4, a2 - 1, w - 6, 1);
	int rx = w - MARGIN - (sn > VISIBLE ? 4 : 0);	/* the right edge of the rows: the scroll bar is to its right */
	for (u32 j = 0; j < VISIBLE; j++) {
		u32 i = stop + j;
		if (i >= sn)
			break;
		const struct srow *r = &sr[i];
		int y = a2 - 9 - PITCH * (int)j;
		int x = MARGIN;
		if (r->kind == K_HEAD) {		/* ... NAME ........ as stock's separators */
			DOTH(ctx, x, y + 2, x + 8);
			x += 12;
		}
		if ((r->kind == K_VALUE || r->kind == K_COST || r->kind == K_LINE) && r->val) {
			/* the label gives way to the value at the right */
			char cut[24];
			u32 n = 0;
			int room = rx - (int)TEXT_W(FONT, -1, r->val) - 6 - x;
			while (r->label[n] && n < 23) {
				cut[n] = r->label[n];
				cut[n + 1] = 0;
				if ((int)TEXT_W(FONT, -1, cut) > room) {
					cut[n] = 0;
					break;
				}
				n++;
			}
			cut[n] = 0;
			DRAWSTR(FONT, ctx, x, y, -1, r->label[n] ? cut : r->label);
		} else
			DRAWSTR(FONT, ctx, x, y, -1, r->label);
		if (r->kind == K_BAR) {
			DRAWSTR(FONT, ctx, BAR_X - 4 - (int)TEXT_W(FONT, -1, r->val), y, -1, r->val);
			load_bar(ctx, w, y, load_now[r->arg], load_pk[r->arg]);
		} else if (r->kind == K_HEAD)
			DOTH(ctx, x + (int)TEXT_W(FONT, -1, r->label) + 4, y + 2, rx);
		else if (r->kind == K_TOGGLE)
			checkbox(ctx, rx - 6, y, r->on);
		else if ((r->kind == K_VALUE || r->kind == K_COST || r->kind == K_LINE) && r->val)
			DRAWSTR(FONT, ctx, rx - (int)TEXT_W(FONT, -1, r->val), y, -1, r->val);
		if (i == scur && selectable(i))
			INVERT(ctx, MARGIN - 2, y - 1, rx + 1, y + 5, -1);
	}
	if (sn > VISIBLE) {			/* the scroll thumb on the right edge */
		int lo = a2 - 9 - PITCH * (VISIBLE - 1) - 1, hi = a2 - 4, span = hi - lo;
		int len = span * VISIBLE / (int)sn, top = hi - (span - len) * (int)stop / (int)(sn - VISIBLE);
		VLINE(ctx, w - 6, lo, hi, 1);		/* the track; the window's border is at w - 3 */
		for (int k = -1; k <= 1; k++)
			VLINE(ctx, w - 6 + k, top - len, top, 1);
	}
}

/* FUNC + LEVEL push on an MKII (the record manifest.py adds to the FUNC
 * layer's keys): the OTOP screen is in MAIN MENU > BRAIN now */
void brain_load_chord(void)
{
	msg[0] = "PROJ > BRAIN";
	msg[1] = "> PERFORMANCE";
	POPUP("PERFORMANCE", 2, msg, 0, 0);
}
