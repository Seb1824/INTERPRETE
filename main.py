import argparse
import json
from pathlib import Path

from src.analyzer import analizar_archivo
from src.analyzer import combinar_diagnosticos as _combinar_diagnosticos
from src.explainer import explain
from src.lexer import Lexer, LexerError
from src.parser import construir_arbol_diagnostico
from src.report import (
    agrupar_diagnosticos_con_notas as _agrupar_diagnosticos_con_notas,
    calcular_resumen_clasificacion as _calcular_resumen_clasificacion,
    construir_reporte_json as _construir_reporte_json,
    normalizar_ruta_json as _normalizar_ruta_json,
    obtener_contexto_codigo as _obtener_contexto_codigo,
)


def _etiqueta_severidad(severidad: str) -> str:
    etiquetas = {
        "error": "ERROR",
        "warning": "ADVERTENCIA",
        "note": "NOTA",
    }
    return etiquetas.get(severidad, severidad.upper())


def _exportar_json(
    ruta_salida: str,
    ruta_fuente: str,
    diagnosticos,
    ast_codigo=None,
    error_ast: str | None = None,
    tabla_simbolos=None,
) -> None:
    destino = Path(ruta_salida)
    destino.parent.mkdir(parents=True, exist_ok=True)
    reporte = _construir_reporte_json(
        ruta_fuente,
        diagnosticos,
        ast_codigo=ast_codigo,
        error_ast=error_ast,
        tabla_simbolos=tabla_simbolos,
    )
    destino.write_text(
        json.dumps(reporte, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _imprimir_salida_debug(
    stderr: str,
    tokens,
    diagnosticos,
    diagnosticos_semanticos=None,
    ast_codigo=None,
    error_ast: str | None = None,
    tabla_simbolos=None,
) -> None:
    print("=== STDERR CRUDO (GCC) ===")
    print(stderr.strip() or "(sin salida)")

    print("\n=== TOKENS ===")
    if not tokens:
        print("(sin tokens)")
    else:
        for t in tokens:
            print(t)

    print("\n=== AST DEL CODIGO C ===")
    if ast_codigo:
        for linea in ast_codigo.render():
            print(linea)
    elif error_ast:
        print(f"(no disponible: {error_ast})")
    else:
        print("(sin AST)")

    print("\n=== TABLA DE SIMBOLOS ===")
    if tabla_simbolos:
        for linea in tabla_simbolos.render():
            print(linea)
    elif error_ast:
        print("(no disponible porque no se pudo construir el AST)")
    else:
        print("(sin tabla de simbolos)")

    print("\n=== DIAGNOSTICOS (PARSER) ===")
    if not diagnosticos:
        print("(sin diagnosticos)")
    else:
        for i, d in enumerate(diagnosticos, start=1):
            print(f"[{i}] archivo={d.archivo} linea={d.linea} columna={d.columna}")
            print(
                f"    severidad={d.severidad} tipo_error={d.tipo_error} "
                f"origen={d.origen} simbolo={d.simbolo}"
            )
            print(f"    mensaje={d.mensaje_crudo}")

    print("\n=== ANALISIS SEMANTICO PROPIO ===")
    diagnosticos_semanticos = diagnosticos_semanticos or []
    if not diagnosticos_semanticos:
        print("(sin diagnosticos semanticos)")
    else:
        for i, d in enumerate(diagnosticos_semanticos, start=1):
            print(f"[{i}] archivo={d.archivo} linea={d.linea} columna={d.columna}")
            print(f"    severidad={d.severidad} tipo_error={d.tipo_error} simbolo={d.simbolo}")
            print(f"    mensaje={d.mensaje_crudo}")

    print("\n=== ARBOL SINTACTICO DE DIAGNOSTICOS ===")
    diagnosticos_agrupados = _agrupar_diagnosticos_con_notas(diagnosticos)
    if not diagnosticos_agrupados:
        print("(sin arbol)")
    else:
        for i, (diagnostico, notas) in enumerate(diagnosticos_agrupados, start=1):
            contexto = _obtener_contexto_codigo(diagnostico)
            arbol = construir_arbol_diagnostico(
                diagnostico,
                notas=notas,
                contexto_codigo=contexto[1:] if contexto else None,
            )
            print(f"[{i}]")
            for linea in arbol.render():
                print(f"    {linea}")


def _imprimir_mensajes_mejorados(diagnosticos) -> None:
    print("=== MENSAJES MEJORADOS ===")
    if not diagnosticos:
        print("Revision completada: no se detectaron errores ni advertencias.")
        return

    diagnosticos_agrupados = _agrupar_diagnosticos_con_notas(diagnosticos)
    for i, (d, notas) in enumerate(diagnosticos_agrupados, start=1):
        mejora = explain(d)
        etiqueta = _etiqueta_severidad(d.severidad)
        print(f"[{i}] [{etiqueta}] {mejora['titulo']}")
        print(f"    Ubicacion: {d.archivo}:{d.linea}:{d.columna}")
        if d.origen != "gcc":
            print(f"    Origen: analizador semantico del proyecto")
        contexto = _obtener_contexto_codigo(d)
        if contexto:
            for linea_contexto in contexto:
                print(linea_contexto)
        print(f"    Explicacion: {mejora['explicacion']}")
        print(f"    Causa probable: {mejora['causa_probable']}")
        print(f"    Sugerencia: {mejora['sugerencia']}")
        if notas:
            print("    Notas de GCC:")
            for nota in notas:
                print(f"      - {nota.mensaje_crudo}")

    resumen = _calcular_resumen_clasificacion(diagnosticos)
    print("\n=== RESUMEN DE CLASIFICACION ===")
    print(f"Diagnosticos principales: {resumen['total']}")
    print(f"Clasificados: {resumen['clasificados']}")
    print(f"Desconocidos: {resumen['desconocidos']}")
    print(f"Cobertura de clasificacion: {resumen['cobertura']:.1f}%")

    if resumen["diagnosticos_desconocidos"]:
        print("Mensajes no clasificados:")
        for diagnostico in resumen["diagnosticos_desconocidos"]:
            print(
                f"  - {diagnostico.archivo}:{diagnostico.linea}:"
                f"{diagnostico.columna}: {diagnostico.mensaje_crudo}"
            )


def _validar_archivo_fuente(ruta: Path) -> str | None:
    if not ruta.exists():
        return f"No existe el archivo: {ruta}"

    if not ruta.is_file():
        return f"La ruta no corresponde a un archivo: {ruta}"

    if ruta.suffix.lower() != ".c":
        return f"El archivo debe tener extension .c: {ruta}"

    try:
        with ruta.open("r", encoding="utf-8") as archivo:
            archivo.read(1)
    except UnicodeError:
        return f"El archivo no esta codificado en UTF-8: {ruta}"
    except OSError as exc:
        return f"No se pudo leer el archivo '{ruta}': {exc}"

    return None


def run_pipeline(
    ruta_archivo: str,
    debug: bool = False,
    json_output: str | None = None,
) -> int:
    ruta = Path(ruta_archivo)
    error_validacion = _validar_archivo_fuente(ruta)
    if error_validacion:
        print(f"[ERROR] {error_validacion}")
        return 1

    try:
        resultado = analizar_archivo(str(ruta))
    except LexerError as exc:
        print(f"[ERROR] {exc}")
        return 1

    stderr = resultado.stderr
    tokens = resultado.tokens
    diagnosticos_semanticos = resultado.diagnosticos_semanticos
    ast_codigo = resultado.ast_codigo
    error_ast = resultado.error_ast
    tabla_simbolos = resultado.tabla_simbolos
    diagnosticos = resultado.diagnosticos

    if json_output:
        try:
            _exportar_json(
                json_output,
                str(ruta),
                diagnosticos,
                ast_codigo=ast_codigo,
                error_ast=error_ast,
                tabla_simbolos=tabla_simbolos,
            )
        except OSError as exc:
            print(f"[ERROR] No se pudo guardar el archivo JSON '{json_output}': {exc}")
            return 1

    if debug:
        _imprimir_salida_debug(
            stderr,
            tokens,
            diagnosticos,
            diagnosticos_semanticos=diagnosticos_semanticos,
            ast_codigo=ast_codigo,
            error_ast=error_ast,
            tabla_simbolos=tabla_simbolos,
        )
        print()

    _imprimir_mensajes_mejorados(diagnosticos)
    if json_output:
        print(f"\nResultado JSON guardado en: {json_output}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline Lexer -> Parser para diagnósticos de GCC")
    parser.add_argument("archivo", help="Ruta al archivo .c a compilar")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Muestra stderr crudo, tokens y diagnosticos tecnicos ademas de los mensajes mejorados",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        metavar="RUTA",
        help="Exporta los diagnosticos y explicaciones a un archivo JSON",
    )
    args = parser.parse_args()

    return run_pipeline(
        args.archivo,
        debug=args.debug,
        json_output=args.json_output,
    )


if __name__ == "__main__":
    raise SystemExit(main())
