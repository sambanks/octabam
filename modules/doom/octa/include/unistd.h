#ifndef OCTA_UNISTD_H
#define OCTA_UNISTD_H
#include <stddef.h>
#include <sys/types.h>
int close(int fd);
ssize_t read(int fd, void *p, size_t n);
ssize_t write(int fd, const void *p, size_t n);
off_t lseek(int fd, off_t off, int whence);
int unlink(const char *path);
int access(const char *path, int mode);
unsigned sleep(unsigned s);
int usleep(unsigned us);
int isatty(int fd);
#define F_OK 0
#define R_OK 4
#endif
