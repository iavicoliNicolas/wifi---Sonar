# Evaluación

Pipeline sobre el simulador, con una calibración de 20 s en cuarto vacío (k = 8).
La latencia es la mediana desde el inicio del evento hasta la primera detección.
El espectro usa 10 s, así que la latencia incluye esa ventana.

| Escenario | Métrica | Valor |
| --- | --- | ---: |
| cuarto vacío 120 s | falsos positivos de movimiento | 0.000 |
| cuarto vacío 120 s | falsos positivos de presencia | 0.000 |
| caminatas | recall | 1.000 |
| caminatas | precisión | 1.000 |
| caminatas | latencia mediana (s) | 1.990 |
| quietud | recall | 1.000 |
| quietud | precisión | 1.000 |
| quietud | latencia mediana (s) | 10.990 |
