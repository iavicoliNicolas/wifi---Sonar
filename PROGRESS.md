# PROGRESS

## Estado actual
Fase: 1 — Núcleo de señal · Última tarea completada: T-05 · Próxima: T-06

## Inventario del repo (2026-10-22)

Diagnóstico de `iavicoliNicolas/wifi---Sonar` en el commit inicial `c5361e0`.

| Área | Hallazgo |
| --- | --- |
| Árbol | Un solo archivo: `README.md` (título `# wifi---Sonar`). No hay código, tests, docs ni config. |
| Lenguaje | Ninguno en el repo. |
| Dependencias | No hay `pyproject.toml`, `requirements*.txt`, `package.json`, lockfile ni `Makefile`. |
| Tests | No hay suite ni runner. |
| Lint / formato | No hay configuración. |
| CI | No hay `.github/workflows` ni plantilla de PR. |
| Entorno | No hay `.gitignore` ni `.env.example`. |
| Producto | No hay fuentes CSI, pipeline, API ni panel. Nada se puede ejecutar. |
| Git | Historial de un commit en `main`. Working tree limpio al auditar. |

Qué funciona: el repositorio clona y el remoto responde.

Qué no funciona: no hay programa, tests ni comando de desarrollo. El README no describe el producto.

El backlog de `DEV_LOOP.md` no se renombró. Ninguna tarea posterior a T-00 estaba hecha: no había código que marcar como completo.

## Plan de adaptación

El repo es greenfield. Se aplica el backlog tal cual, con las responsabilidades de la sección 3 y el stack fijado en `DECISIONS.md` (D-001, D-002).

- El desarrollo no espera hardware. El simulador (T-02) es la fuente hasta la Fase 4.
- T-01 crea el entorno (pyproject, Makefile, `.gitignore`, `.env.example`) y el primer test que solo verifica que el paquete importa.
- A partir de T-02 el código vive en `wifi_sonar/` y los tests en `tests/`.
- FastAPI entra en T-10. El panel entra en T-14. No se adelantan esas piezas.
- Límites de la sección 1 quedan como restricción de producto (D-003).

## Log

### 2026-10-22 T-00 — Auditoría del repo
- Qué se hizo: inventario del árbol, del historial y de lo que falta. Se dejó el backlog operativo en el repo, con T-00 marcada, más el diagnóstico y las decisiones de stack y layout. No se escribió código de producto.
- Archivos tocados: `DEV_LOOP.md`, `PROGRESS.md`, `DECISIONS.md`, `README.md`.
- Tests agregados: ninguno. No existe runner; armar pytest sería T-01. La verificación de esta tarea es el inventario de arriba (un archivo de producto, cero dependencias, cero tests).
- Problemas / deuda: README sigue siendo un puntero corto; la guía de uso queda para T-24. Sin `.gitignore` hasta T-01.
- Siguiente paso sugerido: T-01 — entorno reproducible (`pyproject.toml`, `Makefile` con `test` y `lint`, `.gitignore`, `.env.example`) de modo que un clon limpio corra la suite con un comando.

### 2026-10-22 T-01 — Entorno reproducible
- Qué se hizo: paquete instalable `wifi_sonar` 0.0.1, `pyproject.toml` (setuptools, extra `dev` con pytest y ruff), `Makefile` (`dev`, `test`, `lint`, `format`), `.gitignore` y `.env.example`. `make test` crea `.venv` si no existe. Sin NumPy ni pre-commit (D-005).
- Archivos tocados: `pyproject.toml`, `Makefile`, `.gitignore`, `.env.example`, `wifi_sonar/__init__.py`, `tests/test_package.py`, `README.md`, `DEV_LOOP.md`, `DECISIONS.md`, `PROGRESS.md`.
- Tests agregados: `tests/test_package.py` comprueba que el paquete importa y que `__version__` es `0.0.1`.
- Problemas / deuda: `.env` todavía no lo lee nadie. El README de uso completo sigue siendo T-24.
- Siguiente paso sugerido: T-02 — `CSIFrame` y `SimulatedSource` determinista por seed, con un test de que los eventos cambian la varianza esperada.

### 2026-10-23 T-02 — Modelo de datos y simulador de CSI
- Qué se hizo: `CSIFrame` (timestamp, rssi, amplitudes, phases, node_id) y `SimulatedSource` determinista por seed. ~52 subportadoras, ruido gaussiano, deriva lenta y eventos `enter` / `walk` / `still` / `leave`. NumPy queda como dependencia de arreglos (D-006). `make` toca `.venv/bin/pytest` después de instalar, así un cambio de `pyproject.toml` no deja el target vencido para siempre.
- Archivos tocados: `wifi_sonar/sources/frame.py`, `wifi_sonar/sources/simulated.py`, `wifi_sonar/sources/__init__.py`, `wifi_sonar/__init__.py`, `tests/test_simulated.py`, `pyproject.toml`, `DECISIONS.md`, `DEV_LOOP.md`, `PROGRESS.md`.
- Tests agregados: forma del frame, repetibilidad con la misma semilla, y varianza vacío < quietud < caminata, además de un tramo de caminata más ruidoso que el cuarto vacío que lo rodea.
- Problemas / deuda: el simulador no modela multitrayecto geométrico; alcanza para el pipeline sintético. SciPy sigue afuera.
- Siguiente paso sugerido: T-03 — interfaz `CSISource` y `ReplaySource` desde archivo.

### 2026-10-23 T-03 — Interfaz CSISource y replay
- Qué se hizo: protocolo `CSISource.frames()`, `collect()` como ingreso único, y `ReplaySource` para `.jsonl` y `.csv` a velocidad real o acelerada (`speed <= 0` no espera).
- Archivos tocados: `wifi_sonar/sources/base.py`, `wifi_sonar/sources/replay.py`, `wifi_sonar/pipeline/__init__.py`, `tests/test_replay.py`, `DECISIONS.md`, `DEV_LOOP.md`, `PROGRESS.md`.
- Tests agregados: el mismo `collect()` lee el simulador y el replay JSONL/CSV con los mismos frames; el replay acelerado duerme una fracción del delta grabado.
- Problemas / deuda: una línea corrupta aborta el archivo. El parser tolerante queda para el adaptador ESP32 (T-19).
- Siguiente paso sugerido: T-04 — preprocesamiento (Hampel, huecos, normalización, subportadoras nulas).

### 2026-10-23 T-04 — Preprocesamiento
- Qué se hizo: `preprocess()` rellena NaN, interpola huecos de tiempo, aplica Hampel por subportadora, descarta subportadoras nulas y normaliza por la mediana absoluta (D-008).
- Archivos tocados: `wifi_sonar/pipeline/preprocess.py`, `tests/test_preprocess.py`, `DECISIONS.md`, `DEV_LOOP.md`, `PROGRESS.md`.
- Tests agregados: un pico de 1000 deja de dominar la varianza; un NaN queda entre sus vecinos; un hueco inserta un frame; una subportadora en cero se va y dos escalas distintas convergen; una traza del simulador sigue siendo finita.
- Problemas / deuda: el Hampel es un lazo en Python. Si las trazas largas se ponen lentas, se vectoriza.
- Siguiente paso sugerido: T-05 — features por ventana (varianza, MAD, energía de movimiento y de respiración).

### 2026-10-23 T-05 — Features por ventana
- Qué se hizo: `extract_features()` calcula varianza, media de diferencias absolutas y energía de movimiento (2 s, 0,5–5 Hz) y de respiración (8 s, 0,1–0,5 Hz) con un periodograma (D-009).
- Archivos tocados: `wifi_sonar/pipeline/features.py`, `tests/test_features.py`, `DECISIONS.md`, `DEV_LOOP.md`, `PROGRESS.md`.
- Tests agregados: una constante da varianza 0; una alternancia 0/1 da varianza 0,25; 2 Hz domina movimiento y 0,25 Hz domina respiración; la caminata del simulador sube la energía de movimiento frente al cuarto vacío.
- Problemas / deuda: no hay PCA. No hizo falta para separar las bandas.
- Siguiente paso sugerido: T-06 — calibración de línea base con el cuarto vacío.
