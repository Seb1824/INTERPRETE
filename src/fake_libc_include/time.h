#ifndef _ANALIZADOR_TIME_H
#define _ANALIZADOR_TIME_H

#include <stddef.h>

typedef long clock_t;
typedef long time_t;

struct tm {
    int tm_sec;
    int tm_min;
    int tm_hour;
    int tm_mday;
    int tm_mon;
    int tm_year;
    int tm_wday;
    int tm_yday;
    int tm_isdst;
};

#define CLOCKS_PER_SEC 1000L

clock_t clock(void);
double difftime(time_t end, time_t beginning);
time_t mktime(struct tm *time_pointer);
time_t time(time_t *timer);
char *asctime(const struct tm *time_pointer);
char *ctime(const time_t *timer);
struct tm *gmtime(const time_t *timer);
struct tm *localtime(const time_t *timer);
size_t strftime(
    char *destination,
    size_t maximum,
    const char *format,
    const struct tm *time_pointer
);

#endif
