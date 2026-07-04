/** @odoo-module **/

import { Component, xml, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { getBackendFiscalPrinter, ensureConnected } from "./mf_webserial_service";

/**
 * Fiscalizador MF - Herramienta técnica para diagnóstico de la máquina fiscal
 * desde Facturación/Contabilidad (visible solo en modo desarrollador).
 *
 * Acciones:
 * - Conectar / verificar conexión Web Serial
 * - Leer estado (ENQ) y datos S1 (serial, contadores, últimos números)
 * - Reporte X
 * - Reporte Z (con confirmación + sincronización de mf_reportz en Odoo)
 * - Envío de comando raw (avanzado)
 */
export class MfFiscalizadorDialog extends Component {
    static components = { Dialog };
    static props = {
        close: Function,
    };
    static template = xml`
        <Dialog title="title" size="'lg'">
            <div class="d-flex gap-2 mb-3 flex-wrap">
                <button class="btn btn-primary" t-att-disabled="state.busy" t-on-click="connect">
                    <i class="fa fa-plug me-1"/>Conectar
                </button>
                <button class="btn btn-secondary" t-att-disabled="state.busy" t-on-click="readStatus">
                    <i class="fa fa-heartbeat me-1"/>Estado (ENQ)
                </button>
                <button class="btn btn-secondary" t-att-disabled="state.busy" t-on-click="readS1">
                    <i class="fa fa-info-circle me-1"/>Datos S1
                </button>
                <button class="btn btn-secondary" t-att-disabled="state.busy" t-on-click="readS4">
                    <i class="fa fa-credit-card me-1"/>Medios de Pago (S4)
                </button>
                <button class="btn btn-warning" t-att-disabled="state.busy" t-on-click="reportX">
                    <i class="fa fa-file-text-o me-1"/>Reporte X
                </button>
                <button class="btn btn-danger" t-att-disabled="state.busy" t-on-click="reportZ">
                    <i class="fa fa-lock me-1"/>Reporte Z
                </button>
                <span class="ms-auto align-self-center">
                    <span t-if="state.connected" class="badge text-bg-success">Conectada</span>
                    <span t-else="" class="badge text-bg-secondary">Desconectada</span>
                </span>
            </div>
            <div class="input-group mb-3">
                <input type="text" class="form-control" t-model="state.command"
                       placeholder="Comando raw TFHKA (ej. S1, S3, D)"/>
                <button class="btn btn-outline-secondary" t-att-disabled="state.busy" t-on-click="sendRaw">
                    Enviar
                </button>
            </div>
            <div class="border rounded p-2 bg-100"
                 style="max-height: 320px; overflow: auto; font-family: monospace; font-size: 12px;">
                <div t-if="!state.log.length" class="text-muted">Sin actividad todavía…</div>
                <div t-foreach="state.log" t-as="entry" t-key="entry_index"
                     t-att-class="'text-' + entry.type">
                    <span t-esc="entry.time"/> — <span t-esc="entry.msg"/>
                </div>
            </div>
            <t t-set-slot="footer">
                <button class="btn btn-secondary" t-on-click="() => this.props.close()">Cerrar</button>
            </t>
        </Dialog>`;

    setup() {
        this.title = _t("Fiscalizador Máquina Fiscal (Web Serial)");
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.state = useState({
            busy: false,
            connected: getBackendFiscalPrinter().isConnected,
            command: "",
            log: [],
        });
    }

    log(msg, type = "info") {
        this.state.log.unshift({
            msg,
            type,
            time: new Date().toLocaleTimeString(),
        });
    }

    async withBusy(fn) {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            await fn();
        } catch (error) {
            console.error("MfFiscalizador:: Error", error);
            this.log(error?.data?.message || error?.message || String(error), "danger");
        } finally {
            this.state.busy = false;
            this.state.connected = getBackendFiscalPrinter().isConnected;
        }
    }

    async connect() {
        await this.withBusy(async () => {
            const ok = await ensureConnected(getBackendFiscalPrinter());
            this.log(
                ok ? _t("Conexión establecida con la máquina fiscal") : _t("No se pudo conectar"),
                ok ? "success" : "danger"
            );
        });
    }

    async readStatus() {
        await this.withBusy(async () => {
            const driver = getBackendFiscalPrinter();
            if (!(await ensureConnected(driver))) {
                this.log(_t("No se pudo conectar"), "danger");
                return;
            }
            const status = await driver.getStatus();
            if (!status) {
                this.log(_t("Sin respuesta al ENQ"), "danger");
                return;
            }
            const sts1 = status.raw?.sts1;
            const sts1Hex = typeof sts1 === "number" ? `0x${sts1.toString(16)}` : "N/A";
            this.log(`STS1=${sts1Hex} | ${status.statusText || ""}`, "success");
            if (status.errors && status.errors.length) {
                this.log(_t("Errores: ") + status.errors.join(", "), "danger");
            }
        });
    }

    async readS1() {
        await this.withBusy(async () => {
            const driver = getBackendFiscalPrinter();
            if (!(await ensureConnected(driver))) {
                this.log(_t("No se pudo conectar"), "danger");
                return;
            }
            const result = await driver._readS1Data();
            if (!result.success) {
                this.log(result.error || _t("No se pudo leer S1"), "danger");
                return;
            }
            const d = result.data;
            this.log(
                `Serial=${d.registeredMachineNumber} | RIF=${d.rif} | UltFactura=${d.lastInvoiceNumber} | UltNC=${d.lastNCNumber} | ContadorZ=${d.dailyClosureCounter}`,
                "success"
            );
        });
    }

    async readS4() {
        await this.withBusy(async () => {
            const driver = getBackendFiscalPrinter();
            if (!(await ensureConnected(driver))) {
                this.log(_t("No se pudo conectar"), "danger");
                return;
            }
            const result = await driver.readS4Data();
            if (!result.success) {
                this.log(result.error || _t("No se pudo leer S4"), "danger");
                return;
            }
            const methods = result.data.methods || [];
            if (!methods.length) {
                this.log(_t("S4 no devolvió medios de pago"), "warning");
                return;
            }
            this.log(
                _t("Medios de pago programados (") + methods.length + _t("):"),
                "success"
            );
            for (const m of methods) {
                const code = m.code || "??";
                const name = m.name || "(sin nombre)";
                this.log(`  [${code}] ${name}`);
            }
        });
    }

    async reportX() {
        await this.withBusy(async () => {
            const driver = getBackendFiscalPrinter();
            if (!(await ensureConnected(driver))) {
                this.log(_t("No se pudo conectar"), "danger");
                return;
            }
            const result = await driver.printReportX();
            this.log(
                result.success ? _t("Reporte X impreso") : result.error,
                result.success ? "success" : "danger"
            );
        });
    }

    async reportZ() {
        this.dialog.add(ConfirmationDialog, {
            title: _t("Confirmar Reporte Z"),
            body: _t(
                "El Reporte Z cerrará el día fiscal actual. Esta acción es IRREVERSIBLE. ¿Deseas continuar?"
            ),
            confirmLabel: _t("Imprimir Reporte Z"),
            cancelLabel: _t("Cancelar"),
            confirm: () => this._doReportZ(),
            cancel: () => {},
        });
    }

    async _doReportZ() {
        await this.withBusy(async () => {
            const driver = getBackendFiscalPrinter();
            if (!(await ensureConnected(driver))) {
                this.log(_t("No se pudo conectar"), "danger");
                return;
            }

            const zResult = await driver.printReportZ();
            if (!zResult.success) {
                this.log(zResult.error || _t("Error al imprimir Reporte Z"), "danger");
                return;
            }
            this.log(_t("Reporte Z impreso"), "success");

            // Sincronizar mf_reportz de facturas pendientes en Odoo
            const s1Result = await driver._readS1Data();
            const counter = s1Result.data?.dailyClosureCounter;
            if (!s1Result.success || !s1Result.data?.registeredMachineNumber || !Number.isInteger(counter)) {
                this.log(
                    _t("Z impreso, pero no se pudo leer S1 para sincronizar Odoo. Verifica el libro de ventas."),
                    "warning"
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
            await this.orm.call("account.move", "report_z", [
                [],
                s1Result.data.registeredMachineNumber,
                value,
            ]);
            this.log(
                _t("Reporte Z sincronizado en Odoo (serial ") +
                    s1Result.data.registeredMachineNumber +
                    ")",
                "success"
            );
        });
    }

    async sendRaw() {
        const command = (this.state.command || "").trim();
        if (!command) {
            return;
        }
        await this.withBusy(async () => {
            const driver = getBackendFiscalPrinter();
            if (!(await ensureConnected(driver))) {
                this.log(_t("No se pudo conectar"), "danger");
                return;
            }
            this.log(_t("Enviando comando: ") + command);
            const result = await driver.sendCommand(command);
            this.log(
                result.success ? `OK: ${result.data}` : `ERROR: ${result.error}`,
                result.success ? "success" : "danger"
            );
        });
    }
}
