#ifndef OCTA_ASSERT_H
#define OCTA_ASSERT_H
void octa_assert_fail(const char *e, const char *f, int l) __attribute__((noreturn));
#define assert(e) ((e) ? (void)0 : octa_assert_fail(#e, __FILE__, __LINE__))
#endif
