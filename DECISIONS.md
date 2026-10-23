# DECISIONS

### D-001 — Stack Python greenfield (2026-10-22)
Contexto: el repositorio no tiene código ni dependencias. La sección 3 pide responsabilidades (fuente, pipeline, detector, API, storage) y nombra FastAPI solo como ejemplo, con la regla de respetar el stack existente. No hay stack existente.
Opciones consideradas: Node/TypeScript (cómodo para el panel, incómodo para DSP), Flask + NumPy, FastAPI + NumPy/SciPy.
Decisión: Python 3.11+ (en esta máquina hay 3.12). Paquete instalable vía `pyproject.toml` y venv. NumPy para arreglos de CSI; SciPy solo cuando una tarea lo necesite (Welch/filtros) y quede justificado acá. pytest para tests. ruff para lint y formato. FastAPI y WebSocket recién en T-10/T-11. Panel estático sin framework hasta que T-14 lo pida. SQLite de la stdlib en T-12.
Consecuencias: T-01 no agrega Node ni un gestor de paquetes aparte de pip/venv. No se introducen librerías de ML ni de visualización en el núcleo.

### D-002 — Layout del paquete (2026-10-22)
Contexto: hay que fijar nombres antes de escribir código para no mezclar fuente, DSP y API.
Opciones consideradas: layout `src/wifi_sonar/`, paquete plano `wifi_sonar/` en la raíz, o un solo módulo.
Decisión: paquete plano `wifi_sonar/` y tests en `tests/`. Submódulos cuando la tarea los necesite, no antes: `sources` (T-02/T-03), `pipeline` (T-04/T-05), `detect` (T-06 en adelante), `api` (T-10), `storage` (T-12). Identificadores de código en inglés. Docs operativos (`DEV_LOOP.md`, `PROGRESS.md`, `DECISIONS.md`) en español.
Consecuencias: T-01 puede crear el paquete mínimo y un test de import. No se crean paquetes vacíos en T-00.

### D-003 — Alcance de privacidad heredado del loop (2026-10-22)
Contexto: la sección 1 fija límites éticos y legales (hogar propio, sin identificar personas, procesamiento local, pausa y borrado en T-18).
Opciones consideradas: repetir los límites en cada tarea, o adoptarlos una vez como restricción de producto.
Decisión: el producto detecta presencia, movimiento y zona aproximada dentro de la red propia. No se implementa identificación de personas, reconocimiento de actividades íntimas, telemetría ni una nube por defecto. Si una tarea futura empuja contra eso, se rechaza y se anota una decisión nueva.
Consecuencias: T-21 (RSSI de dispositivos de la LAN) queda limitado a equipos de la red propia y debe marcar sensibilidad baja. No se agregan tareas de vigilancia entre unidades.

### D-004 — Backlog sin renombres (2026-10-22)
Contexto: T-00 pide ajustar el backlog si el código ya cubre tareas.
Opciones consideradas: partir tareas, fusionar T-01 con el esqueleto del simulador, o dejar los IDs como están.
Decisión: los IDs T-00…T-24 se mantienen. Nada previo a T-00 cuenta como hecho. El simulador sigue siendo T-02 y no se adelanta.
Consecuencias: la próxima tarea elegible es T-01.

### D-005 — Entorno mínimo en T-01 (2026-10-22)
Contexto: T-01 pide gestor de dependencias, comandos `dev` / `test` / `lint`, `.gitignore`, `.env.example` y pre-commit opcional. D-001 ya fijó pytest y ruff, y reservó NumPy para arreglos de CSI.
Opciones consideradas: declarar NumPy ya, agregar pre-commit, o dejar el entorno en lo que el test de import necesita.
Decisión: `pyproject.toml` con setuptools y el extra `dev` (pytest, ruff). `make test` crea `.venv` e instala en editable, así un clon limpio corre la suite con un comando. NumPy entra en T-02, cuando existan arreglos. Sin pre-commit: `make lint` hace el mismo chequeo sin un hook adicional.
Consecuencias: T-01 no arrastra dependencias de señal ni de git hooks. `.env.example` documenta que todavía no hay variables.

### D-006 — Simulador de CSI (2026-10-23)
Contexto: T-02 pide `CSIFrame` y un `SimulatedSource` determinista (~52 subportadoras, ruido gaussiano, deriva lenta, eventos de entra / camina / quieto / sale) cuyo efecto se vea en la varianza.
Opciones consideradas: depender de SciPy ya, modelar cada subportadora con un canal geométrico, o una suma de ruido + deriva + un tono por tipo de evento.
Decisión: NumPy entra ahora (arreglos de amplitud y fase). El cuarto vacío es ruido chico más una deriva de 0,02 Hz. Cada evento suma un seno: caminata 2 Hz y amplitud alta, quietud 0,25 Hz y amplitud baja, entrar/salir transiciones intermedias. La fase por subportadora sale del mismo seed. Sin SciPy hasta que una ventana necesite Welch.
Consecuencias: la misma semilla y los mismos eventos reproducen la traza. La varianza temporal cumple vacío < quietud < caminata, que es la señal que van a usar T-05 en adelante.

### D-007 — Replay en JSONL y CSV (2026-10-23)
Contexto: T-03 pide una interfaz común y un `ReplaySource` que lea grabaciones a velocidad real o acelerada, y que el mismo pipeline consuma simulador y replay.
Opciones consideradas: solo JSONL, solo CSV, o los dos con un protocolo explícito.
Decisión: `CSISource.frames()` es la interfaz. `collect()` es el único ingreso que usa el pipeline. JSONL guarda un objeto por línea (timestamp, rssi, amplitudes, phases, node_id). CSV usa el mismo contenido con columnas `amp*` y `phase*`. `speed <= 0` no duerme; `speed > 0` escala los deltas de timestamp. El reloj y el sleep se pueden inyectar para testear sin esperar.
Consecuencias: T-13 puede reusar los mismos writers. No hace falta un tercer formato.

### D-008 — Preprocesamiento (2026-10-23)
Contexto: T-04 pide Hampel, interpolación de paquetes perdidos, normalización por subportadora y descarte de subportadoras nulas.
Opciones consideradas: un filtro de mediana global, o tratar cada subportadora en el tiempo.
Decisión: por subportadora, en este orden: rellenar NaN, insertar muestras cuando el hueco supera 1,5 veces el paso mediano, Hampel (ventana impar, el punto se reemplaza si se aleja de la mediana local; si el MAD es 0 y el punto difiere, también), tirar subportadoras cuya mediana absoluta es < 5 % de la referencia, y dividir por esa mediana absoluta.
Consecuencias: la salida queda en una escala común. Un pico aislado no domina la varianza.

### D-009 — Features por ventana (2026-10-23)
Contexto: T-05 pide ventanas (ejemplo 2 s, paso 0,5 s), varianza, media de diferencias absolutas y energía en bandas de movimiento (0,5–5 Hz) y respiración (0,1–0,5 Hz) vía FFT o Welch.
Opciones consideradas: SciPy `welch`, o un periodograma con `rfft` y ventana de Hann.
Decisión: la serie es la media de subportadoras. Varianza, MAD y energía de movimiento salen de la ventana de 2 s. La respiración usa 8 s, porque en 2 s el salto de frecuencia es 0,5 Hz y esa banda no se resuelve. El espectro es un periodograma normalizado por la energía de la ventana, no Welch: no hace falta SciPy para una senoide conocida.
Consecuencias: una senoide de 2 Hz carga la banda de movimiento; una de 0,25 Hz carga la de respiración. SciPy sigue afuera.

### D-010 — Calibración (2026-10-23)
Contexto: T-06 pide capturar N segundos de cuarto vacío, guardar media y desvío de las features y umbrales media + k·σ.
Opciones consideradas: k=3 (más sensible, más falsos positivos en 10 min) o k=6.
Decisión: `calibrate(source, seconds, k=6)` observa la traza, la preprocesa y resume las cuatro features. El umbral es media + 6·σ. Se persiste en JSON.
Consecuencias: con el simulador, la caminata queda muy por encima del umbral de movimiento y el cuarto vacío no. k se puede cambiar cuando haya grabaciones reales.

### D-011 — Detector de movimiento (2026-10-23)
Contexto: T-07 compara features con la línea base, con histéresis y duración mínima. Tiene que ver al menos el 95 % de las caminatas y como máximo un falso positivo cada 10 min de ruido.
Opciones consideradas: umbral solo de varianza, o energía de la banda de movimiento.
Decisión: hay movimiento si la energía de movimiento supera el umbral y además supera a la de respiración, y eso se sostiene 0,5 s. La histéresis (0,5) baja el umbral de apagado. El score es el exceso sobre el umbral de apagado, recortado a 0–1. El Hampel pasa a ser vectorizado para que 10 min de traza corran en el test.
Consecuencias: una persona quieta no enciende el detector aunque algo de su tono se cuele en la banda de movimiento. El test de 20 caminatas y 10 min de vacío queda en verde.

### D-012 — Presencia quieta (2026-10-23)
Contexto: T-08 pide estados vacío, presencia y movimiento. La presencia sin caminata usa la banda de respiración y una ventana más larga.
Opciones consideradas: un tercer umbral de varianza, o reutilizar la energía de respiración ya calibrada.
Decisión: la máquina de estados delega el movimiento en `MotionDetector`. Si no hay movimiento y la energía de respiración supera su umbral durante 2 s, el estado es presencia. Si no, vacío. El movimiento pisa a la presencia.
Consecuencias: los tres estados se pueden testear con el simulador sin otra feature.

### D-013 — Evaluación en dos trazas (2026-10-23)
Contexto: T-09 pide `make eval` con precisión, recall y latencia sobre escenarios simulados.
Opciones consideradas: una sola traza mezclada, o una traza por clase.
Decisión: caminatas y quietudes se evalúan en trazas separadas. Mezclarlas en una sola normalización (la mediana de toda la captura) aplasta la quietud después de una caminata y genera falsos positivos de presencia. La latencia es el promedio hasta la primera muestra correcta, con 1,5 s de gracia para contar el acierto.
Consecuencias: `docs/eval.md` se regenera con `make eval`. No es una métrica sobre CSI real.

### D-014 — API con FastAPI (2026-10-23)
Contexto: T-10 pide `GET /status`, `POST /calibrate`, `GET /config`, `PUT /config`, `GET /history` y documentación OpenAPI. D-001 había reservado FastAPI para esta tarea.
Opciones consideradas: seguir sin framework y servir JSON a mano, o sumar FastAPI.
Decisión: FastAPI + uvicorn. La sesión vive en `SonarState` (memoria, por ahora). `httpx` queda en el extra `dev` porque el `TestClient` lo necesita. Nada de la API sale de la máquina.
Consecuencias: OpenAPI queda en `/openapi.json`. La persistencia llega en T-12; hasta entonces el historial es el proceso.

### D-015 — WebSocket con cola corta (2026-10-23)
Contexto: T-11 pide un canal a ~10 Hz con frames reducidos, features y estado, y backpressure que descarta frames viejos.
Opciones consideradas: bloquear al productor cuando el cliente no lee, o una cola acotada que tira lo más viejo.
Decisión: `FrameHub` tiene cola de 8 por cliente. Si está llena, se descarta el snapshot más viejo. `follow()` publica sobre el tiempo simulado a 10 Hz con 8 bins de amplitud (media por grupo de subportadoras), más estado y score.
Consecuencias: un panel lento no frena el sensor. No se prometen 10 Hz de reloj de pared si la máquina está ocupada; el ritmo es el de la traza.
