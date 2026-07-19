from io import BytesIO

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
