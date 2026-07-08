/** @odoo-module **/

import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

/**
 * Botón de reimpresión de documento fiscal en la pantalla de Ticket (POS).
 *
 * Reimprime la factura/NC fiscal ya emitida directamente vía Web Serial
 * API (TfhkaDriver.reprintDocument).
 *
 * Caso de uso principal: el cliente perdió su ticket físico y solicita una
 * copia; el cajero busca el pedido ya facturado y reimprime desde aquí.
 */
export class ReprintInvoiceButton extends Component {
    static template = "l10n_ve_pos_mf.ReprintInvoiceButton";
    static props = {
        order: { type: Object, optional: true },
    };

    setup() {
        this.pos = usePos();
        this.dialog = useService("dialog");
    }

    /**
     * Obtiene la instancia del driver de la máquina fiscal (Web Serial)
     * @returns {TfhkaDriver|null}
     */
    getFiscalPrinter() {
        return window.fiscalPrinter || null;
    }

    _alert(title, body) {
        this.dialog.add(AlertDialog, { title, body });
    }

    async _onClick() {
        const order = this.props.order;

        // Solo se puede reimprimir un documento que YA tiene número fiscal
        if (!order || !order.mf_invoice_number) {
            this._alert(
                _t("Nada que reimprimir"),
                _t("Este pedido no tiene un número de factura fiscal asociado.")
            );
            return;
        }

        const driver = this.getFiscalPrinter();
        if (!driver || !driver.isConnected) {
            this._alert(
                _t("Máquina Fiscal no conectada"),
                _t("Conecta la máquina fiscal antes de reimprimir el documento.")
            );
            return;
        }

        const type = order.totalDue >= 0 ? "out_invoice" : "out_refund";

        try {
            const result = await driver.reprintDocument({
                type,
                number: order.mf_invoice_number,
            });

            if (result.success) {
                this._alert(
                    _t("Documento reimpreso"),
                    _t("El documento fiscal se reimprimió correctamente.")
                );
            } else {
                this._alert(
                    _t("Error al reimprimir"),
                    result.error || _t("Error desconocido al reimprimir el documento fiscal.")
                );
            }
        } catch (error) {
            console.error("ReprintInvoiceButton:: Error al reimprimir", error);
            this._alert(
                _t("Error al reimprimir"),
                error?.message || _t("Error interno al comunicar con la máquina fiscal.")
            );
        }
    }
}
