from __future__ import annotations

import json
import os
import tempfile
from io import BytesIO
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from src.analyzer import AnalysisResult, analizar_archivo
from src.explainer import explain
from src.lexer import LexerError
from src.report import construir_reporte_json


MAXIMO_CODIGO_BYTES = 512 * 1024
CODIGO_INICIAL = """#include <stdio.h>

int main() {
    int numero = 10;
    printf("%d\\n", numero);
    return 0;
}
"""


def create_app(configuracion: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        MAX_CONTENT_LENGTH=MAXIMO_CODIGO_BYTES,
    )
    if configuracion:
        app.config.update(configuracion)

    @app.get("/")
    def inicio():
        return render_template(
            "index.html",
            codigo=CODIGO_INICIAL,
            nombre_archivo="codigo.c",
            resultado=None,
            error=None,
        )

    @app.post("/analizar")
    def analizar():
        archivo = request.files.get("archivo")
        codigo_formulario = request.form.get("codigo", "")

        try:
            nombre_archivo, codigo = _obtener_codigo(
                archivo,
                codigo_formulario,
            )
        except ValueError as exc:
            return (
                render_template(
                    "index.html",
                    codigo=codigo_formulario,
                    nombre_archivo="codigo.c",
                    resultado=None,
                    error=str(exc),
                ),
                400,
            )

        try:
            with tempfile.TemporaryDirectory() as directorio:
                ruta_temporal = Path(directorio) / nombre_archivo
                ruta_temporal.write_text(codigo, encoding="utf-8")
                analisis = analizar_archivo(str(ruta_temporal))
                resultado = _crear_vista_resultado(
                    analisis,
                    codigo,
                    nombre_archivo,
                )
        except LexerError as exc:
            return (
                render_template(
                    "index.html",
                    codigo=codigo,
                    nombre_archivo=nombre_archivo,
                    resultado=None,
                    error=str(exc),
                ),
                503,
            )
        except OSError as exc:
            return (
                render_template(
                    "index.html",
                    codigo=codigo,
                    nombre_archivo=nombre_archivo,
                    resultado=None,
                    error=f"No se pudo procesar el archivo: {exc}",
                ),
                500,
            )

        return render_template(
            "index.html",
            codigo=codigo,
            nombre_archivo=nombre_archivo,
            resultado=resultado,
            error=None,
        )

    @app.post("/descargar-json")
    def descargar_json():
        archivo = request.files.get("archivo")
        codigo_formulario = request.form.get("codigo", "")

        try:
            nombre_archivo, codigo = _obtener_codigo(
                archivo,
                codigo_formulario,
            )
            with tempfile.TemporaryDirectory() as directorio:
                ruta_temporal = Path(directorio) / nombre_archivo
                ruta_temporal.write_text(codigo, encoding="utf-8")
                analisis = analizar_archivo(str(ruta_temporal))
                reporte = construir_reporte_json(
                    str(ruta_temporal),
                    analisis.diagnosticos,
                    ast_codigo=analisis.ast_codigo,
                    error_ast=analisis.error_ast,
                    tabla_simbolos=analisis.tabla_simbolos,
                    archivo_visible=nombre_archivo,
                )
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        except LexerError as exc:
            return jsonify(error=str(exc)), 503
        except OSError as exc:
            return jsonify(error=f"No se pudo generar el reporte: {exc}"), 500

        contenido = json.dumps(
            reporte,
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")
        nombre_descarga = f"{Path(nombre_archivo).stem}_diagnosticos.json"
        return send_file(
            BytesIO(contenido),
            mimetype="application/json",
            as_attachment=True,
            download_name=nombre_descarga,
        )

    @app.errorhandler(RequestEntityTooLarge)
    def archivo_demasiado_grande(_error):
        return (
            render_template(
                "index.html",
                codigo=CODIGO_INICIAL,
                nombre_archivo="codigo.c",
                resultado=None,
                error="El archivo supera el limite de 512 KB.",
            ),
            413,
        )

    return app


def _obtener_codigo(archivo, codigo_formulario: str) -> tuple[str, str]:
    if archivo and archivo.filename:
        nombre = secure_filename(archivo.filename)
        if not nombre or Path(nombre).suffix.lower() != ".c":
            raise ValueError("Selecciona un archivo con extension .c.")

        contenido = archivo.read(MAXIMO_CODIGO_BYTES + 1)
        if len(contenido) > MAXIMO_CODIGO_BYTES:
            raise ValueError("El archivo supera el limite de 512 KB.")

        try:
            codigo = contenido.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError(
                "El archivo debe estar codificado en UTF-8."
            ) from exc
    else:
        nombre = "codigo.c"
        codigo = codigo_formulario

    if not codigo.strip():
        raise ValueError("Escribe codigo C o selecciona un archivo .c.")

    return nombre, codigo


def _crear_vista_resultado(
    analisis: AnalysisResult,
    codigo: str,
    nombre_archivo: str,
) -> dict:
    lineas = codigo.splitlines()
    diagnosticos = []

    for diagnostico, notas in _agrupar_con_notas(analisis.diagnosticos):
        mejora = explain(diagnostico)
        linea_codigo = ""
        marcador = ""
        if 1 <= diagnostico.linea <= len(lineas):
            linea_codigo = lineas[diagnostico.linea - 1]
            marcador = " " * max(diagnostico.columna - 1, 0) + "^"

        diagnosticos.append(
            {
                "archivo": nombre_archivo,
                "linea": diagnostico.linea,
                "columna": diagnostico.columna,
                "severidad": diagnostico.severidad,
                "etiqueta": _etiqueta_severidad(diagnostico.severidad),
                "tipo_error": diagnostico.tipo_error,
                "origen": diagnostico.origen,
                "simbolo": diagnostico.simbolo,
                "titulo": mejora["titulo"],
                "explicacion": mejora["explicacion"],
                "causa_probable": mejora["causa_probable"],
                "sugerencia": mejora["sugerencia"],
                "linea_codigo": linea_codigo,
                "marcador": marcador,
                "notas": [nota.mensaje_crudo for nota in notas],
            }
        )

    errores = sum(
        diagnostico["severidad"] == "error"
        for diagnostico in diagnosticos
    )
    advertencias = sum(
        diagnostico["severidad"] == "warning"
        for diagnostico in diagnosticos
    )
    desconocidos = sum(
        diagnostico["tipo_error"] == "desconocido"
        for diagnostico in diagnosticos
    )
    total = len(diagnosticos)

    return {
        "archivo": nombre_archivo,
        "diagnosticos": diagnosticos,
        "errores": errores,
        "advertencias": advertencias,
        "total": total,
        "clasificados": total - desconocidos,
        "cobertura": ((total - desconocidos) / total * 100) if total else 100.0,
        "ast": (
            analisis.ast_codigo.render()
            if analisis.ast_codigo
            else []
        ),
        "error_ast": analisis.error_ast,
        "tabla_simbolos": (
            analisis.tabla_simbolos.render()
            if analisis.tabla_simbolos
            else []
        ),
        "stderr": analisis.stderr,
    }


def _agrupar_con_notas(diagnosticos):
    agrupados = []
    for diagnostico in diagnosticos:
        if diagnostico.severidad == "note" and agrupados:
            notas = agrupados[-1][1]
            if not any(
                nota.mensaje_crudo == diagnostico.mensaje_crudo
                for nota in notas
            ):
                notas.append(diagnostico)
            continue
        agrupados.append((diagnostico, []))
    return agrupados


def _etiqueta_severidad(severidad: str) -> str:
    return {
        "error": "ERROR",
        "warning": "ADVERTENCIA",
        "note": "NOTA",
    }.get(severidad, severidad.upper())


app = create_app()


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=int(os.environ.get("PORT", "5000")),
        debug=False,
    )
