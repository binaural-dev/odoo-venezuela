/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";
import { InfoPopup } from "../InfoPopup/InfoPopup";

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
        super.setup();
        this.pos = usePos();
        this.popup = useService("popup");
        this.orm = useService("orm");
        this.state = useState({ isPrinting: false });
    }

    getFiscalPrinter() {
        return this.pos.getFiscalPrinter?.() || window.fiscalPrinter || null;
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
            await this.popup.add(ErrorPopup, {
                title: _t("Maquina Fiscal no conectada"),
                body: _t("Conecta la maquina fiscal antes de imprimir el pedido pendiente."),
            });
            return;
        }

        this.state.isPrinting = true;
        try {
            const data = await this.pos.get_data_invoice(order);
            if (!data || !data.valid) {
                await this.popup.add(ErrorPopup, {
                    title: _t("Error al preparar la factura"),
                    body: _t(data?.message || "No se pudo preparar la informacion del pedido."),
                });
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
                response = { success: false, error: _t("Tipo de documento no soportado: %s", data.type) };
            }

            if (!response.success) {
                await this.popup.add(ErrorPopup, {
                    title: _t("Error al imprimir"),
                    body: _t(response.error || "Error desconocido al imprimir en la maquina fiscal."),
                });
                return;
            }

            // 1. Actualizar el objeto local (UI reactiva)
            this.pos.set_data_from_fiscal_machine(order, response);

            // 2. Persistir en pos.order
            const mfVals = {
                mf_invoice_number: order.mf_invoice_number,
                fiscal_machine: order.fiscal_machine,
                mf_reportz: order.mf_reportz || false,
            };
            await this.orm.call("pos.order", "write", [[order.backendId], mfVals]);

            // 3. Propagar al account.move asociado (la factura contable pudo
            // haberse creado antes sin estos datos si la impresión fiscal
            // se omitió en su momento).
            const [orderRead] = await this.orm.searchRead(
                "pos.order",
                [["id", "=", order.backendId]],
                ["account_move"]
            );
            if (orderRead?.account_move) {
                await this.orm.call("account.move", "write", [
                    [orderRead.account_move[0]],
                    {
                        mf_invoice_number: order.mf_invoice_number,
                        mf_serial: order.fiscal_machine,
                        mf_reportz: order.mf_reportz || false,
                    },
                ]);
            }

            await this.popup.add(InfoPopup, {
                title: _t("Pedido facturado"),
                body: _t("El pedido se imprimio correctamente en la maquina fiscal."),
                confirmText: _t("Aceptar"),
            });

            // 4. Refrescar la lista de pendientes (invalida cache + refetch)
            await this.props.onOrderFiscalized(order.backendId);
        } catch (error) {
            console.error("PrintPendingOrderButton:: Error al imprimir pedido pendiente", error);
            await this.popup.add(ErrorPopup, {
                title: _t("Error al imprimir"),
                body: _t(error?.message || "Error interno al comunicar con la maquina fiscal."),
            });
        } finally {
            this.state.isPrinting = false;
        }
    }
}
