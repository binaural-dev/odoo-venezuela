/** @odoo-module **/

import { ClosePosPopup } from "@point_of_sale/app/components/popups/closing_popup/closing_popup";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { useState } from "@odoo/owl";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { ask } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { _t } from "@web/core/l10n/translation";

patch(ClosePosPopup.prototype, {
  setup() {
    super.setup(...arguments);
    this.orm = useService("orm");
    this.mfState = useState({ isPrintingReport: false });
    // Permiso VE: usuarios con l10n_ve_pos_mf.group_pos_close_native ven
    // ademas un boton de cierre nativo (sin Reporte Z ni validacion de
    // pedidos sin facturar), junto al flujo dual existente.
    this.canCloseNative = Boolean(this.pos.user._can_close_session_native);
  },

  getFiscalPrinter() {
    return this.pos.getFiscalPrinter?.() || window.fiscalPrinter || null;
  },

  _mfAlert(title, body) {
    this.dialog.add(AlertDialog, { title, body });
  },

  async generate_report_x() {
    if (this.mfState.isPrintingReport) {
      return;
    }

    const fiscalPrinter = this.getFiscalPrinter();
    if (!fiscalPrinter || !fiscalPrinter.isConnected) {
      this._mfAlert(
        _t("Maquina Fiscal no conectada"),
        _t("Por favor, conecta la maquina fiscal antes de imprimir el reporte X.")
      );
      return;
    }

    this.mfState.isPrintingReport = true;
    try {
      const result = await fiscalPrinter.printReportX();
      if (!result.success) {
        this._mfAlert(
          _t("Error al imprimir Reporte X"),
          _t(result.error || "Error desconocido")
        );
      }
    } catch (error) {
      this._mfAlert(
        _t("Error al imprimir Reporte X"),
        _t(error.message || "Error interno")
      );
    } finally {
      this.mfState.isPrintingReport = false;
    }
  },

  /**
   * Imprime el Reporte Z y sincroniza el contador con Odoo.
   * No cierra la sesión — solo se encarga de la parte fiscal.
   * @returns {Promise<boolean>} true si el reporte se imprimió y sincronizó
   */
  async _printFiscalReportZ() {
    const fiscalPrinter = this.getFiscalPrinter();
    if (!fiscalPrinter || !fiscalPrinter.isConnected) {
      this._mfAlert(
        _t("Maquina Fiscal no conectada"),
        _t("Por favor, conecta la maquina fiscal antes de imprimir el reporte Z.")
      );
      return false;
    }

    const confirmed = await ask(this.dialog, {
      title: _t("Confirmar Reporte Z"),
      body: _t(
        "El Reporte Z cerrara el dia fiscal actual. Esta accion es irreversible. Deseas continuar?"
      ),
    });
    if (!confirmed) {
      return false;
    }

    this.mfState.isPrintingReport = true;
    try {
      const zResult = await fiscalPrinter.printReportZ();
      if (!zResult.success) {
        this._mfAlert(
          _t("Error al imprimir Reporte Z"),
          _t(zResult.error || "Error desconocido")
        );
        return false;
      }

      const s1Result = await fiscalPrinter._readS1Data();
      const dailyClosureCounter = s1Result.data?.dailyClosureCounter;
      if (
        !s1Result.success ||
        !s1Result.data?.registeredMachineNumber ||
        !Number.isInteger(dailyClosureCounter)
      ) {
        this._mfAlert(
          _t("Reporte Z impreso con advertencia"),
          _t(
            "El Reporte Z se imprimio, pero no se pudo leer el estado S1 para sincronizar Odoo. Verifica el libro de ventas manualmente."
          )
        );
        return false;
      }

      const value = {
        valid: true,
        data: {
          _registeredMachineNumber: s1Result.data.registeredMachineNumber,
          _dailyClosureCounter: dailyClosureCounter,
        },
      };

      await this.orm.call("account.move", "report_z", [
        [],
        this.pos.config.serial_machine,
        value,
      ]);
      await this.orm.call("pos.session", "set_report_z", [
        [this.pos.session.id],
        value,
      ]);

      return true;
    } catch (error) {
      this._mfAlert(
        _t("Error al imprimir Reporte Z"),
        _t(error.message || "Error interno")
      );
      return false;
    } finally {
      this.mfState.isPrintingReport = false;
    }
  },

  /**
   * Busca en la sesión actual pedidos que no tengan número de factura de
   * la máquina fiscal (mf_invoice_number). Se excluyen los cancelados.
   * @returns {Promise<Array<{id: number, name: string}>>}
   */
  async _getUnfiscalizedOrders() {
    return await this.orm.searchRead(
      "pos.order",
      [
        ["session_id", "=", this.pos.session.id],
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
    if (this.mfState.isPrintingReport) {
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
      this._mfAlert(_t("No se puede cerrar la sesion"), body);

      // Cerramos el popup de cierre y llevamos al cajero a la lista de
      // pedidos filtrada por pendientes por facturar.
      this.props.close();
      this.pos.navigate("TicketScreen", {
        stateOverride: { filter: "UNFISCALIZED" },
      });
      return;
    }

    const zPrinted = await this._printFiscalReportZ();
    if (!zPrinted) {
      return;
    }

    // Flujo nativo de cierre de Odoo 19: confirm() valida diferencias de
    // caja y luego llama a closeSession() (respeta overrides encadenados).
    await this.confirm();
  },
});
