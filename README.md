# wifi---Sonar

Panel local que usa el WiFi del hogar como sensor de presencia y movimiento. El procesamiento corre en la red propia: no hay telemetría ni nube por defecto.

Estado y backlog: [`PROGRESS.md`](PROGRESS.md), [`DEV_LOOP.md`](DEV_LOOP.md), [`DECISIONS.md`](DECISIONS.md).

## Desarrollo

Hace falta Python 3.11 o superior. En un clon limpio:

```bash
make test
```

Eso crea `.venv`, instala el paquete en modo editable y corre la suite. `make lint` corre ruff. Las variables opcionales están en `.env.example`.

Alcance: presencia, movimiento y zona aproximada dentro de tu casa, con consentimiento de quienes viven ahí. No identifica personas.
