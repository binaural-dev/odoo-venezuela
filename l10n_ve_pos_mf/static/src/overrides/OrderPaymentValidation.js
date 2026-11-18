/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

/**
 * Hook del flujo de validación de pago para la máquina fiscal.
 *
 * En Odoo 17 esto vivía en PosStore.push_single_order; en 19 la validación
 * de pago se extrajo a la clase OrderPaymentValidation. Se patchea
 * finalizeValidation, que es el punto donde la orden pasa a "paid" y se
 * sincroniza con el backend:
 *
 * 1. Descuento global (Estrategia A) — se normaliza antes de validar
 * 2. Impresión fiscal (offline, no requiere internet). Si falla, la venta
 *    sigue: la orden se sincroniza sin número fiscal y queda en "Pendientes
 *    por facturar", o "por verificar" si no se supo si la máquina la
 *    emitió (ver PosStore.pushToMF). #85447
 * 3. super.finalizeValidation() — el core sincroniza (con soporte offline
 *    nativo de Odoo 19: las órdenes pendientes se guardan y re-sincronizan)
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

  /**
   * Un pago con código fiscal de divisa (20-24) sin IGTF haría que la
   * máquina anule la factura: se frena aquí, antes de imprimir, y el cajero
   * sigue en la pantalla de pago para cobrar con otro método. En
   * finalizeValidation ya es tarde: el core navega al recibo aunque devuelva
   * false. get_data_invoice repite el chequeo para "Imprimir pedido
   * pendiente". #85447
   */
  async isOrderValid(isForceValidate) {
    if (!(await super.isOrderValid(...arguments))) {
      return false;
    }
    const pos = this.pos;
    if (!pos._mfOrderGoesToFiscalPrinter(this.order)) {
      return true;
    }
    const payment = pos._mfFindForeignCodeWithoutIgtfPayment(this.order);
    if (!payment) {
      return true;
    }
    const method = payment.payment_method_id;
    pos.dialog.add(AlertDialog, {
      title: _t("Fiscal printer error"),
      body: _t(
        "The payment method “%(method)s” has a foreign currency fiscal code (%(code)s) " +
          "without IGTF, so the fiscal printer would void the invoice. Charge it with " +
          "another payment method and ask the administrator to fix this one (local " +
          "currency code 01-19 or “Apply IGTF”): it can only be changed with the register " +
          "sessions closed.",
        { method: method.name, code: method.code_fiscal_printer }
      ),
    });
    return false;
  },

  async finalizeValidation() {
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
    if (pos._mfOrderGoesToFiscalPrinter(order)) {
      console.info("MF:: Iniciando impresión fiscal");
      try {
        const response = await pos.pushToMF(order);
        
        if (!response || response.valid !== true) {
          // pushToMF ya mostró el error. No se detiene el PdV: la orden se
          // sincroniza sin número fiscal y queda pendiente por facturar.
          console.error("MF:: Impresión fiscal falló, la orden queda pendiente", response);
        } else {
          console.info("MF:: Impresión fiscal exitosa", {
            mf_invoice_number: order.mf_invoice_number,
            fiscal_machine: order.fiscal_machine,
          });
        }
      } catch (error) {
        console.error("MF:: Error durante impresión fiscal, la orden queda pendiente", error);
        pos.dialog.add(AlertDialog, {
          title: _t("Error de Máquina Fiscal"),
          body: error.message || _t("Error inesperado durante la impresión fiscal"),
        });
      }
    } else {
      console.info("MF:: Impresión fiscal omitida", {
        useFiscalMachine: pos.useFiscalMachine(),
        hasMfNumber: Boolean(order.mf_invoice_number),
      });
    }

    // 3. Sincronización estándar con manejo de errores
    console.info("MF:: Iniciando sincronización con backend");
    try {
      const result = await super.finalizeValidation(...arguments);
      console.info("MF:: Validación completada exitosamente", result);
      return result;
    } catch (error) {
      console.error("MF:: Error en sincronización backend", error);
      // El core ya maneja la mayoría de errores, pero agregamos log
      throw error;
    }
  },
});
