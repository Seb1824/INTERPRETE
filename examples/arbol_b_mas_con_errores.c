#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define ORDEN 4
#define MAX_CLAVES (ORDEN - 1)
#define MAX_NODOS 32
#define REGISTROS_POR_PAGINA 3

typedef struct {
    int pagina_datos;
    int posicion;
} RID;

typedef struct {
    int codigo;
    char nombre[40];
    int edad;
    double promedio;
    RID rid;
} Registro;

typedef struct Nodo {
    int es_hoja;
    int cantidad_claves;
    int claves[MAX_CLAVES];
    RID referencias[MAX_CLAVES];
    struct Nodo *hijos[ORDEN];
    struct Nodo *padre;
    struct Nodo *siguiente;
    int pagina_indice;
} Nodo;

typedef struct {
    Nodo nodos[MAX_NODOS];
    int cantidad_nodos;
    Nodo *raiz;
} ArbolBMas;

static Nodo *crear_nodo(ArbolBMas *arbol, int es_hoja) {
    Nodo *nuevo;

    if (arbol->cantidad_nodos >= MAX_NODOS) {
        return NULL;
    }

    nuevo = &arbol->nodos[arbol->cantidad_nodos];
    arbol->cantidad_nodos++;

    memset(nuevo, 0, sizeof(Nodo));
    nuevo->es_hoja = es_hoja;
    nuevo->pagina_indice = arbol->cantidad_nodos;
    return nuevo;
}

static void inicializar_arbol(ArbolBMas *arbol) {
    memset(arbol, 0, sizeof(ArbolBMas));
    arbol->raiz = crear_nodo(arbol, 1);
}

static int buscar_posicion(const Nodo *hoja, int clave) {
    int posicion = 0;

    while (
        posicion < hoja->cantidad_claves
        && hoja->claves[posicion] < clave
    ) {
        posicion++;
    }

    return posicion;
}

static int insertar_en_hoja(Nodo *hoja, int clave, RID rid) {
    int posicion = 0;
    int indice = 0;

    if (hoja == NULL || !hoja->es_hoja) {
        return 0;
    }

    if (hoja->cantidad_claves >= MAX_CLAVES) {
        return 0;
    }

    posicion = buscar_posicion(hoja, clave);

    for (indice = hoja->cantidad_claves; indice > posicion; indice--) {
        hoja->claves[indice] = hoja->claves[indice - 1];
        hoja->referencias[indice] = hoja->referencias[indice - 1];
    }

    hoja->claves[posicion] = clave;
    hoja->referencias[posicion] = rid;
    hoja->cantidad_claves++;
    return 1;
}

static int insertar_arbol(ArbolBMas *arbol, int clave, RID rid) {
    if (arbol == NULL || arbol->raiz == NULL) {
        return 0;
    }

    return insertar_en_hoja(arbol->raiz, clave, rid);
}

static int buscar_arbol(
    const ArbolBMas *arbol,
    int clave,
    RID *resultado
) {
    const Nodo *hoja;
    int posicion = 0;

    if (arbol == NULL || arbol->raiz == NULL || resultado == NULL) {
        return 0;
    }

    hoja = arbol->raiz;
    posicion = buscar_posicion(hoja, clave);

    if (
        posicion < hoja->cantidad_claves
        && hoja->claves[posicion] == clave
    ) {
        *resultado = hoja->referencias[posicion];
        return 1;
    }

    return 0;
}

static void generar_registros(Registro registros[], int cantidad) {
    int indice = 0;

    srand((unsigned int)time(NULL));

    for (indice = 0; indice < cantidad; indice++) {
        registros[indice].codigo = 100 + indice * 10;
        snprintf(
            registros[indice].nombre,
            sizeof(registros[indice].nombre),
            "Estudiante_%d",
            indice + 1
        );
        registros[indice].edad = 18 + rand() % 10;
        registros[indice].promedio = 10.0 + (rand() % 100) / 10.0;
        registros[indice].rid.pagina_datos =
            indice / REGISTROS_POR_PAGINA + 1;
        registros[indice].rid.posicion =
            indice % REGISTROS_POR_PAGINA + 1;
    }
}

static void mostrar_registros(
    const Registro registros[],
    int cantidad
) {
    int indice = 0;

    for (indice = 0; indice < cantidad; indice++) {
        printf(
            "%03d | %-15s | edad=%d | promedio=%.1f | RID=(%d,%d)\n",
            registros[indice].codigo,
            registros[indice].nombre,
            registros[indice].edad,
            registros[indice].promedio,
            registros[indice].rid.pagina_datos,
            registros[indice].rid.posicion
        );
    }
}

static int calcular_nivel(int cantidad_claves) {
    if (cantidad_claves > 0) {
        return 1;
    }

    /* ERROR INTENCIONAL: falta retornar cuando no hay claves. */
}

static int retornar_codigo_incorrecto(void) {
    /* ERROR INTENCIONAL: la funcion debe retornar int, no char *. */
    return "codigo_invalido";
}

static void demostrar_errores(ArbolBMas *arbol, Registro *registro) {
    int variable_no_utilizada = 50;
    int codigo_desde_texto = "ABC";
    unsigned char pagina_pequena = 300;
    int numero_sin_inicializar;
    int resultado_division = 100 / 0;
    int repetido = 1;
    int repetido = 2;
    Nodo *nodo_incorrecto = registro;
    char *nombre_incorrecto = 25;

    printf("Numero sin inicializar: %d\n", numero_sin_inicializar);

    /* ERROR INTENCIONAL: Registro no contiene el miembro 'nota'. */
    registro->nota = 18;

    /* ERROR INTENCIONAL: %s espera una cadena y edad es int. */
    printf("Edad como texto: %s\n", registro->edad);

    /* ERROR INTENCIONAL: buscar_arbol necesita tres argumentos. */
    buscar_arbol(arbol);

    /* ERROR INTENCIONAL: el identificador no fue declarado. */
    pagina_actual = 10;

    printf(
        "%d %d %d %p %s\n",
        codigo_desde_texto,
        pagina_pequena,
        resultado_division + repetido,
        (void *)nodo_incorrecto,
        nombre_incorrecto
    );
}

int main(void) {
    ArbolBMas arbol = {0};
    Registro registros[REGISTROS_POR_PAGINA] = {0};
    RID encontrado = {0};
    int indice = 0;

    inicializar_arbol(&arbol);
    generar_registros(registros, REGISTROS_POR_PAGINA);

    for (indice = 0; indice < REGISTROS_POR_PAGINA; indice++) {
        insertar_arbol(
            &arbol,
            registros[indice].codigo,
            registros[indice].rid
        );
    }

    mostrar_registros(registros, REGISTROS_POR_PAGINA);

    if (buscar_arbol(&arbol, registros[1].codigo, &encontrado)) {
        printf(
            "Encontrado en RID=(%d,%d)\n",
            encontrado.pagina_datos,
            encontrado.posicion
        );
    }

    printf("Nivel del arbol: %d\n", calcular_nivel(arbol.raiz->cantidad_claves));
    demostrar_errores(&arbol, &registros[0]);
    return retornar_codigo_incorrecto();
}
