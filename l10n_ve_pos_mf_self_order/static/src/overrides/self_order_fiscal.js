/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { SelfOrder } from "@pos_self_order/app/services/self_order_service";
import { rpc } from "@web/core/network/rpc";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { TfhkaDriver } from "@l10n_ve_mf_base/drivers/TfhkaDriver";
import { buildKioskFiscalPayload } from "@l10n_ve_pos_mf_self_order/app/fiscal_payload";

/**
 * Conexión a la máquina fiscal (TFHKA, Web Serial) en el Kiosko/Autopedido.
 *
 * El Kiosko es DESATENDIDO: a diferencia de la caja (que trae un botón visible
 * `FiscalPrinterButton` en el navbar), aquí no hay botón de cara al cliente. Al
 * arrancar la app se intenta una reconexión SILENCIOSA (`autoConnect` sobre un
 * puerto previamente autorizado, que NO requiere gesto del usuario). El pareo
 * inicial manual (`requestPermission`, que sí exige un gesto) y la reimpresión
 * de fallidas quedan bajo modo debug.
 *
 * Se reutiliza el MISMO driver que la caja (`window.fiscalPrinter`, singleton
 * global del navegador): si el kiosko y un POS de caja conviven en el mismo
 * navegador, comparten la conexión.
 */
patch(SelfOrder.prototype, {
    setup() {
        super.setup(...arguments);
        // Solo en modo kiosko y si la caja tiene habilitada la máquina fiscal.
        // Fire-and-forget: no bloquea el arranque de la app.
        if (this.kioskMode && this.config?.access_button_mf) {
            this.ensureFiscalPrinterConnected();
        }
    },

    /**
     * Enganche de impresión fiscal (modelo REGISTRAR-PRIMERO).
     *
     * Se imprime la factura fiscal SOLO al llegar a la confirmación, cuando la
     * orden YA está registrada y facturada en Odoo (con id de servidor). Nunca
     * antes — así jamás se emite un documento fiscal (número SENIAT) sin su
     * orden/factura en Odoo. El número resultante se persiste en el servidor
     * (orden + account.move) vía `write_mf_invoice_data`.
     *
     * `confirmationPage` es el punto genérico por el que pasan todos los pagos
     * (Megasoft/terminal → bus PAYMENT_STATUS → connectNewData → aquí). Se
     * imprime solo si la orden está pagada y aún no tiene número fiscal; el
     * pago se deriva de `order.payment_ids` (ya presentes tras el registro).
     * Fire-and-forget: no bloquea la pantalla de confirmación.
     */
    async confirmationPage(screen_mode, device, access_token) {
        const res = await super.confirmationPage(...arguments);
        if (this.kioskMode && access_token && this.config?.access_button_mf) {
            const order = this.models["pos.order"].find(
                (o) => o.access_token === access_token
            );
            if (
                order &&
                !order.mf_invoice_number &&
                ["paid", "done", "invoiced"].includes(order.state)
            ) {
                this.printKioskFiscalInvoice(order).then((result) => {
                    if (!result || !result.valid) {
                        console.error(
                            "[MF Kiosk] impresión fiscal en confirmación falló:",
                            result && result.message
                        );
                        this.dialog.add(AlertDialog, {
                            title: _t("Factura fiscal no impresa"),
                            body: _t(
                                "La orden quedó registrada y facturada. La factura fiscal " +
                                    "no se pudo imprimir (motivo: %s). Puede reimprimirse desde " +
                                    "el menú de Debug MF.",
                                (result && result.message) || "error desconocido"
                            ),
                        });
                    }
                });
            }
        }
        return res;
    },

    /** @returns {TfhkaDriver|null} */
    getFiscalPrinter() {
        return window.fiscalPrinter || null;
    },

    /** @returns {boolean} */
    useFiscalMachine() {
        const printer = this.getFiscalPrinter();
        return Boolean(printer && printer.isConnected);
    },

    /**
     * Reconexión silenciosa al arrancar. Crea el singleton si no existe y trata
     * de abrir un puerto ya autorizado (sin prompt). Espeja
     * `FiscalPrinterButton._autoConnect` pero sin estado de UI.
     */
    async ensureFiscalPrinterConnected() {
        if (!("serial" in navigator)) {
            console.error("[MF Kiosk] Web Serial API no soportada en este navegador");
            return null;
        }
        try {
            if (!window.fiscalPrinter) {
                window.fiscalPrinter = new TfhkaDriver();
            }
            const printer = window.fiscalPrinter;
            if (!printer.isConnected) {
                await printer.connect();
            }
            return printer;
        } catch (error) {
            console.error("[MF Kiosk] Error en auto-conexión de la máquina fiscal", error);
            return null;
        }
    },

    /**
     * Pareo inicial manual (modo debug): pide permiso para elegir el puerto
     * serial (prompt del navegador — requiere gesto del usuario). Tras esto,
     * `ensureFiscalPrinterConnected` podrá reconectar silenciosamente.
     */
    async pairFiscalPrinter() {
        if (!("serial" in navigator)) {
            console.error("[MF Kiosk] Web Serial API no soportada en este navegador");
            return false;
        }
        if (!window.fiscalPrinter) {
            window.fiscalPrinter = new TfhkaDriver();
        }
        const printer = window.fiscalPrinter;
        const connected = await printer.connect({ requestPermission: true });
        if (connected) {
            const status = await printer.getStatus();
            printer.isConnected = Boolean(status);
        }
        return printer.isConnected;
    },

    /**
     * Imprime la factura fiscal de la orden del Kiosko en la máquina (TFHKA).
     *
     * Client-side puro: arma el payload desde la orden en memoria y lo manda al
     * driver, sin RPC al servidor. El número fiscal devuelto se guarda en la
     * orden (viaja al servidor al sincronizar vía `_load_pos_self_data_fields`).
     *
     * Idempotente: si la orden ya tiene `mf_invoice_number`, no reimprime (mismo
     * criterio que la caja, `!order.mf_invoice_number`).
     *
     * @param {Object} order  la orden del Kiosko (selfOrder.currentOrder)
     * @param {Object} opts   { paymentMethod (pos.payment.method), amount (VES) }
     * @returns {Promise<{valid:boolean, message?:string, response?:Object}>}
     */
    async printKioskFiscalInvoice(order, { paymentMethod, amount } = {}) {
        if (order.mf_invoice_number) {
            return { valid: true, message: "", alreadyPrinted: true };
        }

        // Reimpresión: si no se pasa el pago explícito (flujo en vivo), derivarlo
        // de la orden YA registrada (sus `payment_ids` ya están en el cliente
        // tras sincronizar). El monto se toma en la moneda de la orden; en este
        // despliegue la moneda base es la fiscal (VES), así que no se convierte.
        if (!paymentMethod || amount == null) {
            const payments = order.payment_ids || [];
            if (!paymentMethod) {
                paymentMethod = payments[0] && payments[0].payment_method_id;
            }
            if (amount == null) {
                amount = payments.reduce((sum, p) => sum + Number(p.amount || 0), 0);
            }
        }

        const printer = await this.ensureFiscalPrinterConnected();
        if (!printer || !printer.isConnected) {
            return {
                valid: false,
                message: "Máquina fiscal no conectada",
                printer_connection: false,
            };
        }

        const payload = buildKioskFiscalPayload(order, {
            config: this.config,
            company: this.company,
            currency: this.currency,
            paymentMethodCode: paymentMethod?.code_fiscal_printer,
            paymentAmount: amount,
        });
        if (!payload.valid) {
            return { valid: false, message: payload.message };
        }

        let response;
        try {
            response = await printer.printInvoice(payload);
        } catch (error) {
            console.error("[MF Kiosk] Error al imprimir en la máquina fiscal", error);
            return {
                valid: false,
                message: String(error?.message || error || "Error al imprimir"),
                printer_connection: true,
            };
        }

        if (!response || !response.success) {
            return {
                valid: false,
                message: (response && response.error) || "Error al imprimir en la máquina fiscal",
                printer_connection: true,
            };
        }

        // Guardar los datos de la MF en la orden en cliente (espejo de
        // PosStore.set_data_from_fiscal_machine).
        order.fiscal_machine = response.serial || response.serial_machine || "TFHKA-LOCAL";
        order.mf_invoice_number = response.invoiceNumber || response.invoice_number || "";
        order.mf_reportz = String(response.reportZ || response.mf_reportz || "");

        // Persistir el número en el servidor (orden + account.move) vía
        // write_mf_invoice_data, igual que la caja (PrintPendingOrderButton).
        // Solo si la orden YA está registrada en Odoo (id numérico). Con el
        // modelo "registrar-primero" siempre lo estará al llegar aquí.
        const persisted = await this._persistKioskFiscalNumber(order);
        return { valid: true, message: "", response, persisted };
    },

    /**
     * Persiste `mf_invoice_number`/`fiscal_machine`/`mf_reportz` en el servidor
     * (orden + account.move) vía el endpoint público del Kiosko, que delega en
     * `pos.order.write_mf_invoice_data`. Devuelve true si persistió.
     *
     * Si la orden aún no está sincronizada (id no numérico) no hay nada que
     * persistir por RPC (el número viajará con la orden al registrarse). Si el
     * RPC falla, NO es fatal: el papel ya salió y la orden ya existe en Odoo;
     * queda pendiente de persistir y se puede reintentar reimprimiendo.
     */
    async _persistKioskFiscalNumber(order) {
        if (typeof order.id !== "number") {
            return false;
        }
        try {
            const res = await rpc(
                "/l10n_ve_pos_mf_self_order/kiosk/write_mf_invoice_data",
                {
                    access_token: this.access_token,
                    order_id: order.id,
                    mf_invoice_number: order.mf_invoice_number,
                    fiscal_machine: order.fiscal_machine,
                    mf_reportz: order.mf_reportz || false,
                }
            );
            if (!res || !res.success) {
                console.error("[MF Kiosk] write_mf_invoice_data no persistió:", res && res.error);
                return false;
            }
            return true;
        } catch (error) {
            console.error("[MF Kiosk] falló persistir el número fiscal en el servidor", error);
            return false;
        }
    },

    /**
     * Reimprime en la máquina fiscal la última orden del Kiosko que quedó SIN
     * número fiscal (impresión fallida u omitida por máquina desconectada).
     * Herramienta de recuperación expuesta desde el modo debug. Deriva el pago
     * de la propia orden (`payment_ids`).
     *
     * @returns {Promise<{valid:boolean, message?:string, order?:Object}>}
     */
    async reprintLastKioskFiscalInvoice() {
        const pending = (this.models["pos.order"] || [])
            .filter(
                (o) =>
                    !o.mf_invoice_number &&
                    o.partner_id &&
                    (o.lines || []).length > 0 &&
                    (o.payment_ids || []).length > 0
            )
            .sort((a, b) => (b.id || 0) - (a.id || 0));
        const order = pending[0];
        if (!order) {
            return {
                valid: false,
                message: "No hay órdenes pendientes de imprimir en esta sesión",
            };
        }
        const result = await this.printKioskFiscalInvoice(order);
        return { ...result, order };
    },
});
