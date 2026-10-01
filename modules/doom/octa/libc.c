/* octabam DOOM -- the freestanding C library doomgeneric links against.
 *
 * SPDX-License-Identifier: GPL-2.0-or-later
 *
 * Only what `m68k-elf-nm -u` on the upstream objects asks for. The heap is
 * a first-fit free list over Doom's arena pages (octa.h DOOM_RAM_*), the
 * one "file" is DOOM1.WAD read whole into that heap at boot (doom_octa.c),
 * and stdout/stderr go to a ring buffer a port dump can read (octa_log).
 * Nothing is ever written to the card.
 */
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <errno.h>
#include <math.h>
#include "octa.h"

int errno;

/* ---- the heap --------------------------------------------------------- */
typedef struct blk { size_t size; struct blk *next; } blk_t;   /* size includes the header */
static blk_t *freelist;
char *octa_heap_next, *octa_heap_end;

void *malloc(size_t n)
{
    blk_t **pp, *b;
    size_t need = (n + sizeof(blk_t) + 15) & ~(size_t)15;
    for (pp = &freelist; (b = *pp) != NULL; pp = &b->next) {
        if (b->size >= need) {
            if (b->size - need >= 64) {         /* split: the tail stays free */
                blk_t *t = (blk_t *)((char *)b + need);
                t->size = b->size - need;
                t->next = b->next;
                *pp = t;
                b->size = need;
            } else
                *pp = b->next;
            return b + 1;
        }
    }
    if (octa_heap_next == NULL || (size_t)(octa_heap_end - octa_heap_next) < need) {
        errno = ENOMEM;
        return NULL;
    }
    b = (blk_t *)octa_heap_next;
    octa_heap_next += need;
    b->size = need;
    return b + 1;
}

void free(void *p)
{
    blk_t *b;
    if (!p)
        return;
    b = (blk_t *)p - 1;
    b->next = freelist;
    freelist = b;
}

void *calloc(size_t n, size_t sz)
{
    void *p = malloc(n * sz);
    if (p)
        memset(p, 0, n * sz);
    return p;
}

void *realloc(void *p, size_t n)
{
    void *q;
    size_t have;
    if (!p)
        return malloc(n);
    have = ((blk_t *)p - 1)->size - sizeof(blk_t);
    if (have >= n)
        return p;
    q = malloc(n);
    if (q) {
        memcpy(q, p, have);
        free(p);
    }
    return q;
}

/* ---- strings ---------------------------------------------------------- */
void *memcpy(void *d, const void *s, size_t n)
{
    uint8_t *dp = d;
    const uint8_t *sp = s;
    if ((((uintptr_t)dp | (uintptr_t)sp) & 3) == 0) {
        uint32_t *dw = (uint32_t *)dp;
        const uint32_t *sw = (const uint32_t *)sp;
        while (n >= 16) {
            dw[0] = sw[0]; dw[1] = sw[1]; dw[2] = sw[2]; dw[3] = sw[3];
            dw += 4; sw += 4; n -= 16;
        }
        while (n >= 4) {
            *dw++ = *sw++;
            n -= 4;
        }
        dp = (uint8_t *)dw;
        sp = (const uint8_t *)sw;
    }
    while (n--)
        *dp++ = *sp++;
    return d;
}

void *memmove(void *d, const void *s, size_t n)
{
    uint8_t *dp = d;
    const uint8_t *sp = s;
    if (dp <= sp || dp >= sp + n)
        return memcpy(d, s, n);
    while (n--)
        dp[n] = sp[n];
    return d;
}

void *memset(void *d, int c, size_t n)
{
    uint8_t *dp = d;
    if (n >= 8 && ((uintptr_t)dp & 3) == 0) {
        uint32_t w = (uint8_t)c * 0x01010101u, *dw = (uint32_t *)dp;
        while (n >= 4) {
            *dw++ = w;
            n -= 4;
        }
        dp = (uint8_t *)dw;
    }
    while (n--)
        *dp++ = (uint8_t)c;
    return d;
}

int memcmp(const void *a, const void *b, size_t n)
{
    const uint8_t *x = a, *y = b;
    for (; n; n--, x++, y++)
        if (*x != *y)
            return *x - *y;
    return 0;
}

size_t strlen(const char *s)
{
    const char *p = s;
    while (*p)
        p++;
    return (size_t)(p - s);
}

char *strcpy(char *d, const char *s)
{
    char *r = d;
    while ((*d++ = *s++))
        ;
    return r;
}

char *strncpy(char *d, const char *s, size_t n)
{
    char *r = d;
    while (n && *s) {
        *d++ = *s++;
        n--;
    }
    while (n--)
        *d++ = 0;
    return r;
}

char *strcat(char *d, const char *s)
{
    strcpy(d + strlen(d), s);
    return d;
}

int strcmp(const char *a, const char *b)
{
    while (*a && *a == *b)
        a++, b++;
    return (uint8_t)*a - (uint8_t)*b;
}

int strncmp(const char *a, const char *b, size_t n)
{
    for (; n; n--, a++, b++) {
        if (*a != *b)
            return (uint8_t)*a - (uint8_t)*b;
        if (!*a)
            return 0;
    }
    return 0;
}

int strcasecmp(const char *a, const char *b)
{
    int x, y;
    do {
        x = tolower((uint8_t)*a++);
        y = tolower((uint8_t)*b++);
    } while (x && x == y);
    return x - y;
}

int strncasecmp(const char *a, const char *b, size_t n)
{
    int x = 0, y = 0;
    while (n--) {
        x = tolower((uint8_t)*a++);
        y = tolower((uint8_t)*b++);
        if (!x || x != y)
            break;
    }
    return x - y;
}

char *strchr(const char *s, int c)
{
    for (;; s++) {
        if (*s == (char)c)
            return (char *)s;
        if (!*s)
            return NULL;
    }
}

char *strrchr(const char *s, int c)
{
    const char *r = NULL;
    for (;; s++) {
        if (*s == (char)c)
            r = s;
        if (!*s)
            return (char *)r;
    }
}

char *strstr(const char *h, const char *n)
{
    size_t l = strlen(n);
    for (; *h; h++)
        if (!strncmp(h, n, l))
            return (char *)h;
    return l ? NULL : (char *)h;
}

char *strdup(const char *s)
{
    char *d = malloc(strlen(s) + 1);
    return d ? strcpy(d, s) : NULL;
}

/* ---- numbers ---------------------------------------------------------- */
int abs(int x) { return x < 0 ? -x : x; }

long strtol(const char *s, char **end, int base)
{
    long v = 0;
    int neg = 0, d;
    while (isspace((uint8_t)*s))
        s++;
    if (*s == '-' || *s == '+')
        neg = *s++ == '-';
    if ((base == 0 || base == 16) && s[0] == '0' && (s[1] == 'x' || s[1] == 'X')) {
        s += 2;
        base = 16;
    } else if (base == 0)
        base = *s == '0' ? 8 : 10;
    for (;; s++) {
        if (isdigit((uint8_t)*s))
            d = *s - '0';
        else if (isalpha((uint8_t)*s))
            d = tolower((uint8_t)*s) - 'a' + 10;
        else
            break;
        if (d >= base)
            break;
        v = v * base + d;
    }
    if (end)
        *end = (char *)s;
    return neg ? -v : v;
}

int atoi(const char *s) { return (int)strtol(s, NULL, 10); }

double atof(const char *s)
{
    double v = 0, scale = 1;
    int neg = 0;
    while (isspace((uint8_t)*s))
        s++;
    if (*s == '-' || *s == '+')
        neg = *s++ == '-';
    while (isdigit((uint8_t)*s))
        v = v * 10 + (*s++ - '0');
    if (*s == '.')
        for (s++; isdigit((uint8_t)*s); s++) {
            scale /= 10;
            v += (*s - '0') * scale;
        }
    return neg ? -v : v;
}

double fabs(double x) { return x < 0 ? -x : x; }

/* ---- formatted output ------------------------------------------------- */
typedef struct { char *p; size_t left; size_t n; } sink_t;

static void put(sink_t *k, char c)
{
    if (k->left > 1) {
        *k->p++ = c;
        k->left--;
    }
    k->n++;
}

int vsnprintf(char *s, size_t size, const char *fmt, va_list ap)
{
    sink_t k = { s, size, 0 };
    char tmp[24];
    for (; *fmt; fmt++) {
        int left = 0, zero = 0, width = 0, prec = -1, lng = 0, i, len;
        const char *str;
        unsigned long u;
        int base = 10, neg = 0, upper = 0;
        if (*fmt != '%') {
            put(&k, *fmt);
            continue;
        }
        fmt++;
        for (;; fmt++) {
            if (*fmt == '-') left = 1;
            else if (*fmt == '0') zero = 1;
            else if (*fmt == '+' || *fmt == ' ' || *fmt == '#') ;
            else break;
        }
        if (*fmt == '*') {
            width = va_arg(ap, int);
            fmt++;
        } else
            while (isdigit((uint8_t)*fmt))
                width = width * 10 + (*fmt++ - '0');
        if (*fmt == '.') {
            prec = 0;
            fmt++;
            if (*fmt == '*') {
                prec = va_arg(ap, int);
                fmt++;
            } else
                while (isdigit((uint8_t)*fmt))
                    prec = prec * 10 + (*fmt++ - '0');
        }
        while (*fmt == 'l' || *fmt == 'h' || *fmt == 'z')
            lng += *fmt++ == 'l';
        switch (*fmt) {
        case 'c':
            tmp[0] = (char)va_arg(ap, int);
            tmp[1] = 0;
            str = tmp;
            len = 1;
            goto emit;
        case 's':
            str = va_arg(ap, const char *);
            if (!str)
                str = "(null)";
            len = (int)strlen(str);
            if (prec >= 0 && len > prec)
                len = prec;
            goto emit;
        case 'f': case 'g': case 'e': {
            double d = va_arg(ap, double);
            long w;
            int p = prec < 0 ? 6 : prec, j;
            char *t = tmp + sizeof tmp;
            if (d < 0) {
                neg = 1;
                d = -d;
            }
            w = (long)d;
            d -= (double)w;
            *--t = 0;
            {
                char frac[12];
                if (p > 9) p = 9;
                for (j = 0; j < p; j++) {
                    d *= 10;
                    frac[j] = (char)('0' + (int)d % 10);
                    d -= (int)d;
                }
                for (j = p - 1; j >= 0; j--)
                    *--t = frac[j];
                if (p)
                    *--t = '.';
            }
            do {
                *--t = (char)('0' + w % 10);
                w /= 10;
            } while (w);
            if (neg)
                *--t = '-';
            str = t;
            len = (int)strlen(t);
            goto emit;
        }
        case 'p':
            u = (unsigned long)va_arg(ap, void *);
            base = 16;
            put(&k, '0');
            put(&k, 'x');
            goto num;
        case 'd': case 'i': {
            long v = va_arg(ap, long);   /* int and long are both 32 bits here */
            if (v < 0) {
                neg = 1;
                u = (unsigned long)-v;
            } else
                u = (unsigned long)v;
            goto num;
        }
        case 'u': u = va_arg(ap, unsigned long); goto num;
        case 'o': u = va_arg(ap, unsigned long); base = 8; goto num;
        case 'X': upper = 1; /* fall through */
        case 'x': u = va_arg(ap, unsigned long); base = 16; goto num;
        case '%': put(&k, '%'); continue;
        default: continue;
        }
    num:
        {
            char *t = tmp + sizeof tmp;
            *--t = 0;
            do {
                int d = (int)(u % (unsigned)base);
                *--t = (char)(d < 10 ? '0' + d : (upper ? 'A' : 'a') + d - 10);
                u /= (unsigned)base;
            } while (u);
            while (prec > 0 && (int)(tmp + sizeof tmp - 1 - t) < prec)
                *--t = '0';
            if (zero && !left && prec < 0)
                while ((int)(tmp + sizeof tmp - 1 - t) + neg < width)
                    *--t = '0';
            if (neg)
                *--t = '-';
            str = t;
            len = (int)strlen(t);
        }
    emit:
        if (!left)
            for (i = len; i < width; i++)
                put(&k, ' ');
        for (i = 0; i < len; i++)
            put(&k, str[i]);
        if (left)
            for (i = len; i < width; i++)
                put(&k, ' ');
        (void)lng;
    }
    if (size)
        *k.p = 0;
    return (int)k.n;
}

int snprintf(char *s, size_t n, const char *fmt, ...)
{
    va_list ap;
    int r;
    va_start(ap, fmt);
    r = vsnprintf(s, n, fmt, ap);
    va_end(ap);
    return r;
}

int sprintf(char *s, const char *fmt, ...)
{
    va_list ap;
    int r;
    va_start(ap, fmt);
    r = vsnprintf(s, 1u << 20, fmt, ap);
    va_end(ap);
    return r;
}

/* ---- scanf: the %d/%x/%o/%s/%c doomgeneric's config and M_StrToInt use */
int sscanf(const char *s, const char *fmt, ...)
{
    va_list ap;
    int got = 0;
    va_start(ap, fmt);
    for (; *fmt; fmt++) {
        if (isspace((uint8_t)*fmt)) {
            while (isspace((uint8_t)*s))
                s++;
            continue;
        }
        if (*fmt != '%') {
            if (*s != *fmt)
                break;
            s++;
            continue;
        }
        fmt++;
        if (*fmt == 'd' || *fmt == 'i' || *fmt == 'x' || *fmt == 'o' || *fmt == 'u') {
            char *e;
            int base = *fmt == 'x' ? 16 : *fmt == 'o' ? 8 : *fmt == 'i' ? 0 : 10;
            long v = strtol(s, &e, base);
            if (e == s)
                break;
            *va_arg(ap, int *) = (int)v;
            s = e;
            got++;
        } else if (*fmt == 's') {
            char *d = va_arg(ap, char *);
            while (isspace((uint8_t)*s))
                s++;
            if (!*s)
                break;
            while (*s && !isspace((uint8_t)*s))
                *d++ = *s++;
            *d = 0;
            got++;
        } else if (*fmt == 'c') {
            if (!*s)
                break;
            *va_arg(ap, char *) = *s++;
            got++;
        } else
            break;
    }
    va_end(ap);
    return got;
}

/* ---- files: DOOM1.WAD in memory, and the log -------------------------- */
struct octa_file { const uint8_t *data; long size, pos; int log; };
static struct octa_file f_out = { 0, 0, 0, 1 }, f_err = { 0, 0, 0, 1 };
FILE *stdin = NULL, *stdout = &f_out, *stderr = &f_err;
const uint8_t *octa_wad;          /* doom_octa.c fills these at boot */
long octa_wad_len;

static int is_wad(const char *path)
{
    const char *b = strrchr(path, '/');
    b = b ? b + 1 : path;
    return !strcasecmp(b, "doom1.wad");
}

FILE *fopen(const char *path, const char *mode)
{
    struct octa_file *f;
    if (!octa_wad || mode[0] != 'r' || !is_wad(path)) {
        errno = ENOENT;
        return NULL;
    }
    f = malloc(sizeof *f);
    if (!f)
        return NULL;
    f->data = octa_wad;
    f->size = octa_wad_len;
    f->pos = 0;
    f->log = 0;
    return f;
}

int fclose(FILE *f)
{
    if (f && !f->log)
        free(f);
    return 0;
}

size_t fread(void *p, size_t sz, size_t n, FILE *f)
{
    long want = (long)(sz * n), have;
    if (!f || f->log || !sz)
        return 0;
    have = f->size - f->pos;
    if (want > have)
        want = have - have % (long)sz;
    memcpy(p, f->data + f->pos, (size_t)want);
    f->pos += want;
    return (size_t)want / sz;
}

size_t fwrite(const void *p, size_t sz, size_t n, FILE *f)
{
    if (f && f->log) {
        octa_log(p, sz * n);
        return n;
    }
    return 0;
}

int fseek(FILE *f, long off, int whence)
{
    long base = whence == SEEK_SET ? 0 : whence == SEEK_CUR ? f->pos : f->size;
    if (f->log || base + off < 0 || base + off > f->size)
        return -1;
    f->pos = base + off;
    return 0;
}

long ftell(FILE *f) { return f->pos; }
int fflush(FILE *f) { (void)f; return 0; }

int vfprintf(FILE *f, const char *fmt, va_list ap)
{
    char buf[256];
    int n = vsnprintf(buf, sizeof buf, fmt, ap);
    if (f && f->log)
        octa_log(buf, strlen(buf));
    return n;
}

int fprintf(FILE *f, const char *fmt, ...)
{
    va_list ap;
    int r;
    va_start(ap, fmt);
    r = vfprintf(f, fmt, ap);
    va_end(ap);
    return r;
}

int printf(const char *fmt, ...)
{
    va_list ap;
    int r;
    va_start(ap, fmt);
    r = vfprintf(stdout, fmt, ap);
    va_end(ap);
    return r;
}

int putchar(int c)
{
    char ch = (char)c;
    octa_log(&ch, 1);
    return c;
}

int puts(const char *s)
{
    octa_log(s, strlen(s));
    octa_log("\n", 1);
    return 0;
}

int remove(const char *p) { (void)p; return -1; }
int rename(const char *a, const char *b) { (void)a; (void)b; return -1; }
int mkdir(const char *p, int m) { (void)p; (void)m; return -1; }
int system(const char *c) { (void)c; return -1; }

/* exit(0) is Doom's own QUIT: back to the flashed OS. Anything else is an
 * I_Error: back to doom_run, which puts the log on the panel. */
void exit(int code)
{
    doom_bail(code ? code : 0x10000);
}
