# Arquitectura de Compiscript

## Flujo de compilación

```text
Código fuente
    │
    ▼
CompiscriptLexer ── errores léxicos
    │ tokens
    ▼
CompiscriptParser ── errores sintácticos ── árbol ANTLR
    │                                      │
    ▼                                      └── JSON para el IDE
SemanticAnalyzer (Visitor)
    ├── sistema de tipos
    ├── tabla de símbolos y ámbitos
    └── errores semánticos
```

ANTLR genera `CompiscriptLexer`, `CompiscriptParser` y `CompiscriptVisitor` desde
`program/Compiscript.g4`. Los archivos generados se excluyen de Git y deben regenerarse al
preparar el proyecto.

## Componentes

- `program/Compiscript.g4`: gramática ejecutable del lenguaje. `Compiscript.bnf` es una
  referencia legible, no una entrada del build.
- `semantic/types.py`: representación de tipos primitivos, arreglos, funciones y clases, junto
  con las reglas de compatibilidad.
- `semantic/analyzer.py`: Visitor que calcula el tipo de las expresiones, valida las reglas y
  administra el contexto de bucles, switches, funciones, clases y `this`.
- `semantic/errors.py`: errores con línea, columna, mensaje y regla; el análisis acumula errores
  en vez de detenerse en el primero.
- `symtable/`: símbolos, ámbitos y resolución léxica. Conserva los ámbitos visitados para que el
  IDE pueda inspeccionarlos y resuelve miembros subiendo la cadena de herencia.
- `ide/app.py`: aplicación Flask. `POST /compile` coordina las tres fases y serializa errores,
  símbolos y árbol a JSON.
- `ide/templates` y `ide/static`: cliente de una sola página con CodeMirror y paneles de
  resultados. No requiere un proceso de build de frontend.
- `tests/`: pruebas unitarias y de integración separadas por categoría semántica e IDE.

## Ámbitos y clases

Cada bloque, función y clase abre un `Scope` enlazado con su padre. La búsqueda de nombres
recorre esos padres, lo que permite shadowing y closures. Los miembros de una clase se registran
en una primera pasada y sus cuerpos/inicializadores se analizan en una segunda; así un método
puede referirse a un miembro declarado después. La búsqueda de propiedades consulta únicamente
el ámbito de la clase y luego sus bases, sin confundir miembros con variables léxicas.

## Contrato de `POST /compile`

Entrada:

```json
{"source": "let answer: integer = 42;"}
```

La respuesta contiene `success`, `errors`, `symbols` y `tree`. Cada error incluye `line`,
`column`, `message`, `rule` y `category` (`lexico`, `sintactico` o `semantico`). Si hay errores
léxicos o sintácticos no se ejecuta el análisis semántico sobre un árbol recuperado.
