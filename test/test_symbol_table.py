from src.ast_builder import construir_ast_codigo
from src.semantic import SemanticAnalyzer
from src.symbol_table import construir_tabla_simbolos


def test_tabla_registra_global_funcion_parametros_y_locales(tmp_path):
    fuente = tmp_path / "simbolos.c"
    fuente.write_text(
        "int global = 1;\n"
        "int sumar(int a, int b) {\n"
        "    int total = a + b;\n"
        "    return total;\n"
        "}\n",
        encoding="utf-8",
    )

    tabla = construir_tabla_simbolos(construir_ast_codigo(str(fuente)))
    globales = {simbolo.nombre: simbolo for simbolo in tabla.ambito_global.simbolos}
    ambito_funcion = next(
        ambito
        for ambito in tabla.todos_los_ambitos()
        if ambito.clase == "funcion" and ambito.nombre == "sumar"
    )
    locales = {simbolo.nombre: simbolo for simbolo in ambito_funcion.simbolos}

    assert globales["global"].clase == "variable"
    assert globales["global"].tipo_dato == "int"
    assert globales["sumar"].clase == "funcion"
    assert globales["sumar"].tipo_dato == "funcion -> int"
    assert locales["a"].clase == "parametro"
    assert locales["b"].clase == "parametro"
    assert locales["total"].clase == "variable"
    assert locales["a"].cantidad_usos == 1
    assert locales["b"].cantidad_usos == 1
    assert locales["total"].cantidad_usos == 1


def test_tabla_resuelve_sombreado_en_ambito_mas_cercano(tmp_path):
    fuente = tmp_path / "sombreado.c"
    fuente.write_text(
        "int main() {\n"
        "    int valor = 1;\n"
        "    {\n"
        "        int valor = 2;\n"
        "        valor++;\n"
        "    }\n"
        "    return valor;\n"
        "}\n",
        encoding="utf-8",
    )

    tabla = construir_tabla_simbolos(construir_ast_codigo(str(fuente)))
    simbolos_valor = [
        simbolo
        for simbolo in tabla.todos_los_simbolos()
        if simbolo.nombre == "valor"
    ]

    assert len(simbolos_valor) == 2
    assert simbolos_valor[0].ambito_id != simbolos_valor[1].ambito_id
    assert [simbolo.cantidad_usos for simbolo in simbolos_valor] == [1, 1]
    assert tabla.redeclaraciones == []


def test_tabla_detecta_redeclaracion_en_el_mismo_ambito(tmp_path):
    fuente = tmp_path / "redeclaracion.c"
    fuente.write_text(
        "int main() {\n"
        "    int valor = 1;\n"
        "    int valor = 2;\n"
        "    return valor;\n"
        "}\n",
        encoding="utf-8",
    )

    tabla = construir_tabla_simbolos(construir_ast_codigo(str(fuente)))
    ambito_main = next(
        ambito
        for ambito in tabla.todos_los_ambitos()
        if ambito.clase == "funcion" and ambito.nombre == "main"
    )
    simbolos_valor = [
        simbolo
        for simbolo in ambito_main.simbolos
        if simbolo.nombre == "valor"
    ]

    assert len(simbolos_valor) == 1
    assert simbolos_valor[0].cantidad_usos == 1
    assert len(tabla.redeclaraciones) == 1
    assert tabla.redeclaraciones[0].nombre == "valor"
    assert tabla.redeclaraciones[0].linea_original == 2
    assert tabla.redeclaraciones[0].linea_redeclaracion == 3


def test_semantico_convierte_redeclaracion_en_diagnostico(tmp_path):
    fuente = tmp_path / "redeclaracion_semantica.c"
    fuente.write_text(
        "int main() {\n"
        "    int contador = 0;\n"
        "    int contador = 1;\n"
        "    return contador;\n"
        "}\n",
        encoding="utf-8",
    )

    diagnosticos = SemanticAnalyzer(str(fuente)).analizar()
    redeclaracion = next(
        diagnostico
        for diagnostico in diagnosticos
        if diagnostico.tipo_error == "redeclaration"
    )

    assert redeclaracion.simbolo == "contador"
    assert redeclaracion.linea == 3
    assert redeclaracion.severidad == "error"
    assert redeclaracion.origen == "semantico"
    assert "linea 2" in redeclaracion.mensaje_crudo


def test_semantico_convierte_uso_no_resuelto_en_diagnostico(tmp_path):
    fuente = tmp_path / "no_declarada.c"
    fuente.write_text(
        "int main() {\n"
        "    return total;\n"
        "}\n",
        encoding="utf-8",
    )

    analizador = SemanticAnalyzer(str(fuente))
    diagnosticos = analizador.analizar()
    no_declarado = next(
        diagnostico
        for diagnostico in diagnosticos
        if diagnostico.tipo_error == "undeclared"
    )

    assert no_declarado.simbolo == "total"
    assert no_declarado.linea == 2
    assert no_declarado.severidad == "error"
    assert no_declarado.origen == "semantico"
    assert analizador.tabla_simbolos is not None
    assert analizador.tabla_simbolos.usos_no_resueltos[0].nombre == "total"


def test_tabla_acepta_prototipo_seguido_de_definicion(tmp_path):
    fuente = tmp_path / "prototipo.c"
    fuente.write_text(
        "int sumar(int numero);\n"
        "int main() { return sumar(2); }\n"
        "int sumar(int numero) { return numero; }\n",
        encoding="utf-8",
    )

    analizador = SemanticAnalyzer(str(fuente))
    diagnosticos = analizador.analizar()

    assert analizador.tabla_simbolos is not None
    assert analizador.tabla_simbolos.redeclaraciones == []
    assert diagnosticos == []


def test_semantico_reporta_solo_simbolo_sombreado_no_usado(tmp_path):
    fuente = tmp_path / "sombreado_no_usado.c"
    fuente.write_text(
        "int main() {\n"
        "    int valor = 1;\n"
        "    {\n"
        "        int valor = 2;\n"
        "    }\n"
        "    return valor;\n"
        "}\n",
        encoding="utf-8",
    )

    diagnosticos = SemanticAnalyzer(str(fuente)).analizar()
    no_usados = [
        diagnostico
        for diagnostico in diagnosticos
        if diagnostico.tipo_error == "unused_variable"
    ]

    assert len(no_usados) == 1
    assert no_usados[0].simbolo == "valor"
    assert no_usados[0].linea == 4


def test_semantico_detecta_parametro_no_usado(tmp_path):
    fuente = tmp_path / "parametro_no_usado.c"
    fuente.write_text(
        "int calcular(int usado, int ignorado) {\n"
        "    return usado;\n"
        "}\n",
        encoding="utf-8",
    )
    analizador = SemanticAnalyzer(str(fuente))

    diagnosticos = analizador.analizar()
    no_usado = next(
        diagnostico
        for diagnostico in diagnosticos
        if diagnostico.tipo_error == "unused_variable"
    )

    assert no_usado.simbolo == "ignorado"
    assert no_usado.linea == 1
    assert analizador.tabla_simbolos is not None


def test_tabla_crea_ambito_para_variable_de_for(tmp_path):
    fuente = tmp_path / "ambito_for.c"
    fuente.write_text(
        "int main() {\n"
        "    for (int i = 0; i < 3; i++) {\n"
        "    }\n"
        "    return 0;\n"
        "}\n",
        encoding="utf-8",
    )

    tabla = construir_tabla_simbolos(construir_ast_codigo(str(fuente)))
    ambito_for = next(
        ambito
        for ambito in tabla.todos_los_ambitos()
        if ambito.clase == "for"
    )
    indice = ambito_for.buscar_local("i")

    assert indice is not None
    assert indice.cantidad_usos == 2


def test_tabla_no_confunde_miembro_de_estructura_con_variable(tmp_path):
    fuente = tmp_path / "estructura.c"
    fuente.write_text(
        "struct Persona { int edad; };\n"
        "int main() {\n"
        "    struct Persona persona;\n"
        "    persona.edad = 20;\n"
        "    return persona.edad;\n"
        "}\n",
        encoding="utf-8",
    )

    tabla = construir_tabla_simbolos(construir_ast_codigo(str(fuente)))
    persona = next(
        simbolo
        for simbolo in tabla.todos_los_simbolos()
        if simbolo.nombre == "persona"
    )

    assert persona.cantidad_usos == 2
    assert not any(
        uso.nombre == "edad"
        for uso in tabla.usos_no_resueltos
    )


def test_tabla_exporta_jerarquia_y_render(tmp_path):
    fuente = tmp_path / "exportar_tabla.c"
    fuente.write_text(
        "int main() {\n"
        "    int numero = 1;\n"
        "    return numero;\n"
        "}\n",
        encoding="utf-8",
    )

    tabla = construir_tabla_simbolos(construir_ast_codigo(str(fuente)))
    datos = tabla.to_dict()
    renderizado = tabla.render()

    assert datos["ambito_global"]["clase"] == "global"
    assert datos["ambito_global"]["hijos"][0]["clase"] == "funcion"
    assert datos["redeclaraciones"] == []
    assert any("numero: int" in linea for linea in renderizado)


def test_semantico_registra_funcion_de_cabecera_como_externa():
    analizador = SemanticAnalyzer("examples/correcto.c")

    diagnosticos = analizador.analizar()
    tabla = analizador.tabla_simbolos

    assert diagnosticos == []
    assert tabla is not None
    printf = next(
        simbolo
        for simbolo in tabla.ambito_global.simbolos
        if simbolo.nombre == "printf"
    )
    assert printf.clase == "funcion_externa"
    assert printf.cantidad_usos == 1
    assert printf.firma_parametros_definida is True
    assert printf.tipos_parametros == ["char *"]
    assert printf.es_variadica is True
    assert not any(
        uso.nombre == "printf"
        for uso in tabla.usos_no_resueltos
    )


def test_tabla_registra_firma_void_y_prototipo_local(tmp_path):
    fuente = tmp_path / "firmas.c"
    fuente.write_text(
        "void limpiar(void);\n"
        "int sumar(int izquierda, int derecha);\n"
        "int main(void) { return sumar(1, 2); }\n",
        encoding="utf-8",
    )

    tabla = construir_tabla_simbolos(construir_ast_codigo(str(fuente)))
    limpiar = tabla.ambito_global.buscar_local("limpiar")
    sumar = tabla.ambito_global.buscar_local("sumar")

    assert limpiar is not None
    assert limpiar.firma_parametros_definida is True
    assert limpiar.tipos_parametros == []
    assert limpiar.es_variadica is False
    assert sumar is not None
    assert sumar.tipos_parametros == ["int", "int"]
    assert "parametros=(int, int)" in "\n".join(tabla.render())
