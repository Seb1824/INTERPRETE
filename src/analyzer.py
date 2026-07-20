from __future__ import annotations

import os
from dataclasses import dataclass

from src.ast_builder import SourceASTNode
from src.lexer import Lexer
from src.parser import DiagnosticEntry, Parser
from src.semantic import SemanticAnalyzer
from src.symbol_table import SymbolTable
from src.token import Token


@dataclass
class AnalysisResult:
    ruta_archivo: str
    stderr: str
    tokens: list[Token]
    diagnosticos_gcc: list[DiagnosticEntry]
    diagnosticos_semanticos: list[DiagnosticEntry]
    diagnosticos: list[DiagnosticEntry]
    ast_codigo: SourceASTNode | None
    error_ast: str | None
    tabla_simbolos: SymbolTable | None


def analizar_archivo(ruta_archivo: str) -> AnalysisResult:
    """Ejecuta el pipeline completo y devuelve sus resultados estructurados."""
    lexer = Lexer(ruta_archivo)
    stderr = lexer.compilar_y_capturar()
    tokens = lexer.tokenizar()

    diagnosticos_gcc = Parser(tokens).parse()
    analizador_semantico = SemanticAnalyzer(ruta_archivo)
    diagnosticos_semanticos = analizador_semantico.analizar()
    diagnosticos = combinar_diagnosticos(
        diagnosticos_gcc,
        diagnosticos_semanticos,
    )

    return AnalysisResult(
        ruta_archivo=ruta_archivo,
        stderr=stderr,
        tokens=tokens,
        diagnosticos_gcc=diagnosticos_gcc,
        diagnosticos_semanticos=diagnosticos_semanticos,
        diagnosticos=diagnosticos,
        ast_codigo=analizador_semantico.ast_codigo,
        error_ast=analizador_semantico.error_ast,
        tabla_simbolos=analizador_semantico.tabla_simbolos,
    )


def combinar_diagnosticos(
    diagnosticos_gcc: list[DiagnosticEntry],
    diagnosticos_semanticos: list[DiagnosticEntry],
) -> list[DiagnosticEntry]:
    """Filtra redundancias internas de GCC y agrega diagnosticos semanticos."""
    gcc_dict = {}
    for diagnostico in diagnosticos_gcc:
        clave = (
            diagnostico.linea,
            diagnostico.columna,
            diagnostico.simbolo,
            diagnostico.tipo_error,
        )

        if clave not in gcc_dict:
            gcc_dict[clave] = diagnostico
            continue

        existente = gcc_dict[clave]
        if (
            diagnostico.severidad == "error"
            and existente.severidad == "warning"
        ):
            gcc_dict[clave] = diagnostico

    gcc_limpios = list(gcc_dict.values())
    combinados = list(gcc_limpios)

    for semantico in diagnosticos_semanticos:
        duplicado = any(
            _diagnosticos_equivalentes(existente, semantico)
            for existente in gcc_limpios
        )
        if not duplicado:
            combinados.append(semantico)

    return combinados


def _diagnosticos_equivalentes(
    diagnostico_gcc: DiagnosticEntry,
    diagnostico_semantico: DiagnosticEntry,
) -> bool:
    if not _misma_ruta(diagnostico_gcc.archivo, diagnostico_semantico.archivo):
        return False

    mismo_simbolo = (
        not diagnostico_gcc.simbolo
        or not diagnostico_semantico.simbolo
        or diagnostico_gcc.simbolo == diagnostico_semantico.simbolo
    )
    misma_linea = diagnostico_gcc.linea == diagnostico_semantico.linea

    if diagnostico_gcc.tipo_error == diagnostico_semantico.tipo_error:
        return (misma_linea and mismo_simbolo) or (
            diagnostico_semantico.tipo_error
            in {"missing_return", "return_error"}
            and diagnostico_semantico.simbolo
            and diagnostico_gcc.simbolo == diagnostico_semantico.simbolo
        )

    categorias_argumento_gcc = {
        "dangerous_conversion",
        "pointer_error",
        "type_mismatch",
        "wrong_arguments",
    }
    return (
        diagnostico_semantico.tipo_error == "wrong_arguments"
        and diagnostico_gcc.tipo_error in categorias_argumento_gcc
        and misma_linea
        and mismo_simbolo
    )


def _misma_ruta(primera: str, segunda: str) -> bool:
    primera_normalizada = os.path.normcase(os.path.normpath(primera))
    segunda_normalizada = os.path.normcase(os.path.normpath(segunda))
    return primera_normalizada == segunda_normalizada
