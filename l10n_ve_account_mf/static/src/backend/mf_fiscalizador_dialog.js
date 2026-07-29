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
                <button class="btn btn-info" t-att-disabled="state.busy" t-on-click="readIgtfInfo">
                    <i class="fa fa-globe me-1"/>Info IGTF (S3+S25)
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

    /**
     * Muestra información de configuración IGTF (Impuesto a las Grandes
     * Transacciones Financieras), según el manual TFHKA v1.1.0:
     * - Tasa IGTF programada (S3, 4ta línea de tasas)
     * - Flags de sistema crudos (S3) — buscar Flag 50 (habilita IGTF/divisas)
     *   y Flag 63 (formato de extracción de reportes con IGTF)
     * - Desglose IGTF del documento fiscal EN CURSO, si hay uno abierto (S25)
     * - Clasificación de medios de pago programados (S4) en Nacional (01-19)
     *   vs Divisa (20-24, dispara cálculo de IGTF)
     */
    async readIgtfInfo() {
        await this.withBusy(async () => {
            const driver = getBackendFiscalPrinter();
            if (!(await ensureConnected(driver))) {
                this.log(_t("No se pudo conectar"), "danger");
                return;
            }

            // 1. Tasa IGTF y flags de sistema (S3)
            const s3Result = await driver.readS3Data();
            if (!s3Result.success) {
                this.log(s3Result.error || _t("No se pudo leer S3"), "danger");
                return;
            }
            const igtf = s3Result.data.igtf;
            this.log(
                `Tasa IGTF programada: ${igtf.value.toFixed(2)}% (tipo: ${igtf.typeLabel})`,
                "success"
            );
            this.log(
                _t("Flags de sistema (S3, crudo): ") + (s3Result.data.systemFlags || []).join(", "),
                "info"
            );
            this.log(
                _t("⚠️ Verifica manualmente que Flag 50 = 01 en la impresora para habilitar IGTF y medios de pago 20-24 (usa comando raw 'S3' o consulta programación física)."),
                "warning"
            );

            // 2. Desglose IGTF del documento en curso (S25) — 0 si no hay transacción abierta
            const s25Result = await driver.readS25Data();
            if (s25Result.success) {
                const d = s25Result.data;
                this.log(
                    `S25 (documento en curso: ${d.documentTypeLabel}) — Base: ${d.subtotalBases.toFixed(2)} | ` +
                        `Impuesto: ${d.subtotalTax.toFixed(2)} | Monto sin IGTF: ${d.totalWithoutIgtf.toFixed(2)} | ` +
                        `Monto con IGTF: ${d.totalWithIgtf.toFixed(2)} | IGTF calculado: ${d.igtfAmount.toFixed(2)}`,
                    "success"
                );
            } else {
                this.log(_t("No se pudo leer S25 (puede ser normal si no hay documento fiscal abierto): ") + s25Result.error, "warning");
            }

            // 3. Clasificación de medios de pago (S4) — Nacional (01-19) vs Divisa (20-24)
            const s4Result = await driver.readS4Data();
            if (s4Result.success) {
                const methods = s4Result.data.methods || [];
                const divisaMethods = methods.filter((m) => driver._isDivisaPaymentMethod(m.code));
                const nacionalMethods = methods.filter((m) => !driver._isDivisaPaymentMethod(m.code));

                this.log(_t("Medios NACIONALES (01-19, sin IGTF): ") + nacionalMethods.length, "info");
                this.log(
                    _t("Medios en DIVISA (20-24, disparan IGTF si Flag 50=01): ") + divisaMethods.length,
                    divisaMethods.length ? "success" : "warning"
                );
                for (const m of divisaMethods) {
                    this.log(`  [${m.code}] ${m.name} → DIVISA (IGTF)`, "success");
                }
                if (!divisaMethods.length) {
                    this.log(
                        _t("No hay medios de pago en divisa (20-24) programados. Si el cliente cobra en USD, deben programarse en la impresora."),
                        "warning"
                    );
                }
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
