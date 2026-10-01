#ifndef OCTA_SYS_STAT_H
#define OCTA_SYS_STAT_H
#include <sys/types.h>
struct stat { off_t st_size; mode_t st_mode; };
#define S_ISDIR(m) (((m) & 0170000) == 0040000)
int stat(const char *path, struct stat *st);
int mkdir(const char *path, mode_t mode);
#endif
