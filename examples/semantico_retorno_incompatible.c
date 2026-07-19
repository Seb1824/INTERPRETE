#include <stdio.h>

int obtener_numero() {
    return "texto";    
}

char *obtener_texto() {
    return 42;         
}

int correcto() {
    return 10;         
}

int main() {
    printf("%d\n", correcto());
    return 0;
}