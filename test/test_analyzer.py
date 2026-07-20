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


def test_analizador_deduplica_tipo_incorrecto_de_argumento():
    resultado = analizar_archivo(
        "examples/semantico_argumento_tipo_incorrecto.c"
    )

    assert any(
        diagnostico.tipo_error == "wrong_arguments"
        and diagnostico.simbolo == "longitud"
        for diagnostico in resultado.diagnosticos_semanticos
    )
    assert not any(
        diagnostico.tipo_error == "wrong_arguments"
        and diagnostico.simbolo == "longitud"
        for diagnostico in resultado.diagnosticos
    )
    assert len(
        [
            diagnostico
            for diagnostico in resultado.diagnosticos
            if diagnostico.tipo_error == "type_mismatch"
            and diagnostico.simbolo == "longitud"
        ]
    ) == 1


def test_analizador_deduplica_conversion_de_puntero_equivalente():
    resultado = analizar_archivo("examples/arbol_b_mas_con_errores.c")

    diagnosticos = [
        diagnostico
        for diagnostico in resultado.diagnosticos
        if diagnostico.simbolo == "nodo_incorrecto"
    ]

    assert len(diagnosticos) == 1
    assert diagnosticos[0].tipo_error == "pointer_error"


def test_analizador_deduplica_retorno_incompatible_equivalente():
    resultado = analizar_archivo("examples/arbol_b_mas_con_errores.c")

    diagnosticos = [
        diagnostico
        for diagnostico in resultado.diagnosticos
        if diagnostico.simbolo == "retornar_codigo_incorrecto"
    ]

    assert len(diagnosticos) == 1
    assert diagnosticos[0].tipo_error == "type_mismatch"
