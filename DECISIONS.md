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

### D-005 — Sin pre-commit (2026-10-22)
Contexto: T-01 pide un pre-commit opcional.
Opciones consideradas: agregar el paquete `pre-commit` y un hook, o dejar lint como comando explícito.
Decisión: no se agrega el paquete. `make lint` corre ruff (check y format). Quien quiera un hook puede enganchar ese comando.
Consecuencias: un clon no instala hooks solo. La verificación de formato queda en `make lint`.

### D-006 — Formato de grabación (2026-10-22)
Contexto: T-03 pide replay desde `.csv` o `.jsonl`.
Opciones consideradas: un solo formato, o los dos con un esquema propio.
Decisión: JSONL es el formato canónico (un objeto por frame, con `timestamp`, `rssi`, `amplitudes`, `phases`, `node_id`). CSV guarda las mismas columnas y codifica las listas con `|`, usando `repr` para no perder el float. Las líneas en blanco se saltean. Una línea mal formada aborta la carga: una grabación corrupta no debe parecer una habitación vacía.
Consecuencias: `write_recording` elige el formato por la extensión. El detector compara resultados sobre los frames releídos, no sobre bits idénticos del JSON.

### D-007 — Ventana espectral de 10 s y sin SciPy (2026-10-22)
Contexto: T-05 pide ventanas de unos 2 s y energía en 0.5–5 Hz y 0.1–0.5 Hz vía FFT/Welch. Una FFT de 2 s tiene bins de 0.5 Hz y no separa la respiración del movimiento.
Opciones consideradas: agregar SciPy y usar `welch` con segmentos cortos, o un periodograma de Hann sobre una ventana más larga hecho con NumPy.
Decisión: varianza y media de diferencias usan la ventana corta (2 s, paso 0.5 s). Las dos energías de banda usan una ventana de 10 s (resolución 0.1 Hz) y un solo segmento de Welch con ventana de Hann. No se agrega SciPy.
Consecuencias: el primer feature aparece a los 10 s. La respiración no dispara la banda de movimiento. El detector de T-07 tiene que esperar esa ventana.

### D-008 — El movimiento se decide con la banda 0.5–5 Hz y k = 8 (2026-10-22)
Contexto: la varianza de la ventana también sube con la respiración, así que no separa "camina" de "está quieto". En 10 minutos de ruido, la energía de movimiento llega a unos 4 σ de una calibración corta con k = 4 y produce dos falsos positivos.
Opciones consideradas: subir la duración mínima, subir el umbral de histéresis, o agrandar k.
Decisión: el score de movimiento es la energía de la banda 0.5–5 Hz, normalizada para valer 1 en `media + k·σ`, con k = 8 por defecto. Histéresis 0.75 / 0.40 y al menos 1 s por encima del umbral. El nodo de cada frame interpolado se elige con búsqueda binaria: la matriz de distancias no entra en memoria a 10 minutos.
Consecuencias: respiración y ruido quedan por debajo de 0.5 de score. Una caminata de unos segundos satura el score en 1. La calibración de T-06 sigue aceptando otro k.

### D-009 — API local y calibración del simulador (2026-10-22)
Contexto: T-10 necesita un servicio. El ciclo demo del simulador alterna caminatas y quietud, así que calibrar contra el stream en vivo mezclaría movimiento en la línea base.
Opciones consideradas: calibrar con lo que esté entrando, o generar una captura vacía aparte.
Decisión: el servidor escucha en `127.0.0.1` por defecto. `POST /calibrate` en modo simulador sintetiza un cuarto vacío con el mismo ruido y la semilla desplazada. FastAPI queda como dependencia de runtime porque la API es el producto a partir de esta tarea. El historial de T-10 vive en memoria, con la misma interfaz que va a implementar SQLite.
Consecuencias: no hay telemetría. Cambiar la config reinicia la histéresis de los detectores. Una calibración nueva también.

### D-010 — Paquete websockets para el servidor (2026-10-22)
Contexto: los tests de `/ws` pasan con el cliente de Starlette, pero Uvicorn responde 404 al upgrade si no hay una librería de WebSocket instalada.
Opciones consideradas: `uvicorn[standard]` (arrastra uvloop, httptools y watchfiles) o declarar `websockets`.
Decisión: dependencia de runtime `websockets`. Alcanza para que el panel se conecte.
Consecuencias: un entorno que solo instala el paquete puede abrir `/ws`.

### D-011 — Config en caliente y webhook local (2026-10-22)
Contexto: T-17 pide que sensibilidad, ventana e histéresis apliquen en caliente y persistan, más una alerta opcional.
Opciones consideradas: recalcular los umbrales al mover la ventana, o seguir usando la calibración guardada hasta que la persona vuelva a calibrar. Para el aviso externo, un cliente nuevo o `urllib` de la stdlib.
Decisión: la ventana viva sale de `AppConfig` y los umbrales siguen siendo los de la última calibración. Cambiar la config reinicia la histéresis. El webhook es un POST JSON a una URL local que la persona escribe; un fallo se loguea y no corta el detector. No se agrega ninguna librería.
Consecuencias: un slider no reescribe la línea base. La notificación del navegador solo sale si el permiso ya está concedido.

### D-012 — Pausa sin leer la fuente y borrado solo del historial (2026-10-22)
Contexto: T-18 pide detener la ingesta y borrar los datos, sin definir si la calibración también se va.
Opciones consideradas: borrar eventos y calibración, o solo el historial de estados.
Decisión: pausar hace que `step` y el hilo no llamen a `next` sobre la fuente, y que `ingest` descarte el frame. `DELETE /history` borra eventos. La calibración queda: es la línea base del cuarto, no un registro de personas.
Consecuencias: reanudar no recalibra. Quien quiera tirar la línea base vuelve a correr el asistente.

### D-013 — ESP32 sin pyserial y dos formatos de línea (2026-10-22)
Contexto: T-19 pide un adaptador serie y/o UDP, parser tolerante y el ejemplo esp-csi. El CSV oficial cambia de columnas entre ESP32/C3 y C5/C6, y trae imag/real crudos.
Opciones consideradas: depender de pyserial, aceptar solo el CSV oficial, o definir una línea corta además del CSV.
Decisión: no se agrega pyserial. El serie es un archivo de texto (tty o FIFO). UDP es el camino para más de una placa. El parser acepta el `CSI_DATA` documentado por Espressif (timestamp en microsegundos, pares imag/real) y la línea `CSI,nodo,segundos,rssi,amps` del snippet `firmware/csi_line.c`. Una línea rota devuelve None.
Consecuencias: no hay un binario propio ni un mapa de registros. El flasheo sigue siendo el de `examples/get-started` de esp-csi.

### D-014 — RSSI solo con lista blanca (2026-10-22)
Contexto: T-21 pide un modo degradado con RSSI de dispositivos conocidos de la LAN, marcado como baja sensibilidad.
Opciones consideradas: escanear vecinos, leer cualquier estación asociada, o aceptar solo nombres que la persona escribe.
Decisión: `RssiSource` exige `devices`. No hay barrido de redes ni descubrimiento. El simulador usa esos nombres; no consulta la LAN. La RSSI entra al pipeline como una sola subportadora. El panel muestra "modo RSSI · sensibilidad baja" cuando `mode` es `rssi`. Arrancar con `WIFI_SONAR_SOURCE=rssi` fuerza ese modo y calibra contra una serie vacía de la misma fuente.
Consecuencias: sin CSI el detector es más grueso. Un nombre en la lista no identifica a una persona. El default `telefono` es un marcador de posición, no un equipo descubierto.
