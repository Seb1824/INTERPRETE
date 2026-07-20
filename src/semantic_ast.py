from __future__ import annotations

import re

from src.ast_builder import SourceASTNode, limpiar_comentarios_codigo
from src.parser import DiagnosticEntry
from src.symbol_table import (
    Scope,
    Symbol,
    SymbolTable,
    construir_tabla_simbolos,
    describir_tipo,
)


_PATRON_INCLUDE_STDIO = re.compile(r'#include\s*[<"]stdio\.h[>"]')
_FUNCIONES_STDIO = {
    "fgets",
    "fputs",
    "getchar",
    "printf",
    "putchar",
    "puts",
    "scanf",
}
_NODOS_CON_CONDICION = {"If", "While", "DoWhile", "For"}


class ASTSemanticAnalyzer:
    """Aplica reglas semanticas recorriendo el AST del programa C."""

    def __init__(
        self,
        ruta_fuente: str,
        codigo_fuente: str,
        ast_codigo: SourceASTNode,
    ):
        self.ruta_fuente = ruta_fuente
        self.codigo_fuente = codigo_fuente
        self.lineas = codigo_fuente.splitlines()
        self.ast_codigo = ast_codigo
        self.codigo_sin_comentarios = limpiar_comentarios_codigo(codigo_fuente)
        self.tiene_stdio = bool(
            _PATRON_INCLUDE_STDIO.search(self.codigo_sin_comentarios)
        )
        self.tabla_simbolos = construir_tabla_simbolos(ast_codigo)

    def analizar(self) -> list[DiagnosticEntry]:
        diagnosticos = []
        diagnosticos.extend(self._analizar_cabeceras())
        diagnosticos.extend(self._analizar_redeclaraciones())
        diagnosticos.extend(self._analizar_usos_no_resueltos())
        diagnosticos.extend(self._analizar_division_cero())
        diagnosticos.extend(self._analizar_asignaciones_en_condiciones())
        diagnosticos.extend(self._analizar_simbolos_no_usados())
        diagnosticos.extend(self._analizar_tipos_asignacion())
        diagnosticos.extend(self._analizar_argumentos_llamadas())
        diagnosticos.extend(self._analizar_variables_no_inicializadas())

        for funcion in _buscar_nodos(self.ast_codigo, "FuncDef"):
            diagnosticos.extend(self._analizar_retorno_faltante(funcion))
            diagnosticos.extend(self._analizar_tipo_main(funcion))
            diagnosticos.extend(self._analizar_tipo_retorno(funcion))  


        return diagnosticos

    def _analizar_cabeceras(self) -> list[DiagnosticEntry]:
        if self.tiene_stdio:
            return []

        for llamada in _buscar_nodos(self.ast_codigo, "FuncCall"):
            nombre = _nombre_funcion_llamada(llamada)
            if nombre not in _FUNCIONES_STDIO:
                continue

            return [
                self._crear_diagnostico(
                    nodo=llamada,
                    severidad="error",
                    mensaje=(
                        f"analizador semantico AST: se uso '{nombre}' "
                        "sin incluir la biblioteca <stdio.h>"
                    ),
                    tipo_error="implicit_declaration",
                    simbolo=nombre,
                )
            ]

        return []

    def _analizar_redeclaraciones(self) -> list[DiagnosticEntry]:
        diagnosticos = []

        for redeclaracion in self.tabla_simbolos.redeclaraciones:
            diagnosticos.append(
                DiagnosticEntry(
                    archivo=self.ruta_fuente,
                    linea=redeclaracion.linea_redeclaracion,
                    columna=redeclaracion.columna_redeclaracion,
                    severidad="error",
                    mensaje_crudo=(
                        f"analizador semantico AST: '{redeclaracion.nombre}' "
                        "se declaro mas de una vez en el mismo ambito; "
                        "la declaracion original esta en la linea "
                        f"{redeclaracion.linea_original}"
                    ),
                    tipo_error="redeclaration",
                    simbolo=redeclaracion.nombre,
                    origen="semantico",
                )
            )

        return diagnosticos

    def _analizar_usos_no_resueltos(self) -> list[DiagnosticEntry]:
        diagnosticos = []

        for uso in self.tabla_simbolos.usos_no_resueltos:
            if uso.nombre in _FUNCIONES_STDIO:
                continue

            diagnosticos.append(
                DiagnosticEntry(
                    archivo=self.ruta_fuente,
                    linea=uso.linea,
                    columna=uso.columna,
                    severidad="error",
                    mensaje_crudo=(
                        f"analizador semantico AST: el identificador "
                        f"'{uso.nombre}' se uso sin una declaracion visible "
                        "en este ambito"
                    ),
                    tipo_error="undeclared",
                    simbolo=uso.nombre,
                    origen="semantico",
                )
            )

        return diagnosticos

    def _analizar_division_cero(self) -> list[DiagnosticEntry]:
        diagnosticos = []

        for operacion in _buscar_nodos(self.ast_codigo, "BinaryOp"):
            if operacion.atributos.get("op") != "/":
                continue

            divisor = _hijo_por_rol(operacion, "right")
            if divisor is None or _evaluar_constante(divisor) != 0:
                continue

            diagnosticos.append(
                self._crear_diagnostico(
                    nodo=operacion,
                    severidad="warning",
                    mensaje=(
                        "analizador semantico AST: division por una expresion "
                        "constante igual a cero"
                    ),
                    tipo_error="division_by_zero",
                    simbolo="/",
                    columna=_buscar_columna_operador(operacion, "/", self.lineas),
                )
            )

        return diagnosticos

    def _analizar_asignaciones_en_condiciones(self) -> list[DiagnosticEntry]:
        diagnosticos = []
        ubicaciones_reportadas = set()

        for control in _recorrer(self.ast_codigo):
            if control.tipo not in _NODOS_CON_CONDICION:
                continue

            condicion = _hijo_por_rol(control, "cond")
            if condicion is None:
                continue

            for asignacion in _buscar_nodos(condicion, "Assignment"):
                if asignacion.atributos.get("op") != "=":
                    continue

                clave = (asignacion.linea, asignacion.columna)
                if clave in ubicaciones_reportadas:
                    continue
                ubicaciones_reportadas.add(clave)

                diagnosticos.append(
                    self._crear_diagnostico(
                        nodo=asignacion,
                        severidad="warning",
                        mensaje=(
                            "analizador semantico AST: posible asignacion '=' "
                            "en lugar de comparacion '=='"
                        ),
                        tipo_error="assignment_in_condition",
                        simbolo="=",
                        columna=_buscar_columna_operador(
                            asignacion,
                            "=",
                            self.lineas,
                        ),
                    )
                )

        return diagnosticos

    def _analizar_simbolos_no_usados(self) -> list[DiagnosticEntry]:
        diagnosticos = []
        for simbolo in self.tabla_simbolos.todos_los_simbolos():
            if simbolo.clase not in {"variable", "parametro"}:
                continue

            ambito = self.tabla_simbolos.buscar_ambito(simbolo.ambito_id)
            if ambito is None or ambito.clase == "global":
                continue
            if simbolo.cantidad_usos > 0:
                continue

            descripcion = (
                "parametro"
                if simbolo.clase == "parametro"
                else "variable"
            )

            diagnosticos.append(
                self._crear_diagnostico_simbolo(
                    simbolo=simbolo,
                    severidad="warning",
                    mensaje=(
                        f"analizador semantico AST: {descripcion} "
                        f"'{simbolo.nombre}' declarado pero no utilizado"
                    ),
                    tipo_error="unused_variable",
                )
            )

        return diagnosticos
    
    def _analizar_tipos_asignacion(self) -> list[DiagnosticEntry]:
        diagnosticos = []
        reportados: set[tuple] = set()

        for decl in _buscar_nodos(self.ast_codigo, "Decl"):
            nombre = decl.atributos.get("name")
            if not nombre:
                continue

            init = _hijo_por_rol(decl, "init")
            if init is None:
                continue

            tipo_decl = _hijo_por_rol(decl, "type")
            tipo_izquierdo = _describir_tipo_nodo(tipo_decl)
            tipo_derecho = _inferir_tipo_expresion(
                init,
                self.tabla_simbolos,
                self._ambito_en_linea(decl.linea or 1),
            )

            if tipo_izquierdo is None or tipo_derecho is None:
                continue
            diagnostico = self._diagnostico_conversion(
                nodo=decl,
                expresion=init,
                tipo_destino=tipo_izquierdo,
                tipo_origen=tipo_derecho,
                simbolo=nombre,
                contexto="inicializacion",
            )
            if diagnostico is not None:
                clave = (decl.linea, decl.columna, nombre)
                if clave not in reportados:
                    reportados.add(clave)
                    diagnosticos.append(diagnostico)

        for asignacion in _buscar_nodos(self.ast_codigo, "Assignment"):
            if asignacion.atributos.get("op") != "=":
                continue

            lvalue = _hijo_por_rol(asignacion, "lvalue")
            rvalue = _hijo_por_rol(asignacion, "rvalue")
            if lvalue is None or rvalue is None:
                continue

            ambito = self._ambito_en_linea(asignacion.linea or 1)
            nombre = _nombre_expresion(lvalue) or "expresion"
            tipo_izquierdo = _inferir_tipo_expresion(
                lvalue,
                self.tabla_simbolos,
                ambito,
            )
            tipo_derecho = _inferir_tipo_expresion(
                rvalue,
                self.tabla_simbolos,
                ambito,
            )

            if tipo_izquierdo is None or tipo_derecho is None:
                continue
            diagnostico = self._diagnostico_conversion(
                nodo=asignacion,
                expresion=rvalue,
                tipo_destino=tipo_izquierdo,
                tipo_origen=tipo_derecho,
                simbolo=nombre,
                contexto="asignacion",
            )
            if diagnostico is not None:
                clave = (asignacion.linea, asignacion.columna, nombre)
                if clave not in reportados:
                    reportados.add(clave)
                    diagnosticos.append(diagnostico)

        return diagnosticos

    def _diagnostico_conversion(
        self,
        nodo: SourceASTNode,
        expresion: SourceASTNode,
        tipo_destino: str,
        tipo_origen: str,
        simbolo: str,
        contexto: str,
    ) -> DiagnosticEntry | None:
        destino = _resolver_alias_tipo(tipo_destino, self.tabla_simbolos)
        origen = _resolver_alias_tipo(tipo_origen, self.tabla_simbolos)

        if not _tipos_compatibles(destino, origen):
            return self._crear_diagnostico(
                nodo=nodo,
                severidad="warning",
                mensaje=(
                    f"analizador semantico AST: {contexto} de "
                    f"'{simbolo}' ({tipo_destino}) con un valor de "
                    f"tipo incompatible ({tipo_origen})"
                ),
                tipo_error="type_mismatch",
                simbolo=simbolo,
            )

        if _es_conversion_peligrosa(destino, origen, expresion):
            return self._crear_diagnostico(
                nodo=nodo,
                severidad="warning",
                mensaje=(
                    f"analizador semantico AST: {contexto} de "
                    f"'{simbolo}' convierte de '{tipo_origen}' a "
                    f"'{tipo_destino}' y puede perder informacion"
                ),
                tipo_error="dangerous_conversion",
                simbolo=simbolo,
            )

        return None
    
    def _analizar_argumentos_llamadas(self) -> list[DiagnosticEntry]:
        diagnosticos = []

        for llamada in _buscar_nodos(self.ast_codigo, "FuncCall"):
            ambito = self._ambito_en_linea(llamada.linea or 1)
            firma = _resolver_firma_llamada(
                llamada,
                self.tabla_simbolos,
                ambito,
            )
            if firma is None:
                continue
            nombre, tipos_parametros, firma_definida, es_variadica = firma
            if not firma_definida:
                continue

            args = _hijo_por_rol(llamada, "args")
            argumentos = args.hijos if args is not None else []
            cantidad_real = len(argumentos)
            cantidad_esperada = len(tipos_parametros)

            cantidad_invalida = (
                cantidad_real < cantidad_esperada
                if es_variadica
                else cantidad_real != cantidad_esperada
            )
            if cantidad_invalida:
                diagnosticos.append(
                    self._crear_diagnostico(
                        nodo=llamada,
                        severidad="error",
                        mensaje=(
                            f"analizador semantico AST: la funcion '{nombre}' "
                            f"espera {cantidad_esperada} argumento(s) "
                            f"pero se le paso {cantidad_real}"
                        ),
                        tipo_error="wrong_arguments",
                        simbolo=nombre,
                    )
                )
                continue

            for posicion, (argumento, tipo_esperado) in enumerate(
                zip(argumentos, tipos_parametros),
                start=1,
            ):
                tipo_real = _inferir_tipo_expresion(
                    argumento,
                    self.tabla_simbolos,
                    ambito,
                )
                if tipo_real is None:
                    continue
                tipo_esperado_resuelto = _resolver_alias_tipo(
                    tipo_esperado,
                    self.tabla_simbolos,
                )
                tipo_real_resuelto = _resolver_alias_tipo(
                    tipo_real,
                    self.tabla_simbolos,
                )
                if _tipos_compatibles(
                    tipo_esperado_resuelto,
                    tipo_real_resuelto,
                ):
                    if _es_conversion_peligrosa(
                        tipo_esperado_resuelto,
                        tipo_real_resuelto,
                        argumento,
                    ):
                        diagnosticos.append(
                            self._crear_diagnostico(
                                nodo=argumento,
                                severidad="warning",
                                mensaje=(
                                    f"analizador semantico AST: el argumento "
                                    f"{posicion} de '{nombre}' convierte de "
                                    f"'{tipo_real}' a '{tipo_esperado}' y "
                                    "puede perder informacion"
                                ),
                                tipo_error="dangerous_conversion",
                                simbolo=nombre,
                            )
                        )
                    continue

                descripcion_esperada = _describir_tipo_resuelto(
                    tipo_esperado,
                    tipo_esperado_resuelto,
                )
                descripcion_real = _describir_tipo_resuelto(
                    tipo_real,
                    tipo_real_resuelto,
                )

                diagnosticos.append(
                    self._crear_diagnostico(
                        nodo=argumento,
                        severidad="warning",
                        mensaje=(
                            f"analizador semantico AST: el argumento "
                            f"{posicion} de '{nombre}' espera "
                            f"'{descripcion_esperada}' pero recibio "
                            f"'{descripcion_real}'"
                        ),
                        tipo_error="wrong_arguments",
                        simbolo=nombre,
                    )
                )

        return diagnosticos
    
    def _analizar_variables_no_inicializadas(self) -> list[DiagnosticEntry]:
        diagnosticos = []

        for funcion in _buscar_nodos(self.ast_codigo, "FuncDef"):
            cuerpo = _hijo_por_rol(funcion, "body")
            if cuerpo is None:
                continue

            for decl in _buscar_nodos(cuerpo, "Decl"):
                nombre = decl.atributos.get("name")
                if not nombre:
                    continue

                if _hijo_por_rol(decl, "init") is not None:
                    continue

                tipo = _hijo_por_rol(decl, "type")
                if tipo is not None and tipo.tipo in {"FuncDecl", "PtrDecl"}:
                    continue

                for uso in _buscar_nodos(cuerpo, "ID"):
                    if uso.atributos.get("name") != nombre:
                        continue
                    if uso.linea is None or decl.linea is None:
                        continue
                    if uso.linea <= decl.linea:
                        continue

                    asignada = False
                    for asignacion in _buscar_nodos(cuerpo, "Assignment"):
                        lvalue = _hijo_por_rol(asignacion, "lvalue")
                        if lvalue is None:
                            continue
                        if lvalue.atributos.get("name") != nombre:
                            continue
                        if asignacion.linea is None:
                            continue
                        if asignacion.linea < uso.linea:
                            asignada = True
                            break

                    if not asignada:
                        diagnosticos.append(
                            self._crear_diagnostico(
                                nodo=uso,
                                severidad="warning",
                                mensaje=(
                                    f"analizador semantico AST: '{nombre}' "
                                    f"puede usarse sin haber sido inicializada"
                                ),
                                tipo_error="uninitialized_variable",
                                simbolo=nombre,
                            )
                        )
                        break  

        return diagnosticos

    def _ambito_en_linea(self, linea: int):
        mejor = self.tabla_simbolos.ambito_global
        for ambito in self.tabla_simbolos.todos_los_ambitos():
            if ambito.linea_inicio <= linea:
                if ambito.linea_inicio > mejor.linea_inicio:
                    mejor = ambito
        return mejor

    def _crear_diagnostico_simbolo(
        self,
        simbolo: Symbol,
        severidad: str,
        mensaje: str,
        tipo_error: str,
    ) -> DiagnosticEntry:
        return DiagnosticEntry(
            archivo=self.ruta_fuente,
            linea=simbolo.linea_declaracion,
            columna=simbolo.columna_declaracion,
            severidad=severidad,
            mensaje_crudo=mensaje,
            tipo_error=tipo_error,
            simbolo=simbolo.nombre,
            origen="semantico",
        )

    def _analizar_retorno_faltante(
        self,
        funcion: SourceASTNode,
    ) -> list[DiagnosticEntry]:
        tipo_retorno = _tipo_retorno_funcion(funcion)
        if not tipo_retorno or tipo_retorno == "void":
            return []

        cuerpo = _hijo_por_rol(funcion, "body")
        if cuerpo is not None and _siempre_retorna(cuerpo):
            return []

        nombre, declaracion = _nombre_y_declaracion_funcion(funcion)
        return [
            self._crear_diagnostico(
                nodo=declaracion or funcion,
                severidad="warning",
                mensaje=(
                    f"analizador semantico AST: la funcion '{nombre}' "
                    "puede terminar sin retornar un valor"
                ),
                tipo_error="missing_return",
                simbolo=nombre,
            )
        ]

    def _analizar_tipo_main(
        self,
        funcion: SourceASTNode,
    ) -> list[DiagnosticEntry]:
        nombre, declaracion = _nombre_y_declaracion_funcion(funcion)
        if nombre != "main" or _tipo_retorno_funcion(funcion) != "void":
            return []

        return [
            self._crear_diagnostico(
                nodo=declaracion or funcion,
                severidad="warning",
                mensaje=(
                    "analizador semantico AST: la funcion principal 'main' "
                    "deberia retornar 'int' en lugar de 'void'"
                ),
                tipo_error="return_error",
                simbolo="main",
            )
        ]
    
    def _analizar_tipo_retorno(
        self,
        funcion: SourceASTNode,
    ) -> list[DiagnosticEntry]:
        tipo_retorno = _tipo_retorno_funcion(funcion)
        if not tipo_retorno or tipo_retorno == "void":
            return []

        nombre, _ = _nombre_y_declaracion_funcion(funcion)
        cuerpo = _hijo_por_rol(funcion, "body")
        if cuerpo is None:
            return []

        diagnosticos = []
        for nodo_return in _buscar_nodos(cuerpo, "Return"):
            expr = _hijo_por_rol(nodo_return, "expr")
            if expr is None:
                continue

            tipo_expresion = _inferir_tipo_expresion(
                expr,
                self.tabla_simbolos,
                self._ambito_en_linea(nodo_return.linea or 1),
            )
            if tipo_expresion is None:
                continue
            retorno_resuelto = _resolver_alias_tipo(
                tipo_retorno,
                self.tabla_simbolos,
            )
            expresion_resuelta = _resolver_alias_tipo(
                tipo_expresion,
                self.tabla_simbolos,
            )
            if _tipos_compatibles(retorno_resuelto, expresion_resuelta):
                if _es_conversion_peligrosa(
                    retorno_resuelto,
                    expresion_resuelta,
                    expr,
                ):
                    diagnosticos.append(
                        self._crear_diagnostico(
                            nodo=nodo_return,
                            severidad="warning",
                            mensaje=(
                                f"analizador semantico AST: la funcion "
                                f"'{nombre}' convierte el retorno de "
                                f"'{tipo_expresion}' a '{tipo_retorno}' y "
                                "puede perder informacion"
                            ),
                            tipo_error="dangerous_conversion",
                            simbolo=nombre,
                        )
                    )
                continue

            diagnosticos.append(
                self._crear_diagnostico(
                    nodo=nodo_return,
                    severidad="warning",
                    mensaje=(
                        f"analizador semantico AST: la funcion '{nombre}' "
                        f"declara retornar '{tipo_retorno}' pero devuelve "
                        f"un valor de tipo '{tipo_expresion}'"
                    ),
                    tipo_error="return_error",
                    simbolo=nombre,
                )
            )

        return diagnosticos

    def _crear_diagnostico(
        self,
        nodo: SourceASTNode,
        severidad: str,
        mensaje: str,
        tipo_error: str,
        simbolo: str,
        columna: int | None = None,
    ) -> DiagnosticEntry:
        return DiagnosticEntry(
            archivo=self.ruta_fuente,
            linea=nodo.linea or 1,
            columna=columna or nodo.columna or 1,
            severidad=severidad,
            mensaje_crudo=mensaje,
            tipo_error=tipo_error,
            simbolo=simbolo,
            origen="semantico",
        )


def _recorrer(nodo: SourceASTNode):
    yield nodo
    for hijo in nodo.hijos:
        yield from _recorrer(hijo)


def _buscar_nodos(nodo: SourceASTNode, tipo: str):
    return (actual for actual in _recorrer(nodo) if actual.tipo == tipo)


def _hijo_por_rol(
    nodo: SourceASTNode,
    rol: str,
) -> SourceASTNode | None:
    for hijo in nodo.hijos:
        if hijo.rol == rol:
            return hijo
    return None


def _nombre_funcion_llamada(llamada: SourceASTNode) -> str | None:
    nombre = _hijo_por_rol(llamada, "name")
    if nombre is None or nombre.tipo != "ID":
        return None
    return nombre.atributos.get("name")


def _nombre_expresion(nodo: SourceASTNode) -> str | None:
    if nodo.tipo == "ID":
        return nodo.atributos.get("name")
    if nodo.tipo == "StructRef":
        campo = _hijo_por_rol(nodo, "field")
        return campo.atributos.get("name") if campo else None
    if nodo.tipo == "ArrayRef":
        base = _hijo_por_rol(nodo, "name")
        return _nombre_expresion(base) if base else None
    return None


def _nombre_y_declaracion_funcion(
    funcion: SourceASTNode,
) -> tuple[str, SourceASTNode | None]:
    declaracion = _hijo_por_rol(funcion, "decl")
    if declaracion is None:
        return "la funcion", None
    return declaracion.atributos.get("name", "la funcion"), declaracion


def _tipo_retorno_funcion(funcion: SourceASTNode) -> str | None:
    declaracion = _hijo_por_rol(funcion, "decl")
    tipo_funcion = (
        _hijo_por_rol(declaracion, "type")
        if declaracion is not None
        else None
    )
    if tipo_funcion is None or tipo_funcion.tipo != "FuncDecl":
        return None
    return _describir_tipo_nodo(_hijo_por_rol(tipo_funcion, "type"))


def _siempre_retorna(nodo: SourceASTNode) -> bool:
    if nodo.tipo == "Return":
        return True

    if nodo.tipo == "Compound":
        for hijo in nodo.hijos:
            if hijo.rol and hijo.rol.startswith("block_items["):
                if _siempre_retorna(hijo):
                    return True
        return False

    if nodo.tipo == "If":
        rama_verdadera = _hijo_por_rol(nodo, "iftrue")
        rama_falsa = _hijo_por_rol(nodo, "iffalse")
        return (
            rama_verdadera is not None
            and rama_falsa is not None
            and _siempre_retorna(rama_verdadera)
            and _siempre_retorna(rama_falsa)
        )

    if nodo.tipo in {"Label", "Case", "Default"}:
        return any(_siempre_retorna(hijo) for hijo in nodo.hijos)

    return False


def _evaluar_constante(nodo: SourceASTNode) -> float | int | None:
    if nodo.tipo == "Constant":
        valor = nodo.atributos.get("value")
        if valor is None:
            return None
        return _convertir_numero_c(valor)

    if nodo.tipo == "UnaryOp":
        operando = _hijo_por_rol(nodo, "expr")
        valor = _evaluar_constante(operando) if operando else None
        if valor is None:
            return None
        operador = nodo.atributos.get("op")
        if operador == "+":
            return valor
        if operador == "-":
            return -valor
        return None

    if nodo.tipo == "BinaryOp":
        izquierda = _hijo_por_rol(nodo, "left")
        derecha = _hijo_por_rol(nodo, "right")
        valor_izquierdo = _evaluar_constante(izquierda) if izquierda else None
        valor_derecho = _evaluar_constante(derecha) if derecha else None
        if valor_izquierdo is None or valor_derecho is None:
            return None

        operador = nodo.atributos.get("op")
        if operador == "+":
            return valor_izquierdo + valor_derecho
        if operador == "-":
            return valor_izquierdo - valor_derecho
        if operador == "*":
            return valor_izquierdo * valor_derecho
        if operador == "/" and valor_derecho != 0:
            return valor_izquierdo / valor_derecho
        if operador == "%" and valor_derecho != 0:
            return valor_izquierdo % valor_derecho
        return None

    if nodo.tipo == "Cast":
        expresion = _hijo_por_rol(nodo, "expr")
        return _evaluar_constante(expresion) if expresion else None

    return None


def _convertir_numero_c(valor: str) -> float | int | None:
    sin_sufijo = re.sub(r"[uUlLfF]+$", "", valor)
    try:
        if any(caracter in sin_sufijo for caracter in ".eEpP"):
            return float(sin_sufijo)
        if re.fullmatch(r"0[0-7]+", sin_sufijo):
            return int(sin_sufijo, 8)
        return int(sin_sufijo, 0)
    except ValueError:
        return None


def _buscar_columna_operador(
    nodo: SourceASTNode,
    operador: str,
    lineas: list[str],
) -> int:
    if nodo.linea is None or not 1 <= nodo.linea <= len(lineas):
        return nodo.columna or 1

    linea = lineas[nodo.linea - 1]
    inicio = max((nodo.columna or 1) - 1, 0)

    if operador == "=":
        coincidencia = re.search(
            r"(?<![=!<>+\-*/%&|^])=(?!=)",
            linea[inicio:],
        )
        if coincidencia:
            return inicio + coincidencia.start() + 1
    else:
        posicion = linea.find(operador, inicio)
        if posicion >= 0:
            return posicion + 1

    return nodo.columna or 1

def _describir_tipo_nodo(nodo: SourceASTNode | None) -> str | None:
    """Extrae el tipo como string desde un nodo de tipo del AST."""
    if nodo is None:
        return None
    return describir_tipo(nodo)


def _inferir_tipo_expresion(
    nodo: SourceASTNode,
    tabla: SymbolTable,
    ambito: Scope | None = None,
) -> str | None:
    """Infiere el tipo de una expresion desde el AST."""
    if nodo.tipo == "Constant":
        tipo = nodo.atributos.get("type", "")
        valor = nodo.atributos.get("value", "")
        if tipo == "string":
            return "char *"
        if tipo == "float" or valor.endswith(("f", "F")):
            return "float"
        if tipo in {"double", "long double"}:
            return tipo
        if tipo == "char":
            return "int"
        if tipo:
            return tipo
        if "." in valor or "e" in valor.lower():
            return "double"
        return "int"

    if nodo.tipo == "ID":
        nombre = nodo.atributos.get("name")
        if not nombre:
            return None
        if ambito is not None:
            simbolo = tabla.resolver(nombre, ambito)
            if simbolo is not None:
                if simbolo.clase in {"funcion", "funcion_externa"}:
                    return _tipo_puntero_funcion_simbolo(simbolo)
                return simbolo.tipo_dato
        for ambito_actual in tabla.todos_los_ambitos():
            simbolo = ambito_actual.buscar_local(nombre)
            if simbolo is not None:
                if simbolo.clase in {"funcion", "funcion_externa"}:
                    return _tipo_puntero_funcion_simbolo(simbolo)
                return simbolo.tipo_dato
        return None

    if nodo.tipo == "Cast":
        tipo_cast = _hijo_por_rol(nodo, "to_type")
        return _describir_tipo_nodo(tipo_cast)

    if nodo.tipo == "UnaryOp":
        op = nodo.atributos.get("op", "")
        if op == "&":
            expr = _hijo_por_rol(nodo, "expr")
            base = (
                _inferir_tipo_expresion(expr, tabla, ambito)
                if expr
                else None
            )
            if base and base.startswith("puntero a funcion"):
                return base
            return f"{base} *" if base else None
        if op == "*":
            expr = _hijo_por_rol(nodo, "expr")
            base = (
                _inferir_tipo_expresion(expr, tabla, ambito)
                if expr
                else None
            )
            if base and base.startswith("puntero a funcion"):
                return base
            return base.rsplit(" *", 1)[0] if base and " *" in base else None
        if op == "sizeof":
            return "unsigned long"
        if op == "!":
            return "int"
        if op in {"+", "-", "~", "p++", "p--", "++", "--"}:
            expr = _hijo_por_rol(nodo, "expr")
            return (
                _inferir_tipo_expresion(expr, tabla, ambito)
                if expr
                else None
            )

    if nodo.tipo == "BinaryOp":
        operador = nodo.atributos.get("op", "")
        if operador in {"==", "!=", "<", "<=", ">", ">=", "&&", "||"}:
            return "int"

        izquierda = _hijo_por_rol(nodo, "left")
        derecha = _hijo_por_rol(nodo, "right")
        tipo_izquierdo = (
            _inferir_tipo_expresion(izquierda, tabla, ambito)
            if izquierda
            else None
        )
        tipo_derecho = (
            _inferir_tipo_expresion(derecha, tabla, ambito)
            if derecha
            else None
        )
        return _tipo_resultado_operacion(
            tipo_izquierdo,
            tipo_derecho,
            tabla,
            operador,
        )

    if nodo.tipo == "FuncCall":
        firma = _resolver_firma_llamada(
            nodo,
            tabla,
            ambito or tabla.ambito_global,
        )
        if firma is None:
            return None
        nombre_llamada = _hijo_por_rol(nodo, "name")
        tipo_llamable = (
            _inferir_tipo_expresion(nombre_llamada, tabla, ambito)
            if nombre_llamada
            else None
        )
        if tipo_llamable:
            retorno = _retorno_tipo_llamable(tipo_llamable)
            if retorno:
                return _resolver_alias_tipo(retorno, tabla)

        nombre = firma[0]
        simbolo = tabla.resolver(nombre, ambito or tabla.ambito_global)
        if simbolo is not None and "->" in simbolo.tipo_dato:
            return _resolver_alias_tipo(
                simbolo.tipo_dato.split("->", 1)[1].strip(),
                tabla,
            )
        return None

    if nodo.tipo == "StructRef":
        expresion_base = _hijo_por_rol(nodo, "name")
        campo = _hijo_por_rol(nodo, "field")
        if expresion_base is None or campo is None:
            return None
        nombre_campo = campo.atributos.get("name")
        tipo_base = _inferir_tipo_expresion(expresion_base, tabla, ambito)
        if not nombre_campo or not tipo_base:
            return None
        tipo_compuesto = _resolver_alias_tipo(tipo_base, tabla)
        if nodo.atributos.get("type") == "->":
            tipo_compuesto = _quitar_nivel_puntero(tipo_compuesto)
        miembro = tabla.buscar_miembro(tipo_compuesto.strip(), nombre_campo)
        return miembro.tipo_dato if miembro else None

    if nodo.tipo == "ArrayRef":
        nombre = _hijo_por_rol(nodo, "name")
        tipo_arreglo = (
            _inferir_tipo_expresion(nombre, tabla, ambito)
            if nombre
            else None
        )
        if tipo_arreglo and tipo_arreglo.endswith("[]"):
            return tipo_arreglo[:-2].rstrip()
        if tipo_arreglo and "*" in tipo_arreglo:
            return tipo_arreglo.rsplit("*", 1)[0].rstrip()

    if nodo.tipo == "TernaryOp":
        verdadero = _hijo_por_rol(nodo, "iftrue")
        falso = _hijo_por_rol(nodo, "iffalse")
        tipo_verdadero = (
            _inferir_tipo_expresion(verdadero, tabla, ambito)
            if verdadero
            else None
        )
        tipo_falso = (
            _inferir_tipo_expresion(falso, tabla, ambito)
            if falso
            else None
        )
        return _tipo_resultado_operacion(
            tipo_verdadero,
            tipo_falso,
            tabla,
            "?:",
        )

    if nodo.tipo == "Assignment":
        destino = _hijo_por_rol(nodo, "lvalue")
        return (
            _inferir_tipo_expresion(destino, tabla, ambito)
            if destino
            else None
        )

    if nodo.tipo == "ExprList":
        if not nodo.hijos:
            return None
        return _inferir_tipo_expresion(nodo.hijos[-1], tabla, ambito)

    if nodo.tipo == "CompoundLiteral":
        tipo_literal = _hijo_por_rol(nodo, "type")
        return _describir_tipo_nodo(tipo_literal)

    return None


def _tipo_resultado_operacion(
    tipo_izquierdo: str | None,
    tipo_derecho: str | None,
    tabla: SymbolTable,
    operador: str,
) -> str | None:
    if tipo_izquierdo is None:
        return tipo_derecho
    if tipo_derecho is None:
        return tipo_izquierdo

    izquierdo = _normalizar_tipo(
        _resolver_alias_tipo(tipo_izquierdo, tabla)
    )
    derecho = _normalizar_tipo(
        _resolver_alias_tipo(tipo_derecho, tabla)
    )

    if "*" in izquierdo or "*" in derecho:
        if operador in {"+", "-"}:
            if "*" in izquierdo and _es_tipo_entero(derecho):
                return tipo_izquierdo
            if operador == "+" and "*" in derecho and _es_tipo_entero(izquierdo):
                return tipo_derecho
            if "*" in izquierdo and "*" in derecho and operador == "-":
                return "ptrdiff_t"
        return tipo_izquierdo

    tipos = {izquierdo, derecho}
    if "long double" in tipos:
        return "long double"
    if "double" in tipos:
        return "double"
    if "float" in tipos:
        return "float"

    izquierdo_promovido = _promover_entero(izquierdo)
    derecho_promovido = _promover_entero(derecho)
    if not _es_tipo_entero(izquierdo_promovido):
        return tipo_izquierdo
    if not _es_tipo_entero(derecho_promovido):
        return tipo_derecho
    return _tipo_entero_comun(izquierdo_promovido, derecho_promovido)


def _resolver_firma_llamada(
    llamada: SourceASTNode,
    tabla: SymbolTable,
    ambito: Scope,
) -> tuple[str, list[str], bool, bool] | None:
    llamable = _hijo_por_rol(llamada, "name")
    if llamable is None:
        return None

    nombre = _nombre_expresion(llamable) or "expresion invocable"
    if llamable.tipo == "ID":
        simbolo = tabla.resolver(nombre, ambito)
        if simbolo is not None and (
            simbolo.clase in {"funcion", "funcion_externa"}
            or simbolo.es_puntero_funcion
        ):
            return (
                nombre,
                list(simbolo.tipos_parametros),
                simbolo.firma_parametros_definida,
                simbolo.es_variadica,
            )

    tipo_llamable = _inferir_tipo_expresion(llamable, tabla, ambito)
    if tipo_llamable is None:
        return None
    tipo_resuelto = _resolver_alias_tipo(tipo_llamable, tabla)
    firma = _firma_desde_tipo_puntero(tipo_resuelto)
    if firma is None:
        return None

    parametros, definida, variadica, _ = firma
    return nombre, parametros, definida, variadica


def _tipo_puntero_funcion_simbolo(simbolo: Symbol) -> str:
    if simbolo.tipo_dato.startswith("puntero a funcion"):
        return simbolo.tipo_dato

    parametros = list(simbolo.tipos_parametros)
    if simbolo.es_variadica:
        parametros.append("...")
    if simbolo.firma_parametros_definida:
        contenido = ", ".join(parametros) or "void"
    else:
        contenido = "no especificados"

    retorno = "desconocido"
    if "->" in simbolo.tipo_dato:
        retorno = simbolo.tipo_dato.split("->", 1)[1].strip()
    return f"puntero a funcion ({contenido}) -> {retorno}"


def _firma_desde_tipo_puntero(
    tipo: str,
) -> tuple[list[str], bool, bool, str] | None:
    prefijo = "puntero a funcion ("
    if not tipo.startswith(prefijo):
        return None

    inicio = len(prefijo)
    profundidad = 1
    cierre = None
    for indice in range(inicio, len(tipo)):
        caracter = tipo[indice]
        if caracter == "(":
            profundidad += 1
        elif caracter == ")":
            profundidad -= 1
            if profundidad == 0:
                cierre = indice
                break

    if cierre is None:
        return None
    resto = tipo[cierre + 1:].strip()
    if not resto.startswith("->"):
        return None

    contenido = tipo[inicio:cierre].strip()
    retorno = resto[2:].strip()
    if contenido == "no especificados":
        return [], False, False, retorno
    if contenido in {"", "void"}:
        return [], True, False, retorno

    parametros = _separar_parametros_tipo(contenido)
    variadica = bool(parametros and parametros[-1] == "...")
    if variadica:
        parametros.pop()
    return parametros, True, variadica, retorno


def _separar_parametros_tipo(contenido: str) -> list[str]:
    parametros = []
    inicio = 0
    profundidad = 0
    for indice, caracter in enumerate(contenido):
        if caracter == "(":
            profundidad += 1
        elif caracter == ")":
            profundidad -= 1
        elif caracter == "," and profundidad == 0:
            parametros.append(contenido[inicio:indice].strip())
            inicio = indice + 1
    parametros.append(contenido[inicio:].strip())
    return parametros


def _retorno_tipo_llamable(tipo: str) -> str | None:
    firma = _firma_desde_tipo_puntero(tipo)
    if firma is not None:
        return firma[3]
    if tipo.startswith("funcion ->"):
        return tipo.split("->", 1)[1].strip()
    return None


def _quitar_nivel_puntero(tipo: str) -> str:
    if tipo.startswith("puntero a funcion"):
        return tipo
    return re.sub(r"\s*\*\s*$", "", tipo).strip()


def _es_tipo_entero(tipo: str) -> bool:
    normalizado = _normalizar_tipo(tipo)
    return normalizado in {
        "_bool",
        "char",
        "signed char",
        "unsigned char",
        "short",
        "short int",
        "signed short",
        "signed short int",
        "unsigned short",
        "unsigned short int",
        "int",
        "signed",
        "signed int",
        "unsigned",
        "unsigned int",
        "long",
        "long int",
        "signed long",
        "signed long int",
        "unsigned long",
        "unsigned long int",
        "long long",
        "long long int",
        "signed long long",
        "signed long long int",
        "unsigned long long",
        "unsigned long long int",
    } or normalizado.startswith("enum ") or _es_alias_entero(normalizado)


def _promover_entero(tipo: str) -> str:
    normalizado = _normalizar_tipo(tipo)
    if normalizado in {
        "_bool",
        "char",
        "signed char",
        "unsigned char",
        "short",
        "short int",
        "signed short",
        "signed short int",
        "unsigned short",
        "unsigned short int",
    } or normalizado.startswith("enum "):
        return "int"

    equivalencias = {
        "signed": "int",
        "signed int": "int",
        "unsigned": "unsigned int",
        "long int": "long",
        "signed long": "long",
        "signed long int": "long",
        "unsigned long int": "unsigned long",
        "long long int": "long long",
        "signed long long": "long long",
        "signed long long int": "long long",
        "unsigned long long int": "unsigned long long",
    }
    return equivalencias.get(normalizado, normalizado)


def _tipo_entero_comun(izquierdo: str, derecho: str) -> str:
    if izquierdo == derecho:
        return izquierdo

    informacion = {
        "int": (1, 32, True),
        "unsigned int": (1, 32, False),
        "long": (2, 32, True),
        "unsigned long": (2, 32, False),
        "long long": (3, 64, True),
        "unsigned long long": (3, 64, False),
    }
    info_izquierda = informacion.get(izquierdo, informacion["int"])
    info_derecha = informacion.get(derecho, informacion["int"])
    rango_izquierdo, bits_izquierdo, signo_izquierdo = info_izquierda
    rango_derecho, bits_derecho, signo_derecho = info_derecha

    if signo_izquierdo == signo_derecho:
        return (
            izquierdo
            if rango_izquierdo >= rango_derecho
            else derecho
        )

    if signo_izquierdo:
        tipo_con_signo, info_con_signo = izquierdo, info_izquierda
        tipo_sin_signo, info_sin_signo = derecho, info_derecha
    else:
        tipo_con_signo, info_con_signo = derecho, info_derecha
        tipo_sin_signo, info_sin_signo = izquierdo, info_izquierda

    if info_sin_signo[0] >= info_con_signo[0]:
        return tipo_sin_signo
    if info_con_signo[1] > info_sin_signo[1]:
        return tipo_con_signo
    return {
        "int": "unsigned int",
        "long": "unsigned long",
        "long long": "unsigned long long",
    }.get(tipo_con_signo, tipo_sin_signo)


def _es_conversion_peligrosa(
    tipo_destino: str,
    tipo_origen: str,
    expresion: SourceASTNode,
) -> bool:
    destino = _normalizar_tipo(tipo_destino)
    origen = _normalizar_tipo(tipo_origen)
    flotantes = {"float", "double", "long double"}

    if _es_tipo_entero(destino) and origen in flotantes:
        return True
    if destino == "float" and origen in {"double", "long double"}:
        return True
    if destino == "double" and origen == "long double":
        return True
    if not (_es_tipo_entero(destino) and _es_tipo_entero(origen)):
        return False

    rango_destino = _rango_tipo_entero(destino)
    valor = _evaluar_constante(expresion)
    if rango_destino is not None and isinstance(valor, int):
        return not rango_destino[0] <= valor <= rango_destino[1]

    destino_promovido = _promover_entero(destino)
    origen_promovido = _promover_entero(origen)
    jerarquia = {
        "int": 1,
        "unsigned int": 1,
        "long": 2,
        "unsigned long": 2,
        "long long": 3,
        "unsigned long long": 3,
    }
    if jerarquia.get(origen_promovido, 1) > jerarquia.get(
        destino_promovido,
        1,
    ):
        return True
    return (
        destino_promovido.startswith("unsigned")
        and not origen_promovido.startswith("unsigned")
    )


def _rango_tipo_entero(tipo: str) -> tuple[int, int] | None:
    normalizado = _normalizar_tipo(tipo)
    normalizado = {
        "signed": "int",
        "signed int": "int",
        "unsigned": "unsigned int",
        "short int": "short",
        "signed short": "short",
        "signed short int": "short",
        "unsigned short int": "unsigned short",
        "long int": "long",
        "signed long": "long",
        "signed long int": "long",
        "unsigned long int": "unsigned long",
        "long long int": "long long",
        "signed long long": "long long",
        "signed long long int": "long long",
        "unsigned long long int": "unsigned long long",
    }.get(normalizado, normalizado)
    bits_y_signo = {
        "_bool": (1, False),
        "char": (8, True),
        "signed char": (8, True),
        "unsigned char": (8, False),
        "short": (16, True),
        "unsigned short": (16, False),
        "int": (32, True),
        "unsigned int": (32, False),
        "long": (32, True),
        "unsigned long": (32, False),
        "long long": (64, True),
        "unsigned long long": (64, False),
    }
    configuracion = bits_y_signo.get(normalizado)
    if configuracion is None:
        return None
    bits, con_signo = configuracion
    if con_signo:
        return -(2 ** (bits - 1)), 2 ** (bits - 1) - 1
    return 0, 2**bits - 1


def _tipos_compatibles(tipo_izq: str, tipo_der: str) -> bool:
    """
    Devuelve True si la asignacion es aceptable sin diagnostico.
    Solo reporta incompatibilidades claras y evita falsos positivos.
    """
    izq = _normalizar_tipo(tipo_izq)
    der = _normalizar_tipo(tipo_der)

    if izq == der:
        return True

    funcion_izquierda = izq.startswith("puntero a funcion")
    funcion_derecha = der.startswith("puntero a funcion")
    if funcion_izquierda or funcion_derecha:
        return False

    enteros = {
        "int",
        "short",
        "long",
        "unsigned",
        "char",
        "_bool",
        "unsigned int",
        "unsigned long",
        "unsigned short",
        "unsigned char",
        "long long",
        "unsigned long long",
        "signed",
    }
    if _es_alias_entero(izq):
        enteros.add(izq)
    if _es_alias_entero(der):
        enteros.add(der)
    if izq in enteros and der in enteros:
        return True

    flotantes = {"float", "double", "long double"}
    if izq in flotantes and der in flotantes:
        return True

    if izq in enteros and der in flotantes:
        return True
    if izq in flotantes and der in enteros:
        return True

    puntero_izquierdo = "*" in izq
    puntero_derecho = "*" in der
    if puntero_izquierdo or puntero_derecho:
        if puntero_izquierdo != puntero_derecho:
            return False
        base_izquierda = izq.rsplit("*", 1)[0].strip()
        base_derecha = der.rsplit("*", 1)[0].strip()
        return (
            base_izquierda == base_derecha
            or base_izquierda == "void"
            or base_derecha == "void"
        )

    if izq.startswith(("struct ", "union ", "enum ")):
        return False
    if der.startswith(("struct ", "union ", "enum ")):
        return False

    return True


def _normalizar_tipo(tipo: str) -> str:
    normalizado = tipo.strip().lower()
    normalizado = re.sub(r"\b(?:const|volatile|restrict)\b", "", normalizado)
    normalizado = re.sub(r"\s+", " ", normalizado).strip()
    normalizado = re.sub(r"\s*\*\s*", " *", normalizado)
    if normalizado.endswith("[]"):
        normalizado = f"{normalizado[:-2].rstrip()} *"
    return normalizado


def _es_alias_entero(tipo: str) -> bool:
    return tipo in {"size_t", "ptrdiff_t", "intptr_t", "uintptr_t"} or bool(
        re.fullmatch(r"u?int(?:8|16|32|64)_t", tipo)
    )


def _resolver_alias_tipo(tipo: str, tabla: SymbolTable) -> str:
    actual = tipo.strip()
    for _ in range(8):
        firma = _firma_desde_tipo_puntero(actual)
        if firma is not None:
            parametros, definida, variadica, retorno = firma
            parametros_resueltos = [
                _resolver_alias_tipo(parametro, tabla)
                for parametro in parametros
            ]
            if variadica:
                parametros_resueltos.append("...")
            if definida:
                contenido = ", ".join(parametros_resueltos) or "void"
            else:
                contenido = "no especificados"
            retorno_resuelto = _resolver_alias_tipo(retorno, tabla)
            return (
                f"puntero a funcion ({contenido}) -> "
                f"{retorno_resuelto}"
            )

        coincidencia = re.fullmatch(
            r"(?P<base>[A-Za-z_][A-Za-z0-9_]*)"
            r"(?P<sufijo>(?:\s*\*)*|\[\])",
            actual,
        )
        if not coincidencia:
            return actual

        simbolo = tabla.ambito_global.buscar_local(coincidencia.group("base"))
        if simbolo is None or simbolo.clase != "typedef":
            return actual

        sufijo = coincidencia.group("sufijo")
        if sufijo == "[]":
            sufijo = " *"
        actual = f"{simbolo.tipo_dato}{sufijo}"

    return actual


def _describir_tipo_resuelto(original: str, resuelto: str) -> str:
    if _normalizar_tipo(original) == _normalizar_tipo(resuelto):
        return original
    return f"{original}, equivalente a {resuelto}"
