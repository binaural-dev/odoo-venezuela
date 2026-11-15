/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

/**
 * Hook del flujo de validación de pago para la máquina fiscal.
 *
 * En Odoo 20 la validación de pago corre detrás de la pantalla de
 * retroalimentación (FeedbackScreen): `shouldHideValidationBehindFeedbackScreen`
 * lanza `finalizeValidation` y navega sin esperarla. La impresión fiscal debe
 * terminar ANTES de mostrarla (si falla, la orden queda sin validar y el
 * cajero vuelve a la pantalla de productos, como en 19), así que se hace en
 * ese punto, antes de la validación estándar:
 *
 * 1. Descuento global (Estrategia A) — se normaliza antes de validar
 * 2. Impresión fiscal (offline, no requiere internet) — bloquea si falla
 * 3. super.shouldHideValidationBehindFeedbackScreen(): el core sincroniza (con
 *    soporte offline nativo: las órdenes pendientes se guardan y se
 *    re-sincronizan)
 */
patch(OrderPaymentValidation.prototype, {
  /**
   * Override para controlar si se debe descargar la factura PDF.
   * Si la caja tiene mf_skip_invoice_pdf activado, no descarga el PDF.
   */
  shouldDownloadInvoice() {
    if (this.pos.config.mf_skip_invoice_pdf) {
      console.info("MF:: Descarga de PDF omitida por configuración");
      return false;
    }
    return super.shouldDownloadInvoice(...arguments);
  },

  async shouldHideValidationBehindFeedbackScreen() {
    if (!(await this._mfPrintBeforeValidation())) {
      const { page, params } = this.pos.defaultPage;
      this.pos.navigate(page, params);
      return false;
    }
    return super.shouldHideValidationBehindFeedbackScreen(...arguments);
  },

  /**
   * El core de 20 abre la gaveta con `pos.openCashbox()` al validar un pago en
   * efectivo, y ese método abre la gaveta de la máquina fiscal. La factura
   * fiscal ya la abrió con su comando de gaveta (como en 19, donde el core
   * llamaba al proxy de hardware y no a `openCashbox`), así que se omite la
   * segunda apertura. `openCashbox` es lo primero que ejecuta el core, antes
   * de su primer `await`. Si no la abrió la factura (p. ej. orden operativa),
   * `pos.openCashbox` no envía nada a la gaveta fiscal durante la validación.
   */
  async finalizeValidation() {
    const order = this.order;
    const openedByInvoice = Boolean(
      order.mf_invoice_number && this.pos.has_cashbox && order.isPaidWithCash()
    );
    this.pos._mfDrawerOpenedByInvoice = openedByInvoice;
    this.pos._mfValidatingOrder = order;
    let result;
    try {
      result = super.finalizeValidation(...arguments);
    } finally {
      this.pos._mfDrawerOpenedByInvoice = false;
      this.pos._mfValidatingOrder = null;
    }
    return result;
  },

  /**
   * Normaliza el descuento global e imprime la orden en la máquina fiscal.
   * @returns {Promise<boolean>} false si la impresión falló (el diálogo de
   * error ya se mostró) y la validación no debe continuar.
   */
  async _mfPrintBeforeValidation() {
    const order = this.order;
    const pos = this.pos;

    console.info("MF:: Iniciando validación de pago fiscal", {
      orderId: order.id,
      uuid: order.uuid,
      total: order.totalDue,
    });

    // 1. Normalizar descuento global antes de validar/imprimir
    try {
      pos._applyGlobalDiscountBeforeValidation(order);
    } catch (error) {
      console.error("MF:: Error normalizando descuento global", error);
      // No bloqueamos por este error, intentamos continuar
    }

    // 2. Imprimir en máquina fiscal (offline - no requiere internet)
    if (pos.useFiscalMachine() && !order.mf_invoice_number) {
      console.info("MF:: Iniciando impresión fiscal");
      try {
        const response = await pos.pushToMF(order);

        if (!response || response.valid !== true) {
          console.error("MF:: Impresión fiscal falló", response);
          // pushToMF ya mostró el diálogo de error correspondiente
          return false;
        }

        console.info("MF:: Impresión fiscal exitosa", {
          mf_invoice_number: order.mf_invoice_number,
          fiscal_machine: order.fiscal_machine,
        });
      } catch (error) {
        console.error("MF:: Error durante impresión fiscal", error);
        pos.dialog.add(AlertDialog, {
          title: _t("Error de Máquina Fiscal"),
          body: error.message || _t("Error inesperado durante la impresión fiscal"),
        });
        return false;
      }
    } else {
      console.info("MF:: Impresión fiscal omitida", {
        useFiscalMachine: pos.useFiscalMachine(),
        hasMfNumber: Boolean(order.mf_invoice_number),
      });
    }
    return true;
  },
});
