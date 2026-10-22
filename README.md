# wifi---Sonar

Panel local que usa el WiFi del hogar como sensor de presencia y movimiento. El procesamiento corre en la red propia: no hay telemetría ni nube por defecto.

Estado y backlog: [`PROGRESS.md`](PROGRESS.md), [`DEV_LOOP.md`](DEV_LOOP.md), [`DECISIONS.md`](DECISIONS.md).

## Desarrollo

Hace falta Python 3.11 o superior. En Debian/Ubuntu también el paquete `python3-venv`. En un clon limpio:

```bash
make test
```

Eso crea `.venv`, instala el paquete en modo editable y corre la suite. `make lint` corre ruff. `make eval` imprime la tabla de precisión, recall y latencia y la guarda en `docs/eval.md`.

El servidor local, con el simulador:

```bash
.venv/bin/python -m wifi_sonar
```

Escucha en `http://127.0.0.1:8000`. El panel está en `/` y la documentación de la API en `/docs`. Las variables opcionales están en `.env.example`.

Alcance: presencia, movimiento y zona aproximada dentro de tu casa, con consentimiento de quienes viven ahí. No identifica personas.
