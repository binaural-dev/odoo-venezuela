/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, xml, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { getBackendFiscalPrinter, ensureConnected } from "./mf_webserial_service";

export class MfReportsWebSerialButtonComponent extends Component {
    static props = ["*"];
    static template = xml`
        <button class="btn btn-primary mb-2" t-att-disabled="state.busy" t-on-click="onClick">
            <i t-if="state.busy" class="fa fa-spinner fa-spin me-1"/>
            <span t-esc="state.label"/>
        </button>`;

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.notification = useService("notification");

        this.buttonLabels = {
            report_x: _t("Imprimir Reporte X"),
            report_z: _t("Imprimir Reporte Z"),
            print_resume_date: _t("Impresion por rango de fecha"),
            reprint_invoices_date: _t("Reimpresion facturas por fecha"),
        };

        this.state = useState({
            busy: false,
            label: this.buttonLabels[this.props.action] || this.props.action || "MF",
        });
    }

    notify(message, type = "info", sticky = false) {
        this.notification.add(message, {
            title: _t("Maquina Fiscal"),
            type,
            sticky,
        });
    }

    errorMessage(error) {
        return (
            error?.data?.message ||
            error?.message?.data?.message ||
            error?.message ||
            _t("Error de comunicacion con la maquina fiscal")
        );
    }

    async _connectDriver() {
        const driver = getBackendFiscalPrinter();
        const connected = await ensureConnected(driver);
        if (!connected) {
            this.notify(_t("No se pudo conectar con la maquina fiscal"), "danger", true);
            return null;
        }
        return driver;
    }

    _normalizeDate(rawDate) {
        if (!rawDate) {
            return null;
        }

        if (typeof rawDate === "object") {
            if (typeof rawDate.toFormat === "function" && rawDate.isValid !== false) {
                const year = String(rawDate.year || "").padStart(4, "0");
                const month = String(rawDate.month || "").padStart(2, "0");
                const day = String(rawDate.day || "").padStart(2, "0");
                if (year && month && day) {
                    return { year, month, day };
                }
            }
            if (rawDate instanceof Date && !Number.isNaN(rawDate.getTime())) {
                const year = String(rawDate.getFullYear()).padStart(4, "0");
                const month = String(rawDate.getMonth() + 1).padStart(2, "0");
                const day = String(rawDate.getDate()).padStart(2, "0");
                return { year, month, day };
            }
            if (
                Number.isInteger(rawDate.year) &&
                Number.isInteger(rawDate.month) &&
                Number.isInteger(rawDate.day)
            ) {
                const year = String(rawDate.year).padStart(4, "0");
                const month = String(rawDate.month).padStart(2, "0");
                const day = String(rawDate.day).padStart(2, "0");
                return { year, month, day };
            }
        }

        const value = String(rawDate).trim();
        let match = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
        if (match) {
            const [, year, month, day] = match;
            return { year, month, day };
        }

        match = value.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
        if (match) {
            const [, day, month, year] = match;
            return { year, month, day };
        }

        return null;
    }

    _formatDateToDDMMYY(rawDate) {
        const normalized = this._normalizeDate(rawDate);
        if (!normalized) {
            return "";
        }
        return `${normalized.day}${normalized.month}${normalized.year.slice(-2)}`;
    }

    _formatDateToYYYYMMDD(rawDate) {
        const normalized = this._normalizeDate(rawDate);
        if (!normalized) {
            return "";
        }
        return `${normalized.year}${normalized.month}${normalized.day}`;
    }

    _getDateRange() {
        const rawFrom = this.props.record?.data?.date_from;
        const rawTo = this.props.record?.data?.date_to;

        const date_from = this._formatDateToDDMMYY(rawFrom);
        const date_to = this._formatDateToDDMMYY(rawTo);

        if (!date_from || !date_to) {
            throw new Error(_t("Debes indicar una fecha desde/hasta valida."));
        }

        const fromComparable = this._formatDateToYYYYMMDD(rawFrom);
        const toComparable = this._formatDateToYYYYMMDD(rawTo);
        if (!fromComparable || !toComparable) {
            throw new Error(_t("Debes indicar una fecha desde/hasta valida."));
        }

        if (toComparable < fromComparable) {
            throw new Error(_t("Date To must be greater than or equal to Date From."));
        }

        return { date_from, date_to };
    }

    async _syncReportZ(driver) {
        const s1Result = await driver._readS1Data();
        const counter = s1Result.data?.dailyClosureCounter;
        if (!s1Result.success || !s1Result.data?.registeredMachineNumber || !Number.isInteger(counter)) {
            this.notify(
                _t("Z impreso, pero no se pudo leer S1 para sincronizar Odoo."),
                "warning",
                true
            );
            return;
        }

        const value = {
            valid: true,
            data: {
                _registeredMachineNumber: s1Result.data.registeredMachineNumber,
                _dailyClosureCounter: counter,
            },
        };
        await this.orm.call("account.move", "report_z", [[], s1Result.data.registeredMachineNumber, value]);
    }

    async onClick() {
        if (this.state.busy) {
            return;
        }

        if (this.props.action === "report_z") {
            this.dialog.add(ConfirmationDialog, {
                title: _t("Confirmar Reporte Z"),
                body: _t(
                    "El Reporte Z cerrara el dia fiscal actual. Esta accion es irreversible. Deseas continuar?"
                ),
                confirmLabel: _t("Imprimir Reporte Z"),
                cancelLabel: _t("Cancelar"),
                confirm: () => this.executeAction(),
                cancel: () => {},
            });
            return;
        }

        await this.executeAction();
    }

    async executeAction() {
        this.state.busy = true;
        try {
            if (!("serial" in navigator)) {
                this.notify(
                    _t(
                        "Este navegador no soporta Web Serial API. Usa Chrome/Edge en contexto seguro (https o localhost)."
                    ),
                    "danger",
                    true
                );
                return;
            }

            const driver = await this._connectDriver();
            if (!driver) {
                return;
            }

            let result;
            if (this.props.action === "report_x") {
                result = await driver.printReportX();
            } else if (this.props.action === "report_z") {
                result = await driver.printReportZ();
                if (result.success) {
                    await this._syncReportZ(driver);
                }
            } else if (this.props.action === "print_resume_date") {
                const payload = await this._getDateRange();
                result = await driver.sendCommand(`I2S${payload.date_from}${payload.date_to}`, 30000);
            } else if (this.props.action === "reprint_invoices_date") {
                const payload = await this._getDateRange();
                const from = payload.date_from.padStart(7, "0");
                const to = payload.date_to.padStart(7, "0");
                result = await driver.sendCommand(`Rf${from}${to}`, 60000);
            } else {
                this.notify(_t("Accion de maquina fiscal desconocida"), "danger", true);
                return;
            }

            if (!result?.success) {
                this.notify(result?.error || _t("Operacion fiscal fallida"), "danger", true);
                return;
            }

            this.notify(_t("Operacion enviada correctamente a la maquina fiscal"), "success");
        } catch (error) {
            console.error("MfReportsWebSerialButton:: Error", error);
            this.notify(this.errorMessage(error), "danger", true);
        } finally {
            this.state.busy = false;
        }
    }
}

export const mfReportsWebSerialButton = {
    component: MfReportsWebSerialButtonComponent,
    extractProps: ({ attrs }) => ({ action: attrs.action }),
};

registry.category("view_widgets").add("mf-reports-webserial-button", mfReportsWebSerialButton);
