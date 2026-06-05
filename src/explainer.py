from __future__ import annotations
from src.parser import DiagnosticEntry


def explain(entry):
    """Recibe un DiagnosticEntry y retorna dict con titulo, explicacion,
    causa_probable y sugerencia en español."""
    handler = _HANDLERS.get(entry.tipo_error, _explain_desconocido)
    return handler(entry)


def _explain_undeclared(entry):
    simbolo = entry.simbolo or "desconocido"
    return {
        "titulo": f"Variable o función '{simbolo}' no declarada",
        "explicacion": (
            f"El compilador encontró el nombre '{simbolo}' en tu código "
            f"pero no sabe qué es, porque nunca fue declarado antes de usarlo. "
            f"En C, todo identificador debe presentarse al compilador antes de usarlo."
        ),
        "causa_probable": (
            f"Olvidaste declarar '{simbolo}', lo escribiste diferente "
            f"(C distingue mayúsculas de minúsculas), o falta el #include "
            f"que lo define."
        ),
        "sugerencia": (
            f"Busca dónde usas '{simbolo}' (línea {entry.linea}) y asegúrate "
            f"de haberlo declarado antes. Si es de biblioteca, revisa el #include."
        ),
    }


def _explain_implicit_declaration(entry):
    simbolo = entry.simbolo or "la función"
    return {
        "titulo": f"Declaración implícita de la función '{simbolo}'",
        "explicacion": (
            f"Estás llamando a '{simbolo}' sin haberla declarado previamente. "
            f"En C moderno esto es un error: el compilador no puede asumir "
            f"cómo está definida una función que no conoce."
        ),
        "causa_probable": (
            f"Falta el #include con el prototipo de '{simbolo}'. "
            f"O la definiste después de donde la llamas, sin declarar su prototipo antes."
        ),
        "sugerencia": (
            f"Agrega el #include correcto al inicio del archivo. Si es tuya, "
            f"agrega su prototipo antes de main(): por ejemplo, int {simbolo}(int x);"
        ),
    }


def _explain_redeclaration(entry):
    simbolo = entry.simbolo or "el identificador"
    return {
        "titulo": f"'{simbolo}' declarado más de una vez",
        "explicacion": (
            f"'{simbolo}' aparece declarado dos veces en el mismo ámbito. "
            f"En C no puedes tener dos variables o funciones con el mismo "
            f"nombre en el mismo nivel de visibilidad."
        ),
        "causa_probable": (
            f"Copiaste y pegaste una declaración por error, o incluyes dos veces "
            f"el mismo archivo de cabecera sin guardas de inclusión (#ifndef)."
        ),
        "sugerencia": (
            f"Busca todas las declaraciones de '{simbolo}' y elimina la duplicada. "
            f"La línea {entry.linea} es la que el compilador marca como redeclaración."
        ),
    }


def _explain_expected_token(entry):
    simbolo = entry.simbolo or "un símbolo de puntuación"
    return {
        "titulo": f"Se esperaba '{simbolo}' pero no se encontró",
        "explicacion": (
            f"El compilador llegó a la línea {entry.linea} esperando encontrar "
            f"'{simbolo}', pero encontró otra cosa. Esto rompe la gramática de C, "
            f"como si en una oración faltara un punto o una coma donde se requería."
        ),
        "causa_probable": (
            f"Olvidar un punto y coma (;) al final de una instrucción, "
            f"no cerrar un paréntesis o una llave, o escribir una expresión incompleta. "
            f"A veces el error real está una línea antes de donde el compilador lo reporta."
        ),
        "sugerencia": (
            f"Revisa la línea {entry.linea} y la anterior. "
            f"¿Falta un ';'? ¿Hay paréntesis o llaves sin cerrar? "
            f"Contar los '(' y ')' puede ayudarte a encontrar el desbalance."
        ),
    }


def _explain_type_mismatch(entry):
    simbolo = entry.simbolo or "una variable"
    return {
        "titulo": f"Tipos de datos incompatibles en '{simbolo}'",
        "explicacion": (
            f"Estás intentando mezclar o asignar valores de tipos incompatibles. "
            f"En C cada valor tiene un tipo (int, float, char, puntero, etc.) "
            f"y no todos pueden combinarse sin una conversión explícita."
        ),
        "causa_probable": (
            f"Asignar un puntero a una variable entera, mezclar tipos en una "
            f"operación aritmética sin cast, pasar un argumento del tipo equivocado, "
            f"o retornar un tipo distinto al declarado en la función."
        ),
        "sugerencia": (
            f"Revisa la línea {entry.linea} e identifica el tipo de cada valor. "
            f"Si la conversión es intencional usa un cast explícito: (int) o (float). "
            f"Si no, corrige la declaración de '{simbolo}' para que coincida."
        ),
    }


def _explain_desconocido(entry):
    mensaje = entry.mensaje_crudo or "Sin mensaje disponible."
    ubicacion = f"línea {entry.linea}" if entry.linea else "ubicación desconocida"
    return {
        "titulo": "Error de compilación no clasificado",
        "explicacion": (
            f"El compilador reportó un problema en {ubicacion} que este "
            f"sistema aún no tiene clasificado. "
            f"Mensaje original: \"{mensaje}\""
        ),
        "causa_probable": (
            "Lee el mensaje original con calma: GCC suele indicar "
            "qué nombre o construcción le resulta problemática."
        ),
        "sugerencia": (
            f"Busca el mensaje en cppreference.com o Stack Overflow, "
            f"o muéstraselo a tu docente junto con el código en la línea {entry.linea}."
        ),
    }


# Tabla de despacho: tipo_error -> handler. Fallback: _explain_desconocido
_HANDLERS = {
    "undeclared":           _explain_undeclared,
    "implicit_declaration": _explain_implicit_declaration,
    "redeclaration":        _explain_redeclaration,
    "expected_token":       _explain_expected_token,
    "type_mismatch":        _explain_type_mismatch,
    "desconocido":          _explain_desconocido,
}