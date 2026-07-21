import json
from io import BytesIO
from pathlib import Path

import pytest

from web_app import create_app


@pytest.fixture
def cliente_web():
    app = create_app({"TESTING": True})
    return app.test_client()


def test_inicio_muestra_editor_y_formulario_accesible(cliente_web):
    respuesta = cliente_web.get("/")
    contenido = respuesta.get_data(as_text=True)

    assert respuesta.status_code == 200
    assert "Analizador educativo de C" in contenido
    assert 'action="/analizar"' in contenido
    assert 'name="codigo"' in contenido
    assert 'name="archivo"' in contenido
    assert 'href="#contenido-principal"' in contenido


def test_editor_incluye_numeros_de_linea(cliente_web):
    respuesta = cliente_web.get("/")
    contenido = respuesta.get_data(as_text=True)

    assert respuesta.status_code == 200
    assert 'class="code-editor"' in contenido
    assert 'id="line-numbers"' in contenido
    assert 'aria-hidden="true"' in contenido


def test_javascript_actualiza_y_sincroniza_numeros_de_linea():
    javascript = Path("static/app.js").read_text(encoding="utf-8")

    assert "function updateLineNumbers()" in javascript
    assert 'codeInput.addEventListener("input", updateEditorMetrics)' in javascript
    assert 'codeInput.addEventListener("scroll", syncLineNumberScroll)' in javascript


def test_resultado_ofrece_descarga_json(cliente_web):
    respuesta = cliente_web.post(
        "/analizar",
        data={"codigo": "int main() { return 0; }\n"},
    )
    contenido = respuesta.get_data(as_text=True)

    assert respuesta.status_code == 200
    assert 'id="download-json"' in contenido
    assert 'formaction="/descargar-json"' in contenido


def test_analiza_codigo_pegado_correcto(cliente_web):
    respuesta = cliente_web.post(
        "/analizar",
        data={"codigo": "int main() { return 0; }\n"},
    )
    contenido = respuesta.get_data(as_text=True)

    assert respuesta.status_code == 200
    assert "Revision completada" in contenido
    assert "No se detectaron errores ni advertencias" in contenido
    assert "scope_0" in contenido
    assert "FileAST" in contenido


def test_analiza_codigo_pegado_con_error_sin_duplicar_gcc(cliente_web):
    respuesta = cliente_web.post(
        "/analizar",
        data={"codigo": "int main() {\n    return total;\n}\n"},
    )
    contenido = respuesta.get_data(as_text=True)

    assert respuesta.status_code == 200
    assert "Variable o función &#39;total&#39; no declarada" in contenido
    assert "linea 2, columna 12" in contenido
    assert contenido.count('class="diagnostic diagnostic-error"') == 1
    assert "Usos no resueltos" in contenido


def test_muestra_controles_de_voz_para_los_diagnosticos(cliente_web):
    respuesta = cliente_web.post(
        "/analizar",
        data={"codigo": "int main() {\n    return total;\n}\n"},
    )
    contenido = respuesta.get_data(as_text=True)

    assert respuesta.status_code == 200
    assert 'id="speech-controls"' in contenido
    assert 'id="speak-all"' in contenido
    assert 'id="pause-speech"' in contenido
    assert 'id="stop-speech"' in contenido
    assert 'id="speech-rate"' in contenido
    assert "data-speech-item" in contenido
    assert "data-speak-diagnostic" in contenido


def test_analiza_archivo_c_cargado(cliente_web):
    respuesta = cliente_web.post(
        "/analizar",
        data={
            "codigo": "",
            "archivo": (
                BytesIO(b"int main() { return 0; }\n"),
                "programa.C",
            ),
        },
        content_type="multipart/form-data",
    )
    contenido = respuesta.get_data(as_text=True)

    assert respuesta.status_code == 200
    assert "programa.C" in contenido
    assert "Revision completada" in contenido


def test_rechaza_archivo_con_extension_invalida(cliente_web):
    respuesta = cliente_web.post(
        "/analizar",
        data={
            "codigo": "",
            "archivo": (BytesIO(b"int main() {}"), "programa.txt"),
        },
        content_type="multipart/form-data",
    )

    assert respuesta.status_code == 400
    assert "Selecciona un archivo con extension .c" in respuesta.get_data(
        as_text=True
    )


def test_rechaza_codigo_vacio(cliente_web):
    respuesta = cliente_web.post("/analizar", data={"codigo": "   "})

    assert respuesta.status_code == 400
    assert "Escribe codigo C" in respuesta.get_data(as_text=True)


def test_descarga_json_del_codigo_pegado(cliente_web):
    respuesta = cliente_web.post(
        "/descargar-json",
        data={"codigo": "int main() { return total; }\n"},
    )

    assert respuesta.status_code == 200
    assert respuesta.mimetype == "application/json"
    assert "codigo_diagnosticos.json" in respuesta.headers[
        "Content-Disposition"
    ]

    reporte = json.loads(respuesta.get_data(as_text=True))
    assert reporte["archivo_fuente"] == "codigo.c"
    assert reporte["resumen"]["diagnosticos_principales"] == 1
    assert reporte["diagnosticos"][0]["archivo"] == "codigo.c"
    assert reporte["diagnosticos"][0]["simbolo"] == "total"
    assert reporte["ast_codigo"] is not None
    assert reporte["tabla_simbolos"] is not None


def test_descarga_json_conserva_nombre_del_archivo(cliente_web):
    respuesta = cliente_web.post(
        "/descargar-json",
        data={
            "codigo": "",
            "archivo": (
                BytesIO(b"int main(void) { return 0; }\n"),
                "Mi Programa.C",
            ),
        },
        content_type="multipart/form-data",
    )

    assert respuesta.status_code == 200
    assert "Mi_Programa_diagnosticos.json" in respuesta.headers[
        "Content-Disposition"
    ]
    reporte = json.loads(respuesta.get_data(as_text=True))
    assert reporte["archivo_fuente"] == "Mi_Programa.C"
    assert reporte["diagnosticos"] == []


def test_descarga_json_rechaza_codigo_vacio(cliente_web):
    respuesta = cliente_web.post(
        "/descargar-json",
        data={"codigo": "   "},
    )

    assert respuesta.status_code == 400
    assert respuesta.get_json()["error"].startswith("Escribe codigo C")
