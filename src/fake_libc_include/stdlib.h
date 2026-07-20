#ifndef _ANALIZADOR_STDLIB_H
#define _ANALIZADOR_STDLIB_H

#include <stddef.h>

void *malloc(size_t size);
void *calloc(size_t count, size_t size);
void *realloc(void *pointer, size_t size);
void free(void *pointer);
int atoi(const char *text);
long atol(const char *text);
double atof(const char *text);
int rand(void);
void srand(unsigned int seed);
void exit(int status);

#define RAND_MAX 2147483647

#endif
