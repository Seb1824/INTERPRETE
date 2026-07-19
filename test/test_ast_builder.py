import pytest

from src.ast_builder import ASTParseError, construir_ast_codigo


def test_ast_codigo_representa_programa_c_real():
    ast = construir_ast_codigo("examples/correcto.c")
    nodos = list(_recorrer(ast))
    tipos = {nodo.tipo for nodo in nodos}

    assert ast.tipo == "FileAST"
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


def _recorrer(nodo):
    yield nodo
    for hijo in nodo.hijos:
        yield from _recorrer(hijo)
