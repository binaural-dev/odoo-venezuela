/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

/**
 * Botón "Imprimir pedido pendiente" en la pantalla de Órdenes (TicketScreen).
 *
 * Se muestra únicamente cuando el pedido seleccionado NO tiene
 * `mf_invoice_number` (es decir, nunca se imprimió en la máquina fiscal).
 * Reutiliza exactamente el mismo flujo que se ejecuta al validar un pedido
 * por primera vez (`PosStore.pushToMF`): construye los datos de factura con
 * `get_data_invoice`, los convierte al formato del driver con
 * `_convertOrderForDriver`, e imprime vía Web Serial API.
 *
 * A diferencia de `pushToMF`, este botón además propaga el resultado
 * (mf_invoice_number, fiscal_machine, mf_reportz) al `account.move` asociado
 * al pedido, ya que la factura contable pudo haberse generado sin esos datos
 * si en su momento la impresión fiscal falló o se omitió.
 */
export class PrintPendingOrderButton extends Component {
    static template = "l10n_ve_pos_mf.PrintPendingOrderButton";
    static props = {
        order: { type: Object, optional: true },
        onOrderFiscalized: { type: Function, optional: true },
    };
    static defaultProps = {
        onOrderFiscalized: () => {},
    };

    setup() {
        this.pos = usePos();
        this.dialog = useService("dialog");
        this.orm = useService("orm");
        this.state = useState({ isPrinting: false });
    }

    getFiscalPrinter() {
        return this.pos.getFiscalPrinter?.() || window.fiscalPrinter || null;
    }

    _alert(title, body) {
        this.dialog.add(AlertDialog, { title, body });
    }

    async _onClick() {
        if (this.state.isPrinting) {
            return;
        }

        const order = this.props.order;
        if (!order || order.mf_invoice_number) {
            return;
        }

        const driver = this.getFiscalPrinter();
        if (!driver || !driver.isConnected) {
            this._alert(
                _t("Maquina Fiscal no conectada"),
                _t("Conecta la maquina fiscal antes de imprimir el pedido pendiente.")
            );
            return;
        }

        this.state.isPrinting = true;
        try {
            const data = await this.pos.get_data_invoice(order);
            if (!data || !data.valid) {
                this._alert(
                    _t("Error al preparar la factura"),
                    _t(data?.message || "No se pudo preparar la informacion del pedido.")
                );
                return;
            }

            const driverOrder = this.pos._convertOrderForDriver(order, data);

            let response;
            if (data.type === "out_invoice") {
                response = await driver.printInvoice(driverOrder);
            } else if (data.type === "out_refund") {
                response = await driver.printCreditNote(driverOrder);
            } else if (data.type === "out_debit") {
                response = await driver.printDebitNote(driverOrder);
            } else {
                response = {
                    success: false,
                    error: _t("Tipo de documento no soportado: %s", data.type),
                };
            }

            if (!response.success) {
                this._alert(
                    _t("Error al imprimir"),
                    _t(response.error || "Error desconocido al imprimir en la maquina fiscal.")
                );
                return;
            }

            // 1. Actualizar el objeto local (UI reactiva)
            this.pos.set_data_from_fiscal_machine(order, response);

            // 2. Persistir en pos.order (via sudo en backend, ya que estos
            // campos son readonly=True a nivel de modelo) y propagar los
            // mismos datos al account.move asociado, si existe.
            const mfResult = await this.orm.call("pos.order", "write_mf_invoice_data", [
                [order.id],
                order.mf_invoice_number,
                order.fiscal_machine,
                order.mf_reportz || false,
            ]);

            // 3. Redirigir a finalización inmediatamente
            // (el refresco de pendientes se hace en segundo plano)
            const orderUuid = order.uuid;
            this.pos.navigate("ReceiptScreen", { orderUuid });

            this.props.onOrderFiscalized(order.id).catch((refreshError) => {
                console.warn(
                    "PrintPendingOrderButton:: No se pudo refrescar la lista de pendientes",
                    refreshError
                );
            });
        } catch (error) {
            console.error("PrintPendingOrderButton:: Error al imprimir pedido pendiente", error);
            this._alert(
                _t("Error al imprimir"),
                _t(error?.message || "Error interno al comunicar con la maquina fiscal.")
            );
        } finally {
            this.state.isPrinting = false;
        }
    }
}
