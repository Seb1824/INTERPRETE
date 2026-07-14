import json

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

