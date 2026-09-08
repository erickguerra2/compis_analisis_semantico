"""Casos de prueba mostrados en la pestaña "Pruebas" del IDE.

Cada caso es un programa Compiscript con el resultado que debe producir.
Se reutilizan en tests/test_demo_suite.py para la suite automática de pytest.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class DemoCase:
    id: str
    group: str
    title: str
    source: str
    expect_success: bool
    expect_rule: Optional[str] = None


DEMO_CASES: list[DemoCase] = [
    # --- Funciones ---
    DemoCase(
        id="funcion-llamada-valida",
        group="Funciones",
        title="Llamada con argumentos correctos",
        source=(
            "function sumar(a: integer, b: integer): integer {\n"
            "    return a + b;\n"
            "}\n"
            "let total: integer = sumar(5, 10);\n"
        ),
        expect_success=True,
    ),
    DemoCase(
        id="funcion-argumento-tipo-invalido",
        group="Funciones",
        title="Argumento de tipo incompatible",
        source=(
            "function sumar(a: integer, b: integer): integer {\n"
            "    return a + b;\n"
            "}\n"
            "sumar(5, true);\n"
        ),
        expect_success=False,
        expect_rule="llamada-tipo-argumento-invalido",
    ),
    DemoCase(
        id="funcion-retorno-no-garantizado",
        group="Funciones",
        title="Retorno no garantizado en todos los caminos",
        source=(
            "function ejemplo(x: integer): integer {\n"
            "    if (x > 0) {\n"
            "        return 1;\n"
            "    }\n"
            "}\n"
        ),
        expect_success=False,
        expect_rule="return-faltante-en-algun-camino",
    ),
    DemoCase(
        id="funcion-retorno-garantizado-if-else",
        group="Funciones",
        title="Retorno garantizado con if/else completo",
        source=(
            "function sign(n: integer): integer {\n"
            "    if (n < 0) {\n"
            "        return -1;\n"
            "    } else {\n"
            "        return 1;\n"
            "    }\n"
            "}\n"
        ),
        expect_success=True,
    ),
    # --- Símbolos y ámbitos ---
    DemoCase(
        id="simbolo-no-declarado",
        group="Símbolos y ámbitos",
        title="Uso de variable no declarada",
        source='print(persona);\n',
        expect_success=False,
        expect_rule="uso-variable-no-declarada",
    ),
    DemoCase(
        id="simbolo-duplicado-mismo-ambito",
        group="Símbolos y ámbitos",
        title="Redeclaración en el mismo ámbito",
        source="let x: integer = 1;\nlet x: integer = 2;\n",
        expect_success=False,
        expect_rule="redeclaracion-mismo-ambito",
    ),
    DemoCase(
        id="shadowing-en-bloque-interno",
        group="Símbolos y ámbitos",
        title="Shadowing válido en un bloque interno",
        source=(
            "let x: integer = 10;\n"
            "{\n"
            "    let x: integer = 20;\n"
            "    print(x);\n"
            "}\n"
        ),
        expect_success=True,
    ),
    # --- Tipos y control de flujo ---
    DemoCase(
        id="aritmetica-tipo-invalido",
        group="Tipos y control de flujo",
        title="Suma entre integer y boolean",
        source="let x: integer = 5 + true;\n",
        expect_success=False,
        expect_rule="operador-aritmetico-tipo-invalido",
    ),
    DemoCase(
        id="reasignacion-de-constante",
        group="Tipos y control de flujo",
        title="Reasignación de una constante",
        source="const PI: integer = 314;\nPI = 500;\n",
        expect_success=False,
        expect_rule="asignacion-a-constante",
    ),
    DemoCase(
        id="arreglo-tipos-mixtos",
        group="Tipos y control de flujo",
        title="Arreglo con tipos incompatibles",
        source='let x: integer[] = [1, "hola", 3];\n',
        expect_success=False,
        expect_rule="arreglo-tipos-inconsistentes",
    ),
    DemoCase(
        id="condicion-if-no-booleana",
        group="Tipos y control de flujo",
        title="Condición de if no booleana",
        source="if (10) {\n    print(1);\n}\n",
        expect_success=False,
        expect_rule="condicion-no-booleana",
    ),
    DemoCase(
        id="continue-fuera-de-bucle",
        group="Tipos y control de flujo",
        title="continue fuera de un bucle",
        source="continue;\n",
        expect_success=False,
        expect_rule="continue-fuera-de-bucle",
    ),
    DemoCase(
        id="switch-fallthrough-sin-break",
        group="Tipos y control de flujo",
        title="switch con fallthrough",
        source=(
            "let x: integer = 1;\n"
            "switch (x) {\n"
            "    case 1:\n"
            "        print(1);\n"
            "    case 2:\n"
            "        print(2);\n"
            "}\n"
        ),
        expect_success=True,
    ),
    DemoCase(
        id="codigo-muerto-tras-return",
        group="Tipos y control de flujo",
        title="Código inalcanzable tras un return",
        source='function f(): integer {\n    return 5;\n    print("hola");\n}\n',
        expect_success=False,
        expect_rule="codigo-muerto",
    ),
    # --- Clases y herencia ---
    DemoCase(
        id="herencia-miembros-heredados",
        group="Clases y herencia",
        title="Acceso a miembros heredados",
        source=(
            "class Animal {\n"
            '    function speak(): string { return "sound"; }\n'
            "}\n"
            "class Dog: Animal {\n"
            "    let age: integer = 2;\n"
            "}\n"
            "let dog: Dog = new Dog();\n"
            "let sound: string = dog.speak();\n"
        ),
        expect_success=True,
    ),
    DemoCase(
        id="subclase-asignable-a-superclase",
        group="Clases y herencia",
        title="Subclase asignable a la superclase, no al revés",
        source=(
            "class Animal {}\n"
            "class Dog: Animal {}\n"
            "let animal: Animal = new Dog();\n"
            "let dog: Dog = new Animal();\n"
        ),
        expect_success=False,
        expect_rule="asignacion-tipo-incompatible",
    ),
    DemoCase(
        id="this-fuera-de-metodo",
        group="Clases y herencia",
        title="this fuera de un método",
        source="print(this);\n",
        expect_success=False,
        expect_rule="this-fuera-de-metodo",
    ),
    DemoCase(
        id="constructor-numero-argumentos-invalido",
        group="Clases y herencia",
        title="Constructor con número de argumentos incorrecto",
        source=(
            "class Person {\n"
            "    function constructor(name: string) {}\n"
            "}\n"
            "let person: Person = new Person();\n"
        ),
        expect_success=False,
        expect_rule="llamada-numero-argumentos-invalido",
    ),
    # --- Demostración rápida ---
    DemoCase(
        id="demo-rapida-programa-valido",
        group="Demostración rápida",
        title="Programa correcto de principio a fin",
        source=(
            "let numero: integer = 10;\n"
            "let resultado: integer = numero + 5;\n"
            "if (resultado > 10) {\n"
            "    print(resultado);\n"
            "}\n"
        ),
        expect_success=True,
    ),
    DemoCase(
        id="demo-rapida-error-semantico",
        group="Demostración rápida",
        title="Mismo programa, con un error semántico",
        source=(
            "let numero: integer = true;\n"
            "let resultado: integer = numero + 5;\n"
            "if (resultado > 10) {\n"
            "    print(resultado);\n"
            "}\n"
        ),
        expect_success=False,
        expect_rule="asignacion-tipo-incompatible",
    ),
]
