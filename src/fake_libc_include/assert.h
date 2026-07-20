#ifndef _ANALIZADOR_ASSERT_H
#define _ANALIZADOR_ASSERT_H

#ifdef NDEBUG
#define assert(expression) ((void)0)
#else
#define assert(expression) ((void)(expression))
#endif

#define static_assert _Static_assert

#endif
