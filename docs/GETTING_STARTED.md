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

## Ejecutar las pruebas

```bash
python -m pytest -q
```

La suite actual contiene 91 pruebas. Debe terminar sin fallos antes de abrir un PR.

## Ejecutar el IDE

```bash
python -m ide.app
```

Abre `http://127.0.0.1:5000`. El botón **Compilar** y `Ctrl+Enter` ejecutan lexer, parser y
análisis semántico. CodeMirror se carga desde cdnjs; sin Internet el campo sigue siendo un
`textarea`, pero no tendrá resaltado ni las mejoras del editor.

La pestaña **Pruebas** corre en vivo, dentro del propio IDE, la batería de casos definida en
`ide/demo_cases.py` y muestra cuáles pasan o fallan, con un botón **Cargar** para reproducir
cualquier caso al instante. Esa misma lista de casos se valida automáticamente vía
`tests/test_demo_suite.py`.

También se puede probar el endpoint directamente:

```bash
curl -X POST http://127.0.0.1:5000/compile \
  -H "Content-Type: application/json" \
  -d '{"source":"print(unknown);"}'
```

## Entorno Docker base

La verificación original del curso se mantiene disponible:

```bash
docker build --rm . -t csp-image
docker run --rm -ti -v "$(pwd)/program:/program" csp-image
```

Dentro del contenedor se puede generar el parser y ejecutar `Driver.py`. Ese driver comprueba la
sintaxis; la integración completa de las tres fases está en `ide/app.py`.
