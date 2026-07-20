#ifndef _ANALIZADOR_STRING_H
#define _ANALIZADOR_STRING_H

#include <stddef.h>

size_t strlen(const char *text);
int strcmp(const char *left, const char *right);
char *strcpy(char *destination, const char *source);
char *strncpy(char *destination, const char *source, size_t count);
char *strcat(char *destination, const char *source);
void *memcpy(void *destination, const void *source, size_t count);
void *memset(void *destination, int value, size_t count);

#endif
