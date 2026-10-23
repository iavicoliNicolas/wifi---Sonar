# PROGRESS

## Estado actual
Fase: 5 — Cierre · Última tarea completada: T-24 · Próxima: ninguna (T-00…T-24 cerradas)

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

### 2026-10-23 T-14 — Shell del panel
- Qué se hizo: página estática en tema oscuro con el estado grande (vacío / presencia / movimiento) y el texto de conexión. `python -m wifi_sonar` corre el simulador y lo publica por `/ws`. Se agregó `websockets` porque uvicorn no acepta el socket sin esa librería (D-018).
- Archivos tocados: `web/index.html`, `web/style.css`, `web/app.js`, `wifi_sonar/live.py`, `wifi_sonar/__main__.py`, `wifi_sonar/api/app.py`, `tests/test_panel.py`, `Makefile`, `pyproject.toml`, `DECISIONS.md`, `DEV_LOOP.md`, `PROGRESS.md`.
- Tests agregados: `GET /` sirve el shell y el CSS declara el color de movimiento. En el navegador, con el socket conectado, el indicador pasó por vacío, presencia y movimiento.
- Problemas / deuda: todavía no hay gráficos ni calibración en la página.
- Siguiente paso sugerido: T-15 — heatmap, score y línea de tiempo.

### 2026-10-23 T-15 — Visualizaciones en vivo
- Qué se hizo: el panel dibuja un heatmap de amplitud (subportadora × tiempo), el score con una línea de umbral en 0,5 y una línea de tiempo de cambios de estado. Los buffers quedan fijos (180 columnas y 12 eventos) y `requestAnimationFrame` junta ráfagas, así 100 Hz de entrada no acumula muestras ni redibuja más de una vez por frame (D-019). El estado grande se achicó para que los tres gráficos entren en la misma vista.
- Archivos tocados: `web/index.html`, `web/style.css`, `web/app.js`, `tests/test_panel.py`, `DECISIONS.md`, `DEV_LOOP.md`, `PROGRESS.md`, `README.md`.
- Tests agregados: el HTML sirve los tres gráficos y el script declara el tope y `requestAnimationFrame`. Un ensayo aparte de 60.000 mensajes (10 min a 100 Hz) dejó el heatmap en 180, el score en 180, la línea de tiempo en 12 y un solo frame pendiente.
- Problemas / deuda: el umbral dibujado es 0,5 del score ya normalizado, no el umbral crudo de energía. Falta el favicon (`/favicon.ico` responde 404).
- Siguiente paso sugerido: T-16 — asistente de calibración en el panel.

### 2026-10-23 T-16 — Asistente de calibración
- Qué se hizo: el panel pide salir de la habitación, cuenta 5 segundos y llama a `POST /calibrate`. La respuesta incluye un resumen de calidad: `buena`, `corta`, `inestable` o `alta` (D-020).
- Archivos tocados: `wifi_sonar/detect/calibrate.py`, `wifi_sonar/api/app.py`, `web/index.html`, `web/style.css`, `web/app.js`, `tests/test_calibrate.py`, `tests/test_api.py`, `tests/test_panel.py`, `DECISIONS.md`, `DEV_LOOP.md`, `PROGRESS.md`, `README.md`.
- Tests agregados: las cuatro etiquetas de calidad; `/calibrate` de un cuarto vacío responde `buena`. En el navegador el botón mostró la cuenta regresiva y el texto "buena — el cuarto vacío quedó estable".
- Problemas / deuda: la captura sigue siendo el simulador vacío (semilla 1), no la fuente en vivo. Cuando haya hardware, el mismo botón tiene que grabar esa fuente.
- Siguiente paso sugerido: T-17 — sliders de sensibilidad, ventana e histéresis, con alertas opcionales.

### 2026-10-23 T-17 — Configuración y alertas
- Qué se hizo: el panel tiene sliders de sensibilidad (k), ventana de movimiento e histéresis. Se guardan en SQLite (`data/sonar.sqlite`) y el simulador en vivo corta la traza actual cuando el config cambia (D-021). Un cambio de estado puede avisar con una notificación del navegador o un webhook que solo acepta `http://127.0.0.1` o `localhost`.
- Archivos tocados: `wifi_sonar/runtime.py`, `wifi_sonar/live.py`, `wifi_sonar/__main__.py`, `web/index.html`, `web/style.css`, `web/app.js`, `tests/test_alerts.py`, `tests/test_panel.py`, `.gitignore`, `DECISIONS.md`, `DEV_LOOP.md`, `PROGRESS.md`, `README.md`.
- Tests agregados: un webhook externo se rechaza; un cambio a movimiento hace POST al loopback; subir la ventana a 30 s evita que una caminata de 6 s cuente como movimiento. En el navegador, histéresis 0 y el webhook quedaron después de recargar, y también en el archivo SQLite.
- Problemas / deuda: la notificación del navegador depende del permiso del usuario. k nuevo se usa en la próxima calibración, no reescribe umbrales ya guardados.
- Siguiente paso sugerido: T-18 — aviso de sensado activo, pausa y borrado del historial.

### 2026-10-23 T-18 — Privacidad y control
- Qué se hizo: el panel muestra "sensado activo", la retención en días, y botones para pausar y borrar. Pausar corta la ingesta. Borrar vacía eventos y calibraciones en memoria y en SQLite; el config (incluida la retención) se conserva (D-003).
- Archivos tocados: `wifi_sonar/runtime.py`, `wifi_sonar/api/app.py`, `web/index.html`, `web/style.css`, `web/app.js`, `tests/test_privacy.py`, `tests/test_panel.py`, `DEV_LOOP.md`, `PROGRESS.md`, `README.md`.
- Tests agregados: con la sesión en pausa una caminata no entra al historial; `DELETE /history` deja la base vacía y el config intacto; `/sensing` se refleja en `/status`. En el navegador el banner pasó a "sensado en pausa" y el borrado confirmado respondió 200.
- Problemas / deuda: al reanudar, el simulador vuelve a grabar eventos. La pausa no apaga el transmisor de WiFi del router.
- Siguiente paso sugerido: T-19 — adaptador ESP32 y el formato de línea.

### 2026-10-23 T-19 — Adaptador ESP32
- Qué se hizo: `parse_csi_line` lee el formato `CSI nodo timestamp rssi amps fases` y descarta líneas rotas. `ESP32Source` implementa `CSISource`. `docs/hardware.md` lista materiales y `firmware/README.md` dice cómo flashear el ejemplo oficial de Espressif, sin traer un binario (D-022).
- Archivos tocados: `wifi_sonar/sources/esp32.py`, `tests/test_esp32.py`, `firmware/README.md`, `docs/hardware.md`, `DECISIONS.md`, `DEV_LOOP.md`, `PROGRESS.md`.
- Tests agregados: una línea ficticia se parsea; basura, comentarios y fases de otro largo se saltan; el source se queda con las líneas buenas.
- Problemas / deuda: nadie abre el UDP en el proceso del panel todavía. El simulador sigue siendo la fuente en vivo.
- Siguiente paso sugerido: T-20 — varias zonas y fusión OR/votación.

### 2026-10-23 T-20 — Zonas
- Qué se hizo: `fuse_states` combina nodos con OR (el estado más activo) o votación (mayoría; el empate queda en el más activo). El config guarda zonas y el modo. El panel lista cada zona (D-023).
- Archivos tocados: `wifi_sonar/detect/zones.py`, `wifi_sonar/runtime.py`, `wifi_sonar/live.py`, `web/index.html`, `web/style.css`, `web/app.js`, `tests/test_zones.py`, `tests/test_panel.py`, `DECISIONS.md`, `DEV_LOOP.md`, `PROGRESS.md`.
- Tests agregados: una caminata simulada en el living y un pasillo vacío fusionan en movimiento para la casa y vacío para el pasillo; la votación no deja que un solo nodo gane si está en minoría. En el navegador la zona "esta habitación" mostró el mismo estado que la palabra grande.
- Problemas / deuda: el simulador en vivo sigue siendo un solo nodo (`sim-0`).
- Siguiente paso sugerido: T-21 — modo RSSI degradado, marcado como sensibilidad baja.

### 2026-10-23 T-21 — Modo RSSI
- Qué se hizo: un detector grueso mira el RSSI de dispositivos que la persona ya nombró. No escanea la red. Solo dice vacío o movimiento, y el panel muestra "sensibilidad baja" (D-024).
- Archivos tocados: `wifi_sonar/detect/rssi.py`, `wifi_sonar/runtime.py`, `wifi_sonar/live.py`, `web/index.html`, `web/style.css`, `web/app.js`, `tests/test_rssi.py`, `tests/test_panel.py`, `DECISIONS.md`, `DEV_LOOP.md`, `PROGRESS.md`.
- Tests agregados: una traza quieta no se mueve y ninguna muestra dice presencia; un balanceo sí es movimiento; el nombre `*` se rechaza. En el navegador, al elegir RSSI apareció el aviso y al volver a CSI se ocultó.
- Problemas / deuda: sin placa, el modo RSSI en vivo sigue siendo una traza simulada con la etiqueta elegida.
- Siguiente paso sugerido: T-22 — reconexión, logs, health y recalibración lenta en vacío.

### 2026-10-23 T-22 — Robustez
- Qué se hizo: `iter_resilient` vuelve a abrir la fuente si se corta el enlace y deja un log JSON. `GET /health` responde aunque la fuente esté cayendo. Si el cuarto queda vacío el tiempo configurado, se recalibra (D-025).
- Archivos tocados: `wifi_sonar/ops.py`, `wifi_sonar/runtime.py`, `wifi_sonar/api/app.py`, `tests/test_ops.py`, `DECISIONS.md`, `DEV_LOOP.md`, `PROGRESS.md`.
- Tests agregados: una fuente que muere después del primer frame se reanuda y `/health` sigue en 200 sin armar otra app; el log es un JSON; el cuarto vacío recalibra y el movimiento no.
- Problemas / deuda: el simulador del panel no pasa por `iter_resilient` porque no se cae. El adaptador ESP32 sí puede usarlo.
- Siguiente paso sugerido: T-23 — Dockerfile y compose.

### 2026-10-23 T-23 — Empaquetado
- Qué se hizo: `Dockerfile` y `compose.yaml` levantan el panel con el simulador en el puerto 8000. El paquete declara todos los submódulos de `wifi_sonar` para que la imagen no se quede con el paquete raíz solo (D-026).
- Archivos tocados: `Dockerfile`, `compose.yaml`, `.dockerignore`, `pyproject.toml`, `DECISIONS.md`, `DEV_LOOP.md`, `PROGRESS.md`, `README.md`.
- Tests agregados: la suite sigue en verde. `docker compose up --build -d` dejó el contenedor en marcha; `/health` respondió `ok` y `/` sirvió el panel.
- Problemas / deuda: la imagen no incluye las herramientas de desarrollo. El puerto 8000 es el del panel, así que no convive con otro `python -m wifi_sonar` en el mismo puerto.
- Siguiente paso sugerido: T-24 — README de instalación, calibración, límites y privacidad.

### 2026-10-23 T-24 — Documentación final
- Qué se hizo: el README queda como guía de instalación (venv y Docker), calibración, ajustes, privacidad y límites conocidos, con dos capturas del panel.
- Archivos tocados: `README.md`, `docs/screenshots/panel.jpg`, `docs/screenshots/calibracion.jpg`, `DEV_LOOP.md`, `PROGRESS.md`.
- Tests agregados: ninguno nuevo. `make test` y `make lint` siguen en verde, y el contenedor de T-23 responde en el puerto 8000.
- Problemas / deuda: la captura de calibración sigue siendo el simulador vacío hasta que haya una placa. El favicon sigue en 404.
- Siguiente paso sugerido: ninguno del backlog. El próximo trabajo real es conectar un ESP32 propio siguiendo `docs/hardware.md`.
