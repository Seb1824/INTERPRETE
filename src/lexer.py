import os
import re
import subprocess
import tempfile
from pathlib import Path
from src.token import Token, TokenType

TIEMPO_MAXIMO_GCC_SEGUNDOS = 10
OPCIONES_GCC = [
    "-x",
    "c",
    "-O1",
    "-Wall",
    "-Wextra",
    "-Wconversion",
    "-Wuninitialized",
    "-Wreturn-type",
    "-c",
]


class LexerError(RuntimeError):
    """Error controlado durante la lectura o compilacion del archivo."""


class CompilerNotFoundError(LexerError):
    """GCC no esta instalado o no se encuentra en PATH."""


class CompilerTimeoutError(LexerError):
    """GCC excedio el tiempo maximo permitido."""


class CompilerExecutionError(LexerError):
    """No fue posible iniciar o ejecutar GCC."""


class SourceReadError(LexerError):
    """No fue posible leer el archivo fuente."""


_PATRON_GCC = re.compile(
    r'^(?P<archivo>[A-Za-z]:[/\\][^:]+\.c|[^:]+\.c):(?P<linea>\d+):(?P<columna>\d+):\s*(?P<severidad>fatal error|error|warning|note):\s*(?P<mensaje>.+)$',
    re.IGNORECASE,
)

# lineas de contexto que GCC imprime pero no son mensajes de error:
# "   4 |     printf(...)  " o  "      |         ^~~~~"
_PATRON_CONTEXTO = re.compile(r'^\s*\d+\s*\||\s*\|[\s^~]*$')

# Patrones para extraer el símbolo problemático del mensaje
_PATRONES_SIMBOLO = [
    re.compile(r"'(?P<simbolo>[^']+)'"),        # cualquier cosa entre comillas simples
    re.compile(r'"(?P<simbolo>[^"]+)"'),         # cualquier cosa entre comillas dobles
]

_TIPOS_C = {
    "auto",
    "char",
    "char *",
    "const",
    "double",
    "enum",
    "extern",
    "float",
    "int",
    "long",
    "register",
    "short",
    "signed",
    "static",
    "struct",
    "typedef",
    "union",
    "unsigned",
    "void",
    "volatile",
}

# Patrones para clasificar el tipo de error a partir del mensaje
_PATRONES_TIPO = [
    (
        re.compile(
            r"assignment used as truth value|assignment in conditional expression",
            re.IGNORECASE,
        ),
        "assignment_in_condition",
    ),
    (
        re.compile(
            r"format .* expects argument|format specifies type|too many arguments for format|"
            r"too few arguments for format|unknown conversion type character",
            re.IGNORECASE,
        ),
        "format_mismatch",
    ),
    (
        re.compile(
            r"used uninitialized|may be used uninitialized|is uninitialized",
            re.IGNORECASE,
        ),
        "uninitialized_variable",
    ),
    (
        re.compile(
            r"control reaches end of non-void function|no return statement in function "
            r"returning non-void",
            re.IGNORECASE,
        ),
        "missing_return",
    ),
    (
        re.compile(
            r"expected .?[})\]].? at end of input|unmatched|unterminated|"
            r"missing terminating|expected .?[})\]].? before|"
            r"expected declaration or statement at end of input",
            re.IGNORECASE,
        ),
        "unbalanced_delimiter",
    ),
    (
        re.compile(
            r"request for member .* in something not a structure or union|"
            r"has no member named|invalid use of (incomplete|undefined) type",
            re.IGNORECASE,
        ),
        "struct_access",
    ),
    (
        re.compile(
            r"invalid type argument of unary .?\*.?|dereferencing .* pointer|"
            r"incompatible pointer type|"
            r"assignment to .* pointer .* from .* without a cast",
            re.IGNORECASE,
        ),
        "pointer_error",
    ),
    (
        re.compile(
            r"conversion .* may change value|overflow in conversion|"
            r"changes value from|conversion loses integer precision",
            re.IGNORECASE,
        ),
        "dangerous_conversion",
    ),
    (
        re.compile(
            r"no such file or directory|#endif without #if|#else without #if|"
            r"#elif without #if|unterminated #if|unterminated #ifdef|"
            r"unterminated #ifndef|macro .* requires .* arguments|"
            r"invalid preprocessing directive|#error|"
            r"missing binary operator before token",
            re.IGNORECASE,
        ),
        "preprocessor_error",
    ),
    (re.compile(r'undeclared|not declared|undefined', re.IGNORECASE), 'undeclared'),
    (re.compile(r"expected\s+.+\s+before", re.IGNORECASE),            'expected_token'),
    (re.compile(r'implicit declaration', re.IGNORECASE),              'implicit_declaration'),
    (
        re.compile(
            r'incompatible type|cannot convert|makes integer from pointer|without a cast',
            re.IGNORECASE,
        ),
        'type_mismatch',
    ),
    (re.compile(r'too (few|many) argument', re.IGNORECASE),           'wrong_arguments'),
    (re.compile(r'unused variable|unused parameter', re.IGNORECASE),  'unused_variable'),
    (
        re.compile(
            r'return type|return value|return.*with a value|function returning void',
            re.IGNORECASE,
        ),
        'return_error',
    ),
    (re.compile(r'redeclar|redefinit', re.IGNORECASE),                'redeclaration'),
    (re.compile(r'divide|division by zero', re.IGNORECASE),           'division_by_zero'),
]


def _extraer_simbolo(mensaje: str) -> str | None:
    for patron in _PATRONES_SIMBOLO:
        for coincidencia in patron.finditer(mensaje):
            simbolo = coincidencia.group('simbolo')
            if not _es_tipo_c(simbolo):
                return simbolo
    return None


def _es_tipo_c(valor: str) -> bool:
    normalizado = valor.replace("*", " ").strip()
    palabras = normalizado.split()
    if not palabras:
        return False

    if palabras[0] in {"struct", "union", "enum"}:
        return True

    return all(palabra in _TIPOS_C for palabra in palabras)


def _clasificar_tipo(mensaje: str) -> str:
    for patron, tipo in _PATRONES_TIPO:
        if patron.search(mensaje):
            return tipo
    return 'desconocido'


def _extraer_variable_de_declaracion(linea_fuente: str | None) -> str | None:
    if not linea_fuente:
        return None

    antes_asignacion = linea_fuente.split("=", 1)[0]
    m = re.search(r'\b(?P<variable>[A-Za-z_][A-Za-z0-9_]*)\s*$', antes_asignacion)
    if not m:
        return None

    variable = m.group("variable")
    if variable in _TIPOS_C:
        return None

    return variable


def _extraer_operando_dereferencia(linea_fuente: str | None) -> str | None:
    if not linea_fuente:
        return None

    coincidencia = re.search(
        r"\*\s*(?P<simbolo>[A-Za-z_][A-Za-z0-9_]*)\b",
        linea_fuente,
    )
    if coincidencia:
        return coincidencia.group("simbolo")
    return None


def _extraer_simbolo_especifico(
    tipo_error: str,
    mensaje: str,
    linea_fuente: str | None = None,
    funcion_contexto: str | None = None,
) -> str | None:
    patrones_por_tipo = {
        "uninitialized_variable": [
            re.compile(
                r"'(?P<simbolo>[^']+)'\s+(?:is|may be)\s+used uninitialized",
                re.IGNORECASE,
            ),
            re.compile(
                r"'(?P<simbolo>[^']+)'\s+is uninitialized",
                re.IGNORECASE,
            ),
        ],
        "struct_access": [
            re.compile(r"has no member named '(?P<simbolo>[^']+)'", re.IGNORECASE),
            re.compile(r"request for member '(?P<simbolo>[^']+)'", re.IGNORECASE),
        ],
        "preprocessor_error": [
            re.compile(
                r"(?P<simbolo>[^:\s]+):\s+No such file or directory",
                re.IGNORECASE,
            ),
        ],
        "format_mismatch": [
            re.compile(r"format '(?P<simbolo>[^']+)' expects", re.IGNORECASE),
            re.compile(r"format specifies type '(?P<simbolo>[^']+)'", re.IGNORECASE),
        ],
        "wrong_arguments": [
            re.compile(
                r"too (?:few|many) arguments? (?:to|for) (?:function )?"
                r"'(?P<simbolo>[^']+)'",
                re.IGNORECASE,
            ),
        ],
        "pointer_error": [
            re.compile(
                r"passing argument \d+ of '(?P<simbolo>[^']+)'",
                re.IGNORECASE,
            ),
        ],
    }

    if tipo_error in {"missing_return", "return_error"} and funcion_contexto:
        return funcion_contexto

    if tipo_error == "assignment_in_condition":
        return "="

    if tipo_error in {"type_mismatch", "dangerous_conversion"}:
        variable = _extraer_variable_de_declaracion(linea_fuente)
        if variable:
            return variable

    if tipo_error == "pointer_error":
        if re.search(
            r"invalid type argument of unary|dereferencing",
            mensaje,
            re.IGNORECASE,
        ):
            operando = _extraer_operando_dereferencia(linea_fuente)
            if operando:
                return operando

        variable = _extraer_variable_de_declaracion(linea_fuente)
        if variable:
            return variable

    for patron in patrones_por_tipo.get(tipo_error, []):
        coincidencia = patron.search(mensaje)
        if coincidencia:
            return coincidencia.group("simbolo")

    return None


def _tokenizar_linea(
    linea: str,
    linea_fuente: str | None = None,
    funcion_contexto: str | None = None,
) -> list[Token]:
    """Convierte una línea del stderr de GCC en una lista de tokens."""
    linea = linea.strip()
    if not linea:
        return []

    # Ignorar líneas de contexto como "4 |  printf(...)" o "  |  ^~~~~"
    if _PATRON_CONTEXTO.match(linea):
        return []

    # Ignorar líneas informativas de GCC
    if re.search(r'In function|In file included', linea):
        return []

    m = _PATRON_GCC.match(linea)
    if not m:
        return [Token(TokenType.DESCONOCIDO, linea)]

    severidad = m.group('severidad')
    if severidad == "fatal error":
        severidad = "error"

    tokens = [
        Token(TokenType.ARCHIVO,       m.group('archivo')),
        Token(TokenType.LINEA,         m.group('linea')),
        Token(TokenType.COLUMNA,       m.group('columna')),
        Token(TokenType.SEVERIDAD,     severidad),
        Token(TokenType.MENSAJE_CRUDO, m.group('mensaje')),
        Token(TokenType.TIPO_ERROR,    _clasificar_tipo(m.group('mensaje'))),
    ]

    tipo_error = tokens[-1].valor
    simbolo = _extraer_simbolo_especifico(
        tipo_error,
        m.group('mensaje'),
        linea_fuente,
        funcion_contexto,
    )

    if not simbolo:
        simbolo = _extraer_simbolo(m.group('mensaje'))

    if simbolo:
        tokens.append(Token(TokenType.SIMBOLO, simbolo))

    return tokens


class Lexer:
    """
    Recibe la ruta a un archivo .c, lo compila con GCC,
    captura el stderr automáticamente y lo tokeniza.
    """

    def __init__(self, ruta_archivo: str):
        self.ruta_archivo = Path(ruta_archivo)
        self.stderr_crudo: str = ""
        self.tokens: list[Token] = []
        self.compilado = False

    def compilar_y_capturar(self) -> str:
        """Ejecuta GCC sobre el archivo y devuelve el stderr completo."""
        try:
            with tempfile.TemporaryDirectory() as directorio_temporal:
                objeto_temporal = Path(directorio_temporal) / "salida.o"
                resultado = subprocess.run(
                    [
                        "gcc",
                        *OPCIONES_GCC,
                        str(self.ruta_archivo),
                        "-o",
                        str(objeto_temporal),
                    ],
                    capture_output=True,
                    text=True,
                    errors="replace",
                    timeout=TIEMPO_MAXIMO_GCC_SEGUNDOS,
                    env={**os.environ, "LC_ALL": "C", "LANG": "C"},  
                )
        except FileNotFoundError as exc:
            raise CompilerNotFoundError(
                "No se encontro GCC. Instalalo y verifica que 'gcc' este disponible en PATH."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise CompilerTimeoutError(
                f"GCC excedio el tiempo maximo de {TIEMPO_MAXIMO_GCC_SEGUNDOS} segundos."
            ) from exc
        except OSError as exc:
            raise CompilerExecutionError(
                f"No se pudo ejecutar GCC: {exc}"
            ) from exc

        self.stderr_crudo = resultado.stderr
        self.compilado = True
        return self.stderr_crudo

    def tokenizar(self) -> list[Token]:
        """
        Compila el archivo, captura el stderr y retorna
        la lista de tokens extraídos de todos los mensajes de error.
        """
        if not self.compilado:
            self.compilar_y_capturar()

        lineas_fuente = []
        if self.ruta_archivo.exists():
            try:
                lineas_fuente = self.ruta_archivo.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeError) as exc:
                raise SourceReadError(
                    f"No se pudo leer el archivo fuente '{self.ruta_archivo}': {exc}"
                ) from exc

        self.tokens = []
        funcion_contexto = None
        for linea in self.stderr_crudo.splitlines():
            coincidencia_funcion = re.search(
                r"In function ['\u2018](?P<funcion>[^'\u2019]+)['\u2019]:",
                linea,
            )
            if coincidencia_funcion:
                funcion_contexto = coincidencia_funcion.group("funcion")
                continue

            linea_fuente = None
            m = _PATRON_GCC.match(linea.strip())
            if m:
                numero_linea = int(m.group("linea"))
                if 1 <= numero_linea <= len(lineas_fuente):
                    linea_fuente = lineas_fuente[numero_linea - 1]

            self.tokens.extend(
                _tokenizar_linea(
                    linea,
                    linea_fuente,
                    funcion_contexto,
                )
            )

        return self.tokens

