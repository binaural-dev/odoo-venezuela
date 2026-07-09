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
 * 2. Impresión fiscal (offline, no requiere internet) — bloquea si falla
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
