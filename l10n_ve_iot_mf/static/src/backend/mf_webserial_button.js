/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, xml, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import {
    getBackendFiscalPrinter,
    ensurePaired,
    toDriverOrder,
    toBackendValues,
    toS1Values,
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
 * - sync_fiscal_data: Recupera número/serial/Z de un documento que salió
 *   impreso sin poder leer S1 (ticket 16293)
 * - fiscalizador: Herramienta técnica (modo debug)
 */
export class MfWebSerialButtonComponent extends Component {
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
            sync_fiscal_data: _t("Recuperar datos fiscales (MF)"),
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
                case "sync_fiscal_data":
                    await this.syncFiscalData();
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
    async logPrintFailure(reason, kind = false) {
        try {
            await this.orm.call("account.move", "log_mf_print_failure", [this.moveId], {
                action: this.props.action,
                reason: reason || false,
                kind: kind || false,
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

        // 2. Parear si hace falta (sin dejar el puerto abierto)
        const paired = await ensurePaired(driver);
        if (!paired) {
            this.notifyError(_t("No se pudo conectar con la máquina fiscal. Verifica el cable y el puerto."));
            await this.logPrintFailure(_t("Sin conexión con la máquina fiscal"), "no_connection");
            return;
        }

        // 3. Imprimir: withConnection abre el puerto bajo demanda solo por
        // esta operación y lo libera al terminar, para no bloquear otras
        // pestañas (POS, otro backoffice) que también hablen con la MF.
        this.notifyInfo(_t("Comunicando con la máquina fiscal, por favor espere..."));
        const order = toDriverOrder(payload);
        let response;
        let before = null;
        try {
            response = await driver.withConnection(async () => {
                // Foto de S1 antes de imprimir: si luego no se puede leer S1,
                // permite saber qué número le asignó la máquina (ticket 16293).
                // Si falla, se imprime igual: es solo un respaldo.
                const s1Before = await driver.readFiscalState();
                before = s1Before.success ? toS1Values(s1Before.data) : null;
                return driver[driverMethod](order);
            });
        } catch (error) {
            this.notifyError(this.errorMessage(error));
            const kind = error?.name === "FiscalPrinterBusyError" ? "no_connection" : false;
            await this.logPrintFailure(error?.message || String(error), kind);
            return;
        }
        if (!response.success && response.printed) {
            // La máquina aceptó el cierre: el documento salió impreso, solo
            // faltan sus datos. Reimprimir lo duplicaría.
            await this.orm.call("account.move", "mf_mark_pending_sync", [this.moveId], {
                action: this.props.action,
                reason: response.error || false,
                before,
            });
            this.notification.add(
                _t("El documento se imprimió, pero no se pudieron leer sus datos fiscales. NO lo vuelva a imprimir: use \"Recuperar datos fiscales (MF)\"."),
                { title: _t("Máquina Fiscal"), type: "warning", sticky: true }
            );
            await this.reloadRecord();
            return;
        }
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

    async reloadRecord() {
        try {
            await this.props.record.model.load();
        } catch (error) {
            window.location.reload();
        }
    }

    /**
     * Recupera los datos fiscales de un documento que salió impreso sin
     * poder leer S1: lee S1 y el backend decide si el número se puede
     * atribuir sin ambigüedad (ver account.move.mf_sync_fiscal_data).
     */
    async syncFiscalData() {
        const driver = getBackendFiscalPrinter();

        await this.orm.call("account.move", "check_mf_sync", [this.moveId]);

        const paired = await ensurePaired(driver);
        if (!paired) {
            this.notifyError(_t("No se pudo conectar con la máquina fiscal. Verifica el cable y el puerto."));
            return;
        }

        this.notifyInfo(_t("Leyendo los datos de la máquina fiscal, por favor espere..."));
        let s1Result;
        try {
            s1Result = await driver.withConnection(() => driver.readFiscalState());
        } catch (error) {
            this.notifyError(this.errorMessage(error));
            return;
        }
        if (!s1Result.success) {
            this.notifyError(
                _t("No se pudieron leer los datos de la máquina fiscal: ") + (s1Result.error || "")
            );
            return;
        }

        const result = await this.orm.call("account.move", "mf_sync_fiscal_data", [this.moveId], {
            s1: toS1Values(s1Result.data),
        });
        this.notifySuccess(_t("Datos fiscales recuperados. Nro: ") + result.sequence);
        await this.reloadRecord();
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

        const paired = await ensurePaired(driver);
        if (!paired) {
            this.notifyError(_t("No se pudo conectar con la máquina fiscal. Verifica el cable y el puerto."));
            await this.logPrintFailure(_t("Sin conexión con la máquina fiscal"), "no_connection");
            return;
        }

        this.notifyInfo(_t("Comunicando con la máquina fiscal, por favor espere..."));
        let response;
        try {
            response = await driver.withConnection(() =>
                driver.reprintDocument({
                    type: payload.type,
                    number: payload.mf_number,
                })
            );
        } catch (error) {
            this.notifyError(this.errorMessage(error));
            await this.logPrintFailure(error?.message || String(error));
            return;
        }
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
