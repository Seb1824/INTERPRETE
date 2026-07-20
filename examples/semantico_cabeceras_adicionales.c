#include <assert.h>
#include <ctype.h>
#include <errno.h>
#include <float.h>
#include <limits.h>
#include <stdarg.h>
#include <time.h>

int primero(int cantidad, ...) {
    va_list argumentos = (va_list)0;
    va_start(argumentos, cantidad);
    int valor = va_arg(argumentos, int);
    va_end(argumentos);
    return valor;
}

int main(void) {
    time_t ahora = time(NULL);
    int letra = toupper('a');
    double precision = DBL_EPSILON;
    errno = 0;

    assert(INT_MAX > 0);
    return (
        primero(1, letra) == 'A'
        && ahora != (time_t)-1
        && precision > 0.0
        && errno == 0
    ) ? 0 : 1;
}
