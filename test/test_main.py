import json

import pytest

from src.lexer import CompilerNotFoundError
from main import _agrupar_diagnosticos_con_notas
from main import _calcular_resumen_clasificacion
from main import _etiqueta_severidad
from main import _normalizar_ruta_json
from main import _obtener_contexto_codigo
from main import run_pipeline
from src.parser import DiagnosticEntry


def make_entry(severidad: str, mensaje: str) -> DiagnosticEntry:
    return DiagnosticEntry(
        archivo="test.c",
        linea=1,
        columna=1,
        severidad=severidad,
        mensaje_crudo=mensaje,
        tipo_error="desconocido",
    )


def test_agrupar_diagnosticos_adjunta_note_al_anterior():
    error = make_entry("error", "error principal")
    note = make_entry("note", "detalle secundario")
    warning = make_entry("warning", "advertencia independiente")

    agrupados = _agrupar_diagnosticos_con_notas([error, note, warning])

    assert len(agrupados) == 2
    assert agrupados[0][0] == error
    assert agrupados[0][1] == [note]
    assert agrupados[1][0] == warning
    assert agrupados[1][1] == []


def test_resumen_clasificacion_excluye_notas():
    clasificado = make_entry("error", "error clasificado")
    clasificado.tipo_error = "undeclared"
    note = make_entry("note", "informacion secundaria")
    desconocido = make_entry("warning", "mensaje sin clasificar")

    resumen = _calcular_resumen_clasificacion(
        [clasificado, note, desconocido]
    )

    assert resumen["total"] == 2
    assert resumen["clasificados"] == 1
    assert resumen["desconocidos"] == 1
    assert resumen["cobertura"] == 50.0
    assert resumen["diagnosticos_desconocidos"] == [desconocido]


def test_resumen_sin_diagnosticos_tiene_cobertura_completa():
    resumen = _calcular_resumen_clasificacion([])

    assert resumen["total"] == 0
    assert resumen["clasificados"] == 0
    assert resumen["desconocidos"] == 0
    assert resumen["cobertura"] == 100.0


def test_run_pipeline_modo_estudiante_oculta_salida_tecnica(capsys):
    exit_code = run_pipeline("examples/error_lexico.c")
    salida = capsys.readouterr().out

    assert exit_code == 0
    assert "=== MENSAJES MEJORADOS ===" in salida
    assert "=== STDERR CRUDO (GCC) ===" not in salida
    assert "=== TOKENS ===" not in salida
    assert "=== DIAGNOSTICOS (PARSER) ===" not in salida
    assert "Codigo:" in salida
    assert "=== RESUMEN DE CLASIFICACION ===" in salida
    assert "Cobertura de clasificacion:" in salida
    assert "[ERROR]" in salida
    assert "[ADVERTENCIA]" in salida


def test_run_pipeline_modo_debug_muestra_salida_tecnica(capsys):
    exit_code = run_pipeline("examples/error_lexico.c", debug=True)
    salida = capsys.readouterr().out

    assert exit_code == 0
    assert "=== STDERR CRUDO (GCC) ===" in salida
    assert "=== TOKENS ===" in salida
    assert "=== AST DEL CODIGO C ===" in salida
    assert "=== TABLA DE SIMBOLOS ===" in salida
    assert "=== DIAGNOSTICOS (PARSER) ===" in salida
    assert "=== ANALISIS SEMANTICO PROPIO ===" in salida
    assert "=== ARBOL SINTACTICO DE DIAGNOSTICOS ===" in salida
    assert "- Diagnostico" in salida
    assert "=== MENSAJES MEJORADOS ===" in salida


def test_run_pipeline_archivo_correcto_muestra_revision_exitosa(capsys):
    exit_code = run_pipeline("examples/correcto.c")
    salida = capsys.readouterr().out

    assert exit_code == 0
    assert "Revision completada" in salida
    assert "no se detectaron errores ni advertencias" in salida
    assert "(sin mensajes mejorados)" not in salida


def test_obtener_contexto_codigo_muestra_linea_y_marcador():
    entry = DiagnosticEntry(
        archivo="examples/error_lexico.c",
        linea=5,
        columna=13,
        severidad="warning",
        mensaje_crudo="type mismatch",
        tipo_error="type_mismatch",
        simbolo="z",
    )

    contexto = _obtener_contexto_codigo(entry)

    assert contexto is not None
    assert "5 |     int z = \"hola\"" in contexto[1]
    assert "^" in contexto[2]


def test_run_pipeline_rechaza_archivo_inexistente(capsys, tmp_path):
    ruta = tmp_path / "no_existe.c"

    exit_code = run_pipeline(str(ruta))
    salida = capsys.readouterr().out

    assert exit_code == 1
    assert "No existe el archivo" in salida


def test_run_pipeline_rechaza_directorio(capsys, tmp_path):
    exit_code = run_pipeline(str(tmp_path))
    salida = capsys.readouterr().out

    assert exit_code == 1
    assert "no corresponde a un archivo" in salida


def test_run_pipeline_rechaza_extension_distinta_de_c(capsys, tmp_path):
    ruta = tmp_path / "programa.txt"
    ruta.write_text("int main() { return 0; }", encoding="utf-8")

    exit_code = run_pipeline(str(ruta))
    salida = capsys.readouterr().out

    assert exit_code == 1
    assert "extension .c" in salida


def test_run_pipeline_acepta_extension_c_mayuscula(capsys):
    exit_code = run_pipeline("examples/extension_mayuscula.C")
    salida = capsys.readouterr().out

    assert exit_code == 0
    assert "variable_no_declarada" in salida


def test_run_pipeline_informa_si_gcc_no_esta_disponible(capsys, monkeypatch):
    def gcc_no_disponible(self):
        raise CompilerNotFoundError("No se encontro GCC.")

    monkeypatch.setattr("main.Lexer.compilar_y_capturar", gcc_no_disponible)

    exit_code = run_pipeline("examples/correcto.c")
    salida = capsys.readouterr().out

    assert exit_code == 1
    assert "[ERROR] No se encontro GCC." in salida


def test_etiquetas_de_severidad():
    assert _etiqueta_severidad("error") == "ERROR"
    assert _etiqueta_severidad("warning") == "ADVERTENCIA"
    assert _etiqueta_severidad("note") == "NOTA"


def test_normalizar_ruta_json_usa_separadores_portables():
    assert _normalizar_ruta_json(r"examples\error_lexico.c") == (
        "examples/error_lexico.c"
    )


def test_run_pipeline_exporta_json(capsys, tmp_path):
    ruta_json = tmp_path / "reportes" / "diagnosticos.json"

    exit_code = run_pipeline(
        "examples/error_lexico.c",
        json_output=str(ruta_json),
    )
    salida = capsys.readouterr().out

    assert exit_code == 0
    assert ruta_json.exists()
    assert "Resultado JSON guardado en:" in salida

    reporte = json.loads(ruta_json.read_text(encoding="utf-8"))
    assert reporte["archivo_fuente"] == "examples/error_lexico.c"
    assert reporte["resumen"]["diagnosticos_principales"] >= 1
    assert reporte["resumen"]["clasificados"] >= 1
    assert reporte["diagnosticos"]

    primer_diagnostico = reporte["diagnosticos"][0]
    assert primer_diagnostico["severidad"] == "error"
    assert primer_diagnostico["etiqueta_severidad"] == "ERROR"
    assert primer_diagnostico["tipo_error"] == "undeclared"
    assert primer_diagnostico["origen"] == "gcc"
    assert primer_diagnostico["simbolo"] == "y"
    assert primer_diagnostico["titulo"]
    assert primer_diagnostico["explicacion"]
    assert primer_diagnostico["causa_probable"]
    assert primer_diagnostico["sugerencia"]
    assert primer_diagnostico["contexto_codigo"]
    assert primer_diagnostico["notas_gcc"]
    assert primer_diagnostico["arbol_sintactico"]["nombre"] == "Diagnostico"


def test_run_pipeline_exporta_json_vacio_para_codigo_correcto(tmp_path):
    ruta_json = tmp_path / "correcto.json"

    exit_code = run_pipeline(
        "examples/correcto.c",
        json_output=str(ruta_json),
    )
    reporte = json.loads(ruta_json.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert reporte["resumen"]["diagnosticos_principales"] == 0
    assert reporte["resumen"]["cobertura_clasificacion"] == 100.0
    assert reporte["diagnosticos"] == []
    assert reporte["ast_codigo"]["tipo"] == "FileAST"
    assert reporte["ast_codigo"]["hijos"]
    assert reporte["error_ast"] is None
    assert reporte["tabla_simbolos"]["ambito_global"]["clase"] == "global"


def test_run_pipeline_json_con_codigo_invalido_conserva_diagnosticos(tmp_path):
    ruta_json = tmp_path / "codigo_invalido.json"

    exit_code = run_pipeline(
        "examples/error_lexico.c",
        json_output=str(ruta_json),
    )
    reporte = json.loads(ruta_json.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert reporte["diagnosticos"]
    assert reporte["ast_codigo"] is None
    assert reporte["error_ast"]
    assert reporte["tabla_simbolos"] is None


@pytest.mark.parametrize(
    ("archivo", "tipo_error", "simbolo", "campo_tabla"),
    [
        (
            "examples/redeclaracion.c",
            "redeclaration",
            "contador",
            "redeclaraciones",
        ),
        (
            "examples/variable_no_declarada.c",
            "undeclared",
            "total",
            "usos_no_resueltos",
        ),
    ],
)
def test_pipeline_deduplica_reglas_semanticas_de_tabla_con_gcc(
    tmp_path,
    archivo,
    tipo_error,
    simbolo,
    campo_tabla,
):
    ruta_json = tmp_path / f"{tipo_error}.json"

    exit_code = run_pipeline(archivo, json_output=str(ruta_json))
    reporte = json.loads(ruta_json.read_text(encoding="utf-8"))
    coincidentes = [
        diagnostico
        for diagnostico in reporte["diagnosticos"]
        if diagnostico["tipo_error"] == tipo_error
        and diagnostico["simbolo"] == simbolo
    ]

    assert exit_code == 0
    assert len(coincidentes) == 1
    assert coincidentes[0]["origen"] == "gcc"
    assert reporte["tabla_simbolos"][campo_tabla]


@pytest.mark.parametrize(
    ("archivo", "tipo_esperado", "simbolo_esperado"),
    [
        (
            "semantico_variable_no_usada.c",
            "unused_variable",
            "temporal",
        ),
        (
            "semantico_falta_retorno.c",
            "missing_return",
            "calcular",
        ),
        (
            "semantico_asignacion.c",
            "assignment_in_condition",
            "=",
        ),
        (
            "semantico_division_cero.c",
            "division_by_zero",
            "/",
        ),
        (
            "semantico_falta_stdio.c",
            "implicit_declaration",
            "printf",
        ),
        (
            "semantico_void_main.c",
            "return_error",
            "main",
        ),
    ],
)
def test_pipeline_integra_regla_semantica_en_json_y_arbol(
    archivo,
    tipo_esperado,
    simbolo_esperado,
    capsys,
    monkeypatch,
    tmp_path,
):
    def gcc_sin_diagnosticos(self):
        self.stderr_crudo = ""
        self.compilado = True
        return ""

    monkeypatch.setattr("main.Lexer.compilar_y_capturar", gcc_sin_diagnosticos)
    monkeypatch.setattr("main.Lexer.tokenizar", lambda self: [])

    ruta_fuente = f"examples/{archivo}"
    ruta_json = tmp_path / f"{tipo_esperado}.json"

    exit_code = run_pipeline(
        ruta_fuente,
        json_output=str(ruta_json),
    )
    salida = capsys.readouterr().out
    reporte = json.loads(ruta_json.read_text(encoding="utf-8"))
    diagnostico = next(
        elemento
        for elemento in reporte["diagnosticos"]
        if elemento["tipo_error"] == tipo_esperado
    )

    assert exit_code == 0
    assert diagnostico["origen"] == "semantico"
    assert diagnostico["simbolo"] == simbolo_esperado
    assert diagnostico["titulo"]
    assert diagnostico["explicacion"]
    assert diagnostico["sugerencia"]
    assert diagnostico["contexto_codigo"]
    assert "Origen: analizador semantico del proyecto" in salida

    arbol = diagnostico["arbol_sintactico"]
    nodos_raiz = {
        hijo["nombre"]: hijo["valor"]
        for hijo in arbol["hijos"]
    }
    assert arbol["nombre"] == "Diagnostico"
    assert nodos_raiz["TipoError"] == tipo_esperado
    assert nodos_raiz["Origen"] == "semantico"
    assert nodos_raiz["Simbolo"] == simbolo_esperado
    assert any(
        hijo["nombre"] == "ContextoFuente"
        for hijo in arbol["hijos"]
    )


@pytest.mark.parametrize(
    ("archivo", "tipo_esperado"),
    [
        ("semantico_asignacion.c", "assignment_in_condition"),
        ("semantico_division_cero.c", "division_by_zero"),
        ("semantico_falta_stdio.c", "implicit_declaration"),
        ("semantico_void_main.c", "return_error"),
    ],
)
def test_pipeline_combina_gcc_y_semantico_sin_duplicar_categoria(
    archivo,
    tipo_esperado,
    tmp_path,
):
    ruta_json = tmp_path / f"combinado_{tipo_esperado}.json"

    exit_code = run_pipeline(
        f"examples/{archivo}",
        json_output=str(ruta_json),
    )
    reporte = json.loads(ruta_json.read_text(encoding="utf-8"))
    coincidencias = [
        diagnostico
        for diagnostico in reporte["diagnosticos"]
        if diagnostico["tipo_error"] == tipo_esperado
    ]

    assert exit_code == 0
    assert len(coincidencias) == 1
    assert coincidencias[0]["arbol_sintactico"]["nombre"] == "Diagnostico"
    assert reporte["resumen"]["desconocidos"] == 0

