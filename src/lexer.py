import re
import subprocess
from pathlib import Path
from src.token import Token, TokenType

TIEMPO_MAXIMO_GCC_SEGUNDOS = 10
OPCIONES_GCC = [
    "-Wall",
    "-Wextra",
    "-Wconversion",
    "-fsyntax-only",
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
    r'^(?P<archivo>[A-Za-z]:[/\\][^:]+\.c|[^:]+\.c):(?P<linea>\d+):(?P<columna>\d+):\s*(?P<severidad>fatal error|error|warning|note):\s*(?P<mensaje>.+)$'
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
            r"missing terminating|expected .?[})\]].? before",
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
        m = patron.search(mensaje)
        if m and m.group('simbolo') not in _TIPOS_C:
            return m.group('simbolo')
    return None


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


def _tokenizar_linea(linea: str, linea_fuente: str | None = None) -> list[Token]:
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
    simbolo = None
    if tipo_error == "type_mismatch":
        simbolo = _extraer_variable_de_declaracion(linea_fuente)

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
            resultado = subprocess.run(
                ["gcc", *OPCIONES_GCC, str(self.ruta_archivo)],
                capture_output=True,
                text=True,
                errors="replace",
                timeout=TIEMPO_MAXIMO_GCC_SEGUNDOS,
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
        for linea in self.stderr_crudo.splitlines():
            linea_fuente = None
            m = _PATRON_GCC.match(linea.strip())
            if m:
                numero_linea = int(m.group("linea"))
                if 1 <= numero_linea <= len(lineas_fuente):
                    linea_fuente = lineas_fuente[numero_linea - 1]

            self.tokens.extend(_tokenizar_linea(linea, linea_fuente))

        return self.tokens

