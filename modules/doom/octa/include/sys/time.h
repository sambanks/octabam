#ifndef OCTA_SYS_TIME_H
#define OCTA_SYS_TIME_H
#include <time.h>
struct timeval { long tv_sec; long tv_usec; };
struct timezone { int tz_minuteswest, tz_dsttime; };
int gettimeofday(struct timeval *tv, void *tz);
#endif
