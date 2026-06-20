/** @odoo-module **/

import { ClosePosPopup } from "@point_of_sale/app/navbar/closing_popup/closing_popup";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { ConfirmPopup } from "@point_of_sale/app/utils/confirm_popup/confirm_popup";
import { _t } from "@web/core/l10n/translation";

patch(ClosePosPopup.prototype, {
  setup() {
    super.setup(...arguments);
    this.orm = useService("orm");
    this.popup = useService("popup");
    this.state.isPrintingReport = false;
  },
  getFiscalPrinter() {
    return this.pos.getFiscalPrinter?.() || window.fiscalPrinter || null;
  },

  async generate_report_x() {
    if (this.state.isPrintingReport) {
      return;
    }

    const fiscalPrinter = this.getFiscalPrinter();
    if (!fiscalPrinter || !fiscalPrinter.isConnected) {
      await this.popup.add(ErrorPopup, {
        title: _t("Maquina Fiscal no conectada"),
        body: _t("Por favor, conecta la maquina fiscal antes de imprimir el reporte X."),
      });
      return;
    }

    this.state.isPrintingReport = true;
    try {
      const result = await fiscalPrinter.printReportX();
      if (!result.success) {
        await this.popup.add(ErrorPopup, {
          title: _t("Error al imprimir Reporte X"),
          body: _t(result.error || "Error desconocido"),
        });
      }
    } catch (error) {
      await this.popup.add(ErrorPopup, {
        title: _t("Error al imprimir Reporte X"),
        body: _t(error.message || "Error interno"),
      });
    } finally {
      this.state.isPrintingReport = false;
    }
  },

  async generate_report_z() {
    if (this.state.isPrintingReport) {
      return;
    }

    const fiscalPrinter = this.getFiscalPrinter();
    if (!fiscalPrinter || !fiscalPrinter.isConnected) {
      await this.popup.add(ErrorPopup, {
        title: _t("Maquina Fiscal no conectada"),
        body: _t("Por favor, conecta la maquina fiscal antes de imprimir el reporte Z."),
      });
      return;
    }

    const { confirmed } = await this.popup.add(ConfirmPopup, {
      title: _t("Confirmar Reporte Z"),
      body: _t("El Reporte Z cerrara el dia fiscal actual. Esta accion es irreversible. Deseas continuar?"),
    });
    if (!confirmed) {
      return;
    }

    this.state.isPrintingReport = true;
    try {
      const zResult = await fiscalPrinter.printReportZ();
      if (!zResult.success) {
        await this.popup.add(ErrorPopup, {
          title: _t("Error al imprimir Reporte Z"),
          body: _t(zResult.error || "Error desconocido"),
        });
        return;
      }

      const s1Result = await fiscalPrinter._readS1Data();
      const dailyClosureCounter = s1Result.data?.dailyClosureCounter;
      if (!s1Result.success || !s1Result.data?.registeredMachineNumber || !Number.isInteger(dailyClosureCounter)) {
        await this.popup.add(ErrorPopup, {
          title: _t("Reporte Z impreso con advertencia"),
          body: _t(
            "El Reporte Z se imprimio, pero no se pudo leer el estado S1 para sincronizar Odoo. Verifica el libro de ventas manualmente."
          ),
        });
        return;
      }

      const value = {
        valid: true,
        data: {
          _registeredMachineNumber: s1Result.data.registeredMachineNumber,
          _dailyClosureCounter: dailyClosureCounter,
        },
      };

      await this.orm.call("account.move", "report_z", [[], this.pos.config.serial_machine, value]);
      await this.orm.call("pos.session", "set_report_z", [this.pos.pos_session.id, value]);

      await this.popup.add(ConfirmPopup, {
        title: _t("Reporte Z impreso"),
        body: _t("Cierre fiscal diario completado y sincronizado con Odoo."),
        confirmText: _t("Aceptar"),
        cancelText: false,
      });
    } catch (error) {
      await this.popup.add(ErrorPopup, {
        title: _t("Error al imprimir Reporte Z"),
        body: _t(error.message || "Error interno"),
      });
    } finally {
      this.state.isPrintingReport = false;
    }
  },
});
