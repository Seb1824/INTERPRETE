from src.analyzer import analizar_archivo


def test_analizador_devuelve_pipeline_estructurado():
    resultado = analizar_archivo("examples/variable_no_declarada.c")

    assert resultado.stderr
    assert resultado.tokens
    assert resultado.diagnosticos_gcc
    assert resultado.diagnosticos_semanticos
    assert len(
        [
            diagnostico
            for diagnostico in resultado.diagnosticos
            if diagnostico.tipo_error == "undeclared"
            and diagnostico.simbolo == "total"
        ]
    ) == 1
    assert resultado.ast_codigo is not None
    assert resultado.tabla_simbolos is not None
