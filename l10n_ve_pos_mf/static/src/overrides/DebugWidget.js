/** @odoo-module **/

import { DebugWidget } from "@point_of_sale/app/debug/debug_widget";
import { patch } from "@web/core/utils/patch";
import { FiscalDebuggerPopup } from "../components/FiscalDebugger/FiscalDebuggerPopup";
import { useService } from "@web/core/utils/hooks";

/**
 * Override del DebugWidget para añadir el botón del Fiscalizador
 */
patch(DebugWidget.prototype, {
    setup() {
        super.setup(...arguments);
        this.popup = useService("popup");
    },

    /**
     * Abre el Fiscalizador (Debugger de Máquina Fiscal)
     */
    async openFiscalDebugger() {
        await this.popup.add(FiscalDebuggerPopup, {
            title: "Fiscalizador - Debugger de Máquina Fiscal",
        });
    },
});
