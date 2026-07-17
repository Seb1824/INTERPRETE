from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from src.parser import DiagnosticEntry


_TIPOS_C = (
    "char",
    "double",
    "float",
    "int",
    "long",
    "short",
    "signed",
    "unsigned",
    "void",
)

_PATRON_FUNCION = re.compile(
    rf"^\s*(?P<tipo>(?:{'|'.join(_TIPOS_C)})(?:\s+\w+)*)\s+"
    r"(?P<nombre>[A-Za-z_][A-Za-z0-9_]*)\s*\([^;]*\)\s*\{"
)
_PATRON_DECLARACION = re.compile(
    rf"\b(?:{'|'.join(_TIPOS_C)})(?:\s+(?:{'|'.join(_TIPOS_C)}))*\s+\*?\s*"
    r"(?P<nombre>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_PALABRAS_RESERVADAS = {
    "else",
    "for",
    "if",
    "return",
    "sizeof",
    "switch",
    "while",
}


@dataclass
class _Funcion:
    nombre: str
    tipo_retorno: str
    linea_inicio: int
    columna_inicio: int
    cuerpo: list[tuple[int, str]]


class SemanticAnalyzer:
    """Analisis semantico basico hecho por el proyecto, independiente de GCC."""

    def __init__(self, ruta_fuente: str):
        self.ruta_fuente = ruta_fuente

    def analizar(self) -> list[DiagnosticEntry]:
        lineas = Path(self.ruta_fuente).read_text(encoding="utf-8").splitlines()
        lineas_limpias = _limpiar_comentarios_y_cadenas(lineas)
        funciones = _extraer_funciones(lineas_limpias)

        diagnosticos: list[DiagnosticEntry] = []

        diagnosticos.extend(self._analizar_cabeceras(lineas, lineas_limpias))
        diagnosticos.extend(self._analizar_division_cero(lineas_limpias))

        for funcion in funciones:
            diagnosticos.extend(self._analizar_variables_no_usadas(funcion))
            diagnosticos.extend(self._analizar_retorno_faltante(funcion))
            diagnosticos.extend(self._analizar_tipo_main(funcion)) 

        return diagnosticos

    def _analizar_variables_no_usadas(self, funcion: _Funcion) -> list[DiagnosticEntry]:
        diagnosticos: list[DiagnosticEntry] = []

        for numero_linea, linea in funcion.cuerpo:
            declaracion = _PATRON_DECLARACION.search(linea)
            if not declaracion:
                continue

            variable = declaracion.group("nombre")
            if variable in _PALABRAS_RESERVADAS:
                continue

            resto_de_linea = linea[declaracion.end():]
            resto_de_cuerpo = "\n".join(
                contenido
                for n, contenido in funcion.cuerpo
                if n > numero_linea
            )
            usos = _contar_identificador(resto_de_linea, variable)
            usos += _contar_identificador(resto_de_cuerpo, variable)

            if usos == 0:
                diagnosticos.append(
                    DiagnosticEntry(
                        archivo=self.ruta_fuente,
                        linea=numero_linea,
                        columna=declaracion.start("nombre") + 1,
                        severidad="warning",
                        mensaje_crudo=(
                            f"analizador semantico: variable '{variable}' "
                            "declarada pero no utilizada"
                        ),
                        tipo_error="unused_variable",
                        simbolo=variable,
                        origen="semantico",
                    )
                )

        return diagnosticos

    def _analizar_retorno_faltante(self, funcion: _Funcion) -> list[DiagnosticEntry]:
        if funcion.tipo_retorno.strip() == "void":
            return []

        if _tiene_return_en_nivel_principal(funcion.cuerpo):
            return []

        return [
            DiagnosticEntry(
                archivo=self.ruta_fuente,
                linea=funcion.linea_inicio,
                columna=funcion.columna_inicio,
                severidad="warning",
                mensaje_crudo=(
                    f"analizador semantico: la funcion '{funcion.nombre}' "
                    "puede terminar sin retornar un valor"
                ),
                tipo_error="missing_return",
                simbolo=funcion.nombre,
                origen="semantico",
            )
        ]
    def _analizar_tipo_main(self, funcion: _Funcion) -> list[DiagnosticEntry]:
        if funcion.nombre == "main" and funcion.tipo_retorno.strip() == "void":
            return [
                DiagnosticEntry(
                    archivo=self.ruta_fuente,
                    linea=funcion.linea_inicio,
                    columna=funcion.columna_inicio,
                    severidad="warning",
                    mensaje_crudo=(
                        "analizador semantico: la funcion principal 'main' "
                        "deberia retornar 'int' en lugar de 'void'"
                    ),
                    tipo_error="return_error",
                    simbolo="main",
                    origen="semantico",
                )
            ]
        return []
    
    def _analizar_cabeceras(self, lineas: list[str], lineas_limpias: list[str]) -> list[DiagnosticEntry]:
        tiene_stdio = any(re.search(r'#include\s*[<"]stdio\.h[>"]', linea) for linea in lineas)
        
        if tiene_stdio:
            return []

        patron_io = re.compile(r'\b(printf|scanf)\b')
        for i, linea in enumerate(lineas_limpias):
            match = patron_io.search(linea)
            if match:
                simbolo_usado = match.group(1)
                return [
                    DiagnosticEntry(
                        archivo=self.ruta_fuente,
                        linea=i + 1,
                        columna=match.start(1) + 1,
                        severidad="error",
                        mensaje_crudo=(
                            f"analizador semantico: se uso '{simbolo_usado}' "
                            "sin incluir la biblioteca <stdio.h>"
                        ),
                        tipo_error="implicit_declaration", 
                        simbolo=simbolo_usado,
                        origen="semantico",
                    )
                ]
        return []
    
    def _analizar_division_cero(self, lineas_limpias: list[str]) -> list[DiagnosticEntry]:
        diagnosticos: list[DiagnosticEntry] = []
        patron_div_cero = re.compile(r'/\s*0(?:\.0+)?\b')

        for i, linea in enumerate(lineas_limpias):
            match = patron_div_cero.search(linea)
            if match:
                diagnosticos.append(
                    DiagnosticEntry(
                        archivo=self.ruta_fuente,
                        linea=i + 1,
                        columna=match.start() + 1,
                        severidad="warning",
                        mensaje_crudo=(
                            "analizador semantico: division directa por cero literal detectada"
                        ),
                        tipo_error="division_by_zero", 
                        simbolo="/",
                        origen="semantico",
                    )
                )
        return diagnosticos

def _limpiar_comentarios_y_cadenas(lineas: list[str]) -> list[str]:
    limpias: list[str] = []
    en_bloque = False

    for linea in lineas:
        resultado = ""
        i = 0
        while i < len(linea):
            if en_bloque:
                cierre = linea.find("*/", i)
                if cierre == -1:
                    break
                i = cierre + 2
                en_bloque = False
                continue

            if linea.startswith("/*", i):
                en_bloque = True
                i += 2
                continue

            if linea.startswith("//", i):
                break

            if linea[i] in {'"', "'"}:
                comilla = linea[i]
                resultado += " "
                i += 1
                while i < len(linea):
                    if linea[i] == "\\":
                        i += 2
                        continue
                    if linea[i] == comilla:
                        i += 1
                        break
                    i += 1
                continue

            resultado += linea[i]
            i += 1

        limpias.append(resultado)

    return limpias


def _extraer_funciones(lineas: list[str]) -> list[_Funcion]:
    funciones: list[_Funcion] = []
    i = 0

    while i < len(lineas):
        linea = lineas[i]
        m = _PATRON_FUNCION.search(linea)
        if not m:
            i += 1
            continue

        cuerpo: list[tuple[int, str]] = []
        balance = linea.count("{") - linea.count("}")
        j = i + 1

        while j < len(lineas) and balance > 0:
            cuerpo.append((j + 1, lineas[j]))
            balance += lineas[j].count("{") - lineas[j].count("}")
            j += 1

        funciones.append(
            _Funcion(
                nombre=m.group("nombre"),
                tipo_retorno=m.group("tipo").strip(),
                linea_inicio=i + 1,
                columna_inicio=m.start("nombre") + 1,
                cuerpo=cuerpo,
            )
        )
        i = j

    return funciones


def _contar_identificador(texto: str, identificador: str) -> int:
    return len(re.findall(rf"\b{re.escape(identificador)}\b", texto))


def _tiene_return_en_nivel_principal(cuerpo: list[tuple[int, str]]) -> bool:
    balance = 0

    for _, linea in cuerpo:
        contenido = linea.strip()
        if not contenido:
            continue

        if balance == 0 and contenido.startswith("return"):
            return True

        balance += contenido.count("{") - contenido.count("}")
        balance = max(balance, 0)

    return False
