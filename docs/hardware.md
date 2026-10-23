# Hardware

El panel se desarrolla y se demuestra con el simulador. Esta página es para el día que quieras CSI de verdad, en tu propia red.

## Materiales

- Una computadora en la misma casa (una Raspberry Pi o una mini PC alcanza).
- Dos placas ESP32 con cable USB.
- Tu router, el de la red donde vivís.
- Nada de esto lee el WiFi de otra unidad.

## Cableado

1. Un ESP32 queda como transmisor de paquetes hacia tu router, o hacia el otro ESP32.
2. El segundo ESP32 es el receptor. Imprime una línea `CSI ...` por muestra.
3. La computadora corre `python -m wifi_sonar` y, cuando conectes la placa, lee esas líneas por UDP `5500` o por el puerto serial.

El formato, el flasheo y el límite de “solo tu red” están en [`firmware/README.md`](../firmware/README.md).

## Qué no promete

CSI atravesando varias paredes y pisos deja de servir. RSSI, si algún día lo usás, es más grueso todavía y el panel lo marca como sensibilidad baja. No identifica personas.
