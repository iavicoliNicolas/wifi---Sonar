# Hardware

Lista para armar un nodo CSI en casa. El panel también corre sin nada de esto, con el simulador.

## Materiales

- Dos placas con CSI de Espressif. El ejemplo `csi_recv` / `csi_send` de esp-csi está probado por ellos en ESP32-C3; ESP32, ESP32-S3, C5 y C6 cambian el CSV y el parser ya contempla esas dos variantes.
- Dos cables USB para flashear y, si no usás UDP, para dejar el receptor conectado a la máquina del panel.
- Alimentación USB de 5 V si la placa no queda en la computadora.
- Una máquina en la misma casa (mini PC o Raspberry Pi) para `python -m wifi_sonar`. No hace falta nube.
- Opcional: otra pareja de placas si querés una segunda zona. Cada una manda su propio nombre de nodo.

No hace falta antena externa para una habitación. El CSI no atraviesa bien varias paredes: un nodo por ambiente alcanza más que subir la potencia.

## Pasos

1. Instalá ESP-IDF siguiendo la guía de Espressif que pide el `esp-csi` que vas a clonar.
2. Cloná <https://github.com/espressif/esp-csi> y flasheá `csi_send` y `csi_recv` como está en [`firmware/README.md`](../firmware/README.md).
3. Dejá las dos placas asociadas a la red de tu casa, no a la de un vecino. El ejemplo oficial filtra por la MAC del emisor (`CONFIG_CSI_SEND_MAC`).
4. Elegí cómo llega la línea al panel:
   - Serie: `WIFI_SONAR_SOURCE=esp32` y `WIFI_SONAR_ESP32_SERIAL=/dev/ttyUSB1`.
   - UDP: el snippet `firmware/csi_line.c` y `WIFI_SONAR_ESP32_PORT=5005`.
5. Arrancá el panel, salí de la habitación y usá Calibrar. Sin esa captura vacía el detector no tiene línea base.
6. Para una segunda zona, repetí el receptor con otro nombre de nodo y cargá el mapa en la config (`zones`).

El parser ignora líneas cortadas o mezcladas con logs del monitor. Si no entra ningún frame, el indicador queda desconectado: revisá el puerto, la MAC del emisor y que el monitor serie no tenga el tty tomado.
