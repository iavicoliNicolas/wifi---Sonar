# wifi---Sonar

Panel local que usa el WiFi del hogar como sensor de presencia y movimiento. El procesamiento corre en la red propia: no hay telemetría ni nube por defecto.

Estado: fase 0, cimientos. El inventario y el próximo paso están en [`PROGRESS.md`](PROGRESS.md). El backlog operativo está en [`DEV_LOOP.md`](DEV_LOOP.md). Las decisiones de stack y layout están en [`DECISIONS.md`](DECISIONS.md).

## Desarrollo

Hace falta Python 3.11 o superior. En Debian o Ubuntu, el módulo `venv` está en el paquete `python3-venv`.

```bash
make test
make lint
make eval
```

`make test` crea `.venv`, instala el paquete en modo editable con las herramientas de desarrollo y corre pytest. `make dev` solo prepara ese entorno. `make eval` corre el simulador y escribe precisión, recall y latencia en `docs/eval.md`.

La API local (FastAPI) expone `/status`, `/calibrate`, `/config` y `/history`. OpenAPI queda en `/openapi.json`. No hay servicio en la nube.

Alcance: presencia, movimiento y zona aproximada dentro de tu casa, con consentimiento de quienes viven ahí. No identifica personas.
