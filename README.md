# Proyecto de compiladores orientado a analizar y mejorar mensajes de error generados por GCC para programas en C.

El sistema no implementa todavia un compilador completo ni un lenguaje propio. Actualmente trabaja sobre la salida de GCC: analiza un archivo `.c`, captura `stderr`, tokeniza los mensajes, los transforma en diagnosticos estructurados y genera explicaciones en espanol pensadas para estudiantes principiantes.

## Estado Actual

El pipeline implementado es:

```text
archivo .c -> GCC -> stderr -> Lexer -> Parser -> arbol de diagnostico -> Explainer -> mensajes mejorados
```

El avance actual incluye:

1. Ejecucion automatica de GCC sobre archivos C.
2. Captura del `stderr` generado por GCC.
3. Analisis lexico de mensajes `error`, `warning` y `note`.
4. Clasificacion de errores frecuentes.
5. Extraccion de simbolos relevantes.
6. Analisis sintactico para construir `DiagnosticEntry`.
7. Generacion de explicaciones en espanol con causa probable y sugerencia.
8. Agrupacion de `note` de GCC como informacion secundaria del diagnostico anterior.
9. Modo estudiante por defecto, mostrando solo mensajes mejorados.
10. Modo `--debug`, mostrando `stderr`, tokens y diagnosticos tecnicos.
11. Contexto de codigo fuente con linea y marcador `^`.
12. Ejemplos separados por tipo de error.
13. Pruebas unitarias e integracion basica del flujo.
14. Manejo controlado de archivos invalidos, GCC ausente, errores de lectura y timeout.
15. Mensaje especifico cuando el codigo no contiene errores ni advertencias.
16. Resumen con diagnosticos clasificados, desconocidos y porcentaje de cobertura.
17. Clasificacion ampliada y comprobada con archivos C reales.
18. Compilacion temporal sin enlace y sin dejar archivos objeto en el proyecto.
19. Diferenciacion visible entre errores y advertencias.
20. Exportacion de resultados estructurados a JSON.
21. Arbol sintactico de diagnosticos para representar la estructura interna de cada error.

## Estructura Del Proyecto

```text
COMPILADOR/
├── main.py
├── README.md
├── examples/
│   ├── correcto.c
│   ├── error_lexico.c
│   ├── acceso_estructura.c
│   ├── argumentos_incorrectos.c
│   ├── conversion_peligrosa.c
│   ├── delimitador_desbalanceado.c
│   ├── division_por_cero.c
│   ├── error_preprocesador.c
│   ├── error_puntero.c
│   ├── extension_mayuscula.C
│   ├── falta_punto_y_coma.c
│   ├── falta_retorno.c
│   ├── formato_printf.c
│   ├── funcion_implicita.c
│   ├── redeclaracion.c
│   ├── retorno_incorrecto.c
│   ├── tipo_incompatible.c
│   ├── variable_no_declarada.c
│   ├── variable_no_inicializada.c
│   └── variable_no_usada.c
├── src/
│   ├── __init__.py
│   ├── explainer.py
│   ├── lexer.py
│   ├── parser.py
│   └── token.py
└── test/
    ├── conftest.py
    ├── test_explainer.py
    ├── test_lexer.py
    ├── test_main.py
    └── test_parser.py
```

## Componentes

### `main.py`

Punto de entrada del proyecto.

Ejecuta el flujo completo:

```text
.c -> GCC -> Lexer -> Parser -> Explainer
```

Por defecto muestra una salida limpia para estudiantes:

- etiqueta `[ERROR]` o `[ADVERTENCIA]`
- titulo del problema
- ubicacion
- contexto de codigo
- explicacion
- causa probable
- sugerencia
- notas de GCC asociadas, si existen
- resumen de cobertura de clasificacion

Tambien soporta modo debug con `--debug`.

Antes de ejecutar GCC valida que:

- la ruta exista
- la ruta corresponda a un archivo
- el archivo tenga extension `.c`
- el archivo pueda leerse como UTF-8

Tambien muestra errores controlados si GCC no esta instalado, no puede ejecutarse o excede el tiempo maximo.

### `src/lexer.py`

Ejecuta GCC en modo de compilacion sin enlace con:

```bash
gcc -x c -O1 -Wall -Wextra -Wconversion -Wuninitialized -Wreturn-type -c archivo.c
```

La opcion `-x c` fuerza el analisis como lenguaje C, incluso cuando el archivo usa la extension `.C`. El archivo objeto se escribe dentro de un directorio temporal que se elimina automaticamente. De esta forma se activan analisis de flujo como variables no inicializadas y funciones sin retorno, sin dejar archivos `.o` en el proyecto.

La ejecucion tiene un tiempo maximo de 10 segundos. Luego se tokeniza la salida de GCC.

Reconoce mensajes con formato:

```text
archivo.c:linea:columna: severidad: mensaje
```

Clasifica errores frecuentes:

- `undeclared`
- `expected_token`
- `implicit_declaration`
- `type_mismatch`
- `wrong_arguments`
- `unused_variable`
- `return_error`
- `redeclaration`
- `division_by_zero`
- `pointer_error`
- `format_mismatch`
- `unbalanced_delimiter`
- `missing_return`
- `dangerous_conversion`
- `uninitialized_variable`
- `struct_access`
- `preprocessor_error`
- `desconocido`

La severidad `fatal error` de GCC se normaliza como `error`.

Tambien evita usar tipos de C como simbolos. Por ejemplo, en:

```text
initialization of 'int' from 'char *'
```

no toma `int` como simbolo. Si puede leer la linea fuente, extrae la variable afectada, por ejemplo `z` en:

```c
int z = "hola";
```

Para las categorias ampliadas realiza extraccion especifica:

- variable no inicializada: `numero`
- miembro inexistente de estructura: `altura`
- funcion sin retorno: `calcular`
- cabecera faltante: `biblioteca_inexistente.h`
- especificador de formato incorrecto: `%d`

El nombre de la funcion se obtiene del contexto `In function 'nombre':` que GCC imprime antes del diagnostico.

### `src/parser.py`

Agrupa tokens consecutivos en objetos `DiagnosticEntry` y construye un arbol sintactico simple para cada diagnostico.

Formato esperado:

```text
ARCHIVO LINEA COLUMNA SEVERIDAD MENSAJE_CRUDO TIPO_ERROR [SIMBOLO]
```

Cada diagnostico contiene:

- `archivo`
- `linea`
- `columna`
- `severidad`
- `mensaje_crudo`
- `tipo_error`
- `simbolo`

El arbol de diagnostico no es un AST completo del lenguaje C. Es una representacion jerarquica del mensaje procesado por el sistema:

```text
Diagnostico
  Ubicacion
    Archivo
    Linea
    Columna
  Severidad
  TipoError
  Simbolo
  MensajeGCC
  ContextoFuente
  NotasGCC
```

Esta estructura permite mostrar que el parser no deja la salida como texto plano, sino que organiza cada diagnostico en partes reconocibles.

### `src/explainer.py`

Convierte un `DiagnosticEntry` en una explicacion pedagogica en espanol.

Retorna:

- `titulo`
- `explicacion`
- `causa_probable`
- `sugerencia`

Ejemplo conceptual:

```text
Variable o funcion 'y' no declarada
Explicacion: El compilador encontro el nombre 'y' en tu codigo pero no sabe que es.
Causa probable: Olvidaste declararla o escribiste mal su nombre.
Sugerencia: Declara 'y' antes de usarla o revisa si falta un #include.
```

### `src/token.py`

Define los tipos de token:

- `ARCHIVO`
- `LINEA`
- `COLUMNA`
- `SEVERIDAD`
- `MENSAJE_CRUDO`
- `TIPO_ERROR`
- `SIMBOLO`
- `DESCONOCIDO`

## Uso

Requisitos:

- Python 3.10 o superior.
- GCC instalado y disponible en el `PATH`.
- `pytest` para ejecutar pruebas.

Modo estudiante:

```bash
python main.py examples/error_lexico.c
```

Salida esperada:

```text
=== MENSAJES MEJORADOS ===
[1] [ERROR] Variable o funcion 'y' no declarada
    Ubicacion: examples\error_lexico.c:4:20
    Codigo:
      4 |     printf("%d\n", y);
        |                    ^
    Explicacion: ...
    Causa probable: ...
    Sugerencia: ...
```

Modo debug:

```bash
python main.py examples/error_lexico.c --debug
```

El modo debug muestra:

- `stderr` crudo de GCC
- tokens generados por el lexer
- diagnosticos del parser
- arbol sintactico de diagnosticos
- mensajes mejorados

Exportar resultados a JSON:

```bash
python main.py examples/error_lexico.c --json outputs/diagnosticos.json
```

La ruta padre se crea automaticamente si no existe. El JSON contiene:

- archivo fuente
- resumen de clasificacion
- archivo, linea y columna de cada diagnostico
- severidad y etiqueta visible
- tipo de error y simbolo
- mensaje original de GCC
- titulo, explicacion, causa probable y sugerencia
- contexto de codigo
- notas asociadas de GCC
- arbol sintactico del diagnostico

El modo debug y la exportacion pueden combinarse:

```bash
python main.py examples/error_lexico.c --debug --json outputs/diagnosticos.json
```

Cuando no existen errores ni advertencias, el programa informa:

```text
Revision completada: no se detectaron errores ni advertencias.
```

Cuando existen diagnosticos, tambien muestra:

```text
=== RESUMEN DE CLASIFICACION ===
Diagnosticos principales: 4
Clasificados: 4
Desconocidos: 0
Cobertura de clasificacion: 100.0%
```

## Ejemplos Incluidos

Archivo correcto:

- `examples/correcto.c`

Archivo con varios errores combinados:

- `examples/error_lexico.c`

Archivos por tipo de error:

- `examples/variable_no_declarada.c`
- `examples/falta_punto_y_coma.c`
- `examples/tipo_incompatible.c`
- `examples/funcion_implicita.c`
- `examples/argumentos_incorrectos.c`
- `examples/variable_no_usada.c`
- `examples/redeclaracion.c`
- `examples/division_por_cero.c`
- `examples/retorno_incorrecto.c`
- `examples/error_puntero.c`
- `examples/formato_printf.c`
- `examples/delimitador_desbalanceado.c`
- `examples/falta_retorno.c`
- `examples/conversion_peligrosa.c`
- `examples/variable_no_inicializada.c`
- `examples/acceso_estructura.c`
- `examples/error_preprocesador.c`
- `examples/extension_mayuscula.C`

Los ejemplos de categorias ampliadas fueron compilados con GCC 13.2.0 para comprobar los mensajes reales emitidos y ajustar la clasificacion. `extension_mayuscula.C` comprueba que `.C` se acepte y se fuerce como lenguaje C, no C++.

## Pruebas

Ejecutar con el entorno virtual:

```bash
.venv\Scripts\python.exe -m pytest -q
```

O con Python global si tiene `pytest` instalado:

```bash
python -m pytest -q
```

Cobertura actual de pruebas:

- lexer sobre archivos correctos y con errores
- captura automatica de `stderr`
- tokenizacion de lineas reales de GCC
- clasificacion de errores frecuentes
- extraccion de simbolos
- parser sobre diagnosticos validos e invalidos
- arbol sintactico de diagnosticos
- explainer para todos los tipos soportados
- agrupacion de `note` como informacion secundaria
- modo estudiante y modo debug
- contexto de codigo fuente
- ejemplos individuales por tipo de error
- manejo de errores externos y timeout
- salida especifica para codigo correcto
- resumen y cobertura de clasificacion
- categorias ampliadas con mensajes simulados y archivos C reales
- normalizacion de `fatal error`

## Relacion Con Los Papers Base

El proyecto se alinea con la idea de mejorar mensajes de error de compilador para principiantes:

- El paper *Compiler Error Messages Considered Unhelpful* justifica que los mensajes de compiladores suelen ser dificiles de entender, especialmente para novatos.
- El paper *An Effective Approach to Enhancing Compiler Error Messages* muestra una estrategia similar a Decaf: tomar mensajes crudos del compilador y presentar mensajes mejorados junto con explicaciones mas utiles.

Este proyecto aplica esa idea a GCC y C:

```text
mensaje crudo de GCC -> diagnostico estructurado -> explicacion pedagogica
```

## Pendientes

- Mejorar sugerencias usando mas contexto del codigo.
- Ampliar patrones a medida que aparezcan nuevos mensajes de GCC.
- Forzar un idioma estable para la salida de GCC.
- Mejorar la extraccion de simbolos para las categorias nuevas.
- Evaluar el sistema con estudiantes o casos reales de laboratorio.
- Agregar una interfaz grafica o web si el proyecto crece.

## Resumen

El proyecto ya cuenta con un pipeline funcional para transformar mensajes de GCC en diagnosticos estructurados y explicaciones mas comprensibles. La contribucion principal actual no es compilar un lenguaje propio, sino mejorar la retroalimentacion que recibe un estudiante cuando comete errores en programas C.
