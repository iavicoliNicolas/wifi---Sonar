# Firmware ESP32 (esp-csi)

WiFi Sonar no trae un binario. El CSI sale del ejemplo oficial de Espressif, y esta carpeta solo dice cómo flashearlo y qué línea tiene que imprimir.

Repositorio: <https://github.com/espressif/esp-csi>

Ejemplo: `examples/get-started/csi_recv` (receptor) y `examples/get-started/csi_send` (el otro módulo, que emite los paquetes). Hacen falta dos placas con CSI, por ejemplo ESP32-C3, y un cable USB por placa. ESP-IDF se instala como indica Espressif para esa versión del ejemplo.

## Flasheo

En la placa que envía:

```bash
cd esp-csi/examples/get-started/csi_send
idf.py set-target esp32c3
idf.py flash -b 921600 -p /dev/ttyUSB0
```

En la placa que recibe:

```bash
cd esp-csi/examples/get-started/csi_recv
idf.py set-target esp32c3
idf.py flash -b 921600 -p /dev/ttyUSB1
```

Cerrá el monitor serie antes de que otra cosa abra el mismo tty. El target (`esp32`, `esp32s3`, `esp32c3`, …) tiene que ser el de la placa. No cambies registros de PHY a mano: el ejemplo ya configura el callback de CSI.

## Formato que entiende el panel

Hay dos líneas. El parser tira las que no puede leer.

### CSV de esp-csi (`CSI_DATA`)

Es el que imprime `csi_recv` hoy. Una línea de ejemplo, recortada:

```text
CSI_DATA,0,94:d9:b3:80:8c:81,-30,11,1,6,1,0,1,0,1,0,0,-93,0,13,2,2751923,0,67,0,128,1,"[0,2,0,2]"
```

- El nodo es la MAC.
- `rssi` es la cuarta columna.
- `local_timestamp` está en microsegundos (columna 18 en ESP32/C3, columna 9 en C5/C6). El parser lo pasa a segundos.
- El array final guarda imag, real, imag, real, … La amplitud es la hipotenusa y la fase es `atan2(imag, real)`.

Con el tty ya abierto a la velocidad del ejemplo:

```bash
WIFI_SONAR_SOURCE=esp32 WIFI_SONAR_ESP32_SERIAL=/dev/ttyUSB1 python -m wifi_sonar
```

Ese camino lee el archivo o el dispositivo como texto. No instala pyserial.

### Línea corta (`CSI`)

Para UDP, reemplazá el `ets_printf` largo del callback por una línea. El snippet está en `csi_line.c`. No toca la configuración de la radio: solo formatea lo que el callback ya recibió (`info->buf`, `info->rx_ctrl`).

```text
CSI,<nodo>,<segundos>,<rssi>,<amp0|amp1|...>,<fase0|fase1|...>
```

La fase se puede omitir. Las listas usan `|`.

```bash
WIFI_SONAR_SOURCE=esp32 WIFI_SONAR_ESP32_HOST=0.0.0.0 WIFI_SONAR_ESP32_PORT=5005 python -m wifi_sonar
```

Cada placa manda un datagrama UDP por línea al puerto 5005 de la máquina del panel. El campo nodo distingue las zonas (T-20).
