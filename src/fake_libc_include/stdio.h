#ifndef _ANALIZADOR_STDIO_H
#define _ANALIZADOR_STDIO_H

#include <stddef.h>

typedef struct _analizador_FILE FILE;

int printf(const char *format, ...);
int fprintf(FILE *stream, const char *format, ...);
int sprintf(char *buffer, const char *format, ...);
int snprintf(char *buffer, size_t size, const char *format, ...);
int scanf(const char *format, ...);
int fscanf(FILE *stream, const char *format, ...);
int sscanf(const char *text, const char *format, ...);
int puts(const char *text);
int fputs(const char *text, FILE *stream);
int putchar(int character);
int getchar(void);
char *fgets(char *buffer, int size, FILE *stream);
FILE *fopen(const char *path, const char *mode);
int fclose(FILE *stream);

#endif
