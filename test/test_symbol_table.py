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
    assert not any(
        uso.nombre == "printf"
        for uso in tabla.usos_no_resueltos
    )
