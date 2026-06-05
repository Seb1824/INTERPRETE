from __future__ import annotations
from src.parser import DiagnosticEntry


def explain(entry):
    """Recibe un DiagnosticEntry y retorna dict con titulo, explicacion,
    causa_probable y sugerencia en español."""
    handler = _HANDLERS.get(entry.tipo_error, _explain_desconocido)
    return handler(entry)


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
    "desconocido": _explain_desconocido,
}