# Firmware del receptor ESP32

Este directorio no trae un binario. El receptor es una placa **tuya**, en tu red, y el texto que imprime lo parsea `ESP32Source`.

No apuntes el sensor a la red de un vecino ni a otra unidad del edificio. El producto es para el hogar donde vivís y con acuerdo de quienes están ahí.

## Qué tiene que imprimir la placa

Una línea por muestra, por serial o por UDP, en UTF-8:

```text
CSI <nodo> <timestamp_s> <rssi> <amp0,amp1,...> <phase0,phase1,...>
```

La fase puede ser `-` si no la tenés. Ejemplo:

```text
CSI living 1.50 -47 1.0,1.1,0.9 0.1,0.2,0.0
```

Las líneas vacías, los comentarios (`#`) y las líneas cortas o con números rotos se descartan. El servidor sigue con la siguiente.

## Cómo flashear

1. Usá el ejemplo oficial de CSI de Espressif ([esp-csi](https://github.com/espressif/esp-csi)), no un firmware bajado de otro lado.
2. Seguí el README de ese ejemplo para instalar ESP-IDF y compilar el receptor.
3. Flasheá con el `esptool` que trae el propio ESP-IDF, hacia el puerto serial de **tu** placa.
4. Configurá el ejemplo para que el transmisor sea tu router o un segundo ESP32 tuyo, y para que el receptor mande las líneas de arriba a la IP de la máquina que corre el panel, puerto UDP `5500`.
5. En la máquina del panel, exportá `WIFI_SONAR_UDP_PORT=5500` y arrancá `python -m wifi_sonar`. Sin esa variable el panel sigue con el simulador y no abre el socket.

`udp_lines(5500)` en `wifi_sonar.sources.esp32` es el socket de recepción. No hace falta `pyserial`: si la placa habla por USB, cualquier programa puede leer el puerto y entregar las líneas al mismo parser.
