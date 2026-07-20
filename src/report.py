from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from src.explainer import explain
from src.parser import DiagnosticEntry, construir_arbol_diagnostico


def agrupar_diagnosticos_con_notas(diagnosticos):
    """Adjunta las notas de GCC al diagnostico principal anterior."""
    agrupados = []

    for diagnostico in diagnosticos:
        if diagnostico.severidad == "note" and agrupados:
            notas_actuales = agrupados[-1][1]
            if not any(
                nota.mensaje_crudo == diagnostico.mensaje_crudo
                for nota in notas_actuales
            ):
                notas_actuales.append(diagnostico)
            continue
        agrupados.append((diagnostico, []))

    return agrupados


def calcular_resumen_clasificacion(diagnosticos) -> dict:
    principales = [
        diagnostico
        for diagnostico, _ in agrupar_diagnosticos_con_notas(diagnosticos)
    ]
    desconocidos = [
        diagnostico
        for diagnostico in principales
        if diagnostico.tipo_error == "desconocido"
    ]
    total = len(principales)
    cantidad_desconocidos = len(desconocidos)
    clasificados = total - cantidad_desconocidos

    return {
        "total": total,
        "clasificados": clasificados,
        "desconocidos": cantidad_desconocidos,
        "cobertura": (clasificados / total * 100) if total else 100.0,
        "diagnosticos_desconocidos": desconocidos,
    }


def obtener_contexto_codigo(diagnostico: DiagnosticEntry) -> list[str] | None:
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
        "    Codigo:",
        f"      {numero} | {codigo}",
        f"      {' ' * ancho_linea} | {marcador[ancho_linea + 3:]}",
    ]


def normalizar_ruta_json(ruta: str) -> str:
    """Usa separadores '/' para que el JSON sea portable entre sistemas."""
    return ruta.replace("\\", "/")


def construir_reporte_json(
    ruta_fuente: str,
    diagnosticos,
    ast_codigo=None,
    error_ast: str | None = None,
    tabla_simbolos=None,
    archivo_visible: str | None = None,
) -> dict:
    resumen = calcular_resumen_clasificacion(diagnosticos)
    elementos = []

    for diagnostico, notas in agrupar_diagnosticos_con_notas(diagnosticos):
        mejora = explain(diagnostico)
        contexto = obtener_contexto_codigo(diagnostico)
        diagnostico_reporte = diagnostico
        if archivo_visible:
            diagnostico_reporte = replace(
                diagnostico,
                archivo=archivo_visible,
            )
        arbol = construir_arbol_diagnostico(
            diagnostico_reporte,
            notas=notas,
            contexto_codigo=contexto[1:] if contexto else None,
        )
        elementos.append(
            {
                "archivo": normalizar_ruta_json(diagnostico_reporte.archivo),
                "linea": diagnostico.linea,
                "columna": diagnostico.columna,
                "severidad": diagnostico.severidad,
                "etiqueta_severidad": _etiqueta_severidad(
                    diagnostico.severidad
                ),
                "tipo_error": diagnostico.tipo_error,
                "origen": diagnostico.origen,
                "simbolo": diagnostico.simbolo,
                "mensaje_crudo": diagnostico.mensaje_crudo,
                "titulo": mejora["titulo"],
                "explicacion": mejora["explicacion"],
                "causa_probable": mejora["causa_probable"],
                "sugerencia": mejora["sugerencia"],
                "contexto_codigo": contexto[1:] if contexto else [],
                "notas_gcc": [nota.mensaje_crudo for nota in notas],
                "arbol_sintactico": arbol.to_dict(),
            }
        )

    ruta_reporte = archivo_visible or ruta_fuente
    return {
        "archivo_fuente": normalizar_ruta_json(ruta_reporte),
        "resumen": {
            "diagnosticos_principales": resumen["total"],
            "clasificados": resumen["clasificados"],
            "desconocidos": resumen["desconocidos"],
            "cobertura_clasificacion": round(resumen["cobertura"], 1),
        },
        "diagnosticos": elementos,
        "ast_codigo": ast_codigo.to_dict() if ast_codigo else None,
        "error_ast": error_ast,
        "tabla_simbolos": tabla_simbolos.to_dict() if tabla_simbolos else None,
    }


def _etiqueta_severidad(severidad: str) -> str:
    return {
        "error": "ERROR",
        "warning": "ADVERTENCIA",
        "note": "NOTA",
    }.get(severidad, severidad.upper())
