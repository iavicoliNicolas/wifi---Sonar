/*
 * Reemplazo del ets_printf de examples/get-started/csi_recv.
 * El callback oficial ya entrega wifi_csi_info_t. Esto solo arma la línea corta.
 * Pares del buffer: imag, real, imag, real, ... como documenta Espressif.
 *
 * Enviá `line` por el puerto serie o por UDP al host del panel (puerto 5005).
 * WIFI_SONAR_NODE es un nombre corto ("living"), no una persona.
 */

#include <math.h>
#include <stdio.h>

#ifndef WIFI_SONAR_NODE
#define WIFI_SONAR_NODE "nodo"
#endif

static void wifi_sonar_format_line(const wifi_csi_info_t *info, char *out, size_t out_len) {
    const wifi_pkt_rx_ctrl_t *rx = &info->rx_ctrl;
    double seconds = (double)rx->timestamp / 1000000.0;
    int used = snprintf(out, out_len, "CSI,%s,%.6f,%d,", WIFI_SONAR_NODE, seconds, rx->rssi);
    if (used < 0 || (size_t)used >= out_len) {
        return;
    }
    for (int i = 0; i + 1 < info->len; i += 2) {
        double imag = (double)(int8_t)info->buf[i];
        double real = (double)(int8_t)info->buf[i + 1];
        double amp = sqrt(real * real + imag * imag);
        int wrote = snprintf(out + used, out_len - (size_t)used, "%s%.4f", (i == 0) ? "" : "|", amp);
        if (wrote < 0 || (size_t)wrote >= out_len - (size_t)used) {
            return;
        }
        used += wrote;
    }
    if ((size_t)used + 1 < out_len) {
        out[used] = '\n';
        out[used + 1] = '\0';
    }
}
