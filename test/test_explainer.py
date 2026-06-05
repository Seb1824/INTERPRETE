import pytest
from src.parser import DiagnosticEntry
from src.explainer import explain

def make_entry(
    tipo_error: str,
    simbolo: str = "",
    mensaje_crudo: str = "",
    linea: int = 5,
    columna: int = 1,
    archivo: str = "test.c",
    severidad: str = "error",
) -> DiagnosticEntry:

    return DiagnosticEntry(
        archivo=archivo,
        linea=linea,
        columna=columna,
        severidad=severidad,
        mensaje_crudo=mensaje_crudo,
        tipo_error=tipo_error,
        simbolo=simbolo,
    )


TODOS_LOS_TIPOS = [
    "undeclared",
    "expected_token",
    "implicit_declaration",
    "type_mismatch",
    "wrong_arguments",
    "unused_variable",
    "return_error",
    "redeclaration",
    "division_by_zero",
    "desconocido",
]

CLAVES_ESPERADAS = {"titulo", "explicacion", "causa_probable", "sugerencia"}


@pytest.mark.parametrize("tipo", TODOS_LOS_TIPOS)
def test_estructura_retorno(tipo):
    entry = make_entry(tipo_error=tipo, simbolo="x")
    resultado = explain(entry)

    assert isinstance(resultado, dict), (
        f"explain() debe retornar un dict, retornó {type(resultado)}"
    )
    assert resultado.keys() == CLAVES_ESPERADAS, (
        f"Para tipo '{tipo}' faltan claves: "
        f"{CLAVES_ESPERADAS - resultado.keys()}"
    )


@pytest.mark.parametrize("tipo", TODOS_LOS_TIPOS)
def test_valores_no_vacios(tipo):
    entry = make_entry(tipo_error=tipo, simbolo="mi_var")
    resultado = explain(entry)

    for clave in CLAVES_ESPERADAS:
        assert resultado[clave].strip(), (
            f"El campo '{clave}' está vacío para tipo_error='{tipo}'"
        )


class TestUndeclared:
    def test_simbolo_en_titulo(self):
        entry = make_entry("undeclared", simbolo="contador")
        r = explain(entry)
        assert "contador" in r["titulo"]

    def test_simbolo_en_explicacion(self):
        entry = make_entry("undeclared", simbolo="contador")
        r = explain(entry)
        assert "contador" in r["explicacion"]

    def test_menciona_declaracion(self):
        entry = make_entry("undeclared", simbolo="x")
        r = explain(entry)
        texto = r["explicacion"] + r["causa_probable"] + r["sugerencia"]
        assert "declar" in texto.lower()

    def test_sin_simbolo_no_falla(self):
        entry = make_entry("undeclared", simbolo="")
        r = explain(entry)
        assert r["titulo"]  # Solo verificamos que tenga título


class TestExpectedToken:
    def test_menciona_linea(self):
        entry = make_entry("expected_token", simbolo=";", linea=12)
        r = explain(entry)
        assert "12" in r["explicacion"] or "12" in r["sugerencia"]

    def test_menciona_punto_y_coma(self):
        entry = make_entry("expected_token", simbolo=";")
        r = explain(entry)
        texto = r["causa_probable"] + r["sugerencia"]
        assert ";" in texto

    def test_simbolo_en_titulo(self):
        entry = make_entry("expected_token", simbolo=")")
        r = explain(entry)
        assert ")" in r["titulo"]


class TestImplicitDeclaration:
    def test_simbolo_en_titulo(self):
        entry = make_entry("implicit_declaration", simbolo="printf")
        r = explain(entry)
        assert "printf" in r["titulo"]

    def test_menciona_include(self):
        entry = make_entry("implicit_declaration", simbolo="printf")
        r = explain(entry)
        texto = r["causa_probable"] + r["sugerencia"]
        assert "#include" in texto

    def test_menciona_prototipo(self):
        entry = make_entry("implicit_declaration", simbolo="mi_funcion")
        r = explain(entry)
        texto = r["causa_probable"] + r["sugerencia"]
        assert "prototipo" in texto.lower()


class TestTypeMismatch:
    def test_simbolo_en_titulo(self):
        entry = make_entry("type_mismatch", simbolo="resultado")
        r = explain(entry)
        assert "resultado" in r["titulo"]

    def test_menciona_cast(self):
        entry = make_entry("type_mismatch", simbolo="x")
        r = explain(entry)
        assert "cast" in r["sugerencia"].lower()

    def test_menciona_tipos(self):
        entry = make_entry("type_mismatch", simbolo="y")
        r = explain(entry)
        texto = r["explicacion"] + r["causa_probable"]
        assert "tipo" in texto.lower()


class TestWrongArguments:
    def test_simbolo_en_titulo(self):
        entry = make_entry("wrong_arguments", simbolo="suma")
        r = explain(entry)
        assert "suma" in r["titulo"]

    def test_menciona_parametros(self):
        entry = make_entry("wrong_arguments", simbolo="suma")
        r = explain(entry)
        texto = r["explicacion"] + r["causa_probable"] + r["sugerencia"]
        assert "argumento" in texto.lower() or "parámetro" in texto.lower()

    def test_menciona_linea(self):
        entry = make_entry("wrong_arguments", simbolo="foo", linea=20)
        r = explain(entry)
        assert "20" in r["sugerencia"]


class TestUnusedVariable:
    def test_simbolo_en_titulo(self):
        entry = make_entry("unused_variable", simbolo="temp")
        r = explain(entry)
        assert "temp" in r["titulo"]

    def test_es_advertencia(self):
        entry = make_entry("unused_variable", simbolo="temp", severidad="warning")
        r = explain(entry)
        texto = r["explicacion"] + r["sugerencia"]
        assert "advertencia" in texto.lower() or "warning" in texto.lower()

    def test_da_dos_opciones(self):
        """La sugerencia debe ofrecer al menos dos caminos."""
        entry = make_entry("unused_variable", simbolo="n")
        r = explain(entry)
        # Verifica que haya dos opciones numeradas
        assert "(1)" in r["sugerencia"] and "(2)" in r["sugerencia"]


class TestReturnError:
    def test_simbolo_en_titulo(self):
        entry = make_entry("return_error", simbolo="calcular")
        r = explain(entry)
        assert "calcular" in r["titulo"]

    def test_menciona_void(self):
        entry = make_entry("return_error", simbolo="f")
        r = explain(entry)
        texto = r["causa_probable"] + r["sugerencia"]
        assert "void" in texto

    def test_menciona_tipo_retorno(self):
        entry = make_entry("return_error", simbolo="g")
        r = explain(entry)
        texto = r["explicacion"] + r["sugerencia"]
        assert "retorn" in texto.lower()


class TestRedeclaration:
    def test_simbolo_en_titulo(self):
        entry = make_entry("redeclaration", simbolo="MAX")
        r = explain(entry)
        assert "MAX" in r["titulo"]

    def test_menciona_ambito(self):
        entry = make_entry("redeclaration", simbolo="i")
        r = explain(entry)
        texto = r["explicacion"]
        assert "ámbito" in texto.lower() or "scope" in texto.lower()

    def test_menciona_linea(self):
        entry = make_entry("redeclaration", simbolo="total", linea=8)
        r = explain(entry)
        assert "8" in r["sugerencia"]


class TestDivisionByZero:
    def test_titulo_claro(self):
        entry = make_entry("division_by_zero")
        r = explain(entry)
        assert "cero" in r["titulo"].lower()

    def test_menciona_comportamiento_indefinido(self):
        entry = make_entry("division_by_zero")
        r = explain(entry)
        texto = r["explicacion"]
        assert "indefinido" in texto.lower() or "impredecible" in texto.lower()

    def test_sugerencia_incluye_if(self):
        """La sugerencia debe recomendar verificar antes de dividir."""
        entry = make_entry("division_by_zero", linea=3)
        r = explain(entry)
        assert "!= 0" in r["sugerencia"] or "if" in r["sugerencia"]

    def test_menciona_linea(self):
        entry = make_entry("division_by_zero", linea=15)
        r = explain(entry)
        assert "15" in r["explicacion"] or "15" in r["sugerencia"]


class TestDesconocido:
    def test_titulo_generico(self):
        entry = make_entry("desconocido", mensaje_crudo="lvalue required")
        r = explain(entry)
        assert r["titulo"]  # Debe tener algún título

    def test_mensaje_crudo_en_explicacion(self):
        """El mensaje crudo debe aparecer en la explicación para ayudar al usuario."""
        entry = make_entry("desconocido", mensaje_crudo="lvalue required as left operand")
        r = explain(entry)
        assert "lvalue required as left operand" in r["explicacion"]

    def test_sin_mensaje_crudo_no_falla(self):
        entry = make_entry("desconocido", mensaje_crudo="")
        r = explain(entry)
        assert r["explicacion"].strip()

    def test_sugerencia_orienta_busqueda(self):
        """La sugerencia debe orientar al estudiante a buscar ayuda."""
        entry = make_entry("desconocido", mensaje_crudo="some weird error")
        r = explain(entry)
        texto = r["sugerencia"].lower()
        assert "busca" in texto or "consulta" in texto or "documenta" in texto


class TestTipoDesconocidoFallback:
    def test_tipo_inexistente_usa_handler_desconocido(self):
        entry = make_entry(
            tipo_error="esto_no_existe",
            mensaje_crudo="error extraño del compilador",
        )
        r = explain(entry)
        assert isinstance(r, dict)
        assert r.keys() == CLAVES_ESPERADAS

    def test_tipo_vacio_no_falla(self):
        entry = make_entry(tipo_error="", mensaje_crudo="algo raro")
        r = explain(entry)
        assert r["titulo"]