typedef int (*Operacion)(int, int);

int sumar(int izquierda, int derecha) {
    return izquierda + derecha;
}

int aplicar(Operacion operacion, int izquierda, int derecha) {
    return operacion(izquierda, derecha);
}

int main(void) {
    return aplicar(sumar, 2, 3) - 5;
}
