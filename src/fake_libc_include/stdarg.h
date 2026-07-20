#ifndef _ANALIZADOR_STDARG_H
#define _ANALIZADOR_STDARG_H

typedef char *va_list;

#define va_start(arguments, last) ((void)(arguments), (void)(last))
#define va_arg(arguments, type) ((void)(arguments), *(type *)0)
#define va_end(arguments) ((void)(arguments))
#define va_copy(destination, source) \
    ((void)(destination), (void)(source))

#endif
