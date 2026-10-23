# PROGRESS

## Estado actual
Fase: 2 — Servicio y tiempo real · Última tarea completada: T-13 · Próxima: T-14

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

### 2026-10-23 T-06 — Calibración de línea base
- Qué se hizo: `calibrate(source, seconds)` resume media, desvío y umbral media + k·σ de las cuatro features. `save_calibration` / `load_calibration` persisten JSON (D-010). `observe()` es el camino común fuente → preprocess → features.
- Archivos tocados: `wifi_sonar/detect/calibrate.py`, `wifi_sonar/detect/observe.py`, `wifi_sonar/detect/__init__.py`, `tests/test_calibrate.py`, `DECISIONS.md`, `DEV_LOOP.md`, `PROGRESS.md`.
- Tests agregados: umbrales por encima de la media, ida y vuelta por archivo, y la misma semilla produce la misma calibración.
- Problemas / deuda: asume cuarto vacío durante la captura. No hay todavía asistente en el panel (T-16).
- Siguiente paso sugerido: T-07 — detector de movimiento con histéresis.

### 2026-10-23 T-07 — Detector de movimiento
- Qué se hizo: `MotionDetector` enciende con histéresis y 0,5 s de permanencia cuando la energía de movimiento supera el umbral y a la banda de respiración. Score en 0–1 (D-011). El Hampel quedó vectorizado para poder evaluar 10 min de ruido.
- Archivos tocados: `wifi_sonar/detect/motion.py`, `wifi_sonar/detect/__init__.py`, `wifi_sonar/pipeline/preprocess.py`, `tests/test_detect.py`, `DECISIONS.md`, `DEV_LOOP.md`, `PROGRESS.md`.
- Tests agregados: 20 caminatas, al menos 19 detectadas y el detector se apaga entre ellas; 10 min de cuarto vacío con como máximo un falso positivo; el score queda en 0–1.
- Problemas / deuda: los umbrales salen del simulador. Con CSI real hay que recalibrar k.
- Siguiente paso sugerido: T-08 — presencia quieta y estados vacío / presencia / movimiento.

### 2026-10-23 T-08 — Detector de presencia
- Qué se hizo: `PresenceDetector` emite `empty`, `presence` o `motion`. La presencia exige 2 s de banda de respiración sobre el umbral y cede si hay movimiento (D-012).
- Archivos tocados: `wifi_sonar/detect/presence.py`, `wifi_sonar/detect/__init__.py`, `tests/test_presence.py`, `DECISIONS.md`, `DEV_LOOP.md`, `PROGRESS.md`.
- Tests agregados: cuarto vacío se queda en vacío; quietud termina en presencia y no marca movimiento; caminata termina en movimiento.
- Problemas / deuda: la respiración del simulador es un tono de 0,25 Hz, no un modelo fisiológico.
- Siguiente paso sugerido: T-09 — `make eval` con precisión, recall y latencia.

### 2026-10-23 T-09 — Métricas de evaluación
- Qué se hizo: `python -m wifi_sonar.eval` y `make eval` imprimen precisión, recall y latencia de movimiento y presencia, y guardan la tabla en `docs/eval.md` (D-013).
- Archivos tocados: `wifi_sonar/eval.py`, `tests/test_eval.py`, `Makefile`, `docs/eval.md`, `README.md`, `DECISIONS.md`, `DEV_LOOP.md`, `PROGRESS.md`.
- Tests agregados: el reporte tiene las dos clases con precisión y recall de al menos 0,95.
- Problemas / deuda: el número es del simulador, no de una grabación etiquetada de una casa real.
- Siguiente paso sugerido: T-10 — API HTTP.

### 2026-10-23 T-10 — API HTTP
- Qué se hizo: FastAPI con `/status`, `/calibrate`, `/config`, `/history` y OpenAPI generado. `SonarState` corre el detector sobre una fuente y guarda los cambios de estado en memoria (D-014).
- Archivos tocados: `wifi_sonar/api/app.py`, `wifi_sonar/api/__init__.py`, `wifi_sonar/runtime.py`, `tests/test_api.py`, `pyproject.toml`, `DECISIONS.md`, `DEV_LOOP.md`, `PROGRESS.md`.
- Tests agregados: OpenAPI lista los cuatro caminos; el config rechaza histéresis fuera de rango; calibrar y correr una caminata deja `/status` y `/history` en movimiento.
- Problemas / deuda: el historial muere con el proceso. `TestClient` avisa que Starlette quiere `httpx2`; los tests pasan con `httpx`.
- Siguiente paso sugerido: T-11 — WebSocket con descarte de frames viejos.

### 2026-10-23 T-11 — Streaming por WebSocket
- Qué se hizo: `/ws` reenvía snapshots. `FrameHub` descarta el frame más viejo si la cola está llena. `follow()` arma ~10 muestras por segundo simulado con estado, score y 8 bins de amplitud (D-015).
- Archivos tocados: `wifi_sonar/api/stream.py`, `wifi_sonar/api/app.py`, `tests/test_stream.py`, `DECISIONS.md`, `DEV_LOOP.md`, `PROGRESS.md`.
- Tests agregados: la cola de 2 se queda con los dos últimos; el stream de una caminata termina en movimiento; el cliente WebSocket recibe estado, score y amplitudes coherentes.
- Problemas / deuda: el productor en vivo (hilo que lee la fuente todo el tiempo) llega con el servicio de T-22. Hoy el test empuja los snapshots.
- Siguiente paso sugerido: T-12 — SQLite para eventos, calibraciones y config.

### 2026-10-23 T-12 — Persistencia local
- Qué se hizo: `Store` abre SQLite, crea el esquema 1 y guarda eventos, calibraciones y config. `SonarState` recarga eso al arrancar y `purge` borra eventos viejos (D-016).
- Archivos tocados: `wifi_sonar/storage/db.py`, `wifi_sonar/storage/__init__.py`, `wifi_sonar/runtime.py`, `wifi_sonar/api/app.py`, `tests/test_storage.py`, `DECISIONS.md`, `DEV_LOOP.md`, `PROGRESS.md`.
- Tests agregados: reabrir el archivo recupera config, calibración y el último estado; la retención borra los eventos anteriores al corte.
- Problemas / deuda: la traza simulada numera el tiempo desde cero, así que la retención no la recorta sola. En vivo hay que guardar tiempo de reloj.
- Siguiente paso sugerido: T-13 — grabar una sesión y reproducirla con el mismo resultado.

### 2026-10-23 T-13 — Grabación y replay de sesiones
- Qué se hizo: `record_session` guarda el CSI en JSONL y las etiquetas manuales en un sidecar. El detector sobre el replay coincide con el de la captura original (D-017).
- Archivos tocados: `wifi_sonar/recording.py`, `tests/test_recording.py`, `DECISIONS.md`, `DEV_LOOP.md`, `PROGRESS.md`.
- Tests agregados: una caminata grabada se reproduce con la misma secuencia de estados y las etiquetas vuelven iguales.
- Problemas / deuda: no hay botón de grabar en el panel todavía.
- Siguiente paso sugerido: T-14 — shell del panel, tema oscuro, conectado al WebSocket.
