/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, xml, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import {
    getBackendFiscalPrinter,
    ensureConnected,
    toDriverOrder,
    toBackendValues,
} from "./mf_webserial_service";
import { MfFiscalizadorDialog } from "./mf_fiscalizador_dialog";

/**
 * Widget de botón para imprimir documentos fiscales desde `account.move`
 * usando Web Serial API (reemplaza al widget `iot-mf-button`).
 *
 * Acciones soportadas (paridad con el flujo IoT anterior):
 * - print_out_invoice: Factura fiscal
 * - print_out_refund: Nota de crédito fiscal
 * - print_debit_note: Nota de débito fiscal
 * - reprint_document: Reimpresión del documento actual
 * - fiscalizador: Herramienta técnica (modo debug)
 */
export class MfWebSerialButtonComponent extends Component {
    static props = ["*"];
    static template = xml`
        <button class="btn btn-primary" t-att-disabled="state.busy" t-on-click="onClick">
            <i t-if="state.busy" class="fa fa-spinner fa-spin me-1"/>
            <span t-esc="state.label"/>
        </button>`;

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.notification = useService("notification");

        this.buttonLabels = {
            print_out_invoice: _t("Imprimir Factura (MF)"),
            print_out_refund: _t("Imprimir NC (MF)"),
            print_debit_note: _t("Imprimir ND (MF)"),
            reprint_document: _t("Reimprimir (MF)"),
            fiscalizador: _t("Fiscalizador MF"),
        };

        this.state = useState({
            busy: false,
            label: this.buttonLabels[this.props.action] || this.props.action || "MF",
        });
    }

    get moveId() {
        return this.props.record.resId;
    }

    notifyError(message) {
        this.notification.add(message, {
            title: _t("Máquina Fiscal"),
            type: "danger",
            sticky: true,
        });
    }

    notifyInfo(message) {
        this.notification.add(message, { title: _t("Máquina Fiscal"), type: "info" });
    }

    notifySuccess(message) {
        this.notification.add(message, { title: _t("Máquina Fiscal"), type: "success" });
    }

    /**
     * Extrae un mensaje legible de un error RPC/JS.
     */
    errorMessage(error) {
        return (
            error?.data?.message ||
            error?.message?.data?.message ||
            error?.message ||
            _t("Error de comunicación con la máquina fiscal")
        );
    }

    async onClick() {
        if (this.state.busy) {
            return;
        }

        if (this.props.action === "fiscalizador") {
            this.dialog.add(MfFiscalizadorDialog, {});
            return;
        }

        if (!("serial" in navigator)) {
            this.notifyError(
                _t("Este navegador no soporta Web Serial API. Usa Chrome/Edge en contexto seguro (https o localhost).")
            );
            await this.logPrintFailure(_t("Navegador sin soporte Web Serial"));
            return;
        }

        this.state.busy = true;
        try {
            switch (this.props.action) {
                case "print_out_invoice":
                    await this.printDocument("check_print_out_invoice", "print_out_invoice", "printInvoice");
                    break;
                case "print_out_refund":
                    await this.printDocument("check_print_out_refund", "print_out_refund", "printCreditNote");
                    break;
                case "print_debit_note":
                    await this.printDocument("check_print_debit_note", "print_debit_note", "printDebitNote");
                    break;
                case "reprint_document":
                    await this.reprintDocument();
                    break;
                default:
                    this.notifyError(_t("Acción de máquina fiscal desconocida: ") + this.props.action);
            }
        } catch (error) {
            console.error("MfWebSerialButton:: Error", error);
            this.notifyError(this.errorMessage(error));
        } finally {
            this.state.busy = false;
        }
    }

    /**
     * Deja constancia en el chatter del documento de un intento fallido
     * de impresión fiscal (sin conexión, error del driver, etc.).
     */
    async logPrintFailure(reason) {
        try {
            await this.orm.call("account.move", "log_mf_print_failure", [this.moveId], {
                action: this.props.action,
                reason: reason || false,
            });
        } catch (error) {
            // No bloquear el flujo por un fallo al escribir en el chatter
            console.warn("MfWebSerialButton:: No se pudo registrar el fallo en el chatter", error);
        }
    }

    /**
     * Flujo genérico de impresión fiscal:
     * 1. check_* en backend (valida y construye payload)
     * 2. Conexión Web Serial + impresión con TfhkaDriver
     * 3. print_* en backend (persiste mf_invoice_number / mf_serial)
     */
    async printDocument(checkMethod, persistMethod, driverMethod) {
        const driver = getBackendFiscalPrinter();

        // 1. Validar y obtener payload desde el backend
        const payload = await this.orm.call("account.move", checkMethod, [this.moveId]);
        if (payload && payload.valid === false) {
            this.notifyError(payload.message || _t("Documento no válido para impresión fiscal"));
            return;
        }

        // 2. Conectar (requestPort si es necesario) e imprimir
        this.notifyInfo(_t("Comunicando con la máquina fiscal, por favor espere..."));
        const connected = await ensureConnected(driver);
        if (!connected) {
            this.notifyError(_t("No se pudo conectar con la máquina fiscal. Verifica el cable y el puerto."));
            await this.logPrintFailure(_t("Sin conexión con la máquina fiscal"));
            return;
        }

        const order = toDriverOrder(payload);
        const response = await driver[driverMethod](order);
        if (!response.success) {
            this.notifyError(response.error || _t("Error al imprimir el documento fiscal"));
            await this.logPrintFailure(response.error || _t("Error del driver al imprimir"));
            return;
        }

        // 3. Persistir número fiscal / serial en el documento
        const values = toBackendValues(response);
        await this.orm.call("account.move", persistMethod, [this.moveId, values]);

        this.notifySuccess(_t("Documento fiscal impreso correctamente. Nro: ") + values.data.sequence);
        window.location.reload();
    }

    /**
     * Reimpresión de un documento fiscal ya emitido.
     */
    async reprintDocument() {
        const driver = getBackendFiscalPrinter();

        const payload = await this.orm.call("account.move", "check_reprint", [this.moveId]);
        if (payload && payload.valid === false) {
            this.notifyError(payload.message || _t("Documento no válido para reimpresión"));
            return;
        }

        this.notifyInfo(_t("Comunicando con la máquina fiscal, por favor espere..."));
        const connected = await ensureConnected(driver);
        if (!connected) {
            this.notifyError(_t("No se pudo conectar con la máquina fiscal. Verifica el cable y el puerto."));
            await this.logPrintFailure(_t("Sin conexión con la máquina fiscal"));
            return;
        }

        const response = await driver.reprintDocument({
            type: payload.type,
            number: payload.mf_number,
        });
        if (!response.success) {
            this.notifyError(response.error || _t("Error al reimprimir el documento fiscal"));
            await this.logPrintFailure(response.error || _t("Error del driver al reimprimir"));
            return;
        }

        this.notifySuccess(_t("Documento reimpreso correctamente"));
    }
}

export const mfWebSerialButton = {
    component: MfWebSerialButtonComponent,
    extractProps: ({ attrs }) => {
        return { action: attrs.action };
    },
};

registry.category("view_widgets").add("mf-webserial-button", mfWebSerialButton);
