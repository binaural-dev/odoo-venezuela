/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { selfOrderIndex } from "@pos_self_order/app/self_order_index";
import { MfDebugDialog } from "@l10n_ve_pos_mf_self_order/app/debug/mf_debug_dialog";

/**
 * Botón flotante "Debug MF", visible SOLO en modo debug (`?debug=1`), en la raíz
 * del Kiosko (aparece en TODAS las pantallas). Abre el panel de herramientas de
 * la máquina fiscal (`MfDebugDialog`): estado de conexión, pareo del puerto Web
 * Serial y reimpresión de la última factura pendiente. Extensible: nuevas
 * opciones se agregan dentro del dialog, no como botones sueltos aquí.
 */
patch(selfOrderIndex.prototype, {
    openMfDebug() {
        this.selfOrder.dialog.add(MfDebugDialog, {});
    },
});
