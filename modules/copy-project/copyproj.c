/* COPY PROJECT -- duplicate a project folder on the card without loading it.
 *
 * PROJECT > COPY PROJECT: pick a project in the mounted set, name the copy,
 * confirm. The live project stays loaded; the job copies the source folder
 * byte-for-byte (stock files and module sidecars) into a new folder.
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
#define SCAN_STATE     ((u8 *)0x460e76ac)
#define SCAN_STATE_LEN 0x10154u
#define SCAN_MAX       1024
/* FS vtable: exists(path) -> 0 absent, 1 file, 2 folder (stems.s). */
#define FS_EXISTS_SLOT 0x46c823fa
#define FS_MKDIR_SLOT  0x46c8240a

#define NMAX   64
#define EMAX   256			/* entries kept per directory */
#define NLEN   32
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
	u32 i;
	for (i = 0; i < SCAN_STATE_LEN; i++)
		SCAN_STATE[i] = scan_save[i];
}

/* Fill ent_* from dir; return count. Names are ours after return. */
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
	for (i = 0; i < n && kept < EMAX; i++) {
		u8 *rec = scan_tab + i * 12;
		const char *nm = *(const char **)rec;
		u32 is_dir = *(u32 *)(rec + 4);
		if (!nm || !nm[0] || eq(nm, ".") || eq(nm, ".."))
			continue;
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
static char labels[NMAX][NLEN + 1];
static const char *name_lp[NMAX];
static void (*name_fp[NMAX])(u32);
static u32 name_sel;
static u32 name_n;

static char src_name[NLEN + 1];
static char dst_name[NLEN + 1];
static char src_path[PATH_N];
static char dst_path[PATH_N];
static char tmp_path[PATH_N];
static const char *msg[3];
static char line1[48];

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

static u32 list_projects(void)
{
	const char *set = SET_PATH;
	int n, i;
	u32 kept = 0;

	if (!set || !set[0])
		return 0;
	n = scan_entries(set);
	if (n <= 0)
		return 0;
	for (i = 0; i < n && kept < NMAX; i++) {
		if (!ent_dir[i])
			continue;
		if (!is_project_dir(set, ent_name[i]))
			continue;
		cpy(names[kept], ent_name[i], NLEN + 1);
		cpy(labels[kept], ent_name[i], NLEN + 1);
		name_lp[kept] = labels[kept];
		name_fp[kept] = cp_picked;
		kept++;
	}
	return kept;
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

void cp_menu(u32 unused)
{
	(void)unused;
	name_n = list_projects();
	if (!name_n) {
		msg[0] = "NO PROJECTS IN SET";
		POPUP("COPY PROJECT", 1, msg, 0, 0);
		return;
	}
	name_sel = 0;
	LISTPOP(name_n, 0, &name_sel, name_lp, (void *)name_fp);
}

static void cp_picked(u32 unused)
{
	(void)unused;
	if (name_sel >= name_n)
		return;
	cpy(src_name, names[name_sel], NLEN + 1);
	/* Same buffer and NAMEED args as SAVE TO NEW (4th arg 0, not 1). */
	stock_default_name(ED_BUF);
	NAMEED(0x20, STR_NAMEED, ED_BUF, 0, cp_named);
}

void cp_named(u32 confirmed)
{
	/* NAMEED done-cb: 0 = cancelled, non-zero = YES (CREATE / KITS / BRAIN). */
	if (!confirmed || !ED_BUF[0])
		return;
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
	cpy(line1, "COPY ", sizeof line1);
	cat(line1, src_name, sizeof line1);
	cat(line1, " -> ", sizeof line1);
	cat(line1, dst_name, sizeof line1);
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
	POST_LOAD(dst_name);
}

static void cp_job(void)
{
	int st;
	cpy(frame_src[0], src_path, PATH_N);
	cpy(frame_dst[0], dst_path, PATH_N);
	st = copy_tree(0);
	if (st < 0) {
		MESSAGE("COPY FAILED", 0x60);
		return;
	}
	msg[0] = "PROJECT COPIED";
	msg[1] = "OPEN IT?";
	POPUP("COPY PROJECT", 2, msg, 3, (u32)cp_open_answer);
}
