/** @odoo-module **/

import { DebugWidget } from "@point_of_sale/app/debug/debug_widget";
import { patch } from "@web/core/utils/patch";
import { FiscalDebuggerPopup } from "../components/FiscalDebugger/FiscalDebuggerPopup";
import { useService } from "@web/core/utils/hooks";

/**
 * Override del DebugWidget para añadir funciones de máquina fiscal
 */
patch(DebugWidget.prototype, {
    setup() {
        super.setup(...arguments);
        this.popup = useService("popup");
        this.orm = useService("orm");
    },

    /**
     * Abre el Fiscalizador (Debugger de Máquina Fiscal)
     */
    async openFiscalDebugger() {
        await this.popup.add(FiscalDebuggerPopup, {
            title: "Fiscalizador - Debugger de Máquina Fiscal",
        });
    },

    /**
     * Imprime la programación de la máquina fiscal (comando PJ)
     */
    async programacion() {
        const fiscalPrinter = window.fiscalPrinter;
        
        if (!fiscalPrinter || !fiscalPrinter.isConnected) {
            alert("Error: Máquina fiscal no conectada");
            return;
        }

        try {
            const result = await fiscalPrinter.sendCommand("PJ");
            
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
     * Obtiene la orden actual para debugging
     */
    async get_order() {
        let uid = this.env.services.pos.get_order().uid;
        const values = Object.values(this.env.services.pos.toRefundLines);
        let lines = [];
        
        for (let i = 0; i < values.length; i++) {
            if (values[i].destinationOrderUid == uid) {
                lines.push(values[i]);
            }
        }

        if (lines.length > 0) {
            let response = await this.orm.call("pos.order", "get_order_by_uid", [
                [],
                lines[0].orderline.orderUid
            ]);
            console.log("Order retrieved:", response);
        }
    },

    /**
     * Logger para debugging
     */
    logger() {
        console.log("POS State:", this.env.services.pos);
        console.log("Current Order:", this.env.services.pos.get_order());
        console.log("Fiscal Printer:", window.fiscalPrinter);
    }
});
