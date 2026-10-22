# PROGRESS

## Estado actual
Fase: 2 — Servicio y tiempo real · Última tarea completada: T-09 · Próxima: T-10

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
- Qué se hizo: `pyproject.toml` con setuptools, extras de desarrollo (pytest y ruff) y sin dependencias de runtime todavía. `Makefile` con `dev`, `test` y `lint`. `.gitignore` y `.env.example`. El paquete `wifi_sonar` expone `__version__`.
- Archivos tocados: `pyproject.toml`, `Makefile`, `.gitignore`, `.env.example`, `wifi_sonar/__init__.py`, `tests/test_package.py`, `README.md`, `DECISIONS.md`, `PROGRESS.md`, `DEV_LOOP.md`.
- Tests agregados: `tests/test_package.py` (el paquete importa y la versión es 0.1.0).
- Problemas / deuda: no hay pre-commit (D-005). NumPy entra en T-02.
- Siguiente paso sugerido: T-02 — `CSIFrame` y `SimulatedSource` determinista.

### 2026-10-22 T-02 — Modelo de datos y simulador de CSI
- Qué se hizo: `CSIFrame` (timestamp, rssi, amplitudes, phases opcionales, node_id). `SimulatedSource` con 52 subportadoras, ruido gaussiano, deriva lenta, subportadora nula y eventos `enter`, `walk`, `still` y `leave`. La semilla fija la secuencia. NumPy pasa a ser dependencia de runtime.
- Archivos tocados: `wifi_sonar/models.py`, `wifi_sonar/sources/simulated.py`, `wifi_sonar/sources/__init__.py`, `tests/test_simulator.py`, `pyproject.toml`, `PROGRESS.md`, `DEV_LOOP.md`.
- Tests agregados: determinismo y forma del frame; la varianza temporal de caminata, quietud y ráfaga queda por encima del cuarto vacío, y la quietud queda por debajo de la caminata.
- Problemas / deuda: el generador infinito (`duration_s=None`) todavía no tiene test propio; lo usa el servidor más adelante.
- Siguiente paso sugerido: T-03 — interfaz `CSISource` y `ReplaySource`.

### 2026-10-22 T-03 — Interfaz CSISource y replay
- Qué se hizo: protocolo `CSISource` y helper `read_frames`. `ReplaySource` lee `.jsonl` y `.csv`, infiere la tasa de muestreo y reproduce a velocidad real o acelerada (`speed=0` no duerme). El simulador ya cumple la interfaz, así que el mismo helper consume las dos fuentes.
- Archivos tocados: `wifi_sonar/sources/base.py`, `wifi_sonar/sources/replay.py`, `wifi_sonar/sources/__init__.py`, `tests/test_replay.py`, `PROGRESS.md`, `DEV_LOOP.md`, `DECISIONS.md`.
- Tests agregados: roundtrip simulador → jsonl/csv → replay; el sleeper solo corre con `speed>0`; una línea JSONL inválida se rechaza.
- Problemas / deuda: ninguna.
- Siguiente paso sugerido: T-04 — preprocesamiento (Hampel, huecos, nulas, normalización).

### 2026-10-22 T-04 — Preprocesamiento
- Qué se hizo: `preprocess` rellena huecos sobre una grilla uniforme, aplica Hampel por subportadora, descarta subportadoras nulas y normaliza por la mediana de amplitud.
- Archivos tocados: `wifi_sonar/pipeline/preprocess.py`, `wifi_sonar/pipeline/__init__.py`, `tests/test_preprocess.py`, `PROGRESS.md`, `DEV_LOOP.md`.
- Tests agregados: un pico aislado desaparece y la traza queda finita; un paquete faltante se interpola; la subportadora en cero se va y la mediana normalizada queda en 1.
- Problemas / deuda: la normalización es por lote, no causal muestra a muestra. El motor la va a aplicar sobre la ventana reciente.
- Siguiente paso sugerido: T-05 — features por ventana.

### 2026-10-22 T-05 — Extracción de features por ventana
- Qué se hizo: ventanas de 2 s con paso de 0.5 s para varianza y media de diferencias absolutas. La energía de las bandas de movimiento (0.5–5 Hz) y respiración (0.1–0.5 Hz) sale de un periodograma de Hann sobre 10 s, que es lo mínimo para separarlas. PCA opcional por ventana vía SVD.
- Archivos tocados: `wifi_sonar/pipeline/features.py`, `tests/test_features.py`, `DECISIONS.md`, `PROGRESS.md`, `DEV_LOOP.md`.
- Tests agregados: una constante no tiene energía; un tono de 2 Hz cae en la banda de movimiento y uno de 0.25 Hz en la de respiración; PCA de un componente conserva el tono compartido.
- Problemas / deuda: ninguna.
- Siguiente paso sugerido: T-06 — calibración de línea base.

### 2026-10-22 T-06 — Calibración de línea base
- Qué se hizo: `calibrate(source, seconds)` consume el cuarto vacío, calcula media y desvío de cada feature y guarda umbrales `media + k·σ` en JSON. El tiempo es el de los frames, así que el simulador no espera en tiempo real.
- Archivos tocados: `wifi_sonar/detect/calibrate.py`, `wifi_sonar/detect/__init__.py`, `tests/test_calibrate.py`, `PROGRESS.md`, `DEV_LOOP.md`.
- Tests agregados: la calibración de 20 s persiste y se recarga; una captura más corta que la ventana espectral se rechaza.
- Problemas / deuda: ninguna.
- Siguiente paso sugerido: T-07 — detector de movimiento con histéresis.

### 2026-10-22 T-07 — Detector de movimiento
- Qué se hizo: el score compara la energía de la banda de movimiento contra la calibración. Histéresis (0.75 / 0.40) y 1 s de duración mínima. En el simulador, 20/20 caminatas y ningún falso positivo en 10 minutos de ruido con k = 8. La búsqueda del nodo al interpolar dejó de armar una matriz de N×N.
- Archivos tocados: `wifi_sonar/detect/motion.py`, `wifi_sonar/detect/calibrate.py`, `wifi_sonar/pipeline/preprocess.py`, `tests/test_motion.py`, `tests/test_preprocess.py`, `DECISIONS.md`, `PROGRESS.md`, `DEV_LOOP.md`.
- Tests agregados: un pico no engancha y un score sostenido sí; recall ≥ 95 % y ≤ 1 falso positivo en 10 minutos.
- Problemas / deuda: ninguna.
- Siguiente paso sugerido: T-08 — detector de presencia quieta y máquina de estados.

### 2026-10-22 T-08 — Detector de presencia
- Qué se hizo: máquina de estados `vacío | presencia | movimiento`. El movimiento del detector anterior gana. La presencia quieta exige que la banda de respiración supere el umbral durante al menos 3 s. `analyze_frames` une preprocesamiento, features y los dos detectores.
- Archivos tocados: `wifi_sonar/detect/presence.py`, `tests/test_presence.py`, `PROGRESS.md`, `DEV_LOOP.md`.
- Tests agregados: transiciones de la máquina (un pico no alcanza, la quietud sostenida sí, el movimiento la interrumpe y al bajar vuelve a vacío); en el simulador un `still` termina en presencia y un `walk` en movimiento.
- Problemas / deuda: ninguna.
- Siguiente paso sugerido: T-09 — `make eval` con precisión, recall y latencia.

### 2026-10-22 T-09 — Métricas de evaluación
- Qué se hizo: `make eval` corre caminatas, quietud y cuarto vacío sobre el simulador. Imprime precisión, recall y latencia mediana, y guarda la tabla en `docs/eval.md`.
- Archivos tocados: `wifi_sonar/eval/report.py`, `wifi_sonar/eval/__main__.py`, `tests/test_eval.py`, `Makefile`, `docs/eval.md`, `README.md`, `PROGRESS.md`, `DEV_LOOP.md`.
- Tests agregados: la tabla cumple recall de caminata ≥ 95 %, quietud perfecta en el escenario y como máximo un falso positivo en el cuarto vacío.
- Problemas / deuda: la latencia de la quietud ronda los 11 s porque la banda de respiración mira 10 s de espectro. Está escrito en el reporte.
- Siguiente paso sugerido: T-10 — API HTTP.
