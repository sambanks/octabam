/* COPY PROJECT -- duplicate a project folder on the card without loading it.
 *
 * CHANGE project list > FUNC+BANK > COPY: the highlighted folder is the
 * source; name the copy, confirm. The live project stays loaded; the job
 * copies the source folder byte-for-byte (stock files and module sidecars)
 * into a new folder. (Was PROJECT > COPY PROJECT; re-homed for packing #931.)
 */

typedef unsigned char u8;
typedef unsigned int u32;

#define DIRSCAN  ((int (*)(const char *, void *, const char *, u32, u32))0x4007f598)
#define FCOPY    ((int (*)(const char *, const char *, u32))0x40016388)
#define NAMEED   ((void (*)(u32, const char *, char *, u32, void (*)(u32)))0x4007e664)
#define LISTPOP  ((void (*)(u32, u32, u32 *, const char *const *, void *))0x4006d94c)
#define POPUP    ((void (*)(const char *, u32, const char *const *, u32, u32))0x4006d57c)
#define MESSAGE  ((void (*)(const char *, u32))0x4005a2b8)
#define Q_SEND   ((int (*)(void *, void *))0x40000c3c)
/* Stock CHANGE/boot path: (name*) posts engine job 4 (LOAD PROJECT). */
#define POST_LOAD ((void (*)(const char *))0x40023c7c)
/* LISTPOP close; toast close; CHOOSE PROJECT window teardown (stock after load). */
#define LIST_CLOSE   ((void (*)(void))0x4006d754)
#define TOAST_CLOSE  ((void (*)(void))0x40056bec)
#define CHOOSE_CLOSE ((void (*)(void))0x40063ee4)
/* Stock CREATE / SAVE TO NEW name fill: strcpy "PROJECT ", date YYMMDD, strcat. */
#define STRCPY   ((void (*)(char *, const char *))0x40013f40)
#define STRCAT   ((void (*)(char *, const char *))0x40013f94)
#define GEN_DATE ((const char *(*)(void))0x40081b30)	/* -> "YYMMDD" at 0x460fab14 */
#define STR_PROJECT ((const char *)0x400b58ab)		/* "PROJECT " */
#define STR_NAMEED  ((const char *)0x400b5c8f)		/* "NAME THE NEW PROJECT" */

#define ENGINE_Q ((void *)0x460d17ce)
#define SET_PATH ((const char *)0x100f8480)
/* CREATE EMPTY's name-editor buffer (NAME THE NEW PROJECT). Not SAVE AS's. */
#define ED_BUF   ((char *)0x460e436a)
/* CHANGE list selection name (RENAME/DELETE handlers pea this; port: "FB"). */
#define SEL_NAME ((const char *)0x100f8378)
#define SCAN_STATE     ((u8 *)0x460e76ac)
#define SCAN_STATE_LEN 0x10154u
#define SCAN_MAX       1024
/* FS vtable: exists(path) -> 0 absent, 1 file, 2 folder (stems.s). */
#define FS_EXISTS_SLOT 0x46c823fa
#define FS_MKDIR_SLOT  0x46c8240a
/* docs/firmware/STORAGE.md: walk(path, &dirs, &files, mode, progress);
 * mode 0 unlinks every file and rmdirs every directory under path. */
#define WALK ((int (*)(const char *, u32 *, u32 *, u32, void *))0x40090a14)

#define NMAX   64
#define EMAX   256			/* entries kept per directory */
#define NLEN   32
#define DLBL   16			/* LISTPOP display cap (panel ~128 px) */
#define PATH_N 260
#define DEPTH  6

static int fs_exists(const char *path)
{
	return ((int (*)(const char *))*(u32 *)FS_EXISTS_SLOT)(path);
}

static int fs_mkdir(const char *path)
{
	return ((int (*)(const char *))*(u32 *)FS_MKDIR_SLOT)(path);
}

static void rm_tree(const char *path)
{
	u32 dirs = 0, files = 0;

	if (!path || !path[0])
		return;
	WALK(path, &dirs, &files, 0, 0);
}

static void cpy(char *d, const char *s, u32 n)
{
	u32 i = 0;
	for (; i + 1 < n && s[i]; i++)
		d[i] = s[i];
	d[i] = 0;
}

static void cat(char *d, const char *s, u32 n)
{
	u32 i = 0;
	while (i + 1 < n && d[i])
		i++;
	for (; i + 1 < n && *s; i++, s++)
		d[i] = *s;
	d[i] = 0;
}

static u32 len(const char *s)
{
	u32 n = 0;
	while (s[n])
		n++;
	return n;
}

static int eq(const char *a, const char *b)
{
	while (*a && *a == *b) {
		a++;
		b++;
	}
	return *a == *b;
}

static void join2(char *o, const char *a, const char *b)
{
	cpy(o, a, PATH_N);
	cat(o, "/", PATH_N);
	cat(o, b, PATH_N);
}

/* ---- scan state borrow (FAILURE_MODES: shared name pool) ----------------- */

static u8 scan_save[SCAN_STATE_LEN];
static u8 scan_tab[SCAN_MAX * 12];
static const char scan_ext[] = "";

/* Names + is_dir copied out of the pool before restore. */
static char ent_name[EMAX][NLEN + 1];
static u8 ent_dir[EMAX];
static u32 ent_n;

static void scan_borrow(void)
{
	u32 i;
	for (i = 0; i < SCAN_STATE_LEN; i++)
		scan_save[i] = SCAN_STATE[i];
}

static void scan_restore(void)
{
	/* The barrier in the loop keeps GCC from relating the two addresses: it compiled
	 * this copy to `move.b (%a2)+,(%a3,%a2.l)`, which assumes the destination uses a2
	 * before the increment; the port's CPU applies it first, so the restore landed one
	 * byte late (sambanks/octabam#1134). A barrier before the loop is not enough: the
	 * loop optimiser rebuilds dst - src at run time.
	 * tools/verify/tests/test_postinc.py refuses the form in any committed unit. */
	const u8 *src = scan_save;
	u32 i;
	for (i = 0; i < SCAN_STATE_LEN; i++) {
		SCAN_STATE[i] = *src++;
		__asm__("" : "+a"(src));
	}
}

/* Fill ent_* from dir; return count, -1 on scan error, -2 if a directory
 * has more than EMAX entries or a name longer than NLEN (silent truncate
 * would copy incompletely). Names are ours after return. */
static int scan_entries(const char *dir)
{
	int n, i;
	u32 kept = 0;

	scan_borrow();
	n = DIRSCAN(dir, scan_tab, scan_ext, 0, 0);
	if (n < 0) {
		scan_restore();
		ent_n = 0;
		return -1;
	}
	for (i = 0; i < n; i++) {
		u8 *rec = scan_tab + i * 12;
		const char *nm = *(const char **)rec;
		u32 is_dir = *(u32 *)(rec + 4);
		if (!nm || !nm[0] || eq(nm, ".") || eq(nm, ".."))
			continue;
		if (kept >= EMAX || len(nm) > NLEN) {
			scan_restore();
			ent_n = 0;
			return -2;
		}
		cpy(ent_name[kept], nm, NLEN + 1);
		ent_dir[kept] = is_dir ? 1 : 0;
		kept++;
	}
	scan_restore();
	ent_n = kept;
	return (int)kept;
}

/* ---- project list in the mounted set ------------------------------------- */

static char names[NMAX][NLEN + 1];
static char labels[NMAX][DLBL + 1];
static const char *name_lp[NMAX];
/* Global: STORE's LEVEL scroll compares M_CBS against this (kits_level idiom). */
void (*name_fp[NMAX])(u32);
static u32 name_sel;
static u32 name_n;

static char src_name[NLEN + 1];
static char dst_name[NLEN + 1];
static char src_path[PATH_N];
static char dst_path[PATH_N];
static char tmp_path[PATH_N];
static const char *msg[3];
static char line1[48];
static char lbl_src[DLBL + 1];
static char lbl_dst[DLBL + 1];

static void cp_picked(u32 unused);
static void cp_answer(u32 answer);
static void cp_open_answer(u32 answer);
static void cp_job(void);
/* Global: RND NAME's date branch compares CB_SLOT against this. */
void cp_named(u32 confirmed);

static int is_project_dir(const char *set, const char *name)
{
	if (eq(name, "AUDIO"))
		return 0;
	join2(tmp_path, set, name);
	cat(tmp_path, "/project.strd", PATH_N);
	if (fs_exists(tmp_path) > 0)
		return 1;
	join2(tmp_path, set, name);
	cat(tmp_path, "/project.work", PATH_N);
	return fs_exists(tmp_path) > 0;
}

/* 0 = none, >0 = count, -1 = scan failed / over NMAX (caller shows COPY FAILED). */
static int list_projects(void)
{
	const char *set = SET_PATH;
	int n, i;
	u32 kept = 0;

	if (!set || !set[0])
		return 0;
	n = scan_entries(set);
	if (n < 0)
		return -1;
	if (n == 0)
		return 0;
	for (i = 0; i < n; i++) {
		if (!ent_dir[i])
			continue;
		if (!is_project_dir(set, ent_name[i]))
			continue;
		if (kept >= NMAX)
			return -1;
		cpy(names[kept], ent_name[i], NLEN + 1);
		/* Full name stays in names[]; LISTPOP sizes to the longest
		 * label, so a 32-char (or wide-glyph) name empties the panel. */
		cpy(labels[kept], ent_name[i], DLBL + 1);
		name_lp[kept] = labels[kept];
		name_fp[kept] = cp_picked;
		kept++;
	}
	return (int)kept;
}

/* Stock CREATE / SAVE TO NEW suggestion: "PROJECT " + YYMMDD (0x40081b30). */
static void stock_default_name(char *dst)
{
	const char *date;

	STRCPY(dst, STR_PROJECT);
	date = GEN_DATE();
	if (date && date[0])
		STRCAT(dst, date);
}

/* FUNC+BANK LISTPOP callback: source = CHANGE-list selection (SEL_NAME). */
void cp_from_change(void)
{
	if (!SEL_NAME[0])
		return;
	cpy(src_name, SEL_NAME, NLEN + 1);
	/* Same buffer and NAMEED args as SAVE TO NEW (4th arg 0, not 1). */
	stock_default_name(ED_BUF);
	NAMEED(0x20, STR_NAMEED, ED_BUF, 0, cp_named);
}

/* Kept for the oversize-dir failure gate: build a pick list, then YES. */
void cp_menu(u32 unused)
{
	int n;

	(void)unused;
	n = list_projects();
	if (n < 0) {
		MESSAGE("COPY FAILED", 0x60);
		return;
	}
	if (!n) {
		msg[0] = "NO PROJECTS IN SET";
		POPUP("COPY PROJECT", 1, msg, 0, 0);
		return;
	}
	name_n = (u32)n;
	name_sel = 0;
	LISTPOP(name_n, 0, &name_sel, name_lp, (void *)name_fp);
}

static void cp_picked(u32 unused)
{
	(void)unused;
	if (name_sel >= name_n)
		return;
	cpy(src_name, names[name_sel], NLEN + 1);
	stock_default_name(ED_BUF);
	NAMEED(0x20, STR_NAMEED, ED_BUF, 0, cp_named);
}

void cp_named(u32 confirmed)
{
	/* NAMEED done-cb: 0 = cancelled, non-zero = YES (CREATE / KITS / BRAIN). */
	if (!confirmed || !ED_BUF[0])
		return;
	if (len(ED_BUF) > NLEN) {
		MESSAGE("COPY FAILED", 0x60);
		return;
	}
	cpy(dst_name, ED_BUF, NLEN + 1);
	if (eq(dst_name, src_name)) {
		msg[0] = "NAME ALREADY IN USE!";
		POPUP("COPY PROJECT", 1, msg, 0, 0);
		return;
	}
	join2(tmp_path, SET_PATH, dst_name);
	if (fs_exists(tmp_path) > 0) {
		msg[0] = "NAME ALREADY IN USE!";
		POPUP("COPY PROJECT", 1, msg, 0, 0);
		return;
	}
	cpy(lbl_src, src_name, DLBL + 1);
	cpy(lbl_dst, dst_name, DLBL + 1);
	cpy(line1, "COPY ", sizeof line1);
	cat(line1, lbl_src, sizeof line1);
	cat(line1, " -> ", sizeof line1);
	cat(line1, lbl_dst, sizeof line1);
	cat(line1, "?", sizeof line1);
	msg[0] = line1;
	POPUP("COPY PROJECT", 1, msg, 3, (u32)cp_answer);
}

static u8 job_rec[8];

static void cp_answer(u32 answer)
{
	if (answer)
		return;
	join2(src_path, SET_PATH, src_name);
	join2(dst_path, SET_PATH, dst_name);
	MESSAGE("COPYING...", 0x60);
	job_rec[0] = 21;
	job_rec[1] = 0;
	*(u32 *)(job_rec + 2) = (u32)cp_job;
	Q_SEND(ENGINE_Q, job_rec);
}

/* ---- recursive folder copy -----------------------------------------------
 * Per-depth path + entry lists in BSS (ColdFire stack is too small). */

static char frame_src[DEPTH + 1][PATH_N];
static char frame_dst[DEPTH + 1][PATH_N];
static char frame_name[DEPTH + 1][EMAX][NLEN + 1];
static u8 frame_dir[DEPTH + 1][EMAX];

static int copy_tree(u32 depth)
{
	const char *src = frame_src[depth];
	const char *dst = frame_dst[depth];
	int n, i;
	u32 local_n;

	if (depth > DEPTH)
		return -1;
	if (fs_mkdir(dst) < 0)
		return -1;
	n = scan_entries(src);
	if (n < 0)
		return -1;
	local_n = ent_n;
	for (i = 0; i < (int)local_n; i++) {
		cpy(frame_name[depth][i], ent_name[i], NLEN + 1);
		frame_dir[depth][i] = ent_dir[i];
	}
	for (i = 0; i < (int)local_n; i++) {
		/* leaf path slots: depth+1 when recursing, else depth's scratch */
		u32 leaf = depth < DEPTH ? depth + 1 : depth;
		join2(frame_src[leaf], src, frame_name[depth][i]);
		join2(frame_dst[leaf], dst, frame_name[depth][i]);
		if (frame_dir[depth][i]) {
			if (depth + 1 > DEPTH)
				return -1;
			if (copy_tree(depth + 1) < 0)
				return -1;
		} else if (FCOPY(frame_dst[leaf], frame_src[leaf], 0) < 0) {
			return -1;
		}
	}
	return 0;
}

static void cp_open_answer(u32 answer)
{
	/* POPUP flags 3: 0 = YES, non-zero = NO (remix-switch / BRAIN). */
	if (answer)
		return;
	LIST_CLOSE();
	TOAST_CLOSE();
	POST_LOAD(dst_name);
	/* Stock CHANGE does this after POST_LOAD; without it CHOOSE PROJECT stays up. */
	CHOOSE_CLOSE();
}

static void cp_job(void)
{
	int st;
	cpy(frame_src[0], src_path, PATH_N);
	cpy(frame_dst[0], dst_path, PATH_N);
	st = copy_tree(0);
	if (st < 0) {
		rm_tree(dst_path);
		MESSAGE("COPY FAILED", 0x60);
		return;
	}
	msg[0] = "PROJECT COPIED";
	msg[1] = "OPEN IT?";
	POPUP("COPY PROJECT", 2, msg, 3, (u32)cp_open_answer);
}
