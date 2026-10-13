/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { KioskDebugDialog } from "@l10n_ve_pos_self_order/app/debug/kiosk_debug_dialog";

/**
 * Extensión fiscal del panel de Debug del Kiosko (`KioskDebugDialog`, base).
 *
 * Añade las herramientas de la MÁQUINA FISCAL (pareo del puerto Web Serial y
 * comprobación del estado de conexión) sobre el shell genérico de base (que ya
 * trae "Ver órdenes" y los reintentos de la cola de registro).
 *
 * El Kiosko conecta bajo demanda (abre el puerto solo durante cada
 * impresión/pareo y lo libera al terminar, ver `self_order_fiscal.js`), así que
 * el badge de estado NO puede leer un flag "conectado" en memoria — en reposo
 * sería casi siempre falso aunque todo esté bien. Por eso el estado mostrado es
 * el resultado de la ÚLTIMA prueba explícita (pareo/"Comprobar estado").
 */
patch(KioskDebugDialog.prototype, {
    setup() {
        super.setup(...arguments);
        this.state.connected = null;
    },

    get connected() {
        return this.state.connected;
    },

    _describe(res) {
        if (res === true) {
            return _t("Fiscal machine connected.");
        }
        if (res === false) {
            return _t("Could not connect the fiscal machine.");
        }
        return super._describe(res);
    },

    onCheckStatus() {
        this._run(_t("Check connection status"), async () => {
            if (typeof this.selfOrder.checkFiscalPrinterConnection !== "function") {
                return { valid: false, message: _t("Not available") };
            }
            const ok = await this.selfOrder.checkFiscalPrinterConnection();
            this.state.connected = ok;
            return ok;
        });
    },

    onPair() {
        this._run(_t("Pair fiscal machine"), async () => {
            const ok = await this.selfOrder.pairFiscalPrinter();
            this.state.connected = ok;
            return ok;
        });
    },
});
