from main import _combinar_diagnosticos
from src.parser import DiagnosticEntry
from src.semantic import SemanticAnalyzer


def test_semantic_detecta_variable_local_no_usada(tmp_path):
    fuente = tmp_path / "variable_no_usada.c"
    fuente.write_text(
        "int main() {\n"
        "    int temporal = 42;\n"
        "    return 0;\n"
        "}\n",
        encoding="utf-8",
    )

    diagnosticos = SemanticAnalyzer(str(fuente)).analizar()

    assert len(diagnosticos) == 1
    assert diagnosticos[0].tipo_error == "unused_variable"
    assert diagnosticos[0].simbolo == "temporal"
    assert diagnosticos[0].origen == "semantico"


def test_semantic_no_reporta_variable_usada(tmp_path):
    fuente = tmp_path / "variable_usada.c"
    fuente.write_text(
        "int main() {\n"
        "    int x = 42;\n"
        "    return x;\n"
        "}\n",
        encoding="utf-8",
    )

    diagnosticos = SemanticAnalyzer(str(fuente)).analizar()

    assert diagnosticos == []


def test_semantic_detecta_funcion_que_puede_no_retornar(tmp_path):
    fuente = tmp_path / "falta_retorno.c"
    fuente.write_text(
        "int calcular(int numero) {\n"
        "    if (numero > 0) {\n"
        "        return numero;\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    diagnosticos = SemanticAnalyzer(str(fuente)).analizar()

    assert len(diagnosticos) == 1
    assert diagnosticos[0].tipo_error == "missing_return"
    assert diagnosticos[0].simbolo == "calcular"
    assert diagnosticos[0].origen == "semantico"


def test_semantic_detecta_asignacion_dentro_de_condicion(tmp_path):
    fuente = tmp_path / "asignacion_condicion.c"
    fuente.write_text(
        "int main() {\n"
        "    int x = 0;\n"
        "    if (x = 1) {\n"
        "        return 1;\n"
        "    }\n"
        "    return 0;\n"
        "}\n",
        encoding="utf-8",
    )

    diagnosticos = SemanticAnalyzer(str(fuente)).analizar()
    asignacion = _buscar_diagnostico(diagnosticos, "assignment_in_condition")

    assert asignacion.linea == 3
    assert asignacion.columna == 11
    assert asignacion.simbolo == "="
    assert asignacion.severidad == "warning"
    assert asignacion.origen == "semantico"


def test_semantic_no_confunde_comparaciones_con_asignacion(tmp_path):
    fuente = tmp_path / "comparaciones.c"
    fuente.write_text(
        "int main() {\n"
        "    int x = 1;\n"
        "    if (x == 1 && x != 2 && x <= 3 && x >= 0) {\n"
        "        return x;\n"
        "    }\n"
        "    return 0;\n"
        "}\n",
        encoding="utf-8",
    )

    diagnosticos = SemanticAnalyzer(str(fuente)).analizar()

    assert not any(
        diagnostico.tipo_error == "assignment_in_condition"
        for diagnostico in diagnosticos
    )


def test_semantic_detecta_funcion_io_sin_stdio(tmp_path):
    fuente = tmp_path / "falta_stdio.c"
    fuente.write_text(
        "int main() {\n"
        "    printf(\"hola\\n\");\n"
        "    return 0;\n"
        "}\n",
        encoding="utf-8",
    )

    diagnosticos = SemanticAnalyzer(str(fuente)).analizar()
    cabecera = _buscar_diagnostico(diagnosticos, "implicit_declaration")

    assert cabecera.linea == 2
    assert cabecera.simbolo == "printf"
    assert cabecera.severidad == "error"
    assert cabecera.origen == "semantico"


def test_semantic_acepta_stdio_incluido(tmp_path):
    fuente = tmp_path / "con_stdio.c"
    fuente.write_text(
        "#include <stdio.h>\n"
        "int main() {\n"
        "    printf(\"hola\\n\");\n"
        "    return 0;\n"
        "}\n",
        encoding="utf-8",
    )

    diagnosticos = SemanticAnalyzer(str(fuente)).analizar()

    assert not any(
        diagnostico.tipo_error == "implicit_declaration"
        for diagnostico in diagnosticos
    )


def test_semantic_detecta_division_literal_por_cero(tmp_path):
    fuente = tmp_path / "division_cero.c"
    fuente.write_text(
        "int main() {\n"
        "    int resultado = 10 / 0;\n"
        "    return resultado;\n"
        "}\n",
        encoding="utf-8",
    )

    diagnosticos = SemanticAnalyzer(str(fuente)).analizar()
    division = _buscar_diagnostico(diagnosticos, "division_by_zero")

    assert division.linea == 2
    assert division.simbolo == "/"
    assert division.severidad == "warning"
    assert division.origen == "semantico"


def test_semantic_ignora_division_cero_en_comentarios_y_cadenas(tmp_path):
    fuente = tmp_path / "texto_division.c"
    fuente.write_text(
        "int main() {\n"
        "    // 10 / 0 no debe analizarse\n"
        "    const char *texto = \"10 / 0\";\n"
        "    return texto[0] == '1' ? 0 : 1;\n"
        "}\n",
        encoding="utf-8",
    )

    diagnosticos = SemanticAnalyzer(str(fuente)).analizar()

    assert not any(
        diagnostico.tipo_error == "division_by_zero"
        for diagnostico in diagnosticos
    )


def test_semantic_detecta_void_main(tmp_path):
    fuente = tmp_path / "void_main.c"
    fuente.write_text("void main() {\n}\n", encoding="utf-8")

    diagnosticos = SemanticAnalyzer(str(fuente)).analizar()
    retorno = _buscar_diagnostico(diagnosticos, "return_error")

    assert retorno.linea == 1
    assert retorno.simbolo == "main"
    assert retorno.severidad == "warning"
    assert retorno.origen == "semantico"


def test_semantic_construye_y_usa_ast_para_codigo_valido(tmp_path):
    fuente = tmp_path / "ast_valido.c"
    fuente.write_text(
        "int main() {\n"
        "    return 0;\n"
        "}\n",
        encoding="utf-8",
    )
    analizador = SemanticAnalyzer(str(fuente))

    diagnosticos = analizador.analizar()

    assert diagnosticos == []
    assert analizador.ast_codigo is not None
    assert analizador.ast_codigo.tipo == "FileAST"
    assert analizador.error_ast is None


def test_semantic_ast_detecta_declaracion_multiple_no_usada(tmp_path):
    fuente = tmp_path / "declaracion_multiple.c"
    fuente.write_text(
        "int main() {\n"
        "    int usada = 1, temporal = 2;\n"
        "    return usada;\n"
        "}\n",
        encoding="utf-8",
    )

    diagnosticos = SemanticAnalyzer(str(fuente)).analizar()
    no_usadas = [
        diagnostico.simbolo
        for diagnostico in diagnosticos
        if diagnostico.tipo_error == "unused_variable"
    ]

    assert no_usadas == ["temporal"]


def test_semantic_ast_acepta_funcion_multilinea_con_retorno(tmp_path):
    fuente = tmp_path / "funcion_multilinea.c"
    fuente.write_text(
        "int\n"
        "calcular(\n"
        "    int numero\n"
        ") {\n"
        "    return numero;\n"
        "}\n",
        encoding="utf-8",
    )

    diagnosticos = SemanticAnalyzer(str(fuente)).analizar()

    assert diagnosticos == []


def test_semantic_ast_reconoce_retorno_en_if_else(tmp_path):
    fuente = tmp_path / "retorno_if_else.c"
    fuente.write_text(
        "int signo(int numero) {\n"
        "    if (numero >= 0) {\n"
        "        return 1;\n"
        "    } else {\n"
        "        return -1;\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    diagnosticos = SemanticAnalyzer(str(fuente)).analizar()

    assert not any(
        diagnostico.tipo_error == "missing_return"
        for diagnostico in diagnosticos
    )


def test_semantic_ast_detecta_asignacion_anidada_en_condicion(tmp_path):
    fuente = tmp_path / "asignacion_anidada.c"
    fuente.write_text(
        "int main() {\n"
        "    int x = 0;\n"
        "    if ((x = 1) > 0) {\n"
        "        return x;\n"
        "    }\n"
        "    return 0;\n"
        "}\n",
        encoding="utf-8",
    )

    diagnosticos = SemanticAnalyzer(str(fuente)).analizar()
    asignacion = _buscar_diagnostico(diagnosticos, "assignment_in_condition")

    assert asignacion.linea == 3
    assert asignacion.simbolo == "="


def test_semantic_ast_detecta_divisor_constante_calculado(tmp_path):
    fuente = tmp_path / "division_expresion_cero.c"
    fuente.write_text(
        "int main() {\n"
        "    int resultado = 10 / (2 - 2);\n"
        "    return resultado;\n"
        "}\n",
        encoding="utf-8",
    )

    diagnosticos = SemanticAnalyzer(str(fuente)).analizar()
    division = _buscar_diagnostico(diagnosticos, "division_by_zero")

    assert division.linea == 2
    assert division.simbolo == "/"


def test_semantic_ast_detecta_tipo_incorrecto_en_argumento(tmp_path):
    fuente = tmp_path / "argumento_tipo.c"
    fuente.write_text(
        "int longitud(const char *texto) { return texto[0]; }\n"
        "int main(void) { return longitud(42); }\n",
        encoding="utf-8",
    )

    diagnosticos = SemanticAnalyzer(str(fuente)).analizar()
    argumento = _buscar_diagnostico(diagnosticos, "wrong_arguments")

    assert argumento.linea == 2
    assert argumento.simbolo == "longitud"
    assert "argumento 1" in argumento.mensaje_crudo
    assert "char *" in argumento.mensaje_crudo
    assert "int" in argumento.mensaje_crudo


def test_semantic_ast_acepta_cadena_para_parametro_const_char(tmp_path):
    fuente = tmp_path / "argumento_compatible.c"
    fuente.write_text(
        "int longitud(const char *texto) { return texto[0]; }\n"
        'int main(void) { return longitud("hola"); }\n',
        encoding="utf-8",
    )

    diagnosticos = SemanticAnalyzer(str(fuente)).analizar()

    assert not any(
        diagnostico.tipo_error == "wrong_arguments"
        for diagnostico in diagnosticos
    )


def test_semantic_ast_valida_cantidad_en_funcion_void(tmp_path):
    fuente = tmp_path / "funcion_void.c"
    fuente.write_text(
        "void limpiar(void) {}\n"
        "int main(void) { limpiar(1); return 0; }\n",
        encoding="utf-8",
    )

    diagnosticos = SemanticAnalyzer(str(fuente)).analizar()
    argumento = _buscar_diagnostico(diagnosticos, "wrong_arguments")

    assert argumento.simbolo == "limpiar"
    assert "espera 0" in argumento.mensaje_crudo


def test_semantic_ast_acepta_argumentos_extra_en_funcion_variadica(tmp_path):
    fuente = tmp_path / "variadica.c"
    fuente.write_text(
        "#include <stdio.h>\n"
        "int main(void) {\n"
        '    printf("%d %s", 7, "dias");\n'
        "    return 0;\n"
        "}\n",
        encoding="utf-8",
    )

    diagnosticos = SemanticAnalyzer(str(fuente)).analizar()

    assert not any(
        diagnostico.tipo_error == "wrong_arguments"
        for diagnostico in diagnosticos
    )


def test_semantic_ast_usa_prototipo_de_cabecera_local(tmp_path):
    cabecera = tmp_path / "texto.h"
    cabecera.write_text(
        "typedef const char *Texto;\n"
        "int procesar(Texto texto);\n",
        encoding="utf-8",
    )
    fuente = tmp_path / "principal.c"
    fuente.write_text(
        '#include "texto.h"\n'
        "int main(void) { return procesar(10); }\n",
        encoding="utf-8",
    )

    diagnosticos = SemanticAnalyzer(str(fuente)).analizar()
    argumento = _buscar_diagnostico(diagnosticos, "wrong_arguments")

    assert argumento.simbolo == "procesar"
    assert "argumento 1" in argumento.mensaje_crudo
    assert "equivalente a char *" in argumento.mensaje_crudo


def test_combinar_diagnosticos_evita_duplicar_tipo_de_argumento():
    gcc = DiagnosticEntry(
        archivo="programa.c",
        linea=4,
        columna=14,
        severidad="warning",
        mensaje_crudo="passing argument 1 makes pointer from integer",
        tipo_error="type_mismatch",
        simbolo="procesar",
    )
    semantico = DiagnosticEntry(
        archivo="programa.c",
        linea=4,
        columna=14,
        severidad="warning",
        mensaje_crudo="argumento 1 espera char * pero recibio int",
        tipo_error="wrong_arguments",
        simbolo="procesar",
        origen="semantico",
    )

    combinados = _combinar_diagnosticos([gcc], [semantico])

    assert combinados == [gcc]


def test_semantic_ast_analiza_codigo_con_macros_y_tipos_estandar(tmp_path):
    fuente = tmp_path / "preprocesado.c"
    fuente.write_text(
        "#include <stdbool.h>\n"
        "#include <stdint.h>\n"
        "#define DOBLE(valor) ((valor) * 2)\n"
        "int main(void) {\n"
        "    bool activo = true;\n"
        "    int32_t numero = DOBLE(4);\n"
        "    return activo ? numero - 8 : 1;\n"
        "}\n",
        encoding="utf-8",
    )
    analizador = SemanticAnalyzer(str(fuente))

    diagnosticos = analizador.analizar()

    assert analizador.error_ast is None
    assert analizador.ast_codigo is not None
    assert diagnosticos == []


def test_semantic_usa_respaldo_textual_si_ast_es_invalido(tmp_path):
    fuente = tmp_path / "ast_invalido.c"
    fuente.write_text(
        "int main() {\n"
        "    int x = 0\n"
        "    if (x = 1) {\n"
        "        return 1;\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    analizador = SemanticAnalyzer(str(fuente))

    diagnosticos = analizador.analizar()

    assert analizador.ast_codigo is None
    assert analizador.error_ast
    _buscar_diagnostico(diagnosticos, "assignment_in_condition")


def test_combinar_diagnosticos_evita_duplicados_por_tipo_y_simbolo():
    gcc = DiagnosticEntry(
        archivo="programa.c",
        linea=2,
        columna=9,
        severidad="warning",
        mensaje_crudo="unused variable 'temporal'",
        tipo_error="unused_variable",
        simbolo="temporal",
    )
    semantico = DiagnosticEntry(
        archivo="programa.c",
        linea=2,
        columna=9,
        severidad="warning",
        mensaje_crudo="analizador semantico: variable 'temporal' declarada pero no utilizada",
        tipo_error="unused_variable",
        simbolo="temporal",
        origen="semantico",
    )

    combinados = _combinar_diagnosticos([gcc], [semantico])

    assert combinados == [gcc]


def test_combinar_conserva_simbolos_homonimos_de_ambitos_distintos():
    primer_ambito = DiagnosticEntry(
        archivo="programa.c",
        linea=3,
        columna=9,
        severidad="warning",
        mensaje_crudo="variable local no utilizada",
        tipo_error="unused_variable",
        simbolo="temporal",
        origen="semantico",
    )
    segundo_ambito = DiagnosticEntry(
        archivo="programa.c",
        linea=9,
        columna=13,
        severidad="warning",
        mensaje_crudo="variable sombreada no utilizada",
        tipo_error="unused_variable",
        simbolo="temporal",
        origen="semantico",
    )

    combinados = _combinar_diagnosticos(
        [],
        [primer_ambito, segundo_ambito],
    )

    assert combinados == [primer_ambito, segundo_ambito]


def test_semantic_ejemplo_variable_no_usada():
    diagnosticos = SemanticAnalyzer(
        "examples/semantico_variable_no_usada.c"
    ).analizar()

    assert len(diagnosticos) == 1
    assert diagnosticos[0].tipo_error == "unused_variable"
    assert diagnosticos[0].simbolo == "temporal"


def test_semantic_ejemplo_falta_retorno():
    diagnosticos = SemanticAnalyzer(
        "examples/semantico_falta_retorno.c"
    ).analizar()

    assert len(diagnosticos) == 1
    assert diagnosticos[0].tipo_error == "missing_return"
    assert diagnosticos[0].simbolo == "calcular"


def test_semantic_ejemplo_correcto_no_genera_diagnosticos():
    diagnosticos = SemanticAnalyzer("examples/semantico_correcto.c").analizar()

    assert diagnosticos == []


def test_semantic_ejemplos_de_reglas_nuevas():
    casos = {
        "examples/semantico_asignacion.c": "assignment_in_condition",
        "examples/semantico_division_cero.c": "division_by_zero",
        "examples/semantico_falta_stdio.c": "implicit_declaration",
        "examples/semantico_void_main.c": "return_error",
    }

    for ruta, tipo_esperado in casos.items():
        diagnosticos = SemanticAnalyzer(ruta).analizar()
        _buscar_diagnostico(diagnosticos, tipo_esperado)


def test_semantic_infiere_tipo_de_miembro_de_estructura(tmp_path):
    fuente = tmp_path / "miembro_estructura.c"
    fuente.write_text(
        "typedef struct { int edad; char *nombre; } Persona;\n"
        "int longitud(char *texto) { return texto[0]; }\n"
        "int main(void) {\n"
        "    Persona persona = {20, \"Ana\"};\n"
        "    return longitud(persona.edad);\n"
        "}\n",
        encoding="utf-8",
    )

    diagnosticos = SemanticAnalyzer(str(fuente)).analizar()
    argumento = _buscar_diagnostico(diagnosticos, "wrong_arguments")

    assert argumento.simbolo == "longitud"
    assert "recibio 'int'" in argumento.mensaje_crudo


def test_semantic_infiere_miembro_mediante_puntero(tmp_path):
    fuente = tmp_path / "miembro_puntero.c"
    fuente.write_text(
        "typedef struct { int edad; char *nombre; } Persona;\n"
        "int longitud(char *texto) { return texto[0]; }\n"
        "int revisar(Persona *persona) {\n"
        "    return longitud(persona->edad);\n"
        "}\n",
        encoding="utf-8",
    )

    diagnosticos = SemanticAnalyzer(str(fuente)).analizar()
    argumento = _buscar_diagnostico(diagnosticos, "wrong_arguments")

    assert argumento.simbolo == "longitud"
    assert argumento.linea == 4


def test_semantic_valida_llamada_mediante_puntero_a_funcion(tmp_path):
    fuente = tmp_path / "puntero_funcion.c"
    fuente.write_text(
        "int aplicar(int (*operacion)(int), int valor) {\n"
        "    return operacion(\"texto\");\n"
        "}\n",
        encoding="utf-8",
    )

    diagnosticos = SemanticAnalyzer(str(fuente)).analizar()
    argumento = _buscar_diagnostico(diagnosticos, "wrong_arguments")

    assert argumento.simbolo == "operacion"
    assert "argumento 1" in argumento.mensaje_crudo


def test_semantic_acepta_funcion_como_callback_compatible(tmp_path):
    fuente = tmp_path / "callback_correcto.c"
    fuente.write_text(
        "int duplicar(int valor) { return valor * 2; }\n"
        "int aplicar(int (*operacion)(int), int valor) {\n"
        "    return operacion(valor);\n"
        "}\n"
        "int main(void) { return aplicar(duplicar, 4) - 8; }\n",
        encoding="utf-8",
    )

    diagnosticos = SemanticAnalyzer(str(fuente)).analizar()

    assert not any(
        diagnostico.tipo_error in {"wrong_arguments", "type_mismatch"}
        for diagnostico in diagnosticos
    )


def test_semantic_rechaza_callback_con_firma_incompatible(tmp_path):
    fuente = tmp_path / "callback_incorrecto.c"
    fuente.write_text(
        "double mitad(double valor) { return valor / 2.0; }\n"
        "int aplicar(int (*operacion)(int), int valor) {\n"
        "    return operacion(valor);\n"
        "}\n"
        "int main(void) { return aplicar(mitad, 4); }\n",
        encoding="utf-8",
    )

    diagnosticos = SemanticAnalyzer(str(fuente)).analizar()
    argumento = _buscar_diagnostico(diagnosticos, "wrong_arguments")

    assert argumento.simbolo == "aplicar"
    assert argumento.linea == 5


def test_semantic_infiere_retorno_de_llamada_anidada(tmp_path):
    fuente = tmp_path / "llamada_anidada.c"
    fuente.write_text(
        "char *crear(void) { return \"texto\"; }\n"
        "int longitud(char *texto) { return texto[0]; }\n"
        "int main(void) { return longitud(crear()); }\n",
        encoding="utf-8",
    )

    diagnosticos = SemanticAnalyzer(str(fuente)).analizar()

    assert not any(
        diagnostico.tipo_error == "wrong_arguments"
        for diagnostico in diagnosticos
    )


def test_semantic_detecta_tipo_incorrecto_en_llamada_anidada(tmp_path):
    fuente = tmp_path / "llamada_anidada_incorrecta.c"
    fuente.write_text(
        "int crear_numero(void) { return 7; }\n"
        "int longitud(char *texto) { return texto[0]; }\n"
        "int main(void) { return longitud(crear_numero()); }\n",
        encoding="utf-8",
    )

    diagnosticos = SemanticAnalyzer(str(fuente)).analizar()
    argumento = _buscar_diagnostico(diagnosticos, "wrong_arguments")

    assert argumento.simbolo == "longitud"
    assert "recibio 'int'" in argumento.mensaje_crudo


def test_semantic_resuelve_funcion_que_devuelve_callback(tmp_path):
    fuente = tmp_path / "callback_anidado.c"
    fuente.write_text(
        "int incrementar(int valor) { return valor + 1; }\n"
        "int (*seleccionar(void))(int) { return incrementar; }\n"
        "int main(void) { return seleccionar()(4) - 5; }\n",
        encoding="utf-8",
    )

    diagnosticos = SemanticAnalyzer(str(fuente)).analizar()

    assert not any(
        diagnostico.tipo_error in {"wrong_arguments", "return_error"}
        for diagnostico in diagnosticos
    )


def test_semantic_resuelve_alias_dentro_de_firma_callback(tmp_path):
    fuente = tmp_path / "callback_alias.c"
    fuente.write_text(
        "typedef int Numero;\n"
        "typedef Numero (*Operacion)(Numero);\n"
        "int duplicar(int valor) { return valor * 2; }\n"
        "int aplicar(Operacion operacion, Numero valor) {\n"
        "    return operacion(valor);\n"
        "}\n"
        "int main(void) { return aplicar(duplicar, 3) - 6; }\n",
        encoding="utf-8",
    )

    diagnosticos = SemanticAnalyzer(str(fuente)).analizar()

    assert not any(
        diagnostico.tipo_error == "wrong_arguments"
        for diagnostico in diagnosticos
    )


def test_semantic_aplica_promocion_entera_en_expresiones(tmp_path):
    fuente = tmp_path / "promociones.c"
    fuente.write_text(
        "int recibir(int valor) { return valor; }\n"
        "int main(void) {\n"
        "    short corto = 2;\n"
        "    char letra = 3;\n"
        "    return recibir(corto + letra) - 5;\n"
        "}\n",
        encoding="utf-8",
    )

    diagnosticos = SemanticAnalyzer(str(fuente)).analizar()

    assert not any(
        diagnostico.tipo_error == "wrong_arguments"
        for diagnostico in diagnosticos
    )


def test_semantic_detecta_conversion_numerica_con_perdida(tmp_path):
    fuente = tmp_path / "conversion_compleja.c"
    fuente.write_text(
        "int main(void) {\n"
        "    unsigned char pequeno = 300;\n"
        "    return pequeno;\n"
        "}\n",
        encoding="utf-8",
    )

    diagnosticos = SemanticAnalyzer(str(fuente)).analizar()
    conversion = _buscar_diagnostico(diagnosticos, "dangerous_conversion")

    assert conversion.simbolo == "pequeno"
    assert "puede perder informacion" in conversion.mensaje_crudo


def test_semantic_valida_asignacion_a_miembro_de_estructura(tmp_path):
    fuente = tmp_path / "asignacion_miembro.c"
    fuente.write_text(
        "typedef struct { char *nombre; } Persona;\n"
        "int main(void) {\n"
        "    Persona persona = {\"Ana\"};\n"
        "    persona.nombre = 42;\n"
        "    return 0;\n"
        "}\n",
        encoding="utf-8",
    )

    diagnosticos = SemanticAnalyzer(str(fuente)).analizar()
    incompatibilidad = _buscar_diagnostico(diagnosticos, "type_mismatch")

    assert incompatibilidad.simbolo == "nombre"
    assert incompatibilidad.linea == 4


def _buscar_diagnostico(
    diagnosticos: list[DiagnosticEntry],
    tipo_error: str,
) -> DiagnosticEntry:
    for diagnostico in diagnosticos:
        if diagnostico.tipo_error == tipo_error:
            return diagnostico

    raise AssertionError(f"No se encontro un diagnostico de tipo {tipo_error!r}")
