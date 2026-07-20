from __future__ import annotations
from dataclasses import dataclass, field
from src.ast_builder import SourceASTNode


@dataclass
class SymbolUse:
    linea: int
    columna: int

    def to_dict(self) -> dict:
        return {
            "linea": self.linea,
            "columna": self.columna,
        }


@dataclass
class CompoundMember:
    nombre: str
    tipo_dato: str
    linea_declaracion: int
    columna_declaracion: int

    def to_dict(self) -> dict:
        return {
            "nombre": self.nombre,
            "tipo_dato": self.tipo_dato,
            "linea_declaracion": self.linea_declaracion,
            "columna_declaracion": self.columna_declaracion,
        }


@dataclass
class Symbol:
    nombre: str
    clase: str
    tipo_dato: str
    ambito_id: str
    linea_declaracion: int
    columna_declaracion: int
    tipos_parametros: list[str] = field(default_factory=list)
    firma_parametros_definida: bool = False
    es_variadica: bool = False
    es_puntero_funcion: bool = False
    usos: list[SymbolUse] = field(default_factory=list)

    @property
    def cantidad_usos(self) -> int:
        return len(self.usos)

    def registrar_uso(self, linea: int, columna: int) -> None:
        self.usos.append(SymbolUse(linea=linea, columna=columna))

    def to_dict(self) -> dict:
        return {
            "nombre": self.nombre,
            "clase": self.clase,
            "tipo_dato": self.tipo_dato,
            "ambito_id": self.ambito_id,
            "linea_declaracion": self.linea_declaracion,
            "columna_declaracion": self.columna_declaracion,
            "cantidad_usos": self.cantidad_usos,
            "usos": [uso.to_dict() for uso in self.usos],
            "tipos_parametros": self.tipos_parametros,
            "firma_parametros_definida": self.firma_parametros_definida,
            "es_variadica": self.es_variadica,
            "es_puntero_funcion": self.es_puntero_funcion,
        }


@dataclass
class Scope:
    identificador: str
    clase: str
    nombre: str
    linea_inicio: int
    padre: "Scope | None" = field(default=None, repr=False)
    simbolos: list[Symbol] = field(default_factory=list)
    hijos: list["Scope"] = field(default_factory=list)

    def buscar_local(self, nombre: str) -> Symbol | None:
        for simbolo in reversed(self.simbolos):
            if simbolo.nombre == nombre:
                return simbolo
        return None

    def to_dict(self) -> dict:
        return {
            "id": self.identificador,
            "clase": self.clase,
            "nombre": self.nombre,
            "linea_inicio": self.linea_inicio,
            "padre_id": self.padre.identificador if self.padre else None,
            "simbolos": [simbolo.to_dict() for simbolo in self.simbolos],
            "hijos": [hijo.to_dict() for hijo in self.hijos],
        }


@dataclass
class UnresolvedSymbolUse:
    nombre: str
    ambito_id: str
    linea: int
    columna: int

    def to_dict(self) -> dict:
        return {
            "nombre": self.nombre,
            "ambito_id": self.ambito_id,
            "linea": self.linea,
            "columna": self.columna,
        }


@dataclass
class SymbolRedeclaration:
    nombre: str
    ambito_id: str
    linea_original: int
    columna_original: int
    linea_redeclaracion: int
    columna_redeclaracion: int

    def to_dict(self) -> dict:
        return {
            "nombre": self.nombre,
            "ambito_id": self.ambito_id,
            "linea_original": self.linea_original,
            "columna_original": self.columna_original,
            "linea_redeclaracion": self.linea_redeclaracion,
            "columna_redeclaracion": self.columna_redeclaracion,
        }


class SymbolTable:
    def __init__(self):
        self.ambito_global = Scope(
            identificador="scope_0",
            clase="global",
            nombre="global",
            linea_inicio=1,
        )
        self.usos_no_resueltos: list[UnresolvedSymbolUse] = []
        self.redeclaraciones: list[SymbolRedeclaration] = []
        self.tipos_compuestos: dict[str, dict[str, CompoundMember]] = {}
        self._contador_ambitos = 1

    def crear_ambito(
        self,
        clase: str,
        nombre: str,
        linea_inicio: int,
        padre: Scope,
    ) -> Scope:
        ambito = Scope(
            identificador=f"scope_{self._contador_ambitos}",
            clase=clase,
            nombre=nombre,
            linea_inicio=linea_inicio,
            padre=padre,
        )
        self._contador_ambitos += 1
        padre.hijos.append(ambito)
        return ambito

    def declarar(
        self,
        ambito: Scope,
        nombre: str,
        clase: str,
        tipo_dato: str,
        linea: int,
        columna: int,
    ) -> Symbol:
        existente = ambito.buscar_local(nombre)
        if existente is not None:
            self.redeclaraciones.append(
                SymbolRedeclaration(
                    nombre=nombre,
                    ambito_id=ambito.identificador,
                    linea_original=existente.linea_declaracion,
                    columna_original=existente.columna_declaracion,
                    linea_redeclaracion=linea,
                    columna_redeclaracion=columna,
                )
            )
            return existente

        simbolo = Symbol(
            nombre=nombre,
            clase=clase,
            tipo_dato=tipo_dato,
            ambito_id=ambito.identificador,
            linea_declaracion=linea,
            columna_declaracion=columna,
        )
        ambito.simbolos.append(simbolo)
        return simbolo

    def resolver(self, nombre: str, ambito: Scope) -> Symbol | None:
        actual: Scope | None = ambito
        while actual is not None:
            simbolo = actual.buscar_local(nombre)
            if simbolo is not None:
                return simbolo
            actual = actual.padre
        return None

    def registrar_uso(
        self,
        nombre: str,
        ambito: Scope,
        linea: int,
        columna: int,
    ) -> Symbol | None:
        simbolo = self.resolver(nombre, ambito)
        if simbolo is not None:
            simbolo.registrar_uso(linea, columna)
            return simbolo

        self.usos_no_resueltos.append(
            UnresolvedSymbolUse(
                nombre=nombre,
                ambito_id=ambito.identificador,
                linea=linea,
                columna=columna,
            )
        )
        return None

    def todos_los_ambitos(self) -> list[Scope]:
        return list(_recorrer_ambitos(self.ambito_global))

    def todos_los_simbolos(self) -> list[Symbol]:
        return [
            simbolo
            for ambito in self.todos_los_ambitos()
            for simbolo in ambito.simbolos
        ]

    def buscar_ambito(self, identificador: str) -> Scope | None:
        for ambito in self.todos_los_ambitos():
            if ambito.identificador == identificador:
                return ambito
        return None

    def registrar_tipo_compuesto(
        self,
        tipo_dato: str,
        miembros: list[CompoundMember],
    ) -> None:
        existentes = self.tipos_compuestos.setdefault(tipo_dato, {})
        for miembro in miembros:
            existentes[miembro.nombre] = miembro

    def buscar_miembro(
        self,
        tipo_dato: str,
        nombre_miembro: str,
    ) -> CompoundMember | None:
        return self.tipos_compuestos.get(tipo_dato, {}).get(nombre_miembro)

    def to_dict(self) -> dict:
        return {
            "ambito_global": self.ambito_global.to_dict(),
            "usos_no_resueltos": [
                uso.to_dict()
                for uso in self.usos_no_resueltos
            ],
            "redeclaraciones": [
                redeclaracion.to_dict()
                for redeclaracion in self.redeclaraciones
            ],
            "tipos_compuestos": {
                tipo: {
                    nombre: miembro.to_dict()
                    for nombre, miembro in miembros.items()
                }
                for tipo, miembros in self.tipos_compuestos.items()
            },
        }

    def render(self) -> list[str]:
        lineas = []
        _renderizar_ambito(self.ambito_global, lineas, nivel=0)

        if self.usos_no_resueltos:
            lineas.append("- Usos no resueltos")
            for uso in self.usos_no_resueltos:
                lineas.append(
                    f"  - {uso.nombre} [{uso.linea}:{uso.columna}] "
                    f"ambito={uso.ambito_id}"
                )

        if self.redeclaraciones:
            lineas.append("- Redeclaraciones")
            for redeclaracion in self.redeclaraciones:
                lineas.append(
                    f"  - {redeclaracion.nombre} "
                    f"[{redeclaracion.linea_redeclaracion}:"
                    f"{redeclaracion.columna_redeclaracion}] "
                    f"original=[{redeclaracion.linea_original}:"
                    f"{redeclaracion.columna_original}] "
                    f"ambito={redeclaracion.ambito_id}"
                )

        if self.tipos_compuestos:
            lineas.append("- Tipos compuestos")
            for tipo, miembros in self.tipos_compuestos.items():
                lineas.append(f"  - {tipo}")
                for miembro in miembros.values():
                    lineas.append(
                        f"    - {miembro.nombre}: {miembro.tipo_dato} "
                        f"[linea={miembro.linea_declaracion}]"
                    )

        return lineas


class SymbolTableBuilder:
    def __init__(
        self,
        ast_codigo: SourceASTNode,
        simbolos_externos: set[str] | None = None,
    ):
        self.ast_codigo = ast_codigo
        self.tabla = SymbolTable()
        self.simbolos_externos = simbolos_externos or set()
        self.funciones_definidas: set[str] = set()

    def construir(self) -> SymbolTable:
        self._registrar_tipos_compuestos(
            self.ast_codigo,
            alias_anonimo=None,
        )

        for nombre in sorted(self.simbolos_externos):
            self.tabla.declarar(
                ambito=self.tabla.ambito_global,
                nombre=nombre,
                clase="funcion_externa",
                tipo_dato="declarado en cabecera",
                linea=1,
                columna=1,
            )

        for nodo in self.ast_codigo.hijos:
            if nodo.tipo == "FuncDef":
                self._procesar_funcion(nodo)
            else:
                self._visitar(nodo, self.tabla.ambito_global)
        return self.tabla

    def _registrar_tipos_compuestos(
        self,
        nodo: SourceASTNode,
        alias_anonimo: str | None,
    ) -> None:
        alias_hijos = alias_anonimo
        if nodo.tipo == "Typedef":
            alias_hijos = nodo.atributos.get("name") or alias_anonimo

        if nodo.tipo in {"Struct", "Union"}:
            clase = nodo.tipo.lower()
            nombre = nodo.atributos.get("name") or alias_anonimo or "anonima"
            miembros = []
            for hijo in nodo.hijos:
                if hijo.tipo != "Decl":
                    continue
                nombre_miembro = hijo.atributos.get("name")
                tipo = _hijo_por_rol(hijo, "type")
                if not nombre_miembro or tipo is None:
                    continue
                miembros.append(
                    CompoundMember(
                        nombre=nombre_miembro,
                        tipo_dato=_describir_tipo(tipo),
                        linea_declaracion=hijo.linea or 1,
                        columna_declaracion=hijo.columna or 1,
                    )
                )
            self.tabla.registrar_tipo_compuesto(
                f"{clase} {nombre}",
                miembros,
            )

        for hijo in nodo.hijos:
            self._registrar_tipos_compuestos(hijo, alias_hijos)

    def _procesar_funcion(self, funcion: SourceASTNode) -> None:
        declaracion = _hijo_por_rol(funcion, "decl")
        if declaracion is None:
            return

        nombre = declaracion.atributos.get("name", "funcion_anonima")
        existente = self.tabla.ambito_global.buscar_local(nombre)
        if (
            existente is None
            or existente.clase not in {"funcion", "funcion_externa"}
            or nombre in self.funciones_definidas
        ):
            self._declarar_desde_nodo(
                declaracion,
                self.tabla.ambito_global,
                clase="funcion",
            )
            
        simbolo_funcion = self.tabla.ambito_global.buscar_local(nombre)
        if simbolo_funcion is not None:
            simbolo_funcion.clase = "funcion"
            _actualizar_firma_funcion(simbolo_funcion, declaracion)

        self.funciones_definidas.add(nombre)
        ambito_funcion = self.tabla.crear_ambito(
            clase="funcion",
            nombre=nombre,
            linea_inicio=declaracion.linea or 1,
            padre=self.tabla.ambito_global,
        )

        for parametro in _parametros_de_funcion(declaracion):
            self._declarar_desde_nodo(
                parametro,
                ambito_funcion,
                clase="parametro",
            )

        cuerpo = _hijo_por_rol(funcion, "body")
        if cuerpo is not None:
            self._procesar_compuesto(
                cuerpo,
                ambito_funcion,
                crear_ambito=False,
            )

    def _visitar(
        self,
        nodo: SourceASTNode,
        ambito: Scope,
        padre: SourceASTNode | None = None,
    ) -> None:
        if nodo.tipo == "Compound":
            self._procesar_compuesto(nodo, ambito, crear_ambito=True)
            return

        if nodo.tipo == "For":
            ambito_for = self.tabla.crear_ambito(
                clase="for",
                nombre="for",
                linea_inicio=nodo.linea or 1,
                padre=ambito,
            )
            for hijo in nodo.hijos:
                self._visitar(hijo, ambito_for, nodo)
            return

        if nodo.tipo == "Decl":
            if _es_declaracion_funcion(nodo):
                nombre = nodo.atributos.get("name")
                existente = ambito.buscar_local(nombre) if nombre else None
                if existente is None or existente.clase not in {
                    "funcion",
                    "funcion_externa",
                }:
                    self._declarar_desde_nodo(
                        nodo,
                        ambito,
                        clase="funcion_externa",
                    )
                simbolo_funcion = ambito.buscar_local(nombre) if nombre else None
                if simbolo_funcion is not None:
                    _actualizar_firma_funcion(simbolo_funcion, nodo)
                return

            clase = "variable"
            self._declarar_desde_nodo(nodo, ambito, clase=clase)
            for hijo in nodo.hijos:
                if hijo.rol in {"init", "bitsize"}:
                    self._visitar(hijo, ambito, nodo)
            return

        if nodo.tipo == "Typedef":
            self._declarar_desde_nodo(nodo, ambito, clase="typedef")
            return

        if nodo.tipo == "Enumerator":
            self._declarar_desde_nodo(nodo, ambito, clase="constante")
            for hijo in nodo.hijos:
                self._visitar(hijo, ambito, nodo)
            return

        if nodo.tipo == "ID":
            if padre is not None and padre.tipo == "StructRef" and nodo.rol == "field":
                return
            nombre = nodo.atributos.get("name")
            if nombre:
                self.tabla.registrar_uso(
                    nombre,
                    ambito,
                    nodo.linea or 1,
                    nodo.columna or 1,
                )
            return

        for hijo in nodo.hijos:
            self._visitar(hijo, ambito, nodo)

    def _procesar_compuesto(
        self,
        compuesto: SourceASTNode,
        ambito_padre: Scope,
        crear_ambito: bool,
    ) -> None:
        ambito = ambito_padre
        if crear_ambito:
            ambito = self.tabla.crear_ambito(
                clase="bloque",
                nombre="bloque",
                linea_inicio=compuesto.linea or 1,
                padre=ambito_padre,
            )

        for hijo in compuesto.hijos:
            self._visitar(hijo, ambito, compuesto)

    def _declarar_desde_nodo(
        self,
        nodo: SourceASTNode,
        ambito: Scope,
        clase: str,
    ) -> Symbol | None:
        nombre = nodo.atributos.get("name")
        if not nombre:
            return None

        tipo = _hijo_por_rol(nodo, "type")
        tipo_dato = _describir_tipo(tipo) if tipo else "desconocido"
        if clase == "typedef" and tipo is not None:
            compuesto_anonimo = next(
                (
                    actual
                    for actual in _recorrer_nodos(tipo)
                    if actual.tipo in {"Struct", "Union"}
                    and not actual.atributos.get("name")
                ),
                None,
            )
            if compuesto_anonimo is not None:
                tipo_dato = f"{compuesto_anonimo.tipo.lower()} {nombre}"

        simbolo = self.tabla.declarar(
            ambito=ambito,
            nombre=nombre,
            clase=clase,
            tipo_dato=tipo_dato,
            linea=nodo.linea or 1,
            columna=nodo.columna or 1,
        )
        if tipo is not None and _contiene_puntero_funcion(tipo):
            simbolo.es_puntero_funcion = True
            _actualizar_firma_funcion(simbolo, nodo)
        elif tipo is not None and tipo.tipo == "TypeDecl":
            identificador = _hijo_por_rol(tipo, "type")
            if identificador is not None and identificador.tipo == "IdentifierType":
                alias = self.tabla.ambito_global.buscar_local(
                    identificador.atributos.get("names", "")
                )
                if alias is not None and alias.es_puntero_funcion:
                    simbolo.tipo_dato = alias.tipo_dato
                    simbolo.tipos_parametros = list(alias.tipos_parametros)
                    simbolo.firma_parametros_definida = (
                        alias.firma_parametros_definida
                    )
                    simbolo.es_variadica = alias.es_variadica
                    simbolo.es_puntero_funcion = True
        return simbolo


def construir_tabla_simbolos(
    ast_codigo: SourceASTNode,
    simbolos_externos: set[str] | None = None,
) -> SymbolTable:
    return SymbolTableBuilder(
        ast_codigo,
        simbolos_externos=simbolos_externos,
    ).construir()


def describir_tipo(nodo: SourceASTNode | None) -> str:
    """Devuelve la representacion canonica de un nodo de tipo de C."""
    return _describir_tipo(nodo)


def _parametros_de_funcion(declaracion: SourceASTNode) -> list[SourceASTNode]:
    for nodo in _recorrer_nodos(declaracion):
        if nodo.tipo == "ParamList":
            return [hijo for hijo in nodo.hijos if hijo.tipo == "Decl"]
    return []


def _actualizar_firma_funcion(
    simbolo: Symbol,
    declaracion: SourceASTNode,
) -> None:
    tipos, firma_definida, es_variadica = _firma_de_funcion(declaracion)
    if not firma_definida and simbolo.firma_parametros_definida:
        return

    simbolo.tipos_parametros = tipos
    simbolo.firma_parametros_definida = firma_definida
    simbolo.es_variadica = es_variadica


def _firma_de_funcion(
    declaracion: SourceASTNode,
) -> tuple[list[str], bool, bool]:
    declaracion_funcion = next(
        (
            nodo
            for nodo in _recorrer_nodos(declaracion)
            if nodo.tipo == "FuncDecl"
        ),
        None,
    )
    if declaracion_funcion is None:
        return [], False, False

    return _firma_desde_func_decl(declaracion_funcion)


def _firma_desde_func_decl(
    declaracion_funcion: SourceASTNode,
) -> tuple[list[str], bool, bool]:
    argumentos = _hijo_por_rol(declaracion_funcion, "args")
    if argumentos is None:
        return [], False, False

    parametros = [
        hijo
        for hijo in argumentos.hijos
        if hijo.tipo in {"Decl", "Typename"}
    ]
    es_variadica = any(
        hijo.tipo == "EllipsisParam"
        for hijo in argumentos.hijos
    )

    if len(parametros) == 1 and not parametros[0].atributos.get("name"):
        tipo_unico = _describir_tipo(
            _hijo_por_rol(parametros[0], "type")
        )
        if tipo_unico == "void":
            return [], True, es_variadica

    tipos = [
        _normalizar_tipo_parametro(
            _describir_tipo(_hijo_por_rol(parametro, "type"))
        )
        for parametro in parametros
    ]
    return tipos, True, es_variadica


def _normalizar_tipo_parametro(tipo: str) -> str:
    if tipo.endswith("[]"):
        return f"{tipo[:-2].rstrip()} *"
    return tipo


def _es_declaracion_funcion(declaracion: SourceASTNode) -> bool:
    tipo = _hijo_por_rol(declaracion, "type")
    return tipo is not None and tipo.tipo == "FuncDecl"


def _describir_tipo(nodo: SourceASTNode | None) -> str:
    if nodo is None:
        return "desconocido"

    if nodo.tipo == "IdentifierType":
        return nodo.atributos.get("names", "desconocido")

    if nodo.tipo == "Struct":
        nombre = nodo.atributos.get("name", "anonima")
        return f"struct {nombre}"

    if nodo.tipo == "Union":
        nombre = nodo.atributos.get("name", "anonima")
        return f"union {nombre}"

    if nodo.tipo == "Enum":
        nombre = nodo.atributos.get("name", "anonimo")
        return f"enum {nombre}"

    tipo_interno = _hijo_por_rol(nodo, "type")
    if nodo.tipo == "PtrDecl" and tipo_interno is not None:
        if tipo_interno.tipo == "FuncDecl":
            retorno = _describir_tipo(_hijo_por_rol(tipo_interno, "type"))
            parametros, firma_definida, es_variadica = (
                _firma_desde_func_decl(tipo_interno)
            )
            descripcion_parametros = list(parametros)
            if es_variadica:
                descripcion_parametros.append("...")
            if firma_definida:
                contenido = ", ".join(descripcion_parametros) or "void"
            else:
                contenido = "no especificados"
            return f"puntero a funcion ({contenido}) -> {retorno}"

    base = _describir_tipo(tipo_interno)

    if nodo.tipo == "PtrDecl":
        return f"{base} *"
    if nodo.tipo == "ArrayDecl":
        return f"{base}[]"
    if nodo.tipo == "FuncDecl":
        return f"funcion -> {base}"
    return base


def _contiene_puntero_funcion(nodo: SourceASTNode) -> bool:
    if nodo.tipo == "PtrDecl":
        interno = _hijo_por_rol(nodo, "type")
        if interno is not None and interno.tipo == "FuncDecl":
            return True
    return any(_contiene_puntero_funcion(hijo) for hijo in nodo.hijos)


def _hijo_por_rol(
    nodo: SourceASTNode,
    rol: str,
) -> SourceASTNode | None:
    for hijo in nodo.hijos:
        if hijo.rol == rol:
            return hijo
    return None


def _recorrer_nodos(nodo: SourceASTNode):
    yield nodo
    for hijo in nodo.hijos:
        yield from _recorrer_nodos(hijo)


def _recorrer_ambitos(ambito: Scope):
    yield ambito
    for hijo in ambito.hijos:
        yield from _recorrer_ambitos(hijo)


def _renderizar_ambito(
    ambito: Scope,
    lineas: list[str],
    nivel: int,
) -> None:
    sangria = "  " * nivel
    lineas.append(
        f"{sangria}- {ambito.identificador} "
        f"[{ambito.clase}: {ambito.nombre}]"
    )

    for simbolo in ambito.simbolos:
        firma = ""
        if simbolo.clase in {"funcion", "funcion_externa"}:
            if simbolo.firma_parametros_definida:
                parametros = list(simbolo.tipos_parametros)
                if simbolo.es_variadica:
                    parametros.append("...")
                firma = f", parametros=({', '.join(parametros) or 'void'})"
            else:
                firma = ", parametros=no especificados"
        lineas.append(
            f"{sangria}  - {simbolo.nombre}: {simbolo.tipo_dato} "
            f"({simbolo.clase}, usos={simbolo.cantidad_usos}, "
            f"linea={simbolo.linea_declaracion}{firma})"
        )

    for hijo in ambito.hijos:
        _renderizar_ambito(hijo, lineas, nivel + 1)
