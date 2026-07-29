/** @odoo-module **/

import { DebugWidget } from "@point_of_sale/app/utils/debug/debug_widget";
import { patch } from "@web/core/utils/patch";
import { FiscalDebuggerPopup } from "../components/FiscalDebugger/FiscalDebuggerPopup";
import { useService } from "@web/core/utils/hooks";

/**
 * Override del DebugWidget para añadir funciones de máquina fiscal
 */
patch(DebugWidget.prototype, {
    setup() {
        super.setup(...arguments);
        this.dialog = useService("dialog");
        this.orm = useService("orm");
    },

    /**
     * Abre el Fiscalizador (Debugger de Máquina Fiscal)
     */
    openFiscalDebugger() {
        this.dialog.add(FiscalDebuggerPopup, {
            title: "Fiscalizador - Debugger de Máquina Fiscal",
        });
    },

    /**
     * Imprime la programación de la máquina fiscal (comando D)
     */
    async programacion() {
        const fiscalPrinter = window.fiscalPrinter;

        if (!fiscalPrinter || !fiscalPrinter.isConnected) {
            alert("Error: Máquina fiscal no conectada");
            return;
        }

        try {
            const result = await fiscalPrinter.sendCommand("D");

            if (result.success) {
                console.log("Programación impresa:", result);
            } else {
                alert(`Error al imprimir programación: ${result.error}`);
            }
        } catch (error) {
            alert(`Error: ${error.message}`);
        }
    },

    /**
     * Imprime reporte X
     */
    async report_x() {
        const fiscalPrinter = window.fiscalPrinter;

        if (!fiscalPrinter || !fiscalPrinter.isConnected) {
            alert("Error: Máquina fiscal no conectada");
            return;
        }

        try {
            const result = await fiscalPrinter.sendCommand("I0X");

            if (result.success) {
                console.log("Reporte X impreso:", result);
            } else {
                alert(`Error al imprimir reporte X: ${result.error}`);
            }
        } catch (error) {
            alert(`Error: ${error.message}`);
        }
    },

    /**
     * Obtiene la orden original afectada (si la actual es una devolución)
     */
    async get_order() {
        const pos = this.env.services.pos;
        const order = pos.getOrder();
        if (!order) {
            console.log("No hay orden activa");
            return;
        }

        const refundLine = [...(order.lines || [])].find(
            (line) => line.refunded_orderline_id
        );
        const originalOrder = refundLine?.refunded_orderline_id?.order_id;
        const originalUid = originalOrder?.uuid || originalOrder?.pos_reference;

        if (originalUid) {
            const response = await this.orm.call("pos.order", "get_order_by_uid", [
                [],
                originalUid,
            ]);
            console.log("Order retrieved:", response);
        } else {
            console.log("La orden actual no es una devolución");
        }
    },

    /**
     * Logger para debugging
     */
    logger() {
        console.log("POS State:", this.env.services.pos);
        console.log("Current Order:", this.env.services.pos.getOrder());
        console.log("Fiscal Printer:", window.fiscalPrinter);
    },
});
