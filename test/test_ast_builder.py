import pytest

from src.ast_builder import (
    ASTParseError,
    ASTPreprocessError,
    construir_ast_codigo,
)


def test_ast_codigo_representa_programa_c_real():
    ast = construir_ast_codigo("examples/correcto.c")
    nodos = list(_recorrer(ast))
    tipos = {nodo.tipo for nodo in nodos}

    assert ast.tipo == "FileAST"
    assert "atributos" in ast.to_dict()
    assert "FuncDef" in tipos
    assert "Decl" in tipos
    assert "FuncCall" in tipos
    assert "Return" in tipos

    funcion_main = next(
        nodo
        for nodo in nodos
        if nodo.tipo == "Decl" and nodo.valor and "name=main" in nodo.valor
    )
    assert funcion_main.linea == 3
    assert funcion_main.columna is not None
    assert funcion_main.atributos["name"] == "main"


def test_ast_codigo_ignora_comentarios_y_directivas_sin_perder_lineas(tmp_path):
    fuente = tmp_path / "comentarios.c"
    fuente.write_text(
        "#include <stdio.h>\n"
        "/* comentario de bloque */\n"
        "int main() {\n"
        "    // comentario de linea\n"
        "    int numero = 10;\n"
        "    return numero;\n"
        "}\n",
        encoding="utf-8",
    )

    ast = construir_ast_codigo(str(fuente))
    numero = next(
        nodo
        for nodo in _recorrer(ast)
        if nodo.tipo == "Decl" and nodo.valor and "name=numero" in nodo.valor
    )

    assert numero.linea == 5


def test_ast_codigo_exporta_estructura_recursiva():
    ast = construir_ast_codigo("examples/correcto.c")

    datos = ast.to_dict()
    renderizado = ast.render()

    assert datos["tipo"] == "FileAST"
    assert datos["hijos"]
    assert renderizado[0] == "- FileAST"
    assert any("FuncDef" in linea for linea in renderizado)


def test_ast_codigo_informa_error_sintactico(tmp_path):
    fuente = tmp_path / "invalido.c"
    fuente.write_text(
        "int main() {\n"
        "    int x = ;\n"
        "}\n",
        encoding="utf-8",
    )

    with pytest.raises(ASTParseError, match="No se pudo construir el AST"):
        construir_ast_codigo(str(fuente))


def test_ast_expande_macros_de_objeto_y_funcion_sin_perder_lineas(tmp_path):
    fuente = tmp_path / "macros.c"
    fuente.write_text(
        "#define TIPO int\n"
        "#define DOBLE(valor) ((valor) * 2)\n"
        "int main(void) {\n"
        "    TIPO resultado = DOBLE(4);\n"
        "    return resultado;\n"
        "}\n",
        encoding="utf-8",
    )

    ast = construir_ast_codigo(str(fuente))
    nodos = list(_recorrer(ast))
    resultado = next(
        nodo
        for nodo in nodos
        if nodo.tipo == "Decl" and nodo.atributos.get("name") == "resultado"
    )

    assert resultado.linea == 4
    assert any(
        nodo.tipo == "BinaryOp" and nodo.atributos.get("op") == "*"
        for nodo in nodos
    )


def test_ast_resuelve_tipos_de_cabeceras_estandar_controladas(tmp_path):
    fuente = tmp_path / "tipos_estandar.c"
    fuente.write_text(
        "#include <stdbool.h>\n"
        "#include <stdint.h>\n"
        "int main(void) {\n"
        "    bool activo = true;\n"
        "    int32_t numero = 4;\n"
        "    return activo ? numero : 0;\n"
        "}\n",
        encoding="utf-8",
    )

    ast = construir_ast_codigo(str(fuente))
    declaraciones = {
        nodo.atributos.get("name")
        for nodo in _recorrer(ast)
        if nodo.tipo == "Decl"
    }

    assert {"activo", "numero", "main"} <= declaraciones


def test_ast_integra_typedef_y_prototipo_de_cabecera_local(tmp_path):
    cabecera = tmp_path / "calculos.h"
    cabecera.write_text(
        "#ifndef CALCULOS_H\n"
        "#define CALCULOS_H\n"
        "typedef unsigned int Contador;\n"
        "int escalar(Contador valor);\n"
        "#endif\n",
        encoding="utf-8",
    )
    fuente = tmp_path / "principal.c"
    fuente.write_text(
        '#include "calculos.h"\n'
        "int main(void) { return escalar(2); }\n",
        encoding="utf-8",
    )

    ast = construir_ast_codigo(str(fuente))
    nodos = list(_recorrer(ast))

    assert any(
        nodo.tipo == "Typedef" and nodo.atributos.get("name") == "Contador"
        for nodo in nodos
    )
    assert any(
        nodo.tipo == "Decl" and nodo.atributos.get("name") == "escalar"
        for nodo in nodos
    )
    main = next(
        nodo
        for nodo in nodos
        if nodo.tipo == "Decl" and nodo.atributos.get("name") == "main"
    )
    assert main.linea == 2


def test_ast_informa_cabecera_inexistente_durante_preprocesamiento(tmp_path):
    fuente = tmp_path / "cabecera_faltante.c"
    fuente.write_text(
        "#include <cabecera_que_no_existe.h>\nint main(void) { return 0; }\n",
        encoding="utf-8",
    )

    with pytest.raises(ASTPreprocessError, match="preprocesar"):
        construir_ast_codigo(str(fuente))


def _recorrer(nodo):
    yield nodo
    for hijo in nodo.hijos:
        yield from _recorrer(hijo)
