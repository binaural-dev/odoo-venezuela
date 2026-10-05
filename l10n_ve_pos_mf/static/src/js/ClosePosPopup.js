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
    if (!fiscalPrinter) {
      await this.popup.add(ErrorPopup, {
        title: _t("Maquina Fiscal no configurada"),
        body: _t("No hay una maquina fiscal configurada para esta caja."),
      });
      return;
    }

    this.state.isPrintingReport = true;
    try {
      // withConnection abre el puerto bajo demanda solo por esta impresión
      // y lo libera al terminar (evita disputar el puerto con Megasoft).
      const result = await fiscalPrinter.withConnection(() => fiscalPrinter.printReportX());
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

  /**
   * Imprime el Reporte Z y sincroniza el contador con Odoo.
   * No cierra la sesión — solo se encarga de la parte fiscal.
   * @returns {Promise<boolean>} true si el reporte se imprimió y sincronizó correctamente
   */
  async _printFiscalReportZ() {
    const fiscalPrinter = this.getFiscalPrinter();
    if (!fiscalPrinter) {
      await this.popup.add(ErrorPopup, {
        title: _t("Maquina Fiscal no configurada"),
        body: _t("No hay una maquina fiscal configurada para esta caja."),
      });
      return false;
    }

    const { confirmed } = await this.popup.add(ConfirmPopup, {
      title: _t("Confirmar Reporte Z"),
      body: _t("El Reporte Z cerrara el dia fiscal actual. Esta accion es irreversible. Deseas continuar?"),
    });
    if (!confirmed) {
      return false;
    }

    this.state.isPrintingReport = true;
    try {
      // Una sola apertura de puerto cubre imprimir el Z y leer S1 justo
      // después para confirmar el cierre — son dos pasos de una misma
      // operación fiscal, no dos operaciones independientes.
      const { zResult, s1Result } = await fiscalPrinter.withConnection(async () => {
        const zResult = await fiscalPrinter.printReportZ();
        if (!zResult.success) {
          return { zResult, s1Result: null };
        }
        const s1Result = await fiscalPrinter._readS1Data();
        return { zResult, s1Result };
      });

      if (!zResult.success) {
        await this.popup.add(ErrorPopup, {
          title: _t("Error al imprimir Reporte Z"),
          body: _t(zResult.error || "Error desconocido"),
        });
        return false;
      }

      const dailyClosureCounter = s1Result.data?.dailyClosureCounter;
      if (!s1Result.success || !s1Result.data?.registeredMachineNumber || !Number.isInteger(dailyClosureCounter)) {
        await this.popup.add(ErrorPopup, {
          title: _t("Reporte Z impreso con advertencia"),
          body: _t(
            "El Reporte Z se imprimio, pero no se pudo leer el estado S1 para sincronizar Odoo. Verifica el libro de ventas manualmente."
          ),
        });
        return false;
      }

      const value = {
        valid: true,
        data: {
          _registeredMachineNumber: s1Result.data.registeredMachineNumber,
          _dailyClosureCounter: dailyClosureCounter,
        },
      };

      await this.orm.call("account.move", "report_z", [[], this.pos.config.serial_machine, value]);
      await this.orm.call("pos.session", "set_report_z", [[this.pos.pos_session.id], value]);

      return true;
    } catch (error) {
      await this.popup.add(ErrorPopup, {
        title: _t("Error al imprimir Reporte Z"),
        body: _t(error.message || "Error interno"),
      });
      return false;
    } finally {
      this.state.isPrintingReport = false;
    }
  },

  /**
   * Busca en la sesión actual pedidos que no tengan número de factura de
   * la máquina fiscal (mf_invoice_number). Se excluyen los pedidos
   * cancelados.
   * @returns {Promise<Array<{id: number, name: string}>>}
   */
  async _getUnfiscalizedOrders() {
    return await this.orm.searchRead(
      "pos.order",
      [
        ["session_id", "=", this.pos.pos_session.id],
        ["mf_invoice_number", "=", false],
        ["state", "!=", "cancel"],
      ],
      ["name"],
      { order: "id asc" }
    );
  },

  /**
   * Botón unificado: valida que todos los pedidos de la sesión estén
   * facturados en la máquina fiscal, imprime el Reporte Z, y solo si todo
   * fue exitoso continúa con el cierre nativo de la sesión de Odoo.
   */
  async closeSessionAndPrintZ() {
    if (this.state.isPrintingReport) {
      return;
    }

    const unfiscalizedOrders = await this._getUnfiscalizedOrders();
    if (unfiscalizedOrders.length > 0) {
      const MAX_SHOWN = 10;
      const shownNames = unfiscalizedOrders.slice(0, MAX_SHOWN).map((o) => o.name);
      let body = _t(
        "Existen %s pedido(s) sin facturar en esta sesion. Debes facturarlos antes de cerrar:\n\n%s",
        unfiscalizedOrders.length,
        shownNames.join("\n")
      );
      if (unfiscalizedOrders.length > MAX_SHOWN) {
        body += _t("\n\n... y %s mas", unfiscalizedOrders.length - MAX_SHOWN);
      }
      await this.popup.add(ErrorPopup, {
        title: _t("No se puede cerrar la sesion"),
        body,
      });

      // Tras aceptar el aviso, cerramos el popup de cierre y llevamos al
      // cajero directo a la lista de pedidos, filtrada para mostrar solo
      // los pendientes por facturar, de manera que pueda ubicarlos e
      // imprimirlos sin tener que buscarlos manualmente.
      this.cancel();
      this.pos.showScreen("TicketScreen", { ui: { filter: "UNFISCALIZED" } });
      return;
    }

    const zPrinted = await this._printFiscalReportZ();
    if (!zPrinted) {
      return;
    }

    // Flujo nativo de cierre de Odoo (respeta otros overrides encadenados,
    // por ejemplo binaural_pos_close para efectivo en moneda extranjera).
    await this.closeSession();
  },
});
