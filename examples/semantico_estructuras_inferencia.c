typedef struct {
    int edad;
    char *nombre;
} Persona;

int longitud(char *texto) {
    return texto[0];
}

int main(void) {
    Persona persona = {20, "Ana"};
    return longitud(persona.edad);
}
