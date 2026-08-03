/** @odoo-module */

import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { ask } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { _t } from "@web/core/l10n/translation";

/**
 * Componente para generar Reportes X y Z desde la UI del POS
 */
export class FiscalReports extends Component {
    static template = "l10n_ve_pos_mf.FiscalReports";
    static props = {};

    setup() {
        this.pos = usePos();
        this.dialog = useService("dialog");
    }

    /**
     * Obtiene la instancia del driver de la máquina fiscal
     * @returns {TfhkaDriver|null}
     */
    getFiscalPrinter() {
        return window.fiscalPrinter || null;
    }

    _alert(title, body) {
        this.dialog.add(AlertDialog, { title, body });
    }

    /**
     * Genera un Reporte X (consulta sin cerrar día)
     */
    async printReportX() {
        const fiscalPrinter = this.getFiscalPrinter();

        if (!fiscalPrinter || !fiscalPrinter.isConnected) {
            this._alert(
                _t("Máquina Fiscal no conectada"),
                _t("Por favor, conecta la máquina fiscal antes de imprimir el reporte X")
            );
            return;
        }

        try {
            const result = await fiscalPrinter.printReportX();

            if (!result.success) {
                this._alert(
                    _t("Error al imprimir Reporte X"),
                    _t(result.error || "Error desconocido")
                );
            }
        } catch (error) {
            console.error("FiscalReports:: Error al imprimir Reporte X", error);
            this._alert(
                _t("Error al imprimir Reporte X"),
                _t(error.message || "Error interno")
            );
        }
    }

    /**
     * Genera un Reporte Z (cierre diario)
     * Requiere confirmación del usuario ya que es irreversible
     */
    async printReportZ() {
        const fiscalPrinter = this.getFiscalPrinter();

        if (!fiscalPrinter || !fiscalPrinter.isConnected) {
            this._alert(
                _t("Máquina Fiscal no conectada"),
                _t("Por favor, conecta la máquina fiscal antes de imprimir el reporte Z")
            );
            return;
        }

        // Confirmación (el Reporte Z es irreversible)
        const confirmed = await ask(this.dialog, {
            title: _t("Confirmar Reporte Z"),
            body: _t(
                "El Reporte Z cerrará el día fiscal actual. Esta acción es IRREVERSIBLE. ¿Deseas continuar?"
            ),
        });

        if (!confirmed) {
            return;
        }

        try {
            const result = await fiscalPrinter.printReportZ();

            if (!result.success) {
                this._alert(
                    _t("Error al imprimir Reporte Z"),
                    _t(result.error || "Error desconocido")
                );
            } else {
                this._alert(
                    _t("Reporte Z impreso"),
                    _t("El cierre diario se ha realizado exitosamente")
                );
            }
        } catch (error) {
            console.error("FiscalReports:: Error al imprimir Reporte Z", error);
            this._alert(
                _t("Error al imprimir Reporte Z"),
                _t(error.message || "Error interno")
            );
        }
    }
}
