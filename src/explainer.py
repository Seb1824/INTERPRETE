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
    "desconocido":          _explain_desconocido,
}