/** @odoo-module **/

import { ClosePosPopup } from "@point_of_sale/app/navbar/closing_popup/closing_popup";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { ConfirmPopup } from "@point_of_sale/app/utils/confirm_popup/confirm_popup";
import { NumberPopup } from "@point_of_sale/app/utils/input_popups/number_popup";
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

  /**
   * En Odoo 17 este popup se confirma con Enter (AbstractAwaitablePopup
   * escucha keyup en toda la ventana) y el confirm() nativo cierra la sesión
   * sin imprimir el Reporte Z. Tras pulsar "Reporte X" el foco queda en ese
   * botón, así que un Enter (o un lector que envía Enter) cerraba la sesión
   * sin Z y el POS abría otra al volver (ticket 16649).
   * Enter queda deshabilitado aquí; Escape sigue funcionando.
   */
  _onWindowKeyup(event) {
    if (event.key === "Enter" || event.key === this.props.confirmKey) {
      return;
    }
    return super._onWindowKeyup(event);
  },

  /**
   * Cualquier confirmación del popup pasa por el flujo fiscal (pedidos sin
   * facturar → Reporte Z → cierre), nunca por el cierre nativo sin Z.
   */
  async confirm() {
    return await this.closeSessionAndPrintZ();
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
      // Sin foco en el botón, un Enter posterior no vuelve a imprimir el X.
      document.activeElement?.blur?.();
    }
  },

  /**
   * Lee el S1 con reintentos. Justo después del Z la máquina puede seguir
   * ocupada terminando la impresión y no responder al primer S1.
   * Debe llamarse con el puerto ya abierto (dentro de withConnection).
   */
  async _readS1AfterZ(fiscalPrinter) {
    const delays = [2000, 3000, 5000, 8000];
    let s1Result = null;
    for (const delayMs of delays) {
      await new Promise((resolve) => setTimeout(resolve, delayMs));
      s1Result = await fiscalPrinter._readS1Data();
      if (this._isValidS1(s1Result)) {
        return s1Result;
      }
    }
    return s1Result;
  },

  _isValidS1(s1Result) {
    return Boolean(
      s1Result?.success &&
        s1Result.data?.registeredMachineNumber &&
        Number.isInteger(s1Result.data?.dailyClosureCounter)
    );
  },

  async _getMfCloseState() {
    return await this.orm.call("pos.session", "get_mf_close_state", [[this.pos.pos_session.id]]);
  },

  /**
   * Cuando el S1 no respondió tras un Z ya impreso, pide al cajero el número
   * del Z que salió en el papel (sugerido desde las órdenes de la sesión).
   * Nunca se vuelve a imprimir el Z: saldría en cero.
   * @returns {Promise<{reportZ: number, serial: string}|null>}
   */
  async _askManualReportZ(closeState) {
    const { confirmed, payload } = await this.popup.add(NumberPopup, {
      title: _t("No se pudo leer el estado S1"),
      body: _t(
        "El Reporte Z ya se imprimio. Confirma el numero de Z que aparece en el papel para cerrar la sesion sin volver a imprimirlo."
      ),
      startingValue: closeState.suggested_report_z ? String(closeState.suggested_report_z) : "",
      isInputSelected: true,
    });
    if (!confirmed) {
      return null;
    }
    const reportZ = parseInt(String(payload || "").replace(/[^0-9]/g, ""), 10);
    if (!Number.isInteger(reportZ) || reportZ <= 0) {
      await this.popup.add(ErrorPopup, {
        title: _t("Numero de Reporte Z invalido"),
        body: _t("Ingresa el numero de Z que aparece en el papel."),
      });
      return null;
    }
    return { reportZ, serial: closeState.suggested_serial || "" };
  },

  async _syncReportZ(reportZ, serial) {
    const value = {
      valid: true,
      data: {
        _registeredMachineNumber: serial,
        _dailyClosureCounter: reportZ,
      },
    };
    if (serial) {
      await this.orm.call("account.move", "report_z", [[], serial, value]);
    }
    await this.orm.call("pos.session", "set_report_z", [[this.pos.pos_session.id], value]);
  },

  /**
   * Imprime el Reporte Z (si aún no se imprimió en esta sesión) y registra
   * su número y el serial en Odoo. No cierra la sesión.
   * @returns {Promise<boolean>} true si la sesión quedó con su Reporte Z registrado
   */
  async _printFiscalReportZ() {
    const closeState = await this._getMfCloseState();
    if (closeState.report_z) {
      // El Z ya quedó registrado (ej. un cierre anterior falló después).
      return true;
    }

    const fiscalPrinter = this.getFiscalPrinter();
    if (!fiscalPrinter && !closeState.mf_z_printed) {
      await this.popup.add(ErrorPopup, {
        title: _t("Maquina Fiscal no configurada"),
        body: _t("No hay una maquina fiscal configurada para esta caja."),
      });
      return false;
    }

    if (!closeState.mf_z_printed) {
      const { confirmed } = await this.popup.add(ConfirmPopup, {
        title: _t("Confirmar Reporte Z"),
        body: _t("El Reporte Z cerrara el dia fiscal actual. Esta accion es irreversible. Deseas continuar?"),
      });
      if (!confirmed) {
        return false;
      }
    }

    this.state.isPrintingReport = true;
    try {
      let s1Result = null;
      if (fiscalPrinter) {
        try {
          // Una sola apertura de puerto cubre imprimir el Z y leer S1.
          s1Result = await fiscalPrinter.withConnection(async () => {
            if (!closeState.mf_z_printed) {
              const zResult = await fiscalPrinter.printReportZ();
              if (!zResult.success) {
                throw new Error(zResult.error || _t("Error desconocido"));
              }
              // Se marca en el servidor antes del S1: si algo falla de aquí
              // en adelante, un reintento no vuelve a emitir el Z.
              closeState.mf_z_printed = true;
              await this.orm.call("pos.session", "mark_mf_z_printed", [[this.pos.pos_session.id]]);
            }
            return await this._readS1AfterZ(fiscalPrinter);
          });
        } catch (error) {
          if (!closeState.mf_z_printed) {
            await this.popup.add(ErrorPopup, {
              title: _t("Error al imprimir Reporte Z"),
              body: error.message || _t("Error interno"),
            });
            return false;
          }
          // Z ya impreso: el fallo fue al reconectar / leer S1 → carga manual.
          s1Result = null;
        }
      }

      let reportZ;
      let serial;
      if (this._isValidS1(s1Result)) {
        reportZ = s1Result.data.dailyClosureCounter;
        serial = s1Result.data.registeredMachineNumber;
      } else {
        const manual = await this._askManualReportZ(closeState);
        if (!manual) {
          return false;
        }
        reportZ = manual.reportZ;
        serial = manual.serial;
      }

      await this._syncReportZ(reportZ, serial);
      return true;
    } catch (error) {
      await this.popup.add(ErrorPopup, {
        title: _t("Error al registrar el Reporte Z"),
        body: error.message || _t("Error interno"),
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
