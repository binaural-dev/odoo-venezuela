/** @odoo-module */

import { WebSerialScale } from "@iot_webserial/web_serial_scale";
import { SerialConnection } from "@l10n_ve_mf_base/core/SerialConnection";
import { WebSerialScaleInterface } from "@point_of_sale/app/utils/scale/web_serial_scale_interface";
import { patch } from "@web/core/utils/patch";

/**
 * Búsqueda de la balanza Web Serial de Odoo 20 sin tocar la máquina fiscal.
 *
 * Al cargar, el POS de 20 recorre los puertos serie que el navegador tiene
 * autorizados para el sitio y prueba cada uno como balanza
 * (`openWebSerialDevice` de `iot_webserial`): lo abre a 9600 8E1, la misma
 * configuración de la TFHKA, manda "Ehello" y espera el eco "hello". La
 * máquina fiscal no contesta, a los 1000 ms `readUntil` lanza "The device has
 * been disconnected", el error sube hasta la carga del POS y el POS no abre.
 * Además el puerto queda abierto y la máquina fiscal ya no puede tomarlo.
 *
 * Aquí la búsqueda:
 * - salta el puerto de la máquina fiscal guardada (VID/PID) sin abrirlo;
 * - salta los puertos que ya están abiertos en la página, que tienen dueño;
 * - prueba los demás uno a uno y, si el sondeo falla, cierra ese puerto y
 *   sigue con el siguiente. No encontrar balanza nunca impide abrir el POS.
 *
 * `openWebSerialDevice` no permite excluir puertos ni atrapa el error del
 * sondeo, por eso se reemplaza en lugar de llamar a super.
 */
patch(WebSerialScaleInterface.prototype, {
    async connectToScale() {
        try {
            this.scale = await findWebSerialScale();
        } catch (error) {
            console.warn("l10n_ve_pos_mf:: no se pudo buscar la balanza Web Serial", error);
            this.scale = null;
        }
        return Boolean(this.scale);
    },
});

/**
 * @returns {Promise<WebSerialScale | null>}
 */
async function findWebSerialScale() {
    if (!navigator.serial) {
        return null;
    }
    const fiscalPrinter = new SerialConnection();
    const ports = await navigator.serial.getPorts();
    for (const port of ports) {
        if (!port.connected || port.readable || port.writable) {
            continue;
        }
        if (fiscalPrinter.isSavedDevice(port)) {
            continue;
        }
        const scale = new WebSerialScale(port);
        try {
            if (await scale.open()) {
                return scale;
            }
        } catch (error) {
            console.warn(
                "l10n_ve_pos_mf:: el puerto serie no respondió como balanza, se cierra",
                error
            );
            try {
                await port.close();
            } catch {
                // No llegó a abrirse (ocupado por otra pestaña o programa).
            }
        }
    }
    return null;
}
