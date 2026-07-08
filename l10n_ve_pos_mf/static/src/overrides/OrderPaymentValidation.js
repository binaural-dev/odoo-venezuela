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
 * 2. Validación contable previa (dry-run) — tolerante a fallos de red
 * 3. Impresión fiscal (offline, no requiere internet) — bloquea si falla
 * 4. super.finalizeValidation() — el core sincroniza (con soporte offline
 *    nativo de Odoo 19: las órdenes pendientes se guardan y re-sincronizan)
 */
patch(OrderPaymentValidation.prototype, {
  async finalizeValidation() {
    const order = this.order;
    const pos = this.pos;

    // 1. Normalizar descuento global antes de validar/imprimir
    pos._applyGlobalDiscountBeforeValidation(order);

    // 2. Validación contable previa (dry-run) - tolerante a fallos de red
    try {
      const serialized = order.serializeForORM({ keepCommands: true });
      // Forzamos el estado "paid" en el payload para que el dry-run ejerza
      // el flujo contable completo (action_pos_order_paid, factura, etc.)
      serialized.state = "paid";
      await pos.data.call("pos.order", "validate_order_dry_run", [[serialized]]);
    } catch (error) {
      const isNetworkError =
        !error.message ||
        error.message.includes("NetworkError") ||
        error.message.includes("fetch") ||
        error.message.includes("connection") ||
        error?.constructor?.name === "ConnectionLostError";

      if (!isNetworkError) {
        // Error de validación real (datos inválidos) - mostrar y bloquear
        let msg = _t("Error desconocido en Odoo");
        if (error.data && error.data.message) {
          msg = error.data.message;
        } else if (error.message) {
          msg = error.message;
        }

        pos.dialog.add(AlertDialog, {
          title: _t("Validación Contable"),
          body: msg,
        });
        return false;
      }

      // Error de red: permitimos continuar, el pedido se sincronizará después
      console.warn("MF:: Validación dry-run omitida (offline)");
    }

    // 3. Imprimir en máquina fiscal (offline - no requiere internet)
    if (pos.useFiscalMachine() && !order.mf_invoice_number) {
      const response = await pos.pushToMF(order);

      if (!response || response.valid !== true) {
        // La impresión fiscal falló: NO continuamos con la validación.
        // pushToMF ya mostró el diálogo de error correspondiente.
        return false;
      }
    }

    // 4. Sincronización estándar (el core maneja offline nativamente)
    return await super.finalizeValidation(...arguments);
  },
});
