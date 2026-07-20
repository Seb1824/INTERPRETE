from __future__ import annotations

import re

from src.ast_builder import SourceASTNode, limpiar_comentarios_codigo
from src.parser import DiagnosticEntry
from src.symbol_table import Symbol, construir_tabla_simbolos


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
        externos = set()
        if self.tiene_stdio:
            externos = {
                nombre
                for llamada in _buscar_nodos(ast_codigo, "FuncCall")
                if (nombre := _nombre_funcion_llamada(llamada))
                in _FUNCIONES_STDIO
            }
        self.tabla_simbolos = construir_tabla_simbolos(
            ast_codigo,
            simbolos_externos=externos,
        )

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
            tipo_derecho = _inferir_tipo_expresion(init, self.tabla_simbolos)

            if tipo_izquierdo is None or tipo_derecho is None:
                continue
            if _tipos_compatibles(tipo_izquierdo, tipo_derecho):
                continue

            clave = (decl.linea, decl.columna, nombre)
            if clave in reportados:
                continue
            reportados.add(clave)

            diagnosticos.append(
                self._crear_diagnostico(
                    nodo=decl,
                    severidad="warning",
                    mensaje=(
                        f"analizador semantico AST: inicializacion de "
                        f"'{nombre}' ({tipo_izquierdo}) con un valor de "
                        f"tipo incompatible ({tipo_derecho})"
                    ),
                    tipo_error="type_mismatch",
                    simbolo=nombre,
                )
            )

        for asignacion in _buscar_nodos(self.ast_codigo, "Assignment"):
            if asignacion.atributos.get("op") != "=":
                continue

            lvalue = _hijo_por_rol(asignacion, "lvalue")
            rvalue = _hijo_por_rol(asignacion, "rvalue")
            if lvalue is None or rvalue is None:
                continue

            nombre = lvalue.atributos.get("name") if lvalue.tipo == "ID" else None
            if not nombre:
                continue

            simbolo = self.tabla_simbolos.resolver(
                nombre,
                self._ambito_en_linea(asignacion.linea or 1),
            )
            if simbolo is None:
                continue

            tipo_izquierdo = simbolo.tipo_dato
            tipo_derecho = _inferir_tipo_expresion(rvalue, self.tabla_simbolos)

            if tipo_derecho is None:
                continue
            if _tipos_compatibles(tipo_izquierdo, tipo_derecho):
                continue

            clave = (asignacion.linea, asignacion.columna, nombre)
            if clave in reportados:
                continue
            reportados.add(clave)

            diagnosticos.append(
                self._crear_diagnostico(
                    nodo=asignacion,
                    severidad="warning",
                    mensaje=(
                        f"analizador semantico AST: asignacion a "
                        f"'{nombre}' ({tipo_izquierdo}) de un valor de "
                        f"tipo incompatible ({tipo_derecho})"
                    ),
                    tipo_error="type_mismatch",
                    simbolo=nombre,
                )
            )

        return diagnosticos
    
    def _analizar_argumentos_llamadas(self) -> list[DiagnosticEntry]:
        diagnosticos = []

        for llamada in _buscar_nodos(self.ast_codigo, "FuncCall"):
            nombre = _nombre_funcion_llamada(llamada)
            if not nombre:
                continue

            simbolo = self.tabla_simbolos.resolver(
                nombre,
                self.tabla_simbolos.ambito_global,
            )
            if simbolo is None or simbolo.clase not in {"funcion", "funcion_externa"}:
                continue
            if not simbolo.tipos_parametros:
                continue

            args = _hijo_por_rol(llamada, "args")
            cantidad_real = len(args.hijos) if args is not None else 0
            cantidad_esperada = len(simbolo.tipos_parametros)

            if cantidad_real == cantidad_esperada:
                continue

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

            tipo_expresion = _inferir_tipo_expresion(expr, self.tabla_simbolos)
            if tipo_expresion is None:
                continue
            if _tipos_compatibles(tipo_retorno, tipo_expresion):
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


def _nombre_y_declaracion_funcion(
    funcion: SourceASTNode,
) -> tuple[str, SourceASTNode | None]:
    declaracion = _hijo_por_rol(funcion, "decl")
    if declaracion is None:
        return "la funcion", None
    return declaracion.atributos.get("name", "la funcion"), declaracion


def _tipo_retorno_funcion(funcion: SourceASTNode) -> str | None:
    actual = _hijo_por_rol(funcion, "decl")

    while actual is not None:
        if actual.tipo == "IdentifierType":
            return actual.atributos.get("names")
        if actual.tipo == "PtrDecl":
            interno = _hijo_por_rol(actual, "type")
            base = _tipo_retorno_funcion_desde(interno)
            return f"{base} *" if base else None
        actual = _hijo_por_rol(actual, "type")

    return None


def _tipo_retorno_funcion_desde(nodo: SourceASTNode | None) -> str | None:
    while nodo is not None:
        if nodo.tipo == "IdentifierType":
            return nodo.atributos.get("names")
        nodo = _hijo_por_rol(nodo, "type")
    return None


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

    if nodo.tipo == "IdentifierType":
        return nodo.atributos.get("names")

    if nodo.tipo == "PtrDecl":
        interno = _hijo_por_rol(nodo, "type")
        base = _describir_tipo_nodo(interno)
        return f"{base} *" if base else None

    if nodo.tipo == "ArrayDecl":
        interno = _hijo_por_rol(nodo, "type")
        base = _describir_tipo_nodo(interno)
        return f"{base}[]" if base else None

    interno = _hijo_por_rol(nodo, "type")
    return _describir_tipo_nodo(interno)


def _inferir_tipo_expresion(
    nodo: SourceASTNode,
    tabla: "SymbolTable",
) -> str | None:
    """Infiere el tipo de una expresion desde el AST."""
    if nodo.tipo == "Constant":
        tipo = nodo.atributos.get("type", "")
        valor = nodo.atributos.get("value", "")
        if tipo == "string":
            return "char *"
        if "." in valor or "e" in valor.lower():
            return "double"
        if valor.endswith(("f", "F")):
            return "float"
        return "int"

    if nodo.tipo == "ID":
        nombre = nodo.atributos.get("name")
        if not nombre:
            return None
        for ambito in tabla.todos_los_ambitos():
            simbolo = ambito.buscar_local(nombre)
            if simbolo is not None:
                return simbolo.tipo_dato
        return None

    if nodo.tipo == "Cast":
        tipo_cast = _hijo_por_rol(nodo, "to_type")
        return _describir_tipo_nodo(tipo_cast)

    if nodo.tipo == "UnaryOp":
        op = nodo.atributos.get("op", "")
        if op == "&":
            expr = _hijo_por_rol(nodo, "expr")
            base = _inferir_tipo_expresion(expr, tabla) if expr else None
            return f"{base} *" if base else None
        if op == "*":
            expr = _hijo_por_rol(nodo, "expr")
            base = _inferir_tipo_expresion(expr, tabla) if expr else None
            return base.replace(" *", "", 1) if base and " *" in base else None

    return None


def _tipos_compatibles(tipo_izq: str, tipo_der: str) -> bool:
    """
    Devuelve True si la asignacion es aceptable sin diagnostico.
    Solo reporta incompatibilidades claras y evita falsos positivos.
    """
    if tipo_izq == tipo_der:
        return True

    izq = tipo_izq.strip().lower()
    der = tipo_der.strip().lower()

    if izq == der:
        return True

    enteros = {"int", "short", "long", "unsigned", "char",
               "unsigned int", "unsigned long", "unsigned short",
               "unsigned char", "long long", "signed"}
    if izq in enteros and der in enteros:
        return True

    flotantes = {"float", "double", "long double"}
    if izq in flotantes and der in flotantes:
        return True

    if izq in enteros and der in flotantes:
        return True
    if izq in flotantes and der in enteros:
        return True

    if "null" in der or der == "0":
        return True

    if izq == "char *" and der == "char *":
        return True

    if izq in enteros and der == "char *":
        return False

    if "*" in izq and der in enteros:
        return False

    return True