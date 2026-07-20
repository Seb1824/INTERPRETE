import os
import subprocess
import pytest
from src.lexer import (
    CompilerExecutionError,
    CompilerNotFoundError,
    CompilerTimeoutError,
    Lexer,
    SourceReadError,
)
from src.parser import Parser
from src.token import TokenType

RUTA_CORRECTO   = os.path.join(os.path.dirname(__file__), '..', 'examples', 'correcto.c')
RUTA_ERROR      = os.path.join(os.path.dirname(__file__), '..', 'examples', 'error_lexico.c')


def test_archivo_correcto_no_genera_tokens():
    """Un archivo sin errores no debe producir ningún token de error."""
    lexer = Lexer(RUTA_CORRECTO)
    tokens = lexer.tokenizar()
    errores = [t for t in tokens if t.tipo == TokenType.SEVERIDAD and t.valor == 'error']
    assert len(errores) == 0, f"Se esperaban 0 errores, se encontraron: {errores}"
    print("PASS: archivo correcto no genera tokens de error")


def test_archivo_con_error_genera_tokens():
    """Un archivo con errores debe producir al menos un token de cada tipo básico."""
    lexer = Lexer(RUTA_ERROR)
    tokens = lexer.tokenizar()

    tipos_presentes = {t.tipo for t in tokens}

    assert TokenType.ARCHIVO in tipos_presentes,    "Falta token ARCHIVO"
    assert TokenType.LINEA in tipos_presentes,      "Falta token LINEA"
    assert TokenType.SEVERIDAD in tipos_presentes,  "Falta token SEVERIDAD"
    assert TokenType.MENSAJE_CRUDO in tipos_presentes, "Falta token MENSAJE_CRUDO"
    assert TokenType.TIPO_ERROR in tipos_presentes, "Falta token TIPO_ERROR"
    print("PASS: archivo con error genera todos los tipos de token esperados")


def test_stderr_se_captura_automaticamente():
    """El lexer debe capturar stderr sin intervención del usuario."""
    lexer = Lexer(RUTA_ERROR)
    lexer.compilar_y_capturar()
    assert len(lexer.stderr_crudo) > 0, "stderr vacío — no se capturó nada"
    print("PASS: stderr capturado automáticamente")


def test_tokens_tienen_valores_no_vacios():
    """Ningún token debe tener un valor vacío."""
    lexer = Lexer(RUTA_ERROR)
    tokens = lexer.tokenizar()
    vacios = [t for t in tokens if not t.valor.strip()]
    assert len(vacios) == 0, f"Tokens con valor vacío: {vacios}"
    print("PASS: todos los tokens tienen valores no vacíos")


if __name__ == "__main__":
    test_stderr_se_captura_automaticamente()
    test_archivo_correcto_no_genera_tokens()
    test_archivo_con_error_genera_tokens()
    test_tokens_tienen_valores_no_vacios()
    
    print("\nTodos los tests pasaron.")

def test_lexer_retorna_desconocido_para_linea_no_parseable():
    from src.lexer import _tokenizar_linea

    tokens = _tokenizar_linea("linea inventada sin formato gcc")
    assert len(tokens) == 1
    assert tokens[0].tipo == TokenType.DESCONOCIDO


def _tipo_error_desde_linea(linea: str) -> str:
    from src.lexer import _tokenizar_linea

    tokens = _tokenizar_linea(linea)
    tipo_error = next(t for t in tokens if t.tipo == TokenType.TIPO_ERROR)
    return tipo_error.valor


def test_lexer_clasifica_expected_token_real_de_gcc():
    linea = "examples\\error_lexico.c:6:5: error: expected ',' or ';' before 'return'"
    assert _tipo_error_desde_linea(linea) == "expected_token"


def test_lexer_clasifica_type_mismatch_real_de_gcc():
    linea = (
        "examples\\error_lexico.c:5:13: warning: initialization of 'int' "
        "from 'char *' makes integer from pointer without a cast [-Wint-conversion]"
    )
    assert _tipo_error_desde_linea(linea) == "type_mismatch"


def test_lexer_clasifica_unused_variable_real_de_gcc():
    linea = "examples\\error_lexico.c:5:9: warning: unused variable 'z' [-Wunused-variable]"
    assert _tipo_error_desde_linea(linea) == "unused_variable"


def test_lexer_clasifica_variable_asignada_pero_no_usada():
    linea = (
        "examples\\acceso_estructura.c:6:20: warning: variable 'persona' "
        "set but not used [-Wunused-but-set-variable]"
    )

    assert _tipo_error_desde_linea(linea) == "unused_variable"


def test_lexer_no_usa_tipo_c_como_simbolo():
    from src.lexer import _tokenizar_linea

    linea = (
        "examples\\error_lexico.c:5:13: warning: initialization of 'int' "
        "from 'char *' makes integer from pointer without a cast [-Wint-conversion]"
    )
    tokens = _tokenizar_linea(linea)
    simbolos = [t.valor for t in tokens if t.tipo == TokenType.SIMBOLO]

    assert "int" not in simbolos


def test_lexer_extrae_variable_de_declaracion_en_type_mismatch():
    from src.lexer import _tokenizar_linea

    linea = (
        "examples\\error_lexico.c:5:13: warning: initialization of 'int' "
        "from 'char *' makes integer from pointer without a cast [-Wint-conversion]"
    )
    tokens = _tokenizar_linea(linea, linea_fuente='    int z = "hola"')
    simbolo = next(t.valor for t in tokens if t.tipo == TokenType.SIMBOLO)

    assert simbolo == "z"


@pytest.mark.parametrize(
    ("archivo", "tipo_esperado"),
    [
        ("variable_no_declarada.c", "undeclared"),
        ("falta_punto_y_coma.c", "expected_token"),
        ("tipo_incompatible.c", "type_mismatch"),
        ("funcion_implicita.c", "implicit_declaration"),
        ("argumentos_incorrectos.c", "wrong_arguments"),
        ("variable_no_usada.c", "unused_variable"),
        ("redeclaracion.c", "redeclaration"),
        ("division_por_cero.c", "division_by_zero"),
        ("retorno_incorrecto.c", "return_error"),
        ("error_puntero.c", "pointer_error"),
        ("formato_printf.c", "format_mismatch"),
        ("delimitador_desbalanceado.c", "unbalanced_delimiter"),
        ("falta_retorno.c", "missing_return"),
        ("conversion_peligrosa.c", "dangerous_conversion"),
        ("variable_no_inicializada.c", "uninitialized_variable"),
        ("acceso_estructura.c", "struct_access"),
        ("error_preprocesador.c", "preprocessor_error"),
    ],
)
def test_examples_generan_tipo_esperado(archivo, tipo_esperado):
    ruta = os.path.join(os.path.dirname(__file__), "..", "examples", archivo)
    tokens = Lexer(ruta).tokenizar()
    tipos = [t.valor for t in tokens if t.tipo == TokenType.TIPO_ERROR]

    assert tipo_esperado in tipos


def test_lexer_informa_si_gcc_no_esta_instalado(monkeypatch):
    def gcc_no_encontrado(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", gcc_no_encontrado)

    with pytest.raises(CompilerNotFoundError, match="No se encontro GCC"):
        Lexer(RUTA_CORRECTO).compilar_y_capturar()


def test_lexer_informa_timeout_de_gcc(monkeypatch):
    def gcc_lento(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", gcc_lento)

    with pytest.raises(CompilerTimeoutError, match="tiempo maximo"):
        Lexer(RUTA_CORRECTO).compilar_y_capturar()


def test_lexer_informa_fallo_al_ejecutar_gcc(monkeypatch):
    def gcc_no_ejecutable(*args, **kwargs):
        raise PermissionError("acceso denegado")

    monkeypatch.setattr(subprocess, "run", gcc_no_ejecutable)

    with pytest.raises(CompilerExecutionError, match="No se pudo ejecutar GCC"):
        Lexer(RUTA_CORRECTO).compilar_y_capturar()


def test_lexer_informa_error_de_lectura(monkeypatch):
    lexer = Lexer(RUTA_ERROR)
    lexer.compilado = True
    lexer.stderr_crudo = "archivo.c:1:1: error: mensaje"

    def lectura_fallida(*args, **kwargs):
        raise PermissionError("acceso denegado")

    monkeypatch.setattr(type(lexer.ruta_archivo), "read_text", lectura_fallida)

    with pytest.raises(SourceReadError, match="No se pudo leer"):
        lexer.tokenizar()


@pytest.mark.parametrize(
    ("mensaje", "tipo_esperado"),
    [
        (
            "invalid type argument of unary '*' (have 'int')",
            "pointer_error",
        ),
        (
            "format '%d' expects argument of type 'int', but argument 2 has type 'char *'",
            "format_mismatch",
        ),
        (
            "expected '}' at end of input",
            "unbalanced_delimiter",
        ),
        (
            "control reaches end of non-void function [-Wreturn-type]",
            "missing_return",
        ),
        (
            "conversion from 'long int' to 'int' may change value [-Wconversion]",
            "dangerous_conversion",
        ),
        (
            "'contador' is used uninitialized [-Wuninitialized]",
            "uninitialized_variable",
        ),
        (
            "request for member 'edad' in something not a structure or union",
            "struct_access",
        ),
        (
            "fatal error: biblioteca_inexistente.h: No such file or directory",
            "preprocessor_error",
        ),
        (
            "suggest parentheses around assignment used as truth value [-Wparentheses]",
            "assignment_in_condition",
        ),
    ],
)
def test_lexer_clasifica_nuevos_mensajes_gcc(mensaje, tipo_esperado):
    from src.lexer import _tokenizar_linea

    linea = f"ejemplo.c:10:5: error: {mensaje}"
    tokens = _tokenizar_linea(linea)
    tipo = next(t.valor for t in tokens if t.tipo == TokenType.TIPO_ERROR)

    assert tipo == tipo_esperado


def test_lexer_normaliza_fatal_error_de_preprocesador():
    from src.lexer import _tokenizar_linea

    linea = (
        "ejemplo.c:1:10: fatal error: biblioteca_inexistente.h: "
        "No such file or directory"
    )
    tokens = _tokenizar_linea(linea)
    severidad = next(t.valor for t in tokens if t.tipo == TokenType.SEVERIDAD)
    tipo = next(t.valor for t in tokens if t.tipo == TokenType.TIPO_ERROR)

    assert severidad == "error"
    assert tipo == "preprocessor_error"


def test_lexer_reconoce_diagnostico_con_extension_c_mayuscula():
    from src.lexer import _tokenizar_linea

    linea = "ejemplo.C:2:12: error: 'x' undeclared"
    tokens = _tokenizar_linea(linea)
    archivo = next(t.valor for t in tokens if t.tipo == TokenType.ARCHIVO)
    tipo = next(t.valor for t in tokens if t.tipo == TokenType.TIPO_ERROR)

    assert archivo == "ejemplo.C"
    assert tipo == "undeclared"


def test_archivo_con_extension_c_mayuscula_se_clasifica():
    ruta = os.path.join(
        os.path.dirname(__file__),
        "..",
        "examples",
        "extension_mayuscula.C",
    )
    tokens = Lexer(ruta).tokenizar()
    tipos = [t.valor for t in tokens if t.tipo == TokenType.TIPO_ERROR]

    assert "undeclared" in tipos


@pytest.mark.parametrize(
    ("linea", "funcion_contexto", "tipo_esperado", "simbolo_esperado"),
    [
        (
            "ejemplo.c:3:19: warning: 'numero' is used uninitialized [-Wuninitialized]",
            None,
            "uninitialized_variable",
            "numero",
        ),
        (
            "ejemplo.c:7:19: error: 'struct Persona' has no member named 'altura'",
            None,
            "struct_access",
            "altura",
        ),
        (
            "ejemplo.c:5:1: warning: control reaches end of non-void function [-Wreturn-type]",
            "calcular",
            "missing_return",
            "calcular",
        ),
        (
            "ejemplo.c:1:10: fatal error: biblioteca_inexistente.h: No such file or directory",
            None,
            "preprocessor_error",
            "biblioteca_inexistente.h",
        ),
        (
            "ejemplo.c:5:14: warning: format '%d' expects argument of type 'int', "
            "but argument 2 has type 'char *' [-Wformat=]",
            None,
            "format_mismatch",
            "%d",
        ),
        (
            "ejemplo.c:4:9: warning: suggest parentheses around assignment "
            "used as truth value [-Wparentheses]",
            None,
            "assignment_in_condition",
            "=",
        ),
    ],
)
def test_lexer_extrae_simbolos_especificos_por_categoria(
    linea,
    funcion_contexto,
    tipo_esperado,
    simbolo_esperado,
):
    from src.lexer import _tokenizar_linea

    tokens = _tokenizar_linea(
        linea,
        funcion_contexto=funcion_contexto,
    )
    tipo = next(t.valor for t in tokens if t.tipo == TokenType.TIPO_ERROR)
    simbolo = next(t.valor for t in tokens if t.tipo == TokenType.SIMBOLO)

    assert tipo == tipo_esperado
    assert simbolo == simbolo_esperado


@pytest.mark.parametrize(
    (
        "linea",
        "linea_fuente",
        "funcion_contexto",
        "tipo_esperado",
        "simbolo_esperado",
    ),
    [
        (
            "ejemplo.c:3:17: error: invalid type argument of unary '*' (have 'int')",
            "    int valor = *numero;",
            "main",
            "pointer_error",
            "numero",
        ),
        (
            "ejemplo.c:4:18: warning: assignment to 'int *' from incompatible "
            "pointer type 'char *' [-Wincompatible-pointer-types]",
            "    int *destino = origen;",
            "main",
            "pointer_error",
            "destino",
        ),
        (
            "ejemplo.c:2:26: warning: overflow in conversion from 'long long int' "
            "to 'long int' changes value from '5000000000' to '705032704'",
            "    long numero_grande = 5000000000L;",
            "main",
            "dangerous_conversion",
            "numero_grande",
        ),
        (
            "ejemplo.c:6:21: error: too few arguments to function 'suma'",
            "    int resultado = suma(5);",
            "main",
            "wrong_arguments",
            "suma",
        ),
        (
            "ejemplo.c:2:12: warning: 'return' with a value, in function returning void",
            "    return 1;",
            "imprimir",
            "return_error",
            "imprimir",
        ),
    ],
)
def test_lexer_extrae_simbolos_de_punteros_conversiones_argumentos_y_retornos(
    linea,
    linea_fuente,
    funcion_contexto,
    tipo_esperado,
    simbolo_esperado,
):
    from src.lexer import _tokenizar_linea

    tokens = _tokenizar_linea(
        linea,
        linea_fuente=linea_fuente,
        funcion_contexto=funcion_contexto,
    )
    tipo = next(t.valor for t in tokens if t.tipo == TokenType.TIPO_ERROR)
    simbolo = next(t.valor for t in tokens if t.tipo == TokenType.SIMBOLO)

    assert tipo == tipo_esperado
    assert simbolo == simbolo_esperado


@pytest.mark.parametrize(
    ("archivo", "tipo_esperado", "simbolo_esperado"),
    [
        ("variable_no_inicializada.c", "uninitialized_variable", "numero"),
        ("acceso_estructura.c", "struct_access", "altura"),
        ("falta_retorno.c", "missing_return", "calcular"),
        ("error_preprocesador.c", "preprocessor_error", "biblioteca_inexistente.h"),
        ("formato_printf.c", "format_mismatch", "%d"),
        ("error_puntero.c", "pointer_error", "numero"),
        ("conversion_peligrosa.c", "dangerous_conversion", "numero_grande"),
        ("argumentos_incorrectos.c", "wrong_arguments", "suma"),
        ("retorno_incorrecto.c", "return_error", "imprimir"),
    ],
)
def test_archivos_reales_extraen_simbolo_correcto(
    archivo,
    tipo_esperado,
    simbolo_esperado,
):
    ruta = os.path.join(os.path.dirname(__file__), "..", "examples", archivo)
    diagnosticos = Parser(Lexer(ruta).tokenizar()).parse()
    diagnostico = next(
        d for d in diagnosticos if d.tipo_error == tipo_esperado
    )

    assert diagnostico.simbolo == simbolo_esperado
