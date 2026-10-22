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
