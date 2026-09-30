/* octabam DOOM -- sound: the effects mixed live, the music streamed from
 * the card, and one 16-sample block a DSP frame handed to core 0.
 *
 * SPDX-License-Identifier: GPL-2.0-or-later
 *
 * The path out (doom_mix.asm, entry.S):
 *   UI task, once a tic   doom_audio_update() mixes enough 44.1 kHz stereo
 *                         into RING to stay TARGET frames ahead of the DSP;
 *   frame interrupt       entry.S's state-7 shim calls doom_audio_block(),
 *                         which takes 16 frames (or silence) into the
 *                         host-port buffer, and starts the transfer to core 0
 *                         (USB AUDIO IN's mechanism, modules/usb-audio-in-ab);
 *   DSP, next frame       doomsnd adds them into MAIN L/R after the mixdown.
 * One producer, one consumer, two indices: the ring needs no lock.
 *
 * Effects: the WAD's DMX lumps (8-bit unsigned, mostly 11,025 Hz), stepped
 * in 16.16 to 44,100, eight channels, Doom's own volume and separation.
 * Music: /DOOMMUS/<lump>.WAV, IMA ADPCM mono 22,050 Hz (modules/doom/
 * music.py renders them from the WAD's MUS with libADLMIDI's OPL3 and
 * Doom's DMX bank), read 4 KB at a time from the card in the UI task,
 * decoded a block at a time, each sample played twice. No file: no music.
 */
#include <stdio.h>
#include <string.h>
#include "octa.h"
#include "doomtype.h"
#include "i_sound.h"
#include "w_wad.h"
#include "z_zone.h"

typedef long (*fs_open_t)(const char *, const char *);
typedef long (*fs_1_t)(long);
typedef long (*fs_read_t)(long, void *, long);

/* doomgeneric's config binds these; built without libsamplerate */
int use_libsamplerate = 0;
float libsamplerate_scale = 0.65f;

/* ---- the ring the frame interrupt drains ------------------------------ */
#define RING    8192                 /* stereo frames, a power of two: 186 ms */
#define TARGET  3072                 /* kept ahead of the DSP: ~70 ms */
static int16_t ring[RING * 2];
static volatile uint32_t prod, cons;
volatile uint32_t doom_audio_underruns, doom_audio_blocks;
static volatile int running;

/* The host-port buffer: word 0 = 1 while Doom sounds, then 16 x (L, R),
 * 64 halfwords = two eDMA minor loops of 64 bytes. The eDMA reads DRAM, so
 * the interrupt writes it through the uncached alias. */
uint16_t doom_tx[64] __attribute__((aligned(16)));

/* In the frame interrupt (entry.S): d0-d1/a0-a1 saved by the IRQ, the rest
 * by GCC. Nothing here may call anything. */
void doom_audio_block(void)
{
    volatile uint16_t *tx = (volatile uint16_t *)((uintptr_t)doom_tx + 0x08000000u);
    uint32_t c = cons, i;
    doom_audio_blocks++;
    if (!running) {
        tx[0] = 0;
        return;
    }
    tx[0] = 1;
    if (prod - c < 16) {
        doom_audio_underruns++;
        for (i = 1; i < 33; i++)
            tx[i] = 0;
        return;
    }
    for (i = 0; i < 16; i++, c++) {
        uint32_t k = (c & (RING - 1)) * 2;
        tx[1 + 2 * i] = (uint16_t)ring[k];
        tx[2 + 2 * i] = (uint16_t)ring[k + 1];
    }
    cons = c;
}

/* ---- effects ---------------------------------------------------------- */
#define NCH 8
typedef struct {
    const uint8_t *data;
    uint32_t len, pos, step;         /* pos and step 16.16 in source samples */
    int lvol, rvol;                  /* 0..256 */
    int on;
} chan_t;
static chan_t ch[NCH];
static boolean sfx_prefix;

static boolean snd_init(boolean use_sfx_prefix)
{
    sfx_prefix = use_sfx_prefix;
    memset(ch, 0, sizeof ch);
#ifndef OCTA_NOSOUND                 /* the bisect builds (Makefile DOOM_CFLAGS) */
    running = 1;
#endif
    return true;
}

static void snd_shutdown(void)
{
    running = 0;
}

static int snd_lump(sfxinfo_t *sfx)
{
    char name[9];
    if (sfx->link)
        sfx = sfx->link;
    snprintf(name, sizeof name, sfx_prefix ? "ds%s" : "%s", sfx->name);
    return W_GetNumForName(name);
}

static void snd_params(int c, int vol, int sep)
{
    int l = ((254 - sep) * vol) / 127, r = (sep * vol) / 127;
    if (c < 0 || c >= NCH)
        return;
    ch[c].lvol = l > 255 ? 256 : l;
    ch[c].rvol = r > 255 ? 256 : r;
}

static int snd_start(sfxinfo_t *sfx, int c, int vol, int sep)
{
    const uint8_t *d;
    int lump, lumplen;
    uint32_t rate, len;
    if (c < 0 || c >= NCH)
        return -1;
    ch[c].on = 0;
    lump = sfx->lumpnum;
    if (lump < 0)
        return -1;
    d = W_CacheLumpNum(lump, PU_STATIC);
    lumplen = W_LumpLength(lump);
    /* the DMX header: format 3, rate, length; 16 pad bytes each end
     * (Chocolate Doom's i_sdlsound.c reads it the same way) */
    if (lumplen < 8 || d[0] != 3 || d[1] != 0)
        return -1;
    rate = d[2] | (d[3] << 8);
    len = d[4] | (d[5] << 8) | (d[6] << 16) | ((uint32_t)d[7] << 24);
    if (len > (uint32_t)lumplen - 8 || len <= 48)
        return -1;
    ch[c].data = d + 8 + 16;
    ch[c].len = len - 32;
    ch[c].pos = 0;
    ch[c].step = (rate << 16) / 44100u;
    snd_params(c, vol, sep);
    ch[c].on = 1;
    return c;
}

static void snd_stop(int c)
{
    if (c >= 0 && c < NCH)
        ch[c].on = 0;
}

static boolean snd_playing(int c)
{
    return c >= 0 && c < NCH && ch[c].on;
}

static void snd_update(void) {}
static void snd_cache(sfxinfo_t *s, int n) { (void)s; (void)n; }

static snddevice_t snd_devices[] = {
    SNDDEVICE_SB, SNDDEVICE_PAS, SNDDEVICE_GUS, SNDDEVICE_WAVEBLASTER,
    SNDDEVICE_SOUNDCANVAS, SNDDEVICE_AWE32,
};

sound_module_t DG_sound_module = {
    snd_devices, sizeof snd_devices / sizeof *snd_devices,
    snd_init, snd_shutdown, snd_lump, snd_update, snd_params,
    snd_start, snd_stop, snd_playing, snd_cache,
};

/* ---- music: IMA ADPCM from the card ------------------------------------ */
static const int16_t ima_step[89] = {
    7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31, 34, 37, 41, 45,
    50, 55, 60, 66, 73, 80, 88, 97, 107, 118, 130, 143, 157, 173, 190, 209, 230,
    253, 279, 307, 337, 371, 408, 449, 494, 544, 598, 658, 724, 796, 876, 963,
    1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066, 2272, 2499, 2749, 3024, 3327,
    3660, 4026, 4428, 4871, 5358, 5894, 6484, 7132, 7845, 8630, 9493, 10442,
    11487, 12635, 13899, 15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794,
    32767,
};
static const int8_t ima_index[16] = { -1, -1, -1, -1, 2, 4, 6, 8, -1, -1, -1, -1, 2, 4, 6, 8 };

#define FILEBUF 4096                 /* 8 sectors: one FS_READ */
static struct {
    long fd;                         /* -1 = none */
    char path[32];
    uint32_t data_left;              /* bytes of the data chunk not yet taken */
    uint32_t data_off, data_len;     /* where the data chunk sits in the file */
    uint32_t block, spb;             /* block align, samples per block */
    uint8_t buf[FILEBUF];
    uint32_t bpos, blen;             /* in buf */
    int16_t pcm[2048];               /* one decoded block */
    uint32_t ppos, plen;
    uint32_t half;                   /* 22.05 -> 44.1: each sample twice */
    int vol, paused, looping, playing;
} m = { .fd = -1, .vol = 100 };

static long fs_open(const char *p)
{
    fs_open_t o = *(fs_open_t *)FS_OPEN;
    if (!*(volatile long *)FS_MOUNTED || !o)
        return -1;
    return o(p, "r");
}

static void fs_close(long fd)
{
    (*(fs_1_t *)FS_CLOSE)(fd);
}

/* refill buf with the next sectors; 0 at the end of the file */
static int m_fill(void)
{
    long n = (*(fs_read_t *)FS_READ)(m.fd, m.buf, FILEBUF / 512);
    (void)n;
    m.bpos = 0;
    m.blen = FILEBUF;
    return 1;
}

static int m_byte(uint8_t *b)
{
    if (m.bpos >= m.blen && !m_fill())
        return 0;
    *b = m.buf[m.bpos++];
    return 1;
}

static uint32_t le32(const uint8_t *p) { return p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24); }
static uint16_t le16(const uint8_t *p) { return (uint16_t)(p[0] | (p[1] << 8)); }

/* open the file and walk its RIFF header to the data chunk */
static int m_open(void)
{
    uint8_t h[8];
    uint32_t off = 12, i;
    if (m.fd >= 0)
        fs_close(m.fd);
    m.fd = fs_open(m.path);
    if (m.fd < 0)
        return 0;
    m.bpos = m.blen = 0;
    m_fill();
    if (memcmp(m.buf, "RIFF", 4) || memcmp(m.buf + 8, "WAVE", 4))
        goto bad;
    m.block = 0;
    while (off + 8 <= FILEBUF) {
        uint32_t n = le32(m.buf + off + 4);
        if (!memcmp(m.buf + off, "fmt ", 4) && n >= 20) {
            if (le16(m.buf + off + 8) != 0x11 || le16(m.buf + off + 10) != 1)
                goto bad;             /* not IMA ADPCM mono */
            m.block = le16(m.buf + off + 20);
            m.spb = le16(m.buf + off + 26);
        } else if (!memcmp(m.buf + off, "data", 4)) {
            m.data_off = off + 8;
            m.data_len = n;
            break;
        }
        off += 8 + n + (n & 1);
    }
    if (!m.block || !m.data_off || m.spb > 2048 || m.data_off >= FILEBUF)
        goto bad;
    m.bpos = m.data_off;
    m.data_left = m.data_len;
    m.ppos = m.plen = 0;
    (void)h; (void)i;
    return 1;
bad:
    fs_close(m.fd);
    m.fd = -1;
    return 0;
}

/* decode the next block into pcm; 0 at the end of the data */
static int m_block(void)
{
    uint8_t b[4];
    int pred, idx, i;
    uint32_t n = 0, bytes;
    if (m.data_left < 4)
        return 0;
    for (i = 0; i < 4; i++)
        if (!m_byte(&b[i]))
            return 0;
    pred = (int16_t)le16(b);
    idx = b[2] > 88 ? 88 : b[2];
    m.pcm[n++] = (int16_t)pred;
    bytes = m.block - 4;
    if (bytes > m.data_left - 4)
        bytes = m.data_left - 4;
    m.data_left -= 4 + bytes;
    while (bytes--) {
        uint8_t v;
        int k;
        if (!m_byte(&v))
            break;
        for (k = 0; k < 2; k++) {
            int nib = k ? v >> 4 : v & 15, step = ima_step[idx], diff = step >> 3;
            if (nib & 4) diff += step;
            if (nib & 2) diff += step >> 1;
            if (nib & 1) diff += step >> 2;
            pred += (nib & 8) ? -diff : diff;
            if (pred > 32767) pred = 32767;
            if (pred < -32768) pred = -32768;
            idx += ima_index[nib];
            if (idx < 0) idx = 0;
            if (idx > 88) idx = 88;
            if (n < 2048)
                m.pcm[n++] = (int16_t)pred;
        }
    }
    m.ppos = 0;
    m.plen = n;
    return n > 0;
}

/* the next 44.1 kHz music sample, or 0 */
static int m_next(void)
{
    int s;
    if (!m.playing || m.paused || m.fd < 0)
        return 0;
    if (m.ppos >= m.plen) {
        if (!m_block()) {
            if (!m.looping || !m_open() || !m_block()) {
                m.playing = 0;
                return 0;
            }
        }
    }
    s = m.pcm[m.ppos];
    if (++m.half == 2) {
        m.half = 0;
        m.ppos++;
    }
    return s;
}

static boolean mus_init(void) { return true; }
static void mus_shutdown(void) { if (m.fd >= 0) fs_close(m.fd); m.fd = -1; m.playing = 0; }
static void mus_volume(int v) { m.vol = v; }
static void mus_pause(void) { m.paused = 1; }
static void mus_resume(void) { m.paused = 0; }

/* The song's handle is its lump's name: the music module is handed only
 * the cached lump, so find the lump whose cache it is. */
static void *mus_register(void *data, int len)
{
    unsigned i;
    for (i = 0; i < numlumps; i++)
        if (lumpinfo[i].cache == data && lumpinfo[i].size == len)
            return &lumpinfo[i];
    return NULL;
}

static void mus_unregister(void *h) { (void)h; }

static void mus_play(void *h, boolean looping)
{
    lumpinfo_t *l = h;
    char name[9];
    int i;
    m.playing = 0;
#if defined(OCTA_NOSOUND) || defined(OCTA_NOMUSIC)
    l = NULL;
#endif
    if (!l)
        return;
    for (i = 0; i < 8 && l->name[i]; i++)
        name[i] = l->name[i];
    name[i] = 0;
    snprintf(m.path, sizeof m.path, "/DOOMMUS/%s.WAV", name);
    m.looping = looping;
    m.half = 0;
    if (!m_open()) {
        printf("music: no %s\n", m.path);
        return;
    }
    m.playing = 1;
}

static void mus_stop(void)
{
    m.playing = 0;
    if (m.fd >= 0)
        fs_close(m.fd);
    m.fd = -1;
}

static boolean mus_isplaying(void) { return m.playing; }
static void mus_poll(void) {}

music_module_t DG_music_module = {
    snd_devices, sizeof snd_devices / sizeof *snd_devices,
    mus_init, mus_shutdown, mus_volume, mus_pause, mus_resume,
    mus_register, mus_unregister, mus_play, mus_stop, mus_isplaying, mus_poll,
};

/* ---- the mixer, once a tic in the UI task ----------------------------- */
void doom_audio_update(void)
{
    static int32_t acc[2 * 256];
    uint32_t fill = prod - cons;
    while (fill < TARGET) {
        uint32_t n = TARGET - fill, i, c;
        int mv = m.vol;
        if (n > 256)
            n = 256;
        for (i = 0; i < n; i++) {
            int s = m_next() * mv >> 6;       /* Doom's default music volume (67 of 127) near unity */
            acc[2 * i] = s;
            acc[2 * i + 1] = s;
        }
        for (c = 0; c < NCH; c++) {
            chan_t *h = &ch[c];
            if (!h->on)
                continue;
            for (i = 0; i < n; i++) {
                uint32_t p = h->pos >> 16;
                int s;
                if (p >= h->len) {
                    h->on = 0;
                    break;
                }
                s = ((int)h->data[p] - 128) << 8;
                acc[2 * i] += s * h->lvol >> 8;
                acc[2 * i + 1] += s * h->rvol >> 8;
                h->pos += h->step;
            }
        }
        for (i = 0; i < n; i++) {
            uint32_t k = ((prod + i) & (RING - 1)) * 2;
            int l = acc[2 * i] >> 1, r = acc[2 * i + 1] >> 1;   /* headroom for 8 + music */
            ring[k] = (int16_t)(l > 32767 ? 32767 : l < -32768 ? -32768 : l);
            ring[k + 1] = (int16_t)(r > 32767 ? 32767 : r < -32768 ? -32768 : r);
        }
        prod += n;
        fill += n;
    }
}

/* Doom has stopped (an error, or the exit): the DSP gets silence */
void doom_audio_off(void)
{
    running = 0;
}
