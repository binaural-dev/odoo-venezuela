import { patch } from "@web/core/utils/patch";
import { selfOrderIndex } from "@pos_self_order/app/self_order_index";
import { IdentificationPage } from "@l10n_ve_pos_self_order/app/pages/identification_page/identification_page";
import { KioskDebugDialog } from "@l10n_ve_pos_self_order/app/debug/kiosk_debug_dialog";

// Register IdentificationPage so the new "identification" slot added to
// pos_self_order.selfOrderIndex can resolve the component.
patch(selfOrderIndex, {
    components: {
        ...selfOrderIndex.components,
        IdentificationPage,
    },
});

/**
 * Botón flotante "Debug Kiosko", visible SOLO en modo debug (`?debug=1`), en la
 * raíz del Kiosko (aparece en TODAS las pantallas). Abre el panel de debug
 * (`KioskDebugDialog`): órdenes de la sesión (crear factura de las pendientes) y
 * reintentos de la cola de registro. `l10n_ve_pos_mf_self_order` extiende ese
 * diálogo con las herramientas de la máquina fiscal, así que el MISMO botón abre
 * el panel ya completo cuando el módulo fiscal está instalado (sin un segundo
 * botón).
 */
patch(selfOrderIndex.prototype, {
    openKioskDebug() {
        this.selfOrder.dialog.add(KioskDebugDialog, {});
    },
});
