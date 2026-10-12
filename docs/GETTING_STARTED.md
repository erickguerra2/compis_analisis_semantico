# Instalación y ejecución

## Requisitos

- Python 3.10 o posterior.
- Java disponible en `PATH` para ejecutar ANTLR.
- El archivo `antlr-4.13.1-complete.jar`, incluido en la raíz.

## Preparación local

Desde la raíz del repositorio:

```bash
python -m venv .venv
```

Activa el entorno en Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

O en Linux/macOS:

```bash
source .venv/bin/activate
```

Instala dependencias y genera el parser con Visitor:

```bash
python -m pip install -r requirements-dev.txt
cd program
java -jar ../antlr-4.13.1-complete.jar -Dlanguage=Python3 -visitor -o generated Compiscript.g4
cd ..
```

## Compilar un programa

```bash
python program/Driver.py program/program.cps
```

El driver ejecuta análisis léxico, sintáctico, semántico y generación de código intermedio. Si el
programa es válido imprime el TAC: primero la sección `.data` con los literales string y después
la sección `.code` con una unidad por `main`, función y método:

```text
.data
    .str0: "Hello, Compiscript!"
    ...
.code
    begin_func main
    PI = 314
    greeting = .str0
    ...
    end_func main
    begin_func makeAdder
    t0 = x + 1
    return t0
    end_func makeAdder
```

Si hay errores semánticos los imprime en stderr con el formato `linea:columna: regla: mensaje`
y termina con código 1, sin generar TAC. Los errores léxicos y sintácticos los reporta ANTLR.

Para guardar el resultado en un archivo:

```bash
python program/Driver.py program/program.cps > program.tac
```

## Ejecutar las pruebas

```bash
python -m pytest -q
```

La suite debe terminar sin fallos antes de subir cambios a `main`; el CI de GitHub Actions corre
la misma suite en cada push. Para correr solo las pruebas del código intermedio:

```bash
python -m pytest -q tests/test_tac_expressions.py tests/test_tac_control_flow.py \
  tests/test_tac_functions.py tests/test_tac_classes.py tests/test_tac_arrays.py \
  tests/test_tac_integration.py
```

## Ejecutar el IDE

```bash
python -m ide.app
```

Abre `http://127.0.0.1:5000`. El botón **Compilar** y `Ctrl+Enter` ejecutan todas las fases.
CodeMirror se carga desde cdnjs; sin Internet el campo sigue siendo un `textarea`, pero no tendrá
resaltado ni las mejoras del editor.

| Pestaña | Contenido |
|---|---|
| Errores | errores léxicos, sintácticos y semánticos con línea y columna |
| Símbolos | tabla de símbolos con tipo, ámbito, `offset`, `size`, `label`, `storage` y `depth`, y los registros de activación de cada función |
| Árbol | árbol sintáctico |
| TAC | código de tres direcciones y literales string del programa |
| Pruebas | batería de casos de `ide/demo_cases.py`, con un botón **Cargar** para reproducir cada uno |

La lista de la pestaña Pruebas también se valida automáticamente en `tests/test_demo_suite.py`.

También se puede probar el endpoint directamente:

```bash
curl -X POST http://127.0.0.1:5000/compile \
  -H "Content-Type: application/json" \
  -d '{"source":"let x = 5 + 3 * 2; print(x);"}'
```

La respuesta incluye, entre otros campos, `"tac": ["begin_func main", "t0 = 3 * 2", ...]`. El
contrato completo está en [ARCHITECTURE.md](ARCHITECTURE.md).

## Entorno Docker base

La imagen del curso se mantiene disponible para generar el parser:

```bash
docker build --rm . -t csp-image
docker run --rm -ti -v "$(pwd)/program:/program" csp-image
```

Ese contenedor solo monta `program/`, y el driver necesita también `semantic/`, `symtable/`,
`tac/` y `codegen/`; por eso el compilador completo se ejecuta desde la raíz del repositorio
como se describe arriba.
