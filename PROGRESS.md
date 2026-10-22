# PROGRESS

## Estado actual
Fase: 5 — Calidad · Última tarea completada: T-21 · Próxima: T-22

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

### 2026-10-22 T-10 — API HTTP
- Qué se hizo: FastAPI con `GET /status`, `POST /calibrate`, `GET /config`, `PUT /config` y `GET /history`. OpenAPI en `/openapi.json`. El motor procesa frames del simulador y publica el estado fusionado. La calibración del simulador usa un cuarto vacío con el mismo ruido, no el ciclo demo.
- Archivos tocados: `wifi_sonar/api/app.py`, `wifi_sonar/engine.py`, `wifi_sonar/settings.py`, `wifi_sonar/storage/memory.py`, `wifi_sonar/__main__.py`, `tests/test_api.py`, `pyproject.toml`, `DECISIONS.md`, `README.md`, `PROGRESS.md`, `DEV_LOOP.md`.
- Tests agregados: config en caliente, calibración, historial de un cambio a movimiento, esquema OpenAPI y fusión OR.
- Problemas / deuda: el historial todavía está en memoria. SQLite es T-12.
- Siguiente paso sugerido: T-11 — WebSocket a ~10 Hz con descarte de frames viejos.

### 2026-10-22 T-11 — Streaming por WebSocket
- Qué se hizo: `/ws` manda el estado, las features y las amplitudes del último frame. El hub guarda un solo snapshot: si el cliente no leyó, el siguiente publish pisa al anterior. El lazo del socket espera 0.1 s, así que sale a unos 10 Hz.
- Archivos tocados: `wifi_sonar/stream.py`, `wifi_sonar/api/app.py`, `wifi_sonar/engine.py`, `tests/test_ws.py`, `PROGRESS.md`, `DEV_LOOP.md`.
- Tests agregados: 50 publishes sin lectura dejan el último y cuentan 49 descartes; el cliente WS ve el mismo estado que `GET /status`.
- Problemas / deuda: ninguna.
- Siguiente paso sugerido: T-12 — SQLite para eventos, calibraciones y config, con retención.

### 2026-10-22 T-12 — Persistencia local
- Qué se hizo: `SqliteStore` con migración inicial para eventos, calibraciones y config. Cada evento guarda la hora de pared y `purge` borra lo que supera la retención. El servidor abre `data/wifi_sonar.sqlite` y el motor recupera la última calibración y la config al arrancar.
- Archivos tocados: `wifi_sonar/storage/sqlite.py`, `wifi_sonar/storage/__init__.py`, `wifi_sonar/engine.py`, `wifi_sonar/api/app.py`, `tests/test_storage.py`, `PROGRESS.md`, `DEV_LOOP.md`.
- Tests agregados: reabrir la base conserva config, calibración y el evento reciente; un evento de 40 días desaparece solo.
- Problemas / deuda: ninguna.
- Siguiente paso sugerido: T-13 — grabar CSI y etiquetas, y reproducirlas con el mismo resultado del detector.

### 2026-10-22 T-13 — Grabación y exportación
- Qué se hizo: `SessionRecorder` escribe JSONL crudo y un archivo de etiquetas. `POST /recordings/start`, `/label` y `/stop`. El replay de esa grabación produce los mismos estados del detector.
- Archivos tocados: `wifi_sonar/recording.py`, `wifi_sonar/sources/replay.py`, `wifi_sonar/engine.py`, `wifi_sonar/api/app.py`, `wifi_sonar/settings.py`, `tests/test_recording.py`, `PROGRESS.md`, `DEV_LOOP.md`.
- Tests agregados: grabar → replay → mismos estados; los endpoints crean la etiqueta y rechazan un segundo stop.
- Problemas / deuda: ninguna.
- Siguiente paso sugerido: T-14 — shell del panel, conectado al WebSocket del simulador.

### 2026-10-22 T-14 — Shell del panel
- Qué se hizo: página oscura en `/` con el estado grande (`vacío` / `presencia` / `movimiento`) y la píldora de conexión. El JavaScript abre `/ws` y se reconecta solo. Si no hay calibración guardada, el arranque del simulador calibra 12 s de cuarto vacío para que el panel tenga línea base. Uvicorn necesita el paquete `websockets` para aceptar el upgrade; quedó como dependencia.
- Archivos tocados: `web/index.html`, `web/style.css`, `web/app.js`, `wifi_sonar/api/app.py`, `wifi_sonar/engine.py`, `tests/test_api.py`, `pyproject.toml`, `DECISIONS.md`, `PROGRESS.md`, `DEV_LOOP.md`.
- Tests agregados: `GET /` sirve el shell y los assets.
- Problemas / deuda: sin gráficos todavía.
- Verificación: en Chrome el panel pasó a "en vivo" y mostró vacío, presencia y movimiento con el simulador acelerado.
- Siguiente paso sugerido: T-15 — heatmap, score y timeline.

### 2026-10-22 T-15 — Visualizaciones en vivo
- Qué se hizo: heatmap de amplitud, gráfico de score con los umbrales de la config y una lista de cambios de estado. Los buffers son anillos de 240 columnas y 40 eventos. El dibujo va en `requestAnimationFrame`. La entrada del socket sigue en ~10 Hz; el anillo no crece aunque lleguen miles de snapshots.
- Archivos tocados: `web/index.html`, `web/style.css`, `web/app.js`, `tests/test_api.py`, `PROGRESS.md`, `DEV_LOOP.md`.
- Tests agregados: el HTML incluye los tres bloques. En Chrome, el heatmap pinta, y 5000 snapshots dejan el anillo en 240 y los eventos en 40.
- Problemas / deuda: no corrí 10 minutos de reloj de pared; el tope de memoria es el anillo fijo.
- Siguiente paso sugerido: T-16 — asistente de calibración en el panel.

### 2026-10-22 T-16 — Asistente de calibración
- Qué se hizo: el botón Calibrar abre un diálogo que pide salir de la habitación, hace una cuenta regresiva de 3 s, llama a `POST /calibrate` y muestra la calidad y el umbral de movimiento.
- Archivos tocados: `web/index.html`, `web/style.css`, `web/app.js`, `tests/test_api.py`, `PROGRESS.md`, `DEV_LOOP.md`.
- Tests agregados: el HTML incluye la consigna. En Chrome la cuenta baja 3, 2, 1 y el resultado fue "Calidad: estable" con un umbral numérico.
- Problemas / deuda: ninguna.
- Siguiente paso sugerido: T-17 — sliders de sensibilidad, ventana e histéresis, más alerta y webhook.

### 2026-10-22 T-17 — Configuración y alertas
- Qué se hizo: sliders de sensibilidad, ventana e histéresis, campo de webhook local y aviso opcional del navegador. El motor aplica la ventana en caliente y, si hay URL, hace POST del cambio de estado. La config se guarda en el store y vuelve al reiniciar el motor.
- Archivos tocados: `web/index.html`, `web/style.css`, `web/app.js`, `wifi_sonar/engine.py`, `tests/test_webhook.py`, `PROGRESS.md`, `DEV_LOOP.md`.
- Tests agregados: un servidor HTTP local recibe el estado `movimiento`; un segundo `Engine` con el mismo store recupera sensibilidad, ventana e histéresis. En Chrome, mover el slider dejó la nota en "Sensibilidad 1.7" y `GET /config` devolvió ese valor.
- Problemas / deuda: el permiso de notificación no se puede conceder en Chrome headless, así que ese camino queda cubierto por el código del panel y no por un clic real.
- Siguiente paso sugerido: T-18 — aviso de sensado, pausa y borrado.

### 2026-10-22 T-18 — Privacidad y control
- Qué se hizo: el panel muestra "Sensado activo", la retención en días, un botón para pausar y otro para borrar el historial. En pausa el motor no avanza la fuente ni procesa frames. `DELETE /history` vacía los eventos y deja la calibración.
- Archivos tocados: `web/index.html`, `web/style.css`, `web/app.js`, `wifi_sonar/api/app.py`, `tests/test_privacy.py`, `DECISIONS.md`, `PROGRESS.md`, `DEV_LOOP.md`.
- Tests agregados: una fuente contadora no se lee mientras está en pausa; borrar deja el historial vacío. En Chrome, pausar cambia el aviso a "Sensado en pausa" y reanudar lo vuelve a "Sensado activo".
- Problemas / deuda: ninguna.
- Siguiente paso sugerido: T-19 — adaptador ESP32.

### 2026-10-22 T-19 — Adaptador ESP32 CSI
- Qué se hizo: `ESP32Source` lee líneas por archivo/tty o UDP. El parser acepta el CSV `CSI_DATA` de esp-csi (ESP32/C3 y C5/C6) y la línea corta `CSI,...`. Las líneas rotas se saltean. `firmware/` explica el flasheo del ejemplo oficial y `docs/hardware.md` lista materiales y pasos.
- Archivos tocados: `wifi_sonar/sources/esp32.py`, `wifi_sonar/engine.py`, `firmware/README.md`, `firmware/csi_line.c`, `docs/hardware.md`, `tests/test_esp32.py`, `DECISIONS.md`, `PROGRESS.md`, `DEV_LOOP.md`.
- Tests agregados: CSV oficial, línea corta, basura, archivo y un datagrama UDP. No se flasheó hardware.
- Problemas / deuda: sin placas en esta máquina. El snippet C no es un proyecto IDF completo.
- Siguiente paso sugerido: T-20 — zonas y fusión en el panel.

### 2026-10-22 T-20 — Multi-nodo y zonas
- Qué se hizo: el panel lista un estado por zona. La fusión OR/voto ya estaba en el motor; la config `zones` le pone nombre a cada `node_id`.
- Archivos tocados: `web/index.html`, `web/style.css`, `web/app.js`, `tests/test_zones.py`, `PROGRESS.md`, `DEV_LOOP.md`.
- Tests agregados: dos fuentes simuladas, living en movimiento y pasillo presente en el estado; la fusión OR queda en movimiento. En Chrome la lista mostró "living / movimiento".
- Problemas / deuda: ninguna.
- Siguiente paso sugerido: T-21 — modo RSSI de sensibilidad baja.
