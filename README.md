# Analizador educativo de errores de C

Proyecto orientado a analizar y mejorar los mensajes de error que GCC genera
al revisar programas escritos en C. El sistema transforma diagnosticos
tecnicos en explicaciones en espanol dirigidas a estudiantes principiantes.

El proyecto puede utilizarse desde una interfaz de linea de comandos o desde
una interfaz web local.

## Alcance del proyecto

Este sistema no es un compilador completo ni un interprete. Es un analizador
estatico educativo y un transformador de diagnosticos que combina:

- GCC como compilador y fuente de diagnosticos reales.
- Un lexer propio para tokenizar la salida de GCC.
- Un parser propio para construir diagnosticos estructurados.
- Un AST real del codigo C construido con `pycparser`.
- Una tabla de simbolos propia con ambitos lexicos y firmas de funciones.
- Reglas de analisis semantico desarrolladas en el proyecto.
- Un generador de explicaciones pedagogicas en espanol.
- Salidas para terminal, JSON e interfaz web.

El objetivo no es reemplazar a GCC, sino usar su precision tecnica y agregar
una capa educativa que explique el problema, su causa probable y una forma de
corregirlo.

## Arquitectura actual

```text
                         +---------------------+
                         | Archivo o codigo C  |
                         +----------+----------+
                                    |
                  +-----------------+-----------------+
                  |                                   |
          +-------v-------+                   +-------v-------+
          |      GCC      |                   |   pycparser   |
          +-------+-------+                   +-------+-------+
                  |                                   |
             stderr real                          AST de C
                  |                                   |
          +-------v-------+                   +-------v-------+
          | Lexer de GCC  |                   | Tabla simbolos|
          +-------+-------+                   +-------+-------+
                  |                                   |
               tokens                         Analisis semantico
                  |                                   |
          +-------v-------+                           |
          |    Parser     |                           |
          +-------+-------+                           |
                  |                                   |
          Diagnosticos GCC                            |
                  +-----------------+-----------------+
                                    |
                          Deduplicacion y union
                                    |
                         +----------v----------+
                         |     Explainer       |
                         +----------+----------+
                                    |
                +-------------------+-------------------+
                |                   |                   |
              CLI                 JSON            Interfaz web
```

El punto comun para CLI y web es `src/analyzer.py`. Su funcion
`analizar_archivo()` ejecuta el pipeline y devuelve un `AnalysisResult` con
todos los productos intermedios y finales. `src/report.py` construye el mismo
reporte JSON para ambos modos de ejecucion.

## Funcionalidades implementadas

### Procesamiento con GCC

- Ejecucion automatica de GCC sobre archivos `.c` y `.C`.
- Forzado del lenguaje C mediante `-x c`, incluso para extension `.C`.
- Activacion de advertencias con `-Wall`, `-Wextra`, `-Wconversion`,
  `-Wuninitialized` y `-Wreturn-type`.
- Compilacion sin enlace y generacion del objeto en un directorio temporal.
- Eliminacion automatica del objeto temporal.
- Captura completa de `stderr`.
- Tiempo maximo de ejecucion de GCC de 10 segundos.
- Configuracion de GCC en ingles mediante `LC_ALL=C` y `LANG=C` para
  mantener estables los patrones de clasificacion del lexer con
  independencia del sistema operativo del usuario.
- Manejo controlado de GCC ausente, timeout y errores de ejecucion.
- Extraccion del nombre de la funcion desde el contexto `In function`
  de GCC para enriquecer el simbolo de errores de retorno y tipos.

El programa del estudiante nunca se ejecuta. GCC solo lo compila con `-c` para
obtener diagnosticos.

### Analisis lexico de diagnosticos

El lexer procesa lineas con este formato:

```text
archivo.c:linea:columna: severidad: mensaje
```

Genera tokens para:

- archivo
- linea
- columna
- severidad
- mensaje crudo
- tipo de error
- simbolo relacionado
- contenido desconocido

Las lineas de contexto que imprime GCC no se convierten en diagnosticos. Las
`note` se conservan como informacion secundaria y se adjuntan al error o
advertencia anterior.

### Categorias reconocidas

El sistema clasifica actualmente:

- `undeclared`: variable o funcion no declarada.
- `implicit_declaration`: funcion utilizada sin declaracion o cabecera.
- `redeclaration`: identificador declarado mas de una vez.
- `expected_token`: token esperado, incluido el punto y coma.
- `type_mismatch`: tipos incompatibles.
- `wrong_arguments`: cantidad o tipo incorrecto de argumentos.
- `return_error`: retorno incompatible o declaracion incorrecta de `main`.
- `unused_variable`: variable o parametro no utilizado.
- `division_by_zero`: division por cero.
- `pointer_error`: uso incorrecto de punteros.
- `format_mismatch`: formato incorrecto en `printf` o funciones similares.
- `unbalanced_delimiter`: llaves, parentesis o delimitadores desbalanceados.
- `missing_return`: funcion no `void` que puede terminar sin retornar.
- `dangerous_conversion`: conversion que puede perder informacion.
- `uninitialized_variable`: variable posiblemente no inicializada.
- `struct_access`: acceso incorrecto a estructuras o miembros inexistentes.
- `preprocessor_error`: errores de cabeceras, macros o directivas.
- `assignment_in_condition`: posible uso de `=` en lugar de `==`.
- `desconocido`: diagnostico que aun no tiene una categoria especifica.

### Extraccion de simbolos

La extraccion evita utilizar tipos de C como si fueran nombres de variables.
Tambien cuenta con reglas especificas para obtener:

- variable afectada por una conversion o incompatibilidad
- variable posiblemente no inicializada
- operando de una desreferencia incorrecta
- miembro inexistente de una estructura
- funcion con argumentos incorrectos
- funcion sin retorno o con retorno incompatible
- archivo de cabecera faltante
- especificador de formato incorrecto
- nombre de funcion extraido del contexto `In function` de GCC para
  errores de tipo en sentencias `return`

Por ejemplo, para:

```c
int z = "hola";
```

el simbolo extraido es `z`, no `int`.

### Parser y arbol de diagnosticos

El parser agrupa los tokens en objetos `DiagnosticEntry` con:

- archivo, linea y columna
- severidad
- mensaje original
- categoria
- simbolo
- origen: `gcc` o `semantico`

Ademas construye un arbol para cada diagnostico:

```text
Diagnostico
  Ubicacion
    Archivo
    Linea
    Columna
  Severidad
  TipoError
  Origen
  Simbolo
  MensajeGCC
  ContextoFuente
  NotasGCC
```

Este arbol representa la estructura del diagnostico. No debe confundirse con
el AST del programa C.

### AST del codigo C

`src/ast_builder.py` construye un AST real del archivo C mediante
`pycparser`.

Antes de analizar:

- ejecuta el preprocesador de GCC en modo C con `-E`
- expande macros de objeto y de funcion
- resuelve directivas condicionales e inclusiones locales
- bloquea las cabeceras reales del sistema con `-nostdinc`
- utiliza cabeceras controladas para `assert.h`, `ctype.h`, `errno.h`,
  `float.h`, `limits.h`, `math.h`, `stdarg.h`, `stdbool.h`, `stddef.h`,
  `stdint.h`, `stdio.h`, `stdlib.h`, `string.h` y `time.h`
- conserva las coordenadas del archivo principal mediante las marcas de linea
  generadas por el preprocesador

Las cabeceras controladas contienen solo los tipos, macros y prototipos
necesarios para construir el AST; no incluyen implementaciones ni ejecutan el
programa. Si GCC no esta disponible, se mantiene como respaldo la limpieza
anterior de comentarios y directivas.

Cada nodo del AST almacena:

- tipo de nodo
- rol respecto al padre
- atributos
- linea y columna
- nodos hijos

El AST se puede visualizar en modo debug y se incluye completo en la salida
JSON. Si el codigo tiene un error sintactico que impide construirlo, el sistema
conserva los diagnosticos de GCC y activa un respaldo semantico basado en
expresiones regulares.

### Tabla de simbolos con ambitos

`src/symbol_table.py` recorre el AST y construye una tabla jerarquica con:

- ambito global
- ambitos de funciones
- ambitos de bloques
- ambitos de ciclos `for`

Registra:

- variables globales y locales
- parametros
- funciones y funciones externas conocidas
- `typedef`
- constantes de enumeraciones
- tipo de dato
- ubicacion de la declaracion
- ubicaciones de cada uso
- cantidad de usos
- firma de funciones: lista de tipos de parametros para validar llamadas
- distincion entre prototipos no especificados, parametros `(void)` y
  funciones variadicas
- firmas obtenidas desde definiciones, prototipos y cabeceras incluidas
- miembros y tipos de estructuras y uniones
- punteros a funcion declarados directamente o mediante `typedef`

La resolucion de un identificador comienza en el ambito actual y continua
hacia sus padres. Esto permite manejar correctamente el sombreado de variables.

La tabla tambien registra:

- usos de identificadores sin declaracion visible
- redeclaraciones en el mismo ambito
- linea de la declaracion original y de la duplicada

Un prototipo seguido por la definicion de la misma funcion se acepta como un
caso valido.

### Analisis semantico propio

El analizador semantico usa el AST y la tabla de simbolos para detectar, sin
depender exclusivamente de GCC:

- variables locales no utilizadas
- parametros no utilizados
- redeclaraciones en el mismo ambito
- identificadores sin declaracion visible
- divisiones por expresiones constantes iguales a cero
- asignaciones dentro de condiciones
- funciones no `void` que pueden terminar sin retornar
- declaracion `void main`
- uso de funciones conocidas de entrada/salida sin incluir `<stdio.h>`
- incompatibilidad de tipos en asignaciones e inicializaciones
- incompatibilidad entre el tipo declarado de retorno y el valor retornado
- cantidad incorrecta de argumentos en llamadas a funciones
- tipo incompatible de cada argumento respecto a su parametro
- alias `typedef` resueltos antes de comparar tipos de argumentos
- tipos de miembros accedidos con `.` y `->`
- firmas y llamadas realizadas mediante punteros a funcion
- funciones usadas como callbacks y funciones que devuelven callbacks
- llamadas anidadas cuyo retorno alimenta otra llamada
- promociones enteras y conversiones aritmeticas usuales
- conversiones numericas que pueden perder rango, precision o signo
- variables locales usadas antes de recibir un valor

La inferencia de argumentos contempla literales, identificadores, casts,
punteros, arreglos, miembros de estructuras, callbacks, operaciones binarias,
expresiones ternarias y tipos de retorno de llamadas simples o anidadas. En
funciones variadicas valida los parametros fijos y permite los argumentos
adicionales.

La evaluacion de constantes soporta numeros, operadores unarios, sumas,
restas, multiplicaciones, divisiones, modulo y conversiones simples.

Cuando el AST no puede construirse, `src/semantic.py` aplica un conjunto mas
limitado de reglas con expresiones regulares.

### Deduplicacion

GCC y el analizador semantico pueden encontrar el mismo problema. Antes de
mostrar resultados, `src/analyzer.py` normaliza rutas y elimina duplicados por:

- archivo
- categoria
- linea
- simbolo

Para argumentos incompatibles tambien reconoce como equivalentes las
categorias relacionadas de GCC (`type_mismatch`, `pointer_error` y
`dangerous_conversion`) y la regla semantica `wrong_arguments`.

Cuando GCC ya tiene el diagnostico equivalente, se conserva el mensaje de GCC
y no se agrega una segunda tarjeta semantica.

### Explicaciones pedagogicas

`src/explainer.py` transforma cada diagnostico en:

- titulo comprensible
- explicacion del problema
- causa probable
- sugerencia de correccion
- contexto de la linea fuente

Algunas sugerencias utilizan la linea real del estudiante para proponer una
correccion mas concreta.

### Modos de salida

El proyecto ofrece:

- modo estudiante por defecto
- modo debug para inspeccionar todas las etapas
- exportacion JSON
- interfaz web local

Los errores y advertencias se distinguen mediante etiquetas visibles, no solo
por color.

## Interfaz web

La aplicacion Flask esta definida en `web_app.py` y ofrece:

- editor para escribir o pegar codigo C
- carga de archivos `.c` y `.C`
- limite de entrada de 512 KB
- validacion de extension y UTF-8
- procesamiento dentro de un directorio temporal
- resumen de errores, advertencias y cobertura
- mensajes mejorados con contexto de codigo
- notas de GCC asociadas
- descarga del reporte JSON completo del analisis actual
- sintesis de voz individual o para todos los diagnosticos
- controles para pausar, continuar, detener y ajustar la velocidad de lectura
- pronunciacion adaptada de simbolos de C, como `#` leido como "numeral"
- seccion desplegable con AST y tabla de simbolos
- diseno responsive para escritorio y movil

La interfaz incluye fundamentos de accesibilidad:

- HTML semantico
- etiquetas asociadas a controles
- navegacion por teclado
- foco visible
- enlace para saltar al contenido
- regiones `role="status"` y `role="alert"`
- indicadores textuales ademas del color
- soporte para preferencia de movimiento reducido
- lectura iniciada solo por accion del usuario
- seleccion automatica de una voz disponible en espanol

La sintesis utiliza la API de voz del navegador. El texto se procesa en el
equipo del usuario y no se envia desde la aplicacion a un servicio de voz.

## Estructura del repositorio

```text
COMPILADOR/
|-- main.py                    # Entrada de linea de comandos
|-- web_app.py                 # Aplicacion Flask
|-- requirements.txt          # Dependencias de ejecucion
|-- requirements-dev.txt      # Dependencias de pruebas
|-- README.md
|-- src/
|   |-- analyzer.py            # API comun y union de resultados
|   |-- ast_builder.py         # Construccion del AST de C
|   |-- explainer.py           # Explicaciones pedagogicas
|   |-- lexer.py               # Ejecucion de GCC y tokenizacion
|   |-- parser.py              # Diagnosticos y arbol de diagnostico
|   |-- report.py              # Reporte JSON compartido por CLI y web
|   |-- semantic.py            # Coordinador y respaldo textual
|   |-- semantic_ast.py        # Reglas semanticas sobre el AST
|   |-- symbol_table.py        # Tabla de simbolos, ambitos y firmas
|   |-- token.py               # Tipos de token
|   `-- fake_libc_include/     # Cabeceras minimas para pycparser
|-- templates/
|   `-- index.html             # Vista principal de la interfaz
|-- static/
|   |-- app.js                 # Interaccion del editor y carga
|   `-- styles.css             # Diseno responsive y accesible
|-- examples/                  # Programas C de demostracion
|-- outputs/                   # JSON generados, ignorados por Git
`-- test/                      # Pruebas automatizadas
```

## Requisitos

- Python 3.10 o superior.
- GCC instalado y disponible en `PATH`.
- Navegador moderno para la interfaz web.

Dependencias de ejecucion:

- `pycparser`
- `Flask`

Dependencia de desarrollo:

- `pytest`

Comprobar herramientas:

```powershell
python --version
gcc --version
```

## Instalacion

Desde PowerShell, dentro de la carpeta del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Para ejecutar tambien las pruebas:

```powershell
python -m pip install -r requirements-dev.txt
```

Si PowerShell bloquea la activacion del entorno, se puede usar directamente:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Ejecucion web

Iniciar Flask:

```powershell
python web_app.py
```

Abrir:

```text
http://127.0.0.1:5000
```

Para detener el servidor:

```text
Ctrl + C
```

El servidor incluido es para desarrollo local. No se recomienda publicarlo en
Internet sin autenticacion, aislamiento adicional y un servidor WSGI de
produccion.

## Ejecucion por terminal

### Modo estudiante

```powershell
python main.py examples\variable_no_declarada.c
```

Muestra solamente los mensajes mejorados y el resumen.

### Modo debug

```powershell
python main.py examples\variable_no_declarada.c --debug
```

Agrega:

- `stderr` crudo de GCC
- tokens del lexer
- AST del codigo C
- tabla de simbolos
- diagnosticos del parser
- diagnosticos semanticos propios
- arboles de diagnosticos

### Exportar JSON

```powershell
python main.py examples\variable_no_declarada.c --json outputs\diagnosticos.json
```

En la interfaz web, despues de analizar el codigo, el boton `Descargar JSON`
genera el mismo formato de reporte sin exponer la ruta temporal del servidor.

### Combinar debug y JSON

```powershell
python main.py examples\variable_no_declarada.c --debug --json outputs\diagnosticos.json
```

### Codigo correcto

```powershell
python main.py examples\correcto.c
```

Salida principal:

```text
Revision completada: no se detectaron errores ni advertencias.
```

## Formato de salida mejorada

Ejemplo conceptual:

```text
[ERROR] Variable o funcion 'total' no declarada
Ubicacion: examples\variable_no_declarada.c:4:20

Codigo:
  4 |     printf("%d\n", total);
    |                    ^

Explicacion: el identificador no tiene una declaracion visible.
Causa probable: se olvido declarar la variable o se escribio otro nombre.
Sugerencia: declarar 'total' antes de utilizarla.
```

## Exportacion JSON

El reporte JSON contiene:

- archivo fuente normalizado con `/`
- resumen de clasificacion
- diagnosticos principales
- severidad y etiqueta visible
- categoria y simbolo
- origen GCC o semantico
- mensaje tecnico original
- explicacion, causa y sugerencia
- contexto de codigo
- notas de GCC
- arbol de cada diagnostico
- AST completo del codigo C
- error de construccion del AST, si existe
- tabla de simbolos jerarquica
- usos no resueltos y redeclaraciones

Estructura resumida:

```json
{
  "archivo_fuente": "examples/programa.c",
  "resumen": {
    "diagnosticos_principales": 1,
    "clasificados": 1,
    "desconocidos": 0,
    "cobertura_clasificacion": 100.0
  },
  "diagnosticos": [],
  "ast_codigo": {},
  "error_ast": null,
  "tabla_simbolos": {}
}
```

## Ejemplos incluidos

### Flujo general

| Archivo | Objetivo |
| --- | --- |
| `correcto.c` | Programa sin diagnosticos |
| `error_lexico.c` | Varios errores combinados |
| `extension_mayuscula.C` | Compatibilidad con extension `.C` |

### Categorias GCC

| Archivo | Caso principal |
| --- | --- |
| `variable_no_declarada.c` | Identificador no declarado |
| `falta_punto_y_coma.c` | Token esperado |
| `tipo_incompatible.c` | Tipos incompatibles |
| `funcion_implicita.c` | Funcion no declarada |
| `argumentos_incorrectos.c` | Cantidad de argumentos |
| `variable_no_usada.c` | Variable no utilizada |
| `redeclaracion.c` | Redeclaracion |
| `division_por_cero.c` | Division por cero |
| `retorno_incorrecto.c` | Retorno incorrecto |
| `error_puntero.c` | Error de puntero |
| `formato_printf.c` | Formato de `printf` |
| `delimitador_desbalanceado.c` | Delimitador faltante |
| `falta_retorno.c` | Funcion sin retorno |
| `conversion_peligrosa.c` | Conversion peligrosa |
| `variable_no_inicializada.c` | Variable no inicializada |
| `acceso_estructura.c` | Acceso a estructura |
| `error_preprocesador.c` | Error de preprocesador |

### Analisis semantico propio

| Archivo | Regla demostrada |
| --- | --- |
| `semantico_correcto.c` | Programa aceptado por reglas propias |
| `semantico_variable_no_usada.c` | Variable local no utilizada |
| `semantico_falta_retorno.c` | Camino sin retorno |
| `semantico_division_cero.c` | Expresion constante igual a cero |
| `semantico_falta_stdio.c` | Funcion de E/S sin `<stdio.h>` |
| `semantico_asignacion.c` | Asignacion dentro de condicion |
| `semantico_void_main.c` | Declaracion `void main` |
| `semantico_tipos_asignacion.c` | Tipos incompatibles en asignacion |
| `semantico_retorno_incompatible.c` | Tipo de retorno incompatible |
| `semantico_variable_no_inicializada.c` | Variable usada sin inicializar |
| `semantico_argumento_tipo_incorrecto.c` | Tipo individual de argumento incompatible |
| `semantico_preprocesador_controlado.c` | Macros y tipos de cabeceras controladas |
| `semantico_cabeceras_adicionales.c` | `ctype`, limites, tiempo, aserciones y argumentos variables |
| `arbol_b_mas_con_errores.c` | Programa C extenso con errores intencionales variados |
| `semantico_estructuras_inferencia.c` | Inferencia del tipo de un miembro de estructura |
| `semantico_puntero_funcion.c` | Callback declarado mediante `typedef` |
| `semantico_callback_anidado.c` | Funcion que devuelve un puntero a funcion |
| `semantico_llamada_anidada.c` | Tipo incorrecto propagado entre llamadas anidadas |
| `semantico_conversion_compleja.c` | Conversion numerica fuera del rango de destino |

Ejecutar cualquier ejemplo:

```powershell
python main.py examples\formato_printf.c
```

## Pruebas

Ejecutar toda la suite:

```powershell
python -m pytest -q
```

Ultima verificacion del estado documentado:

```text
265 passed
```

La cobertura funcional incluye:

- ejecucion real de GCC
- clasificacion y extraccion de simbolos
- compatibilidad de rutas Windows y extension `.C`
- agrupacion de notas
- parser y arboles de diagnosticos
- AST del codigo C
- preprocesamiento de macros, cabeceras locales y 14 cabeceras controladas
- tipos, constantes y prototipos de `ctype.h`, `time.h` y otras bibliotecas
- macros de aserciones y manejo de argumentos variables con `stdarg.h`
- tabla de simbolos y resolucion por ambitos
- firmas normales, `(void)` y variadicas
- validacion de cantidad y tipos individuales de argumentos
- resolucion de alias `typedef` en llamadas
- miembros de estructuras y uniones
- punteros a funcion, callbacks y llamadas anidadas
- promociones enteras y conversiones numericas con perdida
- sombreado y redeclaraciones
- usos no resueltos
- reglas semanticas AST y respaldo textual
- deteccion de tipos incompatibles en asignaciones e inicializaciones
- deteccion de tipo de retorno incompatible con la declaracion
- deteccion de variables usadas sin inicializar
- deduplicacion GCC/semantico
- explicaciones para todas las categorias
- contexto del codigo fuente
- modo estudiante, debug y JSON
- manejo de errores externos
- API estructurada `analizar_archivo()`
- rutas web, codigo pegado y carga de archivos
- descarga web del mismo reporte JSON disponible en CLI
- validaciones de la interfaz Flask
- controles web de sintesis de voz

## Relacion con las etapas de un compilador

El proyecto contiene componentes equivalentes a varias etapas, aunque su
objetivo no sea generar codigo ejecutable:

| Etapa | Implementacion en el proyecto |
| --- | --- |
| Analisis lexico | Tokenizacion de `stderr` de GCC en `src/lexer.py` |
| Analisis sintactico de diagnosticos | `DiagnosticEntry` y arbol de diagnostico en `src/parser.py` |
| Analisis sintactico de C | AST mediante `pycparser` en `src/ast_builder.py` |
| Tabla de simbolos | Ambitos, firmas y resolucion en `src/symbol_table.py` |
| Analisis semantico | Reglas AST en `src/semantic_ast.py` |
| Presentacion de errores | Explicaciones en `src/explainer.py` |

No implementa generacion de codigo, optimizacion, enlazado ni ejecucion de
programas. Es correcto describirlo como un analizador estatico educativo para
C apoyado en GCC.

## Relacion con los papers base

El proyecto sigue la idea central de *Compiler Error Messages Considered
Unhelpful*: los mensajes tecnicos suelen ser dificiles de interpretar para
personas que estan aprendiendo.

Tambien aplica un enfoque relacionado con *An Effective Approach to Enhancing
Compiler Error Messages*: tomar el diagnostico existente, reconocer su
estructura y presentar una version mas util.

La adaptacion realizada en este proyecto es:

```text
diagnostico GCC
  -> clasificacion
  -> contexto estructural y semantico
  -> explicacion pedagogica en espanol
```

## Limitaciones actuales

- Solo analiza codigo C.
- Requiere GCC instalado localmente.
- La clasificacion depende de patrones de mensajes de GCC en ingles.
- El analisis de tipos cubre estructuras, punteros a funcion, llamadas
  anidadas y promociones frecuentes, pero no implementa todos los casos del
  estandar C ni todas las extensiones de GCC.
- El analisis de flujo de control cubre casos basicos, no todos los caminos de
  `switch`, ciclos, `goto` o construcciones complejas.
- El preprocesamiento del AST reconoce las 14 cabeceras controladas incluidas
  en el proyecto y cabeceras locales. Otras cabeceras del sistema requieren un
  stub adicional.
- Macros dependientes de extensiones especificas del compilador pueden producir
  construcciones que `pycparser` no comprenda.
- El respaldo por expresiones regulares es menos preciso que el analisis AST.
- La interfaz Flask incluida es un servidor de desarrollo local.
- La sintesis de voz depende de la API, las voces y el idioma disponibles en el
  navegador y el sistema operativo.
- El sistema propone sugerencias, pero no modifica automaticamente el codigo.

## Pendientes recomendados

1. Evaluar los mensajes mejorados con estudiantes y medir comprension, tiempo
   de correccion y cobertura de categorias.
2. Preparar despliegue con aislamiento y servidor WSGI solo si la aplicacion
   deja de ser exclusivamente local.
