int incrementar(int valor) {
    return valor + 1;
}

int (*seleccionar(void))(int) {
    return incrementar;
}

int main(void) {
    return seleccionar()(4) - 5;
}
