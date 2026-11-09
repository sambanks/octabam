/* The fractional multiply both engine files use: (a * b) >> 31.  On the ColdFire it is the EMAC and
 * needs MACSR = 0x20 (fractional, no rounding) and ACC0 = 0 on entry; on the host, the same value. */
#pragma once
#include <stdint.h>

#ifdef __mcoldfire__
static inline int32_t mul(int32_t a, int32_t b)
{
    int32_t r;
    __asm__ volatile("mac.l %1,%2,%%acc0\n\tmovclr.l %%acc0,%0"
                     : "=r"(r) : "r"(a), "r"(b));
    return r;
}
#else
static inline int32_t mul(int32_t a, int32_t b)
{
    return (int32_t)(((int64_t)a * b) >> 31);
}
#endif
