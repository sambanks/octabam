/* BRAIN -- the brain's run-time layers on the unit (docs/proposals/BRAIN.md).
 *
 * This increment: card-layer FX page defaults, read-only. At each project
 * load (and the power-up's bank load) brain_load() puts every effect's
 * twelve descriptor defaults back to the image's values, reads
 * /BRAIN/card.work (or card.strd, by the pair rule of section 6.2) and
 * writes each valid default record over its effect's descriptor bytes
 * (P+0x5e). The choosers and the new-part initialiser read those bytes when
 * they run (tools/verify/verify_descdefaults.py).
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

struct fx_ent {			/* 36 bytes, as fx_inc() emits it */
	u32 layout;
	const char *id;
	u16 keys[12];
	u8 fx_id;
	u8 id_len;
	u16 pad;
};

extern const struct fx_ent brain_fx[];
extern const u32 brain_fx_n;
/* id, mode slot, nviews, then per view: mode, npairs, (slot, value)*;
 * 0xff ends it (modules/mode-defaults/manifest.py table_inc) */
extern u8 *const brain_modedef;		/* MODEDEF_TABLE or 0 (hooks.s) */
#define MODEDEF_TABLE brain_modedef

#define F_OPEN   ((int (*)(void *, const char *, const char *, void *, u32))0x40016864)
#define F_READ   ((int (*)(void *, void *, u32))0x40016564)
#define F_CLOSE  ((int (*)(void *))0x4001677c)
#define FX2_IDS  ((u8 **)0x400d5fdc)
#define FX1_IDS  ((u8 **)0x400d5f58)

#define MAX_FX    32
#define BUF_LEN   16384
#define HDR       32
#define REC_HDR   20
#define K_DEFAULT 2
#define T_BYTE    5
#define NO_MODE   0xffff

/* The platform loads a unit's image and leaves its .bss as the boot left
 * it (tools/remix/platform_build.py): state read before BRAIN first writes
 * it lives in .data. */
#define DATA __attribute__((section(".data")))

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
	const char *const *labels;
	const char *name, *group;
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
static void apply_settings(const u8 *rec)
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
			if (e->key != key || !same_id(rec + REC_HDR, idlen, e->id, e->id_len))
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

/* Every settings record of the file in buf: a store with two is skipped
 * (rule 5); the table first goes back to the layers below. */
static void load_settings(int have)
{
	for (u32 i = 0; i < brain_set_n && i < MAX_SET; i++)
		brain_values[i] = brain_set[i].def;
	for (int k = 0; k < C_SET_N; k++)
		brain_set_counts[k] = 0;
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
			apply_settings(p);
	}
}

/* ---- templates: the copy brain_load keeps (more below the menu) ---------- */

#define K_TEMPLATE  3
#define TPL_CACHE   4096
#define TPL_MAX     64
#define TPL_NAME    8

static u8 tpl_cache[TPL_CACHE];
static u32 tpl_len DATA;			/* bytes of records in tpl_cache */

/* the copy: every template record of the file in buf (called by brain_load
 * and after each template write) */
static void cache_templates(int have)
{
	tpl_len = 0;
	if (!have)
		return;
	u32 count = be16(buf + 10);
	for (u32 r = 0, at = HDR; r < count; r++, at += be32(buf + at + 16)) {
		const u8 *p = buf + at;
		u32 size = be32(p + 16);
		if (p[0] != K_TEMPLATE || tpl_len + size > TPL_CACHE)
			continue;
		if (crc32(p + REC_HDR + align4(p[1]), be32(p + 8)) != be32(p + 12))
			continue;
		for (u32 k = 0; k < size; k++)
			tpl_cache[tpl_len + k] = p[k];
		tpl_len += size;
	}
}

/* BRAIN's own settings (manifest.py: store octabam.brain) */
extern int brain_v_octabam_brain_1;		/* MIDI LOG: 1 = the debug log records */
extern int brain_v_octabam_brain_2;		/* CARD DEFAULTS: 1 = card defaults apply */

void brain_load(void)
{
	/* the counters after C_LOADS describe the last load */
	for (int k = C_STATE; k < C_N; k++)
		brain_counts[k] = 0;
	brain_counts[C_LOADS]++;
	if (!snapped)
		snapshot();
	restore();
	u32 n = slurp("/BRAIN/card.work");
	if (n && valid(n)) {
		brain_counts[C_STATE] = 1;
		load_settings(1);
		cache_templates(1);
		if (brain_v_octabam_brain_2)
			apply(n);
		return;
	}
	int work_present = n != 0;
	n = slurp("/BRAIN/card.strd");
	if (n && valid(n)) {
		brain_counts[C_STATE] = 2;
		load_settings(1);
		cache_templates(1);
		if (brain_v_octabam_brain_2)
			apply(n);
		return;
	}
	brain_counts[C_STATE] = (work_present || n) ? 3 : 0;
	load_settings(0);
	cache_templates(0);
}

/* ---- writing the card store ------------------------------------------------ */

#define MKDIR    (*(int (**)(const char *))0x46c8240a)	/* FS vtable: create a directory */
#define F_WRITE  ((int (*)(void *, const void *, u32))0x400166b8)
#define DBPTR    (*(u8 **)0x46c82456)			/* the current bank */
#define CUR_PART (*(volatile u8 *)0x80000003)
#define PART_LEN 6322
#define WORKING  0x8ed80

enum { S_SAVES, S_SAVE_ERR, S_STRD, S_STRD_ERR, S_N };
/* S_SAVE_ERR: last error of brain_save_default (0 none, 1 no effect, 2 card
 * store damaged, 3 too large, 4 write); S_STRD: card.strd copies written */
u32 brain_save_counts[S_N] DATA;

static u8 out[BUF_LEN];

static void put32(u8 *p, u32 v) { p[0] = v >> 24; p[1] = v >> 16; p[2] = v >> 8; p[3] = v; }
static void put16(u8 *p, u32 v) { p[0] = v >> 8; p[1] = v; }

static int write_file(const char *path, const u8 *data, u32 n)
{
	int ok = 0;
	if (F_OPEN(fobj, path, "w", iob, sizeof iob) < 0) {
		MKDIR("/BRAIN");			/* the first write on this card */
		if (F_OPEN(fobj, path, "w", iob, sizeof iob) < 0)
			return -1;
	}
	ok = F_WRITE(fobj, data, n) == 1;
	F_CLOSE(fobj);
	return ok ? 0 : -1;
}

/* The card store's current content in buf (BRAIN.md section 6.2): its
 * length, 0 when there is none, -1 when both copies are damaged (no
 * automatic write). */
static int current_store(void)
{
	u32 n = slurp("/BRAIN/card.work");
	if (n && valid(n))
		return (int)n;
	u32 work_present = n != 0;
	n = slurp("/BRAIN/card.strd");
	if (n && valid(n))
		return (int)n;
	return (work_present || n) ? -1 : 0;
}

/* SAVE AS DEFAULT: track t's FX1 (fx 0) or FX2 (fx 1) page in the current
 * Part becomes that effect's card-layer default. The record replaces the
 * effect's default record (no mode) in card.work; every other record keeps
 * its bytes. The descriptor takes the values at once. 0, or an error code
 * (also in brain_save_counts[S_SAVE_ERR]). */
static int write_default(u32 t, u32 fx, int clear);

/* out[HDR..at) holds `kept` records: the header, then card.work. */
static int write_store(u32 at, u32 kept)
{
	for (u32 k = 0; k < HDR; k++)
		out[k] = 0;
	put32(out, 0x4252414eu);			/* "BRAN": a brain file */
	put16(out + 4, HDR);
	out[6] = 1;					/* container 1.0, card .work */
	put16(out + 10, kept);
	put32(out + 12, at);
	for (u32 k = 0; k < 8 && "BRAIN"[k]; k++)
		out[20 + k] = "BRAIN"[k];
	put32(out + 16, crc32(out + 20, at - 20));
	return write_file("/BRAIN/card.work", out, at);
}

/* The settings records in card.work: one per store the table names, its
 * values the table's; the values with keys this image does not know are
 * kept from the record it replaces (rule 2), and every other record keeps
 * its bytes. 0, or an error code as write_default's. */
static int write_settings(void)
{
	int n = current_store();
	if (n < 0)
		return 2;
	u32 at = HDR, kept = 0;
	/* the kept records: everything but the settings of the stores we write */
	for (u32 r = 0, i = HDR; n && r < be16(buf + 10); r++, i += be32(buf + i + 16)) {
		const u8 *p = buf + i;
		u32 size = be32(p + 16), ours = 0;
		if (p[0] == K_SETTINGS)
			for (u32 e = 0; e < brain_set_n && e < MAX_SET; e++)
				ours |= same_id(p + REC_HDR, p[1], brain_set[e].id, brain_set[e].id_len);
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
		int first = 1;
		for (u32 f = 0; f < e; f++)
			if (same_id((const u8 *)brain_set[f].id, brain_set[f].id_len, s->id, s->id_len))
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
			if (!same_id((const u8 *)g->id, g->id_len, s->id, s->id_len))
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
					known |= brain_set[f].key == key
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
	return write_store(at, kept) < 0 ? 4 : 0;
}

int brain_save_default(u32 t, u32 fx)
{
	return write_default(t, fx, 0);
}

/* CLEAR DEFAULT: the effect's default record (no mode) leaves card.work and
 * the descriptor goes back to the image's values. */
int brain_clear_default(u32 t, u32 fx)
{
	return write_default(t, fx, 1);
}

static int write_default(u32 t, u32 fx, int clear)
{
	u8 *part = DBPTR + WORKING + (CUR_PART & 3) * PART_LEN;
	u32 id = part[fx ? 0x8 + t : t];
	int e = -1, err = 0;
	brain_save_counts[S_SAVES]++;
	if (!snapped)
		snapshot();
	for (u32 i = 0; i < brain_fx_n && i < MAX_FX; i++)
		if (brain_fx[i].fx_id == id && (desc[i][0] || desc[i][1]))
			e = (int)i;
	if (e < 0 || t > 7) {
		err = 1;
		goto done;
	}
	const struct fx_ent *f = &brain_fx[e];
	u8 vals[12];
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
	if (write_store(at, kept) < 0) {
		err = 4;
		goto done;
	}
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

/* SAVE PROJECT (the project store): card.work becomes card.strd, the
 * recovery copy (BRAIN.md section 6.2). A damaged or absent card.work is
 * not copied. */
void brain_card_store(void)
{
	u32 n = slurp("/BRAIN/card.work");
	if (!n || !valid(n))
		return;
	buf[8] = 1;					/* file kind: card .strd (outside the CRC) */
	if (write_file("/BRAIN/card.strd", buf, n) < 0)
		brain_save_counts[S_STRD_ERR]++;
	else
		brain_save_counts[S_STRD]++;
}

/* ---- the engine job: SAVE AS DEFAULT off the UI task ----------------------- */

#define Q_SEND   ((int (*)(void *, void *))0x40000c3c)	/* post a message to a queue */
#define ENGINE_Q ((void *)0x460d17ce)			/* the engine task's queue */
#define JOB_SAVE 0x41					/* above stock's 0..45 */

static u32 job_msg[4];		/* type byte first, as stock's records */
static u32 job_args;

/* From any task: SAVE AS DEFAULT for track t's FX1 (0) or FX2 (1), run by
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

/* From any task: CLEAR DEFAULT for track t's FX1 (0) or FX2 (1). */
void brain_post_clear(u32 t, u32 fx)
{
	job_args = (t & 7) | (fx ? 0x100 : 0) | 0x200;
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

static int write_template(int del, u32 t, u32 fx, u32 e, u32 i);

void brain_job(void)
{
	if (job_args & 0x100000)
		brain_save_counts[S_SAVE_ERR] = (u32)write_template(1, 0, 0, (job_args >> 8) & 0xff, job_args & 0xff);
	else if (job_args & 0x80000)
		brain_save_counts[S_SAVE_ERR] = (u32)write_template(0, job_args & 7, (job_args >> 8) & 1, 0, 0);
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
#define MIDI_MODE (*(volatile u8 *)0x80000012)
#define PAGE_KIND (*(volatile u32 *)0x460d1684)	/* 3 = FX1, 4 = FX2 */

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
	POPUP("SAVE AS DEFAULT", 2, msg, 0, 0);
}

void brain_menu_clear(u32 unused)
{
	int fx = menu_target();
	(void)unused;
	if (fx >= 0) {
		brain_post_clear(CUR_TRACK & 7, (u32)fx);
		msg[1] = "DEFAULT CLEARED";
	}
	POPUP("CLEAR DEFAULT", 2, msg, 0, 0);
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

void brain_midi_log(const u8 *m)
{
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

/* Text without stock's sprintf, which does not take %02X or field widths. */
static u32 put_s(char *o, const char *s) { u32 n = 0; while (s[n]) { o[n] = s[n]; n++; } return n; }
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

void brain_menu_log(u32 unused)
{
	(void)unused;
	brain_post_log();
	msg[0] = "WRITING THE LOG TO";
	msg[1] = "/BRAIN/DEBUG.TXT";
	POPUP("DEBUG LOG", 2, msg, 0, 0);
}

/* ---- the pane's sub-lists ------------------------------------------------ */

/* The stock menu engine is two levels deep: LEFT always focuses the root,
 * and YES on a list row runs its action (0x40064e64; docs/firmware/
 * MAINMENU.md section 4). So BRAIN's DEFAULTS, REMIXES and TOOLS rows each
 * point brain_list at another row array, and the redraw that follows every
 * key (0x40064d7c) shows it. Each sub-list's first row goes back to the
 * top; MAIN MENU's opening (REMIX SWITCH's osw_menu) resets to the top too. */

struct mrow { const char *label; void *window; void (*action)(u32); u32 getter; void *child; u32 id; };
struct mlist { u32 count, scroll, cursor, sel, visible, count2; struct mrow *rows; };

extern struct mlist brain_list;
extern struct mrow brain_top_rows[], brain_def_rows[], brain_tool_rows[], brain_rmx_rows[],
	brain_set_rows[];
void brain_post_settings(void);
extern u32 brain_rmx_n;			/* REMIXES' rows, the back row included (switch.s) */

static u32 brain_from DATA;		/* the top row the open sub-list came from */

static void show(struct mrow *rows, u32 n, u32 at)
{
	brain_list.rows = rows;
	brain_list.count = brain_list.count2 = n;
	brain_list.scroll = at >= brain_list.visible ? at - brain_list.visible + 1 : 0;
	brain_list.cursor = at - brain_list.scroll;
	brain_list.sel = at;
}

#define TOP_N   4				/* SETTINGS, DEFAULTS, REMIXES, TOOLS */
#define PANE_W  15				/* characters the list pane shows */
#define NOOP    ((void (*)(u32))0x400648f8)	/* stock's shared row action, `rts` */

void brain_menu_top(void)
{
	show(brain_top_rows, TOP_N, 0);
}

void brain_menu_back(u32 unused)
{
	(void)unused;
	show(brain_top_rows, TOP_N, brain_from);
}

void brain_open_defaults(u32 unused)
{
	(void)unused;
	brain_from = 1;
	show(brain_def_rows, 3, 1);
}

void brain_open_remixes(u32 unused)
{
	(void)unused;
	brain_from = 2;
	show(brain_rmx_rows, brain_rmx_n, brain_rmx_n > 1 ? 1 : 0);
}

void brain_open_tools(u32 unused)
{
	(void)unused;
	brain_from = 3;
	show(brain_tool_rows, 2, 1);
}

/* SETTINGS: the back row, then per module a heading (its key, no action)
 * and its settings, each label "NAME" with the value at the pane's right
 * edge. YES steps the value (Binary and Option wrap; a Number by its step,
 * from max back to min) and has the engine task write card.work. */

static char set_lbl[MAX_SET][PANE_W + 1];
static u8 set_row_ent[MAX_SET * 2 + 2];		/* row -> entry, 0xff: not a setting */
static char set_none[] = "NO SETTINGS";

static void put_row(struct mrow *r, const char *label, void (*action)(u32))
{
	r->label = label;
	r->window = 0;
	r->action = action;
	r->getter = 0;
	r->child = 0;
	r->id = 0;
}

static u32 slen(const char *s)
{
	u32 n = 0;
	while (s[n])
		n++;
	return n;
}

static void set_label(u32 i)
{
	const struct set_ent *e = &brain_set[i];
	char val[12];
	const char *vs = val;
	int v = brain_values[i];
	if (e->type == 1)
		vs = v ? "ON" : "OFF";
	else if (e->type == 2)
		vs = (u32)v < e->nlabels ? e->labels[v] : "?";
	else {
		u32 k = 0, a = (u32)(v < 0 ? -v : v);
		char tmp[8];
		do
			tmp[k++] = (char)('0' + a % 10);
		while ((a /= 10) && k < 7);
		u32 o = 0;
		if (v < 0)
			val[o++] = '-';
		while (k)
			val[o++] = tmp[--k];
		val[o] = 0;
	}
	u32 vl = slen(vs), nl = slen(e->name);
	if (vl > PANE_W - 2)
		vl = PANE_W - 2;
	if (nl > PANE_W - 1 - vl)
		nl = PANE_W - 1 - vl;
	char *o = set_lbl[i];
	u32 k = 0;
	for (; k < nl; k++)
		o[k] = e->name[k];
	for (; k < PANE_W - vl; k++)
		o[k] = ' ';
	for (u32 j = 0; j < vl; j++)
		o[k++] = vs[j];
	o[k] = 0;
}

void brain_set_row(u32 unused)
{
	(void)unused;
	u32 r = brain_list.sel;
	if (r >= sizeof set_row_ent || set_row_ent[r] == 0xff)
		return;
	u32 i = set_row_ent[r];
	const struct set_ent *e = &brain_set[i];
	int v = brain_values[i] + (e->type == 3 ? e->step : 1);
	if (v > e->max)
		v = e->min;
	brain_values[i] = v;
	set_label(i);
	brain_post_settings();
}

void brain_open_settings(u32 unused)
{
	(void)unused;
	struct mrow *row = brain_set_rows + 1;	/* row 0: the back row (manifest) */
	u32 n = 1, first = 0;
	const char *group = 0;
	for (u32 i = 0; i < sizeof set_row_ent; i++)
		set_row_ent[i] = 0xff;
	for (u32 i = 0; i < brain_set_n && i < MAX_SET; i++) {
		const struct set_ent *e = &brain_set[i];
		if (e->group != group) {
			group = e->group;
			put_row(row++, group, 0);
			n++;
		}
		set_label(i);
		put_row(row++, set_lbl[i], brain_set_row);
		set_row_ent[n] = (u8)i;
		if (!first)
			first = n;
		n++;
	}
	if (n == 1) {
		put_row(row, set_none, NOOP);
		n = 2;
		first = 1;
	}
	brain_from = 0;
	show(brain_set_rows, n, first);
}

/* ---- templates: lists, apply, save and delete (BRAIN.md sections 5.2, 9) ---- */

/* The i-th template record of effect entry e among the records at
 * recs[0..len), or 0. */
static const u8 *nth_in(const u8 *recs, u32 len, u32 e, u32 i)
{
	const struct fx_ent *f = &brain_fx[e];
	for (u32 at = 0; at < len; at += be32(recs + at + 16)) {
		const u8 *p = recs + at;
		const u8 *pay = p + REC_HDR + align4(p[1]);
		if (!same_id(p + REC_HDR, p[1], f->id, f->id_len) || be32(p + 8) < 16
		    || be32(pay + 4) != f->layout)
			continue;
		if (p[0] != K_TEMPLATE)
			continue;
		if (i-- == 0)
			return p;
	}
	return 0;
}

static const u8 *tpl_nth(u32 e, u32 i)
{
	return nth_in(tpl_cache, tpl_len, e, i);
}

static u32 tpl_count(u32 e)
{
	u32 n = 0;
	while (n < TPL_MAX && tpl_nth(e, n))
		n++;
	return n;
}

/* The track and page in view and their effect entry, or -1 (msg[] says
 * why); *t and *fx set. */
static int view_entry(u32 *t, u32 *fx)
{
	int f = menu_target();			/* 0 FX1, 1 FX2, -1 */
	if (f < 0)
		return -1;
	u8 *part = DBPTR + WORKING + (CUR_PART & 3) * PART_LEN;
	*t = CUR_TRACK & 7;
	*fx = (u32)f;
	u32 id = part[f ? 0x8 + *t : *t];
	for (u32 i = 0; i < brain_fx_n && i < MAX_FX; i++)
		if (brain_fx[i].fx_id == id)
			return (int)i;
	return -1;
}

/* ---- apply: the twelve slots through the stock paths -------------------- */

#define P1WRITE  ((void (*)(u32, u32, u32))0x40054cd8)	/* page-1 writer (track, flat, value) */
#define LIVEB    0x80000810				/* live lane: track*72 */

/* Track t's FX1 (fx 0) or FX2 (fx 1) page takes vals[12]: page 1 through
 * the stock writer, page 2 as the page-2 editors store it (modules/cc-map:
 * Part, shadow, live lane, the four dirty flags), each value clamped to the
 * descriptor's [min, min + count - 1]. */
static void apply_values(u32 t, u32 fx, const u8 *desc_p, const u8 *vals)
{
	u32 part = CUR_PART & 3;
	u8 *pb = DBPTR + part * PART_LEN;
	for (u32 s = 0; s < 12; s++) {
		int min = (int)be32(desc_p + 0x6a + 4 * s), cnt = (int)be32(desc_p + 0x9a + 4 * s);
		int v = vals[s];
		if (cnt <= 0)
			continue;
		if (v < min)
			v = min;
		if (v > min + cnt - 1)
			v = min + cnt - 1;
		if (s < 6) {
			P1WRITE(t, (fx ? 24 : 18) + s, (u32)v);
			continue;
		}
		u32 s2 = s - 6;
		pb[(fx ? 0x8f084 : 0x8f07e) + t * 30 + s2] = (u8)v;
		*(volatile u8 *)((fx ? 0x100a51d2 : 0x100a51cc) + part * PART_LEN + t * 30 + s2) = (u8)v;
		*(volatile u8 *)(LIVEB + t * 72 + (fx ? 0x38 : 0x32) + s2) = (u8)v;
	}
	DBPTR[0x95048] |= (u8)(1 << part);
	*(volatile u8 *)0x100b145e |= (u8)(1 << part);
	*(volatile u32 *)(DBPTR + 0x9b332) = 1;
	*(volatile u32 *)0x100f8598 = 1;
}

/* The twelve values of template record p for entry e: its Part bytes by
 * key; a slot it has no value for keeps track t's current byte. */
static void tpl_values(const u8 *p, u32 e, u32 t, u32 fx, u8 *vals)
{
	const struct fx_ent *f = &brain_fx[e];
	u8 *part = DBPTR + WORKING + (CUR_PART & 3) * PART_LEN;
	for (int s = 0; s < 6; s++) {
		vals[s] = part[0x11a + t * 24 + (fx ? 18 : 12) + s];
		vals[6 + s] = part[0x2fe + t * 30 + (fx ? 6 : 0) + s];
	}
	const u8 *pay = p + REC_HDR + align4(p[1]);
	u32 plen = be32(p + 8);
	for (u32 at = 16; at + 8 <= plen; at += 8) {
		u32 key = be16(pay + at);
		if (pay[at + 2] != T_BYTE || pay[at + 3] != 1 || !key)
			continue;
		for (int s = 0; s < 12; s++)
			if (f->keys[s] == key)
				vals[s] = pay[at + 4];
	}
}

/* ---- the engine task: a template saved or deleted ------------------------ */

/* Save (del 0): track t's FX1 (fx 0) or FX2 (fx 1) page becomes a new
 * template of its effect, named "TPL nn" with the lowest free nn. Delete
 * (del 1): the i-th template of entry e leaves card.work. Every other
 * record keeps its bytes. The copy is read back after the write. 0, or an
 * error code as write_default's. */
static int write_template(int del, u32 t, u32 fx, u32 e, u32 i)
{
	int n = current_store();
	if (n < 0)
		return 2;
	if (!del) {
		u8 *part = DBPTR + WORKING + (CUR_PART & 3) * PART_LEN;
		u32 id = part[fx ? 0x8 + t : t];
		e = MAX_FX;
		for (u32 k = 0; k < brain_fx_n && k < MAX_FX; k++)
			if (brain_fx[k].fx_id == id)
				e = k;
		if (e == MAX_FX || t > 7)
			return 1;
	}
	const struct fx_ent *f = &brain_fx[e];
	const u8 *drop = (del && n) ? nth_in(buf + HDR, (u32)n - HDR, e, i) : 0;
	if (del && !drop)
		return 1;
	u32 at = HDR, kept = 0;
	for (u32 r = 0, k = HDR; n && r < be16(buf + 10); r++, k += be32(buf + k + 16)) {
		const u8 *p = buf + k;
		u32 size = be32(p + 16);
		if (p == drop)
			continue;
		if (at + size > BUF_LEN)
			return 3;
		for (u32 b = 0; b < size; b++)
			out[at + b] = p[b];
		at += size;
		kept++;
	}
	if (!del) {
		/* the lowest free number among this effect's names */
		u32 num = 1;
		for (int again = 1; again && num < 100;) {
			again = 0;
			for (u32 j = 0; j < TPL_MAX; j++) {
				const u8 *q = nth_in(buf + HDR, n ? (u32)n - HDR : 0, e, j);
				if (!q)
					break;
				const u8 *nm = q + REC_HDR + align4(q[1]) + 8;
				if (nm[0] == 'T' && nm[1] == 'P' && nm[2] == 'L' && nm[3] == ' '
				    && (u32)((nm[4] - '0') * 10 + (nm[5] - '0')) == num) {
					num++;
					again = 1;
				}
			}
		}
		u8 vals[12];
		for (int s = 0; s < 6; s++) {
			u8 *part = DBPTR + WORKING + (CUR_PART & 3) * PART_LEN;
			vals[s] = part[0x11a + t * 24 + (fx ? 18 : 12) + s];
			vals[6 + s] = part[0x2fe + t * 30 + (fx ? 6 : 0) + s];
		}
		u32 nvals = 0;
		for (int s = 0; s < 12; s++)
			nvals += f->keys[s] != 0;
		u32 plen = 16 + 8 * nvals, size = REC_HDR + align4(f->id_len) + plen;
		if (at + size > BUF_LEN)
			return 3;
		u8 *r = out + at;
		for (u32 b = 0; b < size; b++)
			r[b] = 0;
		r[0] = K_TEMPLATE;
		r[1] = f->id_len;
		put16(r + 2, 1);			/* schema major 1, minor 0 */
		put32(r + 8, plen);
		put32(r + 16, size);
		for (u32 b = 0; b < f->id_len; b++)
			r[REC_HDR + b] = f->id[b];
		u8 *pay = r + REC_HDR + align4(f->id_len);
		put16(pay + 2, NO_MODE);		/* target 0, no mode */
		put32(pay + 4, f->layout);
		pay[8] = 'T'; pay[9] = 'P'; pay[10] = 'L'; pay[11] = ' ';
		pay[12] = (u8)('0' + num / 10);
		pay[13] = (u8)('0' + num % 10);
		u8 *v = pay + 16;
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
	}
	if (write_store(at, kept) < 0)
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
static const char *const page_lbl[5] = { "SAVE AS DEFAULT", "CLEAR DEFAULT", "SAVE TEMPLATE",
					 "LOAD TEMPLATE", "DELETE TEMPLATE" };
static void (*const page_fn[5])(u32) = { brain_menu_save, brain_menu_clear, brain_tpl_save,
					 brain_tpl_load, brain_tpl_delete };

void brain_page_func(void)
{
	pop_sel = 0;
	LISTPOP(5, 0, &pop_sel, page_lbl, (void *)page_fn);
}

static char tpl_lbl[TPL_MAX][TPL_NAME + 1];
static const char *tpl_lp[TPL_MAX];
static void (*tpl_fp[TPL_MAX])(u32);
static u32 tpl_e, tpl_t, tpl_fx, tpl_sel;

/* The names of the templates of the effect in view, each row calling fn;
 * their count (0: msg[] says why, the popup shown). */
static u32 tpl_list(const char *title, void (*fn)(u32))
{
	int e = view_entry(&tpl_t, &tpl_fx);
	if (e < 0) {
		POPUP(title, 2, msg, 0, 0);
		return 0;
	}
	tpl_e = (u32)e;
	u32 n = 0;
	for (; n < TPL_MAX; n++) {
		const u8 *p = tpl_nth(tpl_e, n);
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
		msg[1] = "FOR THIS EFFECT";
		POPUP(title, 2, msg, 0, 0);
	}
	return n;
}

static void tpl_apply_sel(u32 unused)
{
	(void)unused;
	const u8 *p = tpl_nth(tpl_e, tpl_sel);
	if (!p)
		return;
	if (!snapped)
		snapshot();
	const u8 *d = desc[tpl_e][tpl_fx] ? desc[tpl_e][tpl_fx] : desc[tpl_e][tpl_fx ^ 1];
	if (!d)
		return;
	u8 vals[12];
	tpl_values(p, tpl_e, tpl_t, tpl_fx, vals);
	apply_values(tpl_t, tpl_fx, d, vals);
}

static void tpl_delete_sel(u32 unused)
{
	(void)unused;
	brain_post_template(0x100000 | (tpl_e << 8) | (tpl_sel & 0xff));
	msg[0] = tpl_lbl[tpl_sel < TPL_MAX ? tpl_sel : 0];
	msg[1] = "DELETED";
	POPUP("DELETE TEMPLATE", 2, msg, 0, 0);
}

void brain_tpl_load(u32 unused)
{
	(void)unused;
	u32 n = tpl_list("LOAD TEMPLATE", tpl_apply_sel);
	if (n) {
		tpl_sel = 0;
		LISTPOP(n, 0, &tpl_sel, tpl_lp, (void *)tpl_fp);
	}
}

void brain_tpl_delete(u32 unused)
{
	(void)unused;
	u32 n = tpl_list("DELETE TEMPLATE", tpl_delete_sel);
	if (n) {
		tpl_sel = 0;
		LISTPOP(n, 0, &tpl_sel, tpl_lp, (void *)tpl_fp);
	}
}

void brain_tpl_save(u32 unused)
{
	(void)unused;
	u32 t, fx;
	if (view_entry(&t, &fx) < 0) {
		POPUP("SAVE TEMPLATE", 2, msg, 0, 0);
		return;
	}
	brain_post_template(0x80000 | t | (fx << 8));
	msg[1] = "TEMPLATE SAVED";
	POPUP("SAVE TEMPLATE", 2, msg, 0, 0);
}
