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
    ├── anotaciones por nodo: Annotation(scope, type, symbol)
    └── errores semánticos ──► si hay alguno, la compilación termina aquí
    │
    ▼
TacGenerator (Visitor + mixins)
    ├── MemoryLayout: offsets, tamaños, etiquetas y registros de activación
    ├── Emitter: cuádruplos, temporales, etiquetas y literales string
    └── emite main y después la cola de funciones y métodos pendientes
    │
    ▼
TAC (Emitter.lines() / Emitter.dump())
```

ANTLR genera `CompiscriptLexer`, `CompiscriptParser` y `CompiscriptVisitor` desde
`program/Compiscript.g4`. Los archivos generados se excluyen de Git y deben regenerarse al
preparar el proyecto.

Cada fase solo corre si la anterior terminó sin errores: con errores léxicos o sintácticos no se
analiza un árbol recuperado, y con errores semánticos no se genera TAC.

## Componentes

### Análisis

- `program/Compiscript.g4`: gramática ejecutable del lenguaje.
- `semantic/types.py`: tipos primitivos, arreglos, funciones y clases, reglas de compatibilidad y
  `size_of` (4 bytes por valor o referencia).
- `semantic/analyzer.py`: Visitor que calcula el tipo de las expresiones, valida las reglas y
  administra el contexto de bucles, switches, funciones, clases y `this`. Además guarda en
  `analyzer.annotations` una `Annotation(scope, type, symbol)` por nodo visitado, con clave
  `id(ctx)`; así el generador conoce el ámbito, el tipo y el símbolo resuelto de cada
  expresión, declaración y sufijo (`.campo`, `[i]`, `(...)`) sin repetir el análisis.
- `semantic/errors.py`: errores con línea, columna, mensaje y regla; el análisis acumula errores
  en vez de detenerse en el primero.

### Tabla de símbolos y memoria

- `symtable/symbol.py`, `scope.py`, `symbol_table.py`: símbolos, ámbitos y resolución léxica. Se
  conservan todos los ámbitos visitados y los miembros se resuelven subiendo la cadena de
  herencia. Cada `Symbol` tiene además `offset`, `size`, `label`, `storage` (`global`, `local`,
  `param`, `field`) y `depth`.
- `symtable/activation.py`: `MemoryLayout` llena esos campos y crea un `ActivationRecord` por
  unidad de código (dirección de retorno, enlace de control, enlace de acceso, parámetros,
  locales y temporales). También calcula los offsets de campos de cada clase con los heredados
  primero (`analyzer.class_layouts`).

### Generación de código intermedio

- `tac/quad.py`: `Quad` y los operandos `Var`, `Temp`, `Const`, `StrLit` y `Label`. `str(quad)`
  produce el texto canónico de cada instrucción.
- `tac/temps.py`: pool de temporales que entrega siempre el menor id libre y registra el máximo
  de temporales vivos por unidad.
- `tac/emitter.py`: `Emitter` acumula los cuádruplos, crea etiquetas globales, interna los
  literales string y separa las unidades con `begin_func`/`end_func`.
- `codegen/generator.py`: `TacGenerator`, que combina un mixin por área del lenguaje. Mantiene
  `loop_stack` (destinos de `break`/`continue`), `try_depth` (handlers abiertos), `pending`
  (funciones y métodos por emitir) y el renombrado de variables homónimas (`x`, `x_1`, ...).

| Mixin | Archivo | Construcciones |
|---|---|---|
| `ExpressionsMixin` | `codegen/expressions.py` | expresiones, declaraciones, asignaciones, `print` y la cadena de sufijos de `leftHandSide` |
| `ControlFlowMixin` | `codegen/control_flow.py` | `if`, `while`, `do-while`, `for`, `switch`, `break`, `continue`, `try/catch` |
| `FunctionsMixin` | `codegen/functions.py` | declaración de funciones, llamadas y `return` |
| `ClassesMixin` | `codegen/classes.py` | clases, `new`, `this`, campos y llamadas a métodos |
| `ArraysMixin` | `codegen/arrays.py` | literales de arreglo, índices con `bounds` y `foreach` |

`visitLeftHandSide` recorre los sufijos de izquierda a derecha y delega en ganchos
(`gen_function_call`, `gen_method_call`, `gen_index`, `gen_property`, `gen_new`, `gen_this`,
`gen_array_literal`, `gen_index_store`, `gen_property_store`) que implementa cada mixin. Un
`.m` seguido de `(...)` se traduce como llamada a método con el receptor como parámetro 0.

El formato de cada instrucción y el patrón de traducción de cada construcción están en
[INTERMEDIATE_LANGUAGE.md](INTERMEDIATE_LANGUAGE.md).

### Puntos de entrada

- `program/Driver.py`: compilador de línea de comandos. Ejecuta las cuatro fases sobre un archivo
  `.cps`, imprime el TAC con su sección de datos o los errores en stderr (código de salida 1).
- `ide/app.py`: aplicación Flask. `POST /compile` coordina las fases y serializa errores,
  símbolos, árbol, TAC y registros de activación a JSON.
- `ide/templates` y `ide/static`: cliente de una sola página con CodeMirror y pestañas de
  Errores, Símbolos, Árbol, TAC y Pruebas. No requiere un proceso de build de frontend.
- `tests/`: pruebas por categoría semántica, por área del TAC (`test_tac_*.py`), de memoria
  (`test_symtable.py`), del IDE y de integración de punta a punta
  (`test_tac_integration.py`). `tests/helpers.py` expone `compile_source(source)`, que devuelve
  errores, líneas de TAC, emisor, analizador y árbol.

## Ámbitos y clases

Cada bloque, función y clase abre un `Scope` enlazado con su padre. La búsqueda de nombres
recorre esos padres, lo que permite shadowing y funciones anidadas. Los miembros de una clase se
registran en una primera pasada y sus cuerpos/inicializadores se analizan en una segunda; así un
método puede referirse a un miembro declarado después. La búsqueda de propiedades consulta
únicamente el ámbito de la clase y luego sus bases, sin confundir miembros con variables
léxicas.

En el TAC una clase no emite código donde se declara: sus métodos se emiten como unidades
`Clase.metodo` después de `main`, y `new` emite los inicializadores de campos y la llamada al
constructor en el sitio de la instanciación.

## Contrato de `POST /compile`

Entrada:

```json
{"source": "let answer: integer = 42;"}
```

| Campo | Contenido |
|---|---|
| `success` | `true` si no hubo errores léxicos, sintácticos ni semánticos |
| `errors` | lista con `line`, `column`, `message`, `rule` y `category` (`lexico`, `sintactico` o `semantico`) |
| `symbols` | símbolos de todos los ámbitos, con `offset`, `size`, `label`, `storage` y `depth` |
| `tree` | árbol sintáctico para la pestaña Árbol |
| `tac` | líneas de `Emitter.lines()`; lista vacía si hubo errores |
| `strings` | literales string (`.str0` → texto) |
| `activationRecords` | un registro por unidad, con sus slots, parámetros, locales y temporales |
| `tacError` | mensaje si la generación lanzó `NotImplementedError`; `null` en caso normal |
