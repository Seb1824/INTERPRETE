import argparse
from pathlib import Path

from src.explainer import explain
from src.lexer import Lexer
from src.parser import Parser


def _agrupar_diagnosticos_con_notas(diagnosticos):
    """Adjunta las notas de GCC al diagnostico anterior."""
    agrupados = []

    for diagnostico in diagnosticos:
        if diagnostico.severidad == "note" and agrupados:
            agrupados[-1][1].append(diagnostico)
            continue

        agrupados.append((diagnostico, []))

    return agrupados


def _obtener_contexto_codigo(diagnostico):
    ruta = Path(diagnostico.archivo)
    if not ruta.exists() or diagnostico.linea <= 0:
        return None

    try:
        lineas = ruta.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None

    if diagnostico.linea > len(lineas):
        return None

    numero = diagnostico.linea
    codigo = lineas[numero - 1]
    ancho_linea = len(str(numero))
    columna = max(diagnostico.columna, 1)
    marcador = " " * (ancho_linea + 3 + columna - 1) + "^"

    return [
        f"    Codigo:",
        f"      {numero} | {codigo}",
        f"      {' ' * ancho_linea} | {marcador[ancho_linea + 3:]}",
    ]


def _imprimir_salida_debug(stderr: str, tokens, diagnosticos) -> None:
    print("=== STDERR CRUDO (GCC) ===")
    print(stderr.strip() or "(sin salida)")

    print("\n=== TOKENS ===")
    if not tokens:
        print("(sin tokens)")
    else:
        for t in tokens:
            print(t)

    print("\n=== DIAGNOSTICOS (PARSER) ===")
    if not diagnosticos:
        print("(sin diagnosticos)")
    else:
        for i, d in enumerate(diagnosticos, start=1):
            print(f"[{i}] archivo={d.archivo} linea={d.linea} columna={d.columna}")
            print(f"    severidad={d.severidad} tipo_error={d.tipo_error} simbolo={d.simbolo}")
            print(f"    mensaje={d.mensaje_crudo}")


def _imprimir_mensajes_mejorados(diagnosticos) -> None:
    print("=== MENSAJES MEJORADOS ===")
    if not diagnosticos:
        print("(sin mensajes mejorados)")
        return

    for i, (d, notas) in enumerate(_agrupar_diagnosticos_con_notas(diagnosticos), start=1):
        mejora = explain(d)
        print(f"[{i}] {mejora['titulo']}")
        print(f"    Ubicacion: {d.archivo}:{d.linea}:{d.columna}")
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


def run_pipeline(ruta_archivo: str, debug: bool = False) -> int:
    ruta = Path(ruta_archivo)
    if not ruta.exists():
        print(f"[ERROR] No existe el archivo: {ruta}")
        return 1

    lexer = Lexer(str(ruta))
    stderr = lexer.compilar_y_capturar()
    tokens = lexer.tokenizar()
    diagnosticos = Parser(tokens).parse()

    if debug:
        _imprimir_salida_debug(stderr, tokens, diagnosticos)
        print()

    _imprimir_mensajes_mejorados(diagnosticos)

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline Lexer -> Parser para diagnósticos de GCC")
    parser.add_argument("archivo", help="Ruta al archivo .c a compilar")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Muestra stderr crudo, tokens y diagnosticos tecnicos ademas de los mensajes mejorados",
    )
    args = parser.parse_args()

    return run_pipeline(args.archivo, debug=args.debug)


if __name__ == "__main__":
    raise SystemExit(main())
