# DEV_LOOP.md — WiFi Sonar

> Documento operativo para Cursor (modo agente). Leelo completo al inicio de **cada** iteración.
> Objetivo del proyecto: un panel web que usa el WiFi del hogar como sensor (WiFi sensing / "sonar") para detectar presencia y movimiento a partir de la perturbación de la señal.

---

## 0. Reglas del loop

1. **Una tarea por iteración.** Tomá la primera tarea `[ ]` del backlog cuyo prerequisito esté `[x]`.
2. **Leé antes de escribir.** Revisá `PROGRESS.md`, la estructura del repo y los tests existentes.
3. **Primero el test, después el código** (o al menos juntos). Sin test, la tarea no está hecha.
4. **Todo corre sin hardware.** Existe un simulador de señal (T-02). Nunca bloquees el desarrollo esperando un ESP32 o un router.
5. **Cambios chicos y commiteables.** Un commit por tarea: `feat(T-07): detector de movimiento por varianza móvil`.
6. **No inventes dependencias pesadas.** Preferí stdlib, NumPy/SciPy y lo que ya esté en el repo. Justificá en `DECISIONS.md` cualquier librería nueva.
7. **Si algo es ambiguo, decidí, anotalo en `DECISIONS.md` y seguí.** Solo frená si la decisión es irreversible o requiere hardware que no tenés.
8. **No toques tareas futuras** ni refactorices "de paso".

### Ciclo de cada iteración

```
1. LEER      → PROGRESS.md, DECISIONS.md, backlog (sección 4)
2. ELEGIR    → próxima tarea elegible
3. PLANEAR   → 3-6 líneas: archivos a tocar, enfoque, riesgos
4. IMPLEMENTAR + TESTEAR
5. VERIFICAR → correr lint + tests + (si hay UI) levantar y chequear a mano
6. REGISTRAR → marcar [x], actualizar PROGRESS.md (qué se hizo, qué quedó, próximo paso)
7. COMMIT    → mensaje convencional
8. REPETIR
```

### Definition of Done (toda tarea)

- [ ] Criterios de aceptación de la tarea cumplidos
- [ ] Tests nuevos pasando y suite completa en verde
- [ ] Lint/format sin errores
- [ ] `PROGRESS.md` actualizado
- [ ] README o docs actualizados si cambió algo visible para el usuario

---

## 1. Límites éticos y legales (innegociables)

El proyecto es para uso **en tu propio hogar y red**, con consentimiento de quienes viven ahí.

- Detectar presencia/movimiento dentro de tu casa: OK.
- Usarlo para **monitorear a vecinos u otras unidades del edificio** sin su conocimiento: **no**. Es una invasión de privacidad y puede ser ilegal (en Argentina, ver Ley 25.326 de protección de datos personales y el régimen de intimidad del Código Civil y Comercial).
- Alcance técnico del producto: **presencia / movimiento / zona aproximada**. Sin identificación de personas, sin reconocimiento de actividades íntimas, sin grabación de datos que permitan reconstruir hábitos de terceros.
- Todo dato se procesa **localmente**. Sin telemetría, sin nube por defecto.
- El panel debe mostrar un aviso claro de "sensado activo" y permitir pausar/borrar datos (tarea T-18).

Si una tarea futura empuja contra estos límites, no la implementes y anotalo en `DECISIONS.md`.

---

## 2. Realidad técnica (para tomar buenas decisiones)

- El "sonar con WiFi" real se hace con **CSI (Channel State Information)**: amplitud/fase por subportadora, que cambia cuando algo se mueve en el camino de la señal.
- **RSSI** (lo único que dan la mayoría de routers y celulares) sirve para detección muy gruesa; es ruidoso. Se soporta como modo degradado.
- Fuentes de CSI accesibles: **ESP32** (esp-csi, la más simple), Raspberry Pi con Nexmon CSI, Intel 5300 / Atheros con firmware parcheado. Un router comercial normal **no** expone CSI.
- Lo realista: detectar **presencia y movimiento** en un departamento/zona, y con más trabajo, respiración en reposo. Atravesar varias paredes y pisos reduce mucho la señal útil; no prometas "ver el edificio".
- Mejor arquitectura: **transmisor** (el router o un ESP32 emitiendo paquetes a ~50-100 Hz) + **receptor(es)** (ESP32) que reportan CSI por UDP/serial al servidor.

---

## 3. Arquitectura objetivo

```
[ Fuente CSI ]──►[ Ingesta ]──►[ Pipeline DSP ]──►[ Detector ]──►[ API + WebSocket ]──►[ Panel web ]
 ESP32 / Pi /      adaptadores   limpieza, filtros  presencia,       FastAPI (o lo que     tiempo real,
 simulador /       con interfaz  features           movimiento,      ya use el repo)       calibración,
 replay de archivo común          ventanas          zonas                                  histórico
                                                       │
                                                   [ Storage local: SQLite / archivos ]
```

Principios:
- Cada fuente implementa la misma interfaz `CSISource` → emite `CSIFrame(timestamp, rssi, amplitudes[], phases[] | None, node_id)`.
- Pipeline y detector son **funciones puras sobre ventanas**, fáciles de testear con señales sintéticas.
- El panel solo consume la API; no conoce el hardware.

> Si el repo ya usa otro stack (Node, Flask, etc.), **respetá el stack existente**. Esta arquitectura define responsabilidades, no tecnologías obligatorias.

---

## 4. Backlog

Formato: `[ ] ID — Título` · *Depende de* · **Aceptación**

### Fase 0 — Cimientos

- [x] **T-00 — Auditoría del repo**
  *Depende de:* nada
  Listá estructura, lenguaje, dependencias, qué funciona y qué no. Escribí `PROGRESS.md` y `DECISIONS.md` iniciales con un diagnóstico y un plan de adaptación de este backlog al código existente.
  **Aceptación:** `PROGRESS.md` con inventario del repo; backlog ajustado si hace falta (renombrar tareas, marcar como hechas las que ya existan).

- [x] **T-01 — Entorno reproducible**
  *Depende de:* T-00
  Gestor de dependencias, `Makefile` o scripts (`dev`, `test`, `lint`), `.gitignore`, `.env.example`, pre-commit opcional.
  **Aceptación:** clon limpio + un comando = tests corriendo.

- [x] **T-02 — Modelo de datos y simulador de CSI**
  *Depende de:* T-01
  Definir `CSIFrame`. Implementar `SimulatedSource`: ~52 subportadoras, ruido gaussiano, deriva lenta y eventos configurables (persona entra, camina, se queda quieta, sale).
  **Aceptación:** generador determinista por seed; test que verifica que los eventos alteran la varianza esperada.

- [x] **T-03 — Interfaz `CSISource` + replay desde archivo**
  *Depende de:* T-02
  Interfaz común, y `ReplaySource` que lee grabaciones (`.csv`/`.jsonl`) a velocidad real o acelerada.
  **Aceptación:** mismo pipeline consume simulador y replay sin cambios.

### Fase 1 — Núcleo de señal

- [x] **T-04 — Preprocesamiento**
  *Depende de:* T-03
  Filtro Hampel (outliers), interpolación de paquetes perdidos, normalización de amplitud por subportadora, remoción de subportadoras nulas.
  **Aceptación:** tests con ruido/outliers inyectados; salida estable.

- [x] **T-05 — Extracción de features por ventana**
  *Depende de:* T-04
  Ventanas deslizantes (ej. 2 s, paso 0.5 s). Features: varianza, media absoluta de diferencias, energía en bandas (movimiento ~0.5-5 Hz, respiración ~0.1-0.5 Hz) vía FFT/Welch, PCA opcional.
  **Aceptación:** features con valores esperados sobre señales sintéticas conocidas.

- [x] **T-06 — Calibración de línea base**
  *Depende de:* T-05
  Capturar N segundos con el ambiente vacío; guardar media y desvío de features; umbrales derivados (ej. media + k·σ).
  **Aceptación:** función `calibrate(source, seconds)` + persistencia de la calibración; test con simulador.

- [x] **T-07 — Detector de movimiento**
  *Depende de:* T-06
  Compara features contra la línea base con histéresis y mínimo de duración para evitar parpadeo. Salida: `{moving: bool, score: 0-1, ts}`.
  **Aceptación:** en simulador, detecta ≥95 % de eventos de caminata con ≤1 falso positivo cada 10 min de ruido.

- [x] **T-08 — Detector de presencia (quieto)**
  *Depende de:* T-07
  Detecta presencia sin movimiento grande usando banda de respiración / cambio sostenido respecto de la línea base, con ventana más larga.
  **Aceptación:** estados `vacío | presencia | movimiento` con máquina de estados testeada.

- [x] **T-09 — Métricas de evaluación**
  *Depende de:* T-08
  Script que corre el pipeline sobre escenarios simulados y/o grabaciones etiquetadas y reporta precisión, recall y latencia.
  **Aceptación:** `make eval` imprime tabla de métricas; se guarda en `docs/eval.md`.

### Fase 2 — Servicio y tiempo real

- [x] **T-10 — API HTTP**
  *Depende de:* T-08
  Endpoints: `GET /status`, `POST /calibrate`, `GET /config`, `PUT /config`, `GET /history`.
  **Aceptación:** tests de API; OpenAPI/docs generada.

- [x] **T-11 — Streaming por WebSocket**
  *Depende de:* T-10
  Canal con frames reducidos, features y estado a ~10 Hz.
  **Aceptación:** cliente de test recibe estado coherente; backpressure manejado (descarta frames viejos).

- [x] **T-12 — Persistencia local**
  *Depende de:* T-10
  SQLite para eventos (cambios de estado), calibraciones y config. Retención configurable.
  **Aceptación:** migración inicial, tests, limpieza automática por antigüedad.

- [x] **T-13 — Grabación y exportación de sesiones**
  *Depende de:* T-12
  Grabar CSI crudo + etiquetas manuales para generar datasets propios y reusar en `ReplaySource`.
  **Aceptación:** grabar → replay → mismo resultado del detector.

### Fase 3 — Panel

- [x] **T-14 — Shell del panel**
  *Depende de:* T-11
  Layout, estado de conexión, indicador grande `vacío / presencia / movimiento`, tema oscuro.
  **Aceptación:** el panel se conecta al WS y refleja el estado en vivo con el simulador.

- [x] **T-15 — Visualizaciones en vivo**
  *Depende de:* T-14
  Heatmap de amplitud (subportadora × tiempo), gráfico de score con umbrales, timeline de eventos.
  **Aceptación:** 60 fps aceptables con 100 Hz de entrada; sin fugas de memoria tras 10 min.

- [x] **T-16 — Asistente de calibración en el panel**
  *Depende de:* T-14, T-06
  Flujo guiado: "salí de la habitación" → cuenta regresiva → captura → resumen de calidad.
  **Aceptación:** se calibra de punta a punta desde la UI.

- [x] **T-17 — Configuración y alertas**
  *Depende de:* T-15
  Sliders de sensibilidad, ventana, histéresis; alertas opcionales (notificación del navegador, webhook local).
  **Aceptación:** cambios aplican en caliente y persisten.

- [x] **T-18 — Privacidad y control**
  *Depende de:* T-12, T-14
  Aviso de sensado activo, botón pausar, botón borrar todo el historial, retención visible.
  **Aceptación:** pausar detiene ingesta y borrar elimina datos (verificado por test).

### Fase 4 — Hardware real

- [x] **T-19 — Adaptador ESP32 CSI**
  *Depende de:* T-03
  `ESP32Source` por serial y/o UDP. Incluir `firmware/` con instrucciones de flasheo (esp-csi) y formato de línea documentado. Parser tolerante a líneas corruptas.
  **Aceptación:** parser con tests sobre muestras reales/ficticias del formato; documento `docs/hardware.md` con lista de materiales y pasos.

- [x] **T-20 — Multi-nodo y zonas**
  *Depende de:* T-19, T-08
  Varios receptores, estado por nodo, fusión simple (OR/votación) y mapa de zonas configurable (ej. "living", "pasillo").
  **Aceptación:** panel muestra un estado por zona; test de fusión con nodos simulados.

- [x] **T-21 — Modo RSSI degradado**
  *Depende de:* T-08
  Fuente alternativa con solo RSSI (por ejemplo, dispositivos conocidos de la LAN) con detector adaptado y sensibilidad claramente marcada como baja.
  **Aceptación:** el panel indica el modo y su limitación.

### Fase 5 — Calidad y cierre

- [x] **T-22 — Robustez operativa**
  *Depende de:* T-12
  Reconexión automática de fuentes, logs estructurados, health check, manejo de deriva (recalibración automática lenta cuando está vacío).
  **Aceptación:** test de caos: cortar y reanudar la fuente sin reiniciar el servicio.

- [x] **T-23 — Empaquetado**
  *Depende de:* T-22
  Dockerfile / compose, o servicio systemd, para correr en una Raspberry Pi o mini PC.
  **Aceptación:** `docker compose up` deja todo funcionando con el simulador.

- [x] **T-24 — Documentación final**
  *Depende de:* T-23
  README con capturas, guía de instalación, guía de calibración, límites conocidos, sección de privacidad.
  **Aceptación:** alguien externo puede reproducir el setup leyendo solo el README.

### Fase 6 — Deuda sin hardware

- [x] **T-25 — Favicon**
  *Depende de:* T-14
  El navegador deja de pedir `/favicon.ico` en vano.
  **Aceptación:** `GET /favicon.ico` responde 200 con una imagen.

- [x] **T-26 — Reloj de pared en el historial en vivo**
  *Depende de:* T-12, T-14
  Los eventos que publica el simulador del panel se guardan con hora real, así la retención puede borrarlos. El gráfico sigue mostrando el tiempo de la traza.
  **Aceptación:** un test fija el reloj y el historial usa ese instante; el snapshot del socket conserva el tiempo de la traza.

- [x] **T-27 — Calibrar la fuente conectada**
  *Depende de:* T-16
  Si hay una captura reciente marcada como fuente real, la calibración sale de ahí. Si no, sigue el cuarto vacío simulado.
  **Aceptación:** una fuente quieta distinta de la semilla 1 cambia los umbrales; sin fuente, el resultado sigue siendo el de la semilla 1.

- [x] **T-28 — UDP opcional**
  *Depende de:* T-19, T-22
  Con `WIFI_SONAR_UDP_PORT` el proceso lee líneas CSI propias. Apagado, sigue el simulador.
  **Aceptación:** un datagrama de prueba se parsea; sin la variable no se abre el socket.

### Fase 7 — Robustez del ingreso real

- [x] **T-29 — Reabrir el UDP si el socket muere**
  *Depende de:* T-22, T-28
  Un timeout sin datagramas sigue en silencio. Un error del socket cuenta como caída y `iter_resilient` vuelve a abrirlo. Si las caídas se agotan, `/health` dice `down` y el proceso sigue.
  **Aceptación:** después de un socket muerto, el datagrama siguiente se parsea; sin error no hay reapertura.

- [x] **T-30 — Zonas en el ingreso CSI**
  *Depende de:* T-20, T-28
  Cada `node_id` tiene su propia ventana. El snapshot fusiona con la config (OR o votación). Sin zonas, sigue «esta habitación».
  **Aceptación:** dos nodos simulados, uno caminando y otro vacío, publican living en movimiento y pasillo vacío.

- [x] **T-31 — Grabar la traza reciente**
  *Depende de:* T-13, T-14
  Un botón guarda en disco los frames que ya están en memoria, con el mismo JSONL del replay. No arranca una grabación nueva ni manda nada fuera de la máquina.
  **Aceptación:** un POST deja un archivo que el replay lee; sin frames responde que no hay nada para guardar. El panel tiene el botón.

---

## 5. Plantilla de `PROGRESS.md`

```markdown
# PROGRESS

## Estado actual
Fase: X · Última tarea completada: T-NN · Próxima: T-NN

## Log
### [fecha] T-NN — título
- Qué se hizo:
- Archivos tocados:
- Tests agregados:
- Problemas / deuda:
- Siguiente paso sugerido:
```

## 6. Plantilla de `DECISIONS.md`

```markdown
# DECISIONS
### D-001 — título (fecha)
Contexto · Opciones consideradas · Decisión · Consecuencias
```

---

## 7. Prompt de arranque para Cursor

Pegá esto en el chat del agente para iniciar o continuar el loop:

> Leé `DEV_LOOP.md`, `PROGRESS.md` y `DECISIONS.md`. Ejecutá **una** iteración del loop: elegí la próxima tarea elegible, planeala en pocas líneas, implementala con tests, verificá que todo pase, actualizá `PROGRESS.md`, marcá la tarea `[x]` en el backlog y hacé el commit. Respetá las reglas de la sección 0 y los límites de la sección 1. Al terminar, resumí qué hiciste y cuál es la próxima tarea. No empieces la siguiente sin que te lo pida.

Para modo continuo, cambiá la última frase por: *"Seguí con la siguiente tarea hasta completar la fase actual o hasta bloquearte; en ese caso, explicá el bloqueo."*
