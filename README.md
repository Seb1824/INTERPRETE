# COMPILADOR

Proyecto de compiladores orientado a analizar y mejorar mensajes de error generados por GCC para programas en C.

El sistema no implementa todavia un compilador completo ni un lenguaje propio. Actualmente trabaja sobre la salida de GCC: compila un archivo `.c` en modo de revision sintactica, captura `stderr`, tokeniza los mensajes, los transforma en diagnosticos estructurados y genera explicaciones en espanol pensadas para estudiantes principiantes.

## Estado Actual

El pipeline implementado es:

```text
archivo .c -> GCC -> stderr -> Lexer -> Parser -> Explainer -> mensajes mejorados
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

## Estructura Del Proyecto

```text
COMPILADOR/
├── main.py
├── README.md
├── examples/
│   ├── correcto.c
│   ├── error_lexico.c
│   ├── argumentos_incorrectos.c
│   ├── division_por_cero.c
│   ├── falta_punto_y_coma.c
│   ├── funcion_implicita.c
│   ├── redeclaracion.c
│   ├── retorno_incorrecto.c
│   ├── tipo_incompatible.c
│   ├── variable_no_declarada.c
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

- titulo del problema
- ubicacion
- contexto de codigo
- explicacion
- causa probable
- sugerencia
- notas de GCC asociadas, si existen

Tambien soporta modo debug con `--debug`.

### `src/lexer.py`

Ejecuta GCC con:

```bash
gcc -Wall -fsyntax-only archivo.c
```

Luego tokeniza la salida de GCC.

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
- `desconocido`

Tambien evita usar tipos de C como simbolos. Por ejemplo, en:

```text
initialization of 'int' from 'char *'
```

no toma `int` como simbolo. Si puede leer la linea fuente, extrae la variable afectada, por ejemplo `z` en:

```c
int z = "hola";
```

### `src/parser.py`

Agrupa tokens consecutivos en objetos `DiagnosticEntry`.

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
[1] Variable o funcion 'y' no declarada
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
- mensajes mejorados

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
- explainer para todos los tipos soportados
- agrupacion de `note` como informacion secundaria
- modo estudiante y modo debug
- contexto de codigo fuente
- ejemplos individuales por tipo de error

Ultima verificacion realizada:

```text
84 passed
```

## Relacion Con Los Papers Base

El proyecto se alinea con la idea de mejorar mensajes de error de compilador para principiantes:

- El paper *Compiler Error Messages Considered Unhelpful* justifica que los mensajes de compiladores suelen ser dificiles de entender, especialmente para novatos.
- El paper *An Effective Approach to Enhancing Compiler Error Messages* muestra una estrategia similar a Decaf: tomar mensajes crudos del compilador y presentar mensajes mejorados junto con explicaciones mas utiles.

Este proyecto aplica esa idea a GCC y C:

```text
mensaje crudo de GCC -> diagnostico estructurado -> explicacion pedagogica
```

## Pendientes

- Agregar exportacion a `outputs/diagnosticos.txt` o `outputs/diagnosticos.json`.
- Medir cuantos diagnosticos quedan como `desconocido`.
- Mejorar sugerencias usando mas contexto del codigo.
- Separar visualmente errores y advertencias.
- Ampliar patrones para mas mensajes de GCC.
- Evaluar el sistema con estudiantes o casos reales de laboratorio.
- Agregar una interfaz grafica o web si el proyecto crece.

## Resumen

El proyecto ya cuenta con un pipeline funcional para transformar mensajes de GCC en diagnosticos estructurados y explicaciones mas comprensibles. La contribucion principal actual no es compilar un lenguaje propio, sino mejorar la retroalimentacion que recibe un estudiante cuando comete errores en programas C.
