/* CORE -- the OBAM store's run-time layers on the unit (docs/proposals/STORE.md).
 *
 * This increment: card-layer FX page defaults, read-only. At each project
 * load (and the power-up's bank load) core_load() puts every effect's
 * twelve descriptor defaults back to the image's values, reads
 * /OCTABAM/card.work (or card.strd, by the pair rule of section 6.2) and
 * writes each valid default record over its effect's descriptor bytes
 * (P+0x5e). The choosers and the new-part initialiser read those bytes when
 * they run (tools/verify/verify_descdefaults.py).
 *
 * The table core_fx[] (one entry per effect in the image: store id, fx id,
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

extern const struct fx_ent core_fx[];
extern const u32 core_fx_n;

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

/* counters, read by the gates (tools/verify/verify_core.py); all but
 * C_LOADS describe the last core_load() */
enum { C_LOADS, C_STATE, C_RECORDS, C_APPLIED, C_VALUES, C_SKIP_ID, C_SKIP_LAYOUT,
       C_SKIP_MODE, C_SKIP_CRC, C_SKIP_DUP, C_SKIP_VALUE, C_N };
/* C_STATE: 0 fresh, 1 card.work, 2 recovered from card.strd, 3 damaged */
u32 core_counts[C_N];

static u8 shadow[MAX_FX][2][12];
static u8 *desc[MAX_FX][2];
static u32 snapped;

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
	for (u32 i = 0; i < core_fx_n && i < MAX_FX; i++) {
		desc[i][0] = find((const u8 *const *)FX2_IDS, core_fx[i].fx_id);
		desc[i][1] = find((const u8 *const *)FX1_IDS, core_fx[i].fx_id);
		if (desc[i][1] == desc[i][0])
			desc[i][1] = 0;
		for (int t = 0; t < 2; t++)
			if (desc[i][t])
				for (int s = 0; s < 12; s++)
					shadow[i][t][s] = desc[i][t][0x5e + s];
	}
	snapped = 1;
}

static void restore(void)
{
	for (u32 i = 0; i < core_fx_n && i < MAX_FX; i++)
		for (int t = 0; t < 2; t++)
			if (desc[i][t])
				for (int s = 0; s < 12; s++)
					desc[i][t][0x5e + s] = shadow[i][t][s];
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

/* STORE.md section 7.1/7.2: 1 when buf[0..n) is a valid file. */
static int valid(u32 n)
{
	if (n < HDR || be32(buf) != 0x4f42414du || be16(buf + 4) != HDR || buf[6] != 1
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
	for (u32 i = 0; i < core_fx_n && i < MAX_FX; i++)
		if (same_id(rec + REC_HDR, idlen, core_fx[i].id, core_fx[i].id_len))
			return (int)i;
	return -1;
}

static void apply_record(const u8 *rec, int e)
{
	const struct fx_ent *f = &core_fx[e];
	u32 idlen = rec[1], plen = be32(rec + 8);
	const u8 *pay = rec + REC_HDR + align4(idlen);
	if (be16(rec + 2) != 1 || plen < 8)		/* schema major 1 */
		return;
	if (be16(pay) != 0 || be16(pay + 2) != NO_MODE) {
		core_counts[C_SKIP_MODE]++;
		return;
	}
	if (be32(pay + 4) != f->layout) {
		core_counts[C_SKIP_LAYOUT]++;
		return;
	}
	core_counts[C_APPLIED]++;
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
		if (type == T_BYTE && n == 1 && key) {
			u8 v = pay[at + head];
			for (int s = 0; s < 12; s++)
				if (f->keys[s] == key)
					for (int t = 0; t < 2; t++) {
						u8 *p = desc[e][t];
						if (!p)
							continue;
						if (v < be32(p + 0x9a + 4 * s)) {
							p[0x5e + s] = v;
							core_counts[C_VALUES]++;
						} else {
							core_counts[C_SKIP_VALUE]++;
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
		core_counts[C_RECORDS]++;
		if (p[0] != K_DEFAULT)
			continue;
		u32 plen = be32(p + 8);
		if (crc32(p + REC_HDR + align4(p[1]), plen) != be32(p + 12)) {
			core_counts[C_SKIP_CRC]++;
			continue;
		}
		int e = entry_of(p);
		if (e < 0) {
			core_counts[C_SKIP_ID]++;
			continue;
		}
		if (m < 64) {
			rec[m] = p;
			ent[m++] = e;
		}
	}
	(void)n;
	/* STORE.md section 7.7 rule 5: two records with one store id and
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
			core_counts[C_SKIP_DUP]++;
		else
			apply_record(rec[i], ent[i]);
	}
}

void core_load(void)
{
	/* the counters after C_LOADS describe the last load */
	for (int k = C_STATE; k < C_N; k++)
		core_counts[k] = 0;
	core_counts[C_LOADS]++;
	if (!snapped)
		snapshot();
	restore();
	u32 n = slurp("/OCTABAM/card.work");
	if (n && valid(n)) {
		core_counts[C_STATE] = 1;
		apply(n);
		return;
	}
	int work_present = n != 0;
	n = slurp("/OCTABAM/card.strd");
	if (n && valid(n)) {
		core_counts[C_STATE] = 2;
		apply(n);
		return;
	}
	core_counts[C_STATE] = (work_present || n) ? 3 : 0;
}
