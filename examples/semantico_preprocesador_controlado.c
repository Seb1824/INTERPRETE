#include <stdbool.h>
#include <stdint.h>

#define DOBLE(valor) ((valor) * 2)

int main(void) {
    bool activo = true;
    int32_t numero = DOBLE(4);
    return activo ? numero - 8 : 1;
}
