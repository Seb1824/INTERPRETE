from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ASTBuildError(RuntimeError):
    """Error controlado al construir el AST del codigo C."""


class ASTDependencyError(ASTBuildError):
    """La dependencia necesaria para construir el AST no esta disponible."""


class ASTParseError(ASTBuildError):
    """El codigo fuente no pudo convertirse en un AST completo."""


class ASTSourceReadError(ASTBuildError):
    """El archivo fuente no pudo leerse."""


@dataclass
class SourceASTNode:
    tipo: str
    valor: str | None = None
    atributos: dict[str, str] = field(default_factory=dict)
    rol: str | None = None
    linea: int | None = None
    columna: int | None = None
    hijos: list["SourceASTNode"] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "tipo": self.tipo,
            "valor": self.valor,
            "atributos": self.atributos,
            "rol": self.rol,
            "linea": self.linea,
            "columna": self.columna,
            "hijos": [hijo.to_dict() for hijo in self.hijos],
        }

    def render(self, nivel: int = 0) -> list[str]:
        sangria = "  " * nivel
        etiqueta = self.tipo

        if self.rol:
            etiqueta = f"{self.rol}: {etiqueta}"
        if self.valor:
            etiqueta += f" ({self.valor})"
        if self.linea is not None:
            ubicacion = f"linea {self.linea}"
            if self.columna is not None:
                ubicacion += f", columna {self.columna}"
            etiqueta += f" [{ubicacion}]"

        lineas = [f"{sangria}- {etiqueta}"]
        for hijo in self.hijos:
            lineas.extend(hijo.render(nivel + 1))
        return lineas


def construir_ast_codigo(ruta_fuente: str) -> SourceASTNode:
    """Construye un AST real del codigo C mediante pycparser."""
    try:
        from pycparser import c_parser, plyparser
    except ImportError as exc:
        raise ASTDependencyError(
            "No se encontro pycparser. Instala las dependencias con "
            "'python -m pip install -r requirements.txt'."
        ) from exc

    ruta = Path(ruta_fuente)
    try:
        codigo = ruta.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ASTSourceReadError(
            f"No se pudo leer el archivo fuente '{ruta}': {exc}"
        ) from exc

    codigo_preparado = _preparar_codigo_para_parser(codigo)
    parser = c_parser.CParser()

    try:
        raiz_pycparser = parser.parse(codigo_preparado, filename=str(ruta))
    except plyparser.ParseError as exc:
        raise ASTParseError(
            f"No se pudo construir el AST completo: {exc}"
        ) from exc

    return _convertir_nodo(raiz_pycparser)


def _convertir_nodo(nodo: Any, rol: str | None = None) -> SourceASTNode:
    coordenada = getattr(nodo, "coord", None)
    atributos = _extraer_atributos(nodo)
    convertido = SourceASTNode(
        tipo=type(nodo).__name__,
        valor=_describir_atributos(atributos),
        atributos=atributos,
        rol=rol,
        linea=getattr(coordenada, "line", None),
        columna=getattr(coordenada, "column", None),
    )

    for rol_hijo, hijo in nodo.children():
        convertido.hijos.append(_convertir_nodo(hijo, rol_hijo))

    return convertido


def _extraer_atributos(nodo: Any) -> dict[str, str]:
    atributos = {}
    for nombre in getattr(nodo, "attr_names", ()):
        valor = getattr(nodo, nombre, None)
        if valor is None or valor == [] or valor == ():
            continue
        if isinstance(valor, (list, tuple)):
            valor = " ".join(str(elemento) for elemento in valor)
        atributos[nombre] = str(valor)

    return atributos


def _describir_atributos(atributos: dict[str, str]) -> str | None:
    partes = [f"{nombre}={valor}" for nombre, valor in atributos.items()]
    return ", ".join(partes) or None


def _preparar_codigo_para_parser(codigo: str) -> str:
    sin_comentarios = limpiar_comentarios_codigo(codigo)
    return _reemplazar_directivas_por_espacios(sin_comentarios)


def limpiar_comentarios_codigo(codigo: str) -> str:
    """Reemplaza comentarios por espacios sin alterar lineas ni columnas."""
    resultado = list(codigo)
    i = 0
    estado = "codigo"

    while i < len(codigo):
        actual = codigo[i]
        siguiente = codigo[i + 1] if i + 1 < len(codigo) else ""

        if estado == "codigo":
            if actual == '"':
                estado = "cadena"
            elif actual == "'":
                estado = "caracter"
            elif actual == "/" and siguiente == "/":
                resultado[i] = " "
                resultado[i + 1] = " "
                estado = "comentario_linea"
                i += 1
            elif actual == "/" and siguiente == "*":
                resultado[i] = " "
                resultado[i + 1] = " "
                estado = "comentario_bloque"
                i += 1
        elif estado == "cadena":
            if actual == "\\":
                i += 1
            elif actual == '"':
                estado = "codigo"
        elif estado == "caracter":
            if actual == "\\":
                i += 1
            elif actual == "'":
                estado = "codigo"
        elif estado == "comentario_linea":
            if actual in "\r\n":
                estado = "codigo"
            else:
                resultado[i] = " "
        elif estado == "comentario_bloque":
            if actual == "*" and siguiente == "/":
                resultado[i] = " "
                resultado[i + 1] = " "
                estado = "codigo"
                i += 1
            elif actual not in "\r\n":
                resultado[i] = " "

        i += 1

    return "".join(resultado)


def _reemplazar_directivas_por_espacios(codigo: str) -> str:
    resultado = []
    continuacion = False

    for linea in codigo.splitlines(keepends=True):
        contenido = linea.rstrip("\r\n")
        salto = linea[len(contenido):]
        es_directiva = continuacion or contenido.lstrip().startswith("#")

        if es_directiva:
            resultado.append(" " * len(contenido) + salto)
            continuacion = contenido.rstrip().endswith("\\")
        else:
            resultado.append(linea)
            continuacion = False

    return "".join(resultado)
