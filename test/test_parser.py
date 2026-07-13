from src.lexer import Lexer
from src.parser import Parser, construir_arbol_diagnostico
from src.token import Token, TokenType


def test_parser_genera_diagnosticos_desde_lexer():
    lexer = Lexer("examples/error_lexico.c")
    tokens = lexer.tokenizar()

    parser = Parser(tokens)
    diagnosticos = parser.parse()

    assert len(diagnosticos) >= 1
    for d in diagnosticos:
        assert d.archivo.endswith('.c')
        assert d.linea > 0
        assert d.columna > 0
        assert d.severidad in {"error", "warning", "note"}
        assert d.mensaje_crudo.strip() != ""
        assert d.tipo_error.strip() != ""


def test_parser_soporta_diagnostico_sin_simbolo():
    tokens = [
        Token(TokenType.ARCHIVO, "archivo.c"),
        Token(TokenType.LINEA, "10"),
        Token(TokenType.COLUMNA, "2"),
        Token(TokenType.SEVERIDAD, "error"),
        Token(TokenType.MENSAJE_CRUDO, "mensaje cualquiera"),
        Token(TokenType.TIPO_ERROR, "desconocido"),
    ]

    diagnosticos = Parser(tokens).parse()

    assert len(diagnosticos) == 1
    assert diagnosticos[0].simbolo is None


def test_parser_ignora_bloques_incompletos():
    tokens = [
        Token(TokenType.ARCHIVO, "archivo.c"),
        Token(TokenType.LINEA, "10"),
        Token(TokenType.COLUMNA, "2"),
    ]

    diagnosticos = Parser(tokens).parse()
    assert diagnosticos == []


def test_parser_procesa_multiples_diagnosticos():
    tokens = [
        Token(TokenType.ARCHIVO, "a.c"),
        Token(TokenType.LINEA, "1"),
        Token(TokenType.COLUMNA, "1"),
        Token(TokenType.SEVERIDAD, "error"),
        Token(TokenType.MENSAJE_CRUDO, "msg1"),
        Token(TokenType.TIPO_ERROR, "expected_token"),
        Token(TokenType.SIMBOLO, ";"),
        Token(TokenType.ARCHIVO, "b.c"),
        Token(TokenType.LINEA, "3"),
        Token(TokenType.COLUMNA, "8"),
        Token(TokenType.SEVERIDAD, "warning"),
        Token(TokenType.MENSAJE_CRUDO, "msg2"),
        Token(TokenType.TIPO_ERROR, "unused_variable"),
    ]

    diagnosticos = Parser(tokens).parse()

    assert len(diagnosticos) == 2
    assert diagnosticos[0].archivo == "a.c"
    assert diagnosticos[0].simbolo == ";"
    assert diagnosticos[1].archivo == "b.c"
    assert diagnosticos[1].simbolo is None


def test_parser_ignora_tokens_desconocidos_entre_diagnosticos():
    tokens = [
        Token(TokenType.DESCONOCIDO, "ruido"),
        Token(TokenType.ARCHIVO, "x.c"),
        Token(TokenType.LINEA, "2"),
        Token(TokenType.COLUMNA, "5"),
        Token(TokenType.SEVERIDAD, "error"),
        Token(TokenType.MENSAJE_CRUDO, "msg"),
        Token(TokenType.TIPO_ERROR, "desconocido"),
    ]

    diagnosticos = Parser(tokens).parse()
    assert len(diagnosticos) == 1
    assert diagnosticos[0].archivo == "x.c"


def test_parser_ignora_diagnostico_si_linea_columna_no_son_numericas():
    tokens = [
        Token(TokenType.ARCHIVO, "x.c"),
        Token(TokenType.LINEA, "no_num"),
        Token(TokenType.COLUMNA, "5"),
        Token(TokenType.SEVERIDAD, "error"),
        Token(TokenType.MENSAJE_CRUDO, "msg"),
        Token(TokenType.TIPO_ERROR, "desconocido"),
    ]

    diagnosticos = Parser(tokens).parse()
    assert diagnosticos == []


def test_construir_arbol_diagnostico_genera_jerarquia():
    diagnostico = Parser(
        [
            Token(TokenType.ARCHIVO, "archivo.c"),
            Token(TokenType.LINEA, "4"),
            Token(TokenType.COLUMNA, "9"),
            Token(TokenType.SEVERIDAD, "error"),
            Token(TokenType.MENSAJE_CRUDO, "'x' undeclared"),
            Token(TokenType.TIPO_ERROR, "undeclared"),
            Token(TokenType.SIMBOLO, "x"),
        ]
    ).parse()[0]

    arbol = construir_arbol_diagnostico(
        diagnostico,
        contexto_codigo=["4 |     x = 10;", "  |     ^"],
    )
    datos = arbol.to_dict()

    assert datos["nombre"] == "Diagnostico"
    assert datos["hijos"][0]["nombre"] == "Ubicacion"
    assert any(hijo["nombre"] == "TipoError" for hijo in datos["hijos"])
    assert any(hijo["nombre"] == "Simbolo" for hijo in datos["hijos"])
    assert "- Diagnostico" in arbol.render()[0]
