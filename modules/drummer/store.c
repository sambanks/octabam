/* DRUMMER -- drummer.work: the kits of the project, through STORE (client 8).
 * Compiled after drummer.c, adapter.c and kit.c in one unit.
 *
 * The file: {MAGIC 'DRMK', VERSION, size, CRC-32} then DrSave (8 tracks of
 * zones, roles, combo masks, ALIGN, priority, SHIFT, PHRASE and whether the
 * track has a kit), then (version 2) each slice's GAIN, 8 x 64 signed dB,
 * then (version 3) each slice's SCENE (0 none, 1..16) and DOSE (%, 0 = 100),
 * 8 x 64 each, then (version 4) each slice's SIMILAR group (the kept slice
 * + 1, 0 alone), 8 x 64, and each track's SIMILAR tolerance and mode. An older file loads with what it lacks at 0 and is written
 * back as version 4 at the next save. FREE LOOP's form: written at the bank writer and the
 * project store when it changed, copied to drummer.strd at the project store,
 * back at the reload; a file that is not that is never written over (STORE
 * lists it and asks). No file: no kit on any track (each starts with the
 * built-in one until 4e's AUTO). */

enum { DR_MAGIC = 0x44524d4bu, DR_VERSION = 5u, F_COPY = 0x40016388u };

typedef struct {
    uint8_t zone[DR_SLICES], role[DR_SLICES];
    uint16_t combo[DR_SLICES];
    uint8_t align[DR_SLICES];
    uint8_t prio[DR_ZONES];
    uint8_t shift, phrase, ready;
} DrTrackSave;
typedef struct {
    DrTrackSave t[TRACKS];
    int8_t gain[TRACKS][DR_SLICES];                       /* version 2 */
    uint8_t scene[TRACKS][DR_SLICES], dose[TRACKS][DR_SLICES];   /* version 3 */
    uint8_t link[TRACKS][DR_SLICES], simtol[TRACKS], simmode[TRACKS];   /* version 4 */
    uint8_t redrum[TRACKS];                               /* version 5 (image 77) */
} DrSave;
_Static_assert(sizeof(DrSave) == 8 * 332 + 4 * 8 * 64 + 24, "hooks.s reserves 4728 bytes a DrSave");
#define DR_V1_SIZE (8u * 332u)       /* version 1: the tracks alone */
#define DR_V2_SIZE (8u * 332u + 8u * 64u)   /* version 2: + GAIN */
#define DR_V3_SIZE (8u * 332u + 3u * 8u * 64u)   /* version 3: + SCENE, DOSE */
#define DR_V4_SIZE (8u * 332u + 4u * 8u * 64u + 16u)   /* version 4: + SIMILAR */
extern uint8_t dr_simtol[TRACKS], dr_simmode[TRACKS], dr_link[TRACKS][DR_SLICES], dr_redrum[TRACKS];
DATA uint8_t dr_file_ver;            /* the version read (DR_VERSION with no file) */

extern DrSave dr_payload, dr_saved;
extern char dr_path[260], dr_path2[260];
extern uint8_t dr_loaded;
DATA uint8_t dr_nowrite, dr_backup;

int32_t  dr_file_path(const char *format, char *out);
int32_t  dr_file_open(const char *path, const char *mode);
int32_t  dr_file_read(void *buffer, uint32_t length);
int32_t  dr_file_write(const void *buffer, uint32_t length);
void     dr_file_close(void);
uint32_t dr_file_crc(const void *buffer, uint32_t length);
void     dr_file_refuse(void);

static const char WORK[] = "%s/drummer.work", STRD[] = "%s/drummer.strd", BAK[] = "%s/drummer.bak";

static void bytes_copy(void *dst, const void *src, uint32_t n)
{
    uint8_t *d = dst;
    const uint8_t *s = src;
    while (n--)
        *d++ = *s++;
}

static unsigned bytes_same(const void *a, const void *b, uint32_t n)
{
    const uint8_t *x = a, *y = b;
    while (n--)
        if (*x++ != *y++)
            return 0;
    return 1;
}

static void bytes_zero(void *p, uint32_t n)
{
    uint8_t *d = p;
    while (n--)
        *d++ = 0;
}

static void gather(DrSave *sv)
{
    unsigned t;
    bytes_zero(sv, sizeof *sv);
    for (t = 0; t < TRACKS; t++) {
        DrTrackSave *o = &sv->t[t];
        if (dr_kit_ready[t] != 1)                 /* no kit, or AUTO not answered: none saved */
            continue;
        bytes_copy(o->zone, dr_kit[t].zone, DR_SLICES);
        bytes_copy(o->role, dr_kit[t].role, DR_SLICES);
        bytes_copy(o->combo, dr_kit[t].combo, sizeof o->combo);
        bytes_copy(o->align, dr_align[t], DR_SLICES);
        bytes_copy(o->prio, dr_kit[t].prio, DR_ZONES);
        o->shift = dr_shift[t];
        o->phrase = dr_phrase[t];
        o->ready = 1;
        bytes_copy(sv->gain[t], dr_gain[t], DR_SLICES);
        bytes_copy(sv->scene[t], dr_scene[t], DR_SLICES);
        bytes_copy(sv->dose[t], dr_dose[t], DR_SLICES);
        bytes_copy(sv->link[t], dr_link[t], DR_SLICES);
        sv->simtol[t] = dr_simtol[t];
        sv->simmode[t] = dr_simmode[t];
        sv->redrum[t] = dr_redrum[t];
    }
}

/* The file's values, clamped: a zone past COMBO is OUT, a role past SOFT NORMAL. */
static void apply(const DrSave *sv)
{
    unsigned t, i;
    for (t = 0; t < TRACKS; t++) {
        const DrTrackSave *o = &sv->t[t];
        dr_kit_ready[t] = 0;
        dr_shift[t] = 0;
        dr_phrase[t] = 4;
        dr_simtol[t] = AK_TOL_DEFAULT;            /* a file before version 4: SIMILAR at its default */
        dr_simmode[t] = AK_DUP_OUT;
        dr_redrum[t] = 0;                         /* a file before version 5: REDRUM off */
        for (i = 0; i < DR_SLICES; i++) {
            dr_align[t][i] = 0;
            dr_gain[t][i] = 0;
            dr_scene[t][i] = 0;
            dr_dose[t][i] = 0;
            dr_link[t][i] = 0;
        }
        if (!o->ready)
            continue;
        dr_kit_init(&dr_kit[t], 0);
        for (i = 0; i < DR_SLICES; i++) {
            dr_kit[t].zone[i] = o->zone[i] <= DR_COMBO ? o->zone[i] : DR_OUT;
            dr_kit[t].role[i] = o->role[i] < DR_ROLES ? o->role[i] : DR_NORMAL;
            dr_kit[t].combo[i] = o->combo[i];
            dr_align[t][i] = o->align[i] <= 250 ? o->align[i] : 250;
            dr_gain[t][i] = sv->gain[t][i] < DR_GAIN_MIN ? DR_GAIN_MIN
                            : sv->gain[t][i] > DR_GAIN_MAX ? DR_GAIN_MAX : sv->gain[t][i];
            dr_scene[t][i] = sv->scene[t][i] <= 16 ? sv->scene[t][i] : 0;
            dr_dose[t][i] = sv->dose[t][i] <= 100 && sv->dose[t][i] % 5 == 0 ? sv->dose[t][i] : 0;
            dr_link[t][i] = sv->link[t][i] <= DR_SLICES ? sv->link[t][i] : 0;
        }
        if (dr_file_ver >= 4u) {
            dr_simtol[t] = sv->simtol[t] <= AK_TOL_MAX ? sv->simtol[t] : AK_TOL_DEFAULT;
            dr_simmode[t] = sv->simmode[t] ? AK_DUP_LINK : AK_DUP_OUT;
        }
        if (dr_file_ver >= 5u)
            dr_redrum[t] = sv->redrum[t] <= 5 ? sv->redrum[t] : 1;   /* 1 AUTO (image 77's ON), 2..5 bars */
        {   /* the old default order (before image 58) is the new default's */
            static const uint8_t OLD[DR_ZONES] = { DR_KICK, DR_SNARE, DR_CRASH, DR_HATO, DR_HATC, DR_RIDE, DR_TOM,
                                                   DR_PERC, DR_GHOST };
            unsigned old = bytes_same(o->prio, OLD, DR_ZONES);
            for (i = 0; i < DR_ZONES && !old; i++)
                if (o->prio[i] < DR_ZONES)
                    dr_kit[t].prio[i] = o->prio[i];
        }
        dr_shift[t] = o->shift ? 1 : 0;
        dr_phrase[t] = o->phrase == 8 ? 8 : 4;
        dr_kit_ready[t] = 1;
    }
}

static void file_copy(const char *to, const char *from)
{
    dr_file_path(to, dr_path);
    dr_file_path(from, dr_path2);
    FN(F_COPY, const char *, const char *, uint32_t)(dr_path, dr_path2, 0);
}

static void save(void)
{
    uint32_t head[4];
    int32_t ok;
    if (dr_nowrite)
        return;
    gather(&dr_payload);
    if (bytes_same(&dr_payload, &dr_saved, sizeof dr_payload))
        return;
    if (dr_backup) {
        dr_backup = 0;
        file_copy(BAK, WORK);
    }
    head[0] = DR_MAGIC;
    head[1] = DR_VERSION;
    head[2] = sizeof dr_payload;
    head[3] = dr_file_crc(&dr_payload, sizeof dr_payload);
    dr_file_path(WORK, dr_path);
    if (dr_file_open(dr_path, "w") < 0)
        return;
    ok = dr_file_write(head, sizeof head) == 1 && dr_file_write(&dr_payload, sizeof dr_payload) == 1;
    dr_file_close();
    if (ok)
        bytes_copy(&dr_saved, &dr_payload, sizeof dr_payload);
}

static void load(void)
{
    uint32_t head[4];
    dr_nowrite = 0;
    dr_backup = 0;
    dr_file_ver = DR_VERSION;
    bytes_zero(&dr_payload, sizeof dr_payload);
    dr_file_path(WORK, dr_path);
    if (dr_file_open(dr_path, "r") >= 0) {
        unsigned good = dr_file_read(head, sizeof head) == 1 && head[0] == DR_MAGIC
                        && ((head[1] == DR_VERSION && head[2] == sizeof dr_payload)
                            || (head[1] == 4u && head[2] == DR_V4_SIZE)
                            || (head[1] == 3u && head[2] == DR_V3_SIZE)
                            || (head[1] == 2u && head[2] == DR_V2_SIZE)
                            || (head[1] == 1u && head[2] == DR_V1_SIZE))
                        && dr_file_read(&dr_payload, head[2]) == 1;
        dr_file_close();
        if (good)
            dr_file_ver = (uint8_t)head[1];
        if (!good || dr_file_crc(&dr_payload, head[2]) != head[3]) {
            bytes_zero(&dr_payload, sizeof dr_payload);
            dr_nowrite = 1;
            dr_file_refuse();
        }
    }
    apply(&dr_payload);
    gather(&dr_saved);
    dr_loaded = 1;
}

/* A load begins: the banks arrive before drummer.work is read, so a signed
 * track would look kit-less; the KIT question waits for the _post (measured:
 * asked in between, it stayed open unanswered). */
extern uint8_t dr_slot_seen[TRACKS];
void dr_kit_slots_reset(void);
static void slots_unseen(void)
{
    unsigned t;
    for (t = 0; t < TRACKS; t++)
        dr_slot_seen[t] = 0xff;                  /* the loaded kits are the loaded samples' */
    dr_kit_slots_reset();
}
void dr_st_loadall_pre(void)   { dr_loaded = 0; slots_unseen(); }
void dr_st_loadmask_pre(void)  { dr_loaded = 0; slots_unseen(); }
void dr_st_loadall_post(void)  { load(); }
void dr_st_loadmask_post(void) { load(); }
void dr_st_newproj(void)
{
    slots_unseen();
    dr_file_ver = DR_VERSION;
    dr_nowrite = 0;
    dr_backup = 0;
    bytes_zero(&dr_payload, sizeof dr_payload);
    apply(&dr_payload);
    gather(&dr_saved);
    dr_loaded = 1;
}
void dr_st_bankw_post(void) { save(); }
void dr_st_pstore_pre(void) { save(); }
void dr_st_pstore_post(void)
{
    if (!dr_nowrite)
        file_copy(STRD, WORK);
}
void dr_st_preload_post(void)
{
    dr_file_path(WORK, dr_path);
    dr_file_path(STRD, dr_path2);
    if ((int32_t)FN(F_COPY, const char *, const char *, uint32_t)(dr_path, dr_path2, 0) >= 0)
        load();
}
/* A refused drummer.work: IGNORE (0) / OVERWRITE (1) / BACKUP (2); the
 * writes happen at the next save. */
void dr_answer(unsigned answer)
{
    if (!answer)
        return;
    if (answer == 2)
        dr_backup = 1;
    dr_nowrite = 0;
    bytes_zero(&dr_saved, sizeof dr_saved);
    dr_saved.t[0].ready = 0xff;                  /* matches nothing: the next save writes */
}

/* ---- the kit file (image 68): the engine task's side ---------------------
 * dr_drk_post (UI) puts a DRUMMER job (type 0x42, above stock's 0..45 and
 * BRAIN's 0x41) on the engine task's queue, as BRAIN posts its; hooks.s
 * dr_on_job runs dr_job there, where the stock reads and writes the
 * project's files (and drummer.work's calls run: one file context, one task).
 * The path: the slot's PATH (FLEX settings + 0, relative to the project,
 * "../AUDIO/X.wav" measured) with its extension swapped for drk. */
enum { Q_SEND = 0x40000c3cu, ENGINE_Q = 0x460d17ceu, DR_JOB = 0x42u,
       DRK_MAGIC = 0x44524b54u /* 'DRKT' */, DRK_VERSION = 1u };
DATA uint32_t dr_job_msg[4];                     /* type byte first, as stock's records */
DATA uint8_t dr_job_kind, dr_job_slot;
DATA char dr_drk_fmt[216];

void dr_drk_post(unsigned kind, unsigned slot)
{
    dr_job_kind = (uint8_t)kind;
    dr_job_slot = (uint8_t)slot;
    ((uint8_t *)dr_job_msg)[0] = DR_JOB;
    FN(Q_SEND, void *, void *)((void *)(uintptr_t)ENGINE_Q, dr_job_msg);
}

/* "%s/" + the slot's path, extension drk, into dr_path (store_path puts the
 * project's directory for %s); 0 for no path, a '%' in it or one too long. */
static unsigned drk_path(unsigned slot)
{
    const volatile char *src = (const volatile char *)ADDR(FLEX_SET + 0x448u * slot);
    char *f = dr_drk_fmt;
    unsigned i, n = 3, dot = 0;
    f[0] = '%';
    f[1] = 's';
    f[2] = '/';
    for (i = 0; src[i]; i++) {
        char c = src[i];
        if (c == '%' || i >= 200)
            return 0;
        if (c == '.')
            dot = n;
        else if (c == '/')
            dot = 0;
        f[n++] = c;
    }
    if (!i)
        return 0;
    if (dot)
        n = dot;
    f[n++] = '.';
    f[n++] = 'd';
    f[n++] = 'r';
    f[n++] = 'k';
    f[n] = 0;
    dr_file_path(dr_drk_fmt, dr_path);
    return 1;
}

/* The slices the kit fits: their count and a CRC-32 of their bounds. */
static uint32_t drk_sig(unsigned slot, unsigned *count)
{
    uint32_t set = FLEX_SET + 0x448u * slot;
    unsigned n = U32(set + 1092u);
    if (n > DR_SLICES)
        n = DR_SLICES;
    *count = n;
    return dr_file_crc((const void *)(uintptr_t)ADDR(set + 312u), 12u * n);
}

void dr_job(void)
{
    uint32_t head[4], sig;
    unsigned slot = dr_job_slot, n, ok;
    if (slot >= 128 || !drk_path(slot)) {
        dr_drk_res = dr_job_kind == DRK_SAVE ? DRK_FAILED : DRK_NONE;
        return;
    }
    sig = drk_sig(slot, &n);
    if (dr_job_kind == DRK_SAVE) {
        dr_drk.n = (uint8_t)n;
        dr_drk.sig = sig;
        head[0] = DRK_MAGIC;
        head[1] = DRK_VERSION;
        head[2] = sizeof dr_drk;
        head[3] = dr_file_crc(&dr_drk, sizeof dr_drk);
        ok = 0;
        if (dr_file_open(dr_path, "w") >= 0) {
            ok = dr_file_write(head, sizeof head) == 1 && dr_file_write(&dr_drk, sizeof dr_drk) == 1;
            dr_file_close();
        }
        dr_drk_res = ok ? DRK_SAVED : DRK_FAILED;
        return;
    }
    ok = 0;
    if (dr_file_open(dr_path, "r") >= 0) {
        ok = dr_file_read(head, sizeof head) == 1 && head[0] == DRK_MAGIC && head[1] == DRK_VERSION
             && head[2] == sizeof dr_drk && dr_file_read(&dr_drk, sizeof dr_drk) == 1
             && dr_file_crc(&dr_drk, sizeof dr_drk) == head[3];
        dr_file_close();
    }
    dr_drk_res = !ok ? DRK_NONE : dr_drk.n == n && dr_drk.sig == sig ? DRK_FOUND : DRK_STALE;
}

