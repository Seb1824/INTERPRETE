from __future__ import annotations
import inspect
import re
from pathlib import Path

from src.parser import DiagnosticEntry

def _extraer_linea_cruda(archivo: str, numero_linea: int) -> str:
    """Lee el archivo y extrae la línea exacta de código limpiando espacios."""
    try:
        ruta = Path(archivo)
        if ruta.exists():
            lineas = ruta.read_text(encoding="utf-8").splitlines()
            if 0 < numero_linea <= len(lineas):
                return lineas[numero_linea - 1].strip()
    except Exception:
        pass
    return ""

def explain(entry):
    linea_codigo = _extraer_linea_cruda(entry.archivo, entry.linea)
    
    handler = _HANDLERS.get(entry.tipo_error, _explain_desconocido)
    
    if "linea_codigo" in inspect.signature(handler).parameters:
        return handler(entry, linea_codigo)
        
    return handler(entry)

def _explain_undeclared(entry, linea_codigo=""):
    simbolo = entry.simbolo or "desconocido"
    
    if linea_codigo:
        sugerencia_dinamica = (
            f"Asegúrate de declarar '{simbolo}' antes de esta línea:\n"
            f"    {linea_codigo}"
        )
    else:
        sugerencia_dinamica = (
            f"Busca dónde usas '{simbolo}' (línea {entry.linea}) y asegúrate "
            f"de haberlo declarado antes. Si es de biblioteca, revisa el #include."
        )

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
        "sugerencia": sugerencia_dinamica,
    }


def _explain_implicit_declaration(entry):
    simbolo = entry.simbolo or "la función"
    
    if simbolo in ["printf", "scanf", "puts", "getchar"]:
        return {
            "titulo": f"Falta incluir <stdio.h> para usar '{simbolo}'",
            "explicacion": (
                f"Estás intentando usar '{simbolo}', que es una función de la biblioteca "
                f"estándar de C, pero el compilador no sabe cómo usarla."
            ),
            "causa_probable": (
                f"Olvidaste incluir la biblioteca de entrada/salida estándar <stdio.h> "
                f"al principio de tu código."
            ),
            "sugerencia": (
                f"Agrega la línea '#include <stdio.h>' en la parte superior de tu archivo, "
                f"justo en la línea 1, antes de declarar cualquier función."
            ),
        }

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


def _explain_expected_token(entry, linea_codigo=""):
    simbolo = entry.simbolo or "un símbolo de puntuación"
    
    if simbolo in [";", ",", "';'", "','"]:
        linea_anterior = _extraer_linea_cruda(entry.archivo, entry.linea - 1)
        
        if linea_anterior:
            sugerencia_dinamica = (
                f"Agrega el punto y coma faltante. La línea anterior debería quedar así:\n"
                f"    {linea_anterior};"
            )
        else:
            sugerencia_dinamica = "Asegúrate de colocar un ';' al final de la instrucción anterior."
            
        return {
            "titulo": "Falta punto y coma ';'",
            "explicacion": f"El compilador se detuvo en la línea {entry.linea} porque la instrucción anterior no fue terminada correctamente.",
            "causa_probable": f"Olvidaste poner un punto y coma (;) al final de la línea {entry.linea - 1}.",
            "sugerencia": sugerencia_dinamica,
        }

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

def _explain_wrong_arguments(entry):
    simbolo = entry.simbolo or "la función"
    return {
        "titulo": f"Argumentos incorrectos en la llamada a '{simbolo}'",
        "explicacion": (
            f"'{simbolo}' fue llamada con una cantidad o tipo de argumentos "
            f"diferente a lo que su declaración especifica. El compilador verifica "
            f"que las llamadas coincidan exactamente con el prototipo."
        ),
        "causa_probable": (
            f"Pasaste más o menos argumentos de los que '{simbolo}' espera, "
            f"intercambiaste el orden de los parámetros, o uno de los argumentos "
            f"es del tipo equivocado."
        ),
        "sugerencia": (
            f"Busca la declaración de '{simbolo}' y compara sus parámetros uno a uno "
            f"con los argumentos de la línea {entry.linea}. Verifica cantidad, orden y tipo. "
            f"Si es de biblioteca, consulta su documentación."
        ),
    }

def _explain_return_error(entry):
    simbolo = entry.simbolo or "la función"
    
    if simbolo == "main":
        return {
            "titulo": "Uso de 'void main' en lugar de 'int main'",
            "explicacion": (
                "La función principal de un programa en C siempre debe devolver un "
                "número entero al sistema operativo para indicar si terminó correctamente."
            ),
            "causa_probable": (
                "Declaraste la función como 'void main()'. Aunque en algunos compiladores "
                "antiguos esto funcionaba, el estándar estricto de C exige que sea 'int'."
            ),
            "sugerencia": (
                "Cambia 'void main()' por 'int main()'. Además, asegúrate de agregar "
                "'return 0;' justo antes de cerrar la llave final de main() para indicar "
                "que el programa terminó con éxito."
            ),
        }

    return {
        "titulo": f"Error en el valor de retorno de '{simbolo}'",
        "explicacion": (
            f"Hay un problema con el return en '{simbolo}': puede que esté declarada "
            f"para retornar un tipo pero el return devuelve otro, o que falte el return."
        ),
        "causa_probable": (
            f"Una función declarada como int sin return, una función void que intenta "
            f"retornar un valor, o un return que devuelve un tipo incompatible con el declarado."
        ),
        "sugerencia": (
            f"Revisa la declaración de '{simbolo}': ¿qué tipo dice que retorna? "
            f"Verifica que todos los return dentro de la función devuelvan ese mismo tipo. "
            f"Si no debe retornar nada, declárala como void. Revisa la línea {entry.linea}."
        ),
    }

def _explain_unused_variable(entry):
    simbolo = entry.simbolo or "una variable"
    return {
        "titulo": f"Variable '{simbolo}' declarada pero nunca usada",
        "explicacion": (
            f"Declaraste '{simbolo}' pero nunca la lees ni la modificas después. "
            f"El compilador lo reporta como advertencia (-Wall) porque suele "
            f"indicar un olvido o código innecesario."
        ),
        "causa_probable": (
            f"Planeaste usar '{simbolo}' pero olvidaste hacerlo, la renombraste "
            f"en algún momento y quedó la versión vieja, o era para depuración "
            f"y ya no se necesita."
        ),
        "sugerencia": (
            f"(1) Si '{simbolo}' sí se necesita, úsala en alguna instrucción. "
            f"(2) Si ya no la necesitas, elimina su declaración en la línea "
            f"{entry.linea}. Aunque es solo una advertencia, es buena práctica "
            f"no dejar variables sin usar."
        ),
    }

def _explain_division_by_zero(entry):
    return {
        "titulo": "División por cero detectada en tiempo de compilación",
        "explicacion": (
            f"Hay una división entre cero en la línea {entry.linea}. "
            f"Matemáticamente no está definida, y en C produce comportamiento "
            f"indefinido: el programa puede terminar abruptamente o dar "
            f"resultados impredecibles."
        ),
        "causa_probable": (
            f"Estás dividiendo entre la constante literal 0, o entre una "
            f"expresión que el compilador calculó en tiempo de compilación "
            f"y resultó ser 0."
        ),
        "sugerencia": (
            f"Revisa la operación de división en la línea {entry.linea}. "
            f"Si el divisor puede ser cero, agrega una verificación antes: "
            f"if (divisor != 0) {{ resultado = dividendo / divisor; }}"
        ),
    }

def _explain_pointer_error(entry):
    simbolo = entry.simbolo or "el puntero"
    return {
        "titulo": f"Uso incorrecto de puntero en '{simbolo}'",
        "explicacion": (
            "El compilador detectó una operación de punteros incompatible o inválida. "
            "Un puntero debe apuntar a un tipo compatible antes de ser asignado o desreferenciado."
        ),
        "causa_probable": (
            "Se intentó desreferenciar un valor que no es puntero, asignar un entero a "
            "un puntero, o mezclar punteros de tipos incompatibles."
        ),
        "sugerencia": (
            f"Revisa los tipos involucrados en la línea {entry.linea}. Comprueba el uso "
            "de '&' y '*', y evita aplicar un cast únicamente para ocultar la advertencia."
        ),
    }

def _explain_format_mismatch(entry):
    return {
        "titulo": "Formato y argumentos incompatibles en una función de impresión",
        "explicacion": (
            "El especificador de formato no coincide con el tipo o la cantidad de "
            "argumentos enviados a printf, fprintf, sprintf u otra función similar."
        ),
        "causa_probable": (
            "Se usó, por ejemplo, %d para una cadena, %s para un entero, o existe una "
            "cantidad diferente de especificadores y argumentos."
        ),
        "sugerencia": (
            f"Compara cada especificador de formato con su argumento en la línea "
            f"{entry.linea}: %d para int, %f para double, %c para char y %s para cadenas."
        ),
    }

def _explain_unbalanced_delimiter(entry, linea_codigo=""):
    simbolo = entry.simbolo or "un delimitador"
    
    if linea_codigo:
        sugerencia_dinamica = (
            f"Revisa este fragmento de tu código en busca de un '{simbolo}' faltante o desbalanceado:\n"
            f"    {linea_codigo}"
        )
    else:
        sugerencia_dinamica = (
            f"Revisa la línea {entry.linea} y las anteriores. Empareja (), [] y {{}} "
            f"y verifica que todas las cadenas tengan comillas de apertura y cierre."
        )

    return {
        "titulo": f"Delimitador '{simbolo}' faltante o desbalanceado",
        "explicacion": (
            "La estructura del programa contiene una llave, un paréntesis, un corchete "
            "o una comilla que no fue cerrada correctamente."
        ),
        "causa_probable": (
            "Falta un símbolo de cierre, existe uno adicional, o una cadena quedó sin "
            "comilla final. El error real puede estar varias líneas antes."
        ),
        "sugerencia": sugerencia_dinamica,
    }

def _explain_missing_return(entry):
    simbolo = entry.simbolo or "la función"
    return {
        "titulo": f"Falta retornar un valor en '{simbolo}'",
        "explicacion": (
            "Una función declarada con un tipo de retorno distinto de void puede "
            "terminar sin ejecutar una instrucción return válida."
        ),
        "causa_probable": (
            "Falta return al final de la función o alguna rama de un if, switch o bucle "
            "permite llegar al final sin devolver un valor."
        ),
        "sugerencia": (
            f"Revisa todos los caminos de ejecución de la función cerca de la línea "
            f"{entry.linea} y asegúrate de que cada uno retorne el tipo declarado."
        ),
    }

def _explain_dangerous_conversion(entry):
    simbolo = entry.simbolo or "el valor"
    return {
        "titulo": f"Conversión potencialmente peligrosa en '{simbolo}'",
        "explicacion": (
            "La conversión puede perder precisión, cambiar el signo o producir un valor "
            "distinto porque el tipo de destino no puede representar todos los valores."
        ),
        "causa_probable": (
            "Se está convirtiendo desde un tipo de mayor tamaño o rango hacia uno menor, "
            "por ejemplo de long a int o de un entero grande a char."
        ),
        "sugerencia": (
            f"Comprueba los rangos de ambos tipos en la línea {entry.linea}. Usa un tipo "
            "de destino más amplio y valida el valor antes de convertirlo."
        ),
    }

def _explain_uninitialized_variable(entry):
    simbolo = entry.simbolo or "la variable"
    return {
        "titulo": f"Variable '{simbolo}' usada sin inicializar",
        "explicacion": (
            "La variable puede leerse antes de recibir un valor definido. Su contenido "
            "inicial es indeterminado y el resultado del programa no es confiable."
        ),
        "causa_probable": (
            "La variable fue declarada sin valor inicial o solo se asigna en algunas "
            "ramas del programa."
        ),
        "sugerencia": (
            f"Inicializa '{simbolo}' al declararla y verifica que todos los caminos de "
            f"ejecución le asignen un valor antes de usarla. Revisa la línea {entry.linea}."
        ),
    }

def _explain_struct_access(entry):
    simbolo = entry.simbolo or "el miembro"
    return {
        "titulo": f"Acceso inválido a estructura o miembro '{simbolo}'",
        "explicacion": (
            "El programa intenta acceder a un miembro que no existe o usa el operador "
            "equivocado para el tipo de dato."
        ),
        "causa_probable": (
            "Se usó '.' sobre un puntero, '->' sobre una estructura no puntero, el nombre "
            "del miembro está mal escrito o la estructura aún no fue definida."
        ),
        "sugerencia": (
            f"Revisa la definición de la estructura y el acceso de la línea {entry.linea}. "
            "Usa objeto.miembro para estructuras y puntero->miembro para punteros."
        ),
    }

def _explain_preprocessor_error(entry):
    simbolo = entry.simbolo or "la directiva"
    return {
        "titulo": f"Error del preprocesador relacionado con '{simbolo}'",
        "explicacion": (
            "El problema ocurrió antes de la compilación principal, durante el manejo "
            "de #include, macros o directivas condicionales."
        ),
        "causa_probable": (
            "Puede faltar un archivo de cabecera, existir un #endif sin #if, una directiva "
            "mal escrita o una macro invocada con argumentos incorrectos."
        ),
        "sugerencia": (
            f"Revisa las directivas cercanas a la línea {entry.linea}. Confirma las rutas "
            "de #include y que cada #if/#ifdef tenga su #endif correspondiente."
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

def _explain_assignment_in_condition(entry, linea_codigo=""):
    if linea_codigo:
        linea_corregida = re.sub(
            r"(\b(?:if|while)\s*\([^)]*?)(?<![=!<>+\-*/%&|^])=(?!=)",
            r"\1==",
            linea_codigo,
            count=1,
        )
        sugerencia_dinamica = (
            f"Cambia la asignación '=' por una comparación '=='. Debería quedar así:\n"
            f"    {linea_corregida}"
        )
    else:
        sugerencia_dinamica = "Cambia el '=' por '==' si tu intención era comparar."

    return {
        "titulo": "Asignación '=' en lugar de comparación '=='",
        "explicacion": (
            "Estás usando un solo '=' dentro de una condición. Esto asigna un valor a la "
            "variable y luego evalúa ese valor, en lugar de comparar los dos operandos. "
            "El flujo del programa puede ser distinto al esperado."
        ),
        "causa_probable": (
            "Probablemente querías comparar valores con '==', pero escribiste una "
            "asignación con un solo '='."
        ),
        "sugerencia": sugerencia_dinamica,
    }

# Tabla de despacho: tipo_error -> handler. Fallback: _explain_desconocido
_HANDLERS = {
    "undeclared":           _explain_undeclared,
    "implicit_declaration": _explain_implicit_declaration,
    "redeclaration":        _explain_redeclaration,
    "expected_token":       _explain_expected_token,
    "type_mismatch":        _explain_type_mismatch,
    "wrong_arguments":      _explain_wrong_arguments,
    "return_error":         _explain_return_error,
    "unused_variable":      _explain_unused_variable,
    "division_by_zero":     _explain_division_by_zero,
    "pointer_error":        _explain_pointer_error,
    "format_mismatch":      _explain_format_mismatch,
    "unbalanced_delimiter": _explain_unbalanced_delimiter,
    "missing_return":       _explain_missing_return,
    "dangerous_conversion": _explain_dangerous_conversion,
    "uninitialized_variable": _explain_uninitialized_variable,
    "struct_access":        _explain_struct_access,
    "preprocessor_error":   _explain_preprocessor_error,
    "desconocido":          _explain_desconocido,
    "assignment_in_condition": _explain_assignment_in_condition,
}
