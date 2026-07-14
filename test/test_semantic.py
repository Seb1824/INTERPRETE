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
