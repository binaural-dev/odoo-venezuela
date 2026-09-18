/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import { roundPrecision as round_pr } from "@web/core/utils/numbers";

/**
 * Máquina fiscal: líneas con descuento del 100% → SUBTOTAL de línea 0,01.
 * Ticket #15105.
 *
 * Problema: la máquina fiscal no acepta una línea en 0,00 (el driver la
 * descarta) y la validación `_check_max_discount` (l10n_ve_accountant) bloquea
 * toda factura con descuento >= 100%.
 *
 * Solución (definida por Producto): cuando un descuento —de línea o global—
 * dejaría el neto de la línea en 0, se factura la LÍNEA COMPLETA en el mínimo
 * fiscal 0,01, conservando la cantidad. No se puede hacer con un precio
 * unitario fraccionario (precio y descuento de la factura son de 2 decimales y
 * un unitario de 0,01/qty redondea a 0). En su lugar se fija:
 *   - precio unitario = 0,01
 *   - descuento = (1 - 1/qty) * 100
 * de modo que subtotal = 0,01 * qty * (1/qty) = 0,01 exacto, con el descuento
 * por debajo de 100% (no bloquea) y el precio > 0. Se guarda el precio original
 * para revertir, y se recalcula el descuento si cambia la cantidad.
 *
 * La máquina fiscal (precio × cantidad, 2 decimales) no puede repartir 0,01
 * entre N unidades; por eso `PosStore._convertOrderForDriver` envía estas
 * líneas marcadas (`_mf_fiscal_min`) como 1 × 0,01, para que la línea fiscal
 * sume 0,01 y el cierre 199 cuadre con el pago.
 *
 * Punto de intercepción: `setDiscount` (numpad por línea y descuento global) y
 * `setQuantity` (recálculo), más un respaldo en `PosStore.pay()`.
 */

// Precio mínimo que la máquina fiscal acepta en una línea (Bs 0,01).
export const MF_MIN_LINE_PRICE = 0.01;
// Redondeo a céntimo para detectar si el neto de la línea es cero.
const MF_ROUNDING = 0.01;

patch(PosOrderline.prototype, {
  /**
   * Restaura el precio unitario real de una línea sustituida por el mínimo
   * fiscal y limpia la marca. No hace nada si la línea no fue sustituida.
   */
  mfRestoreOriginalPrice() {
    if (this._mf_zeroed_original_price == null || this._mf_fiscal_guard) {
      return;
    }
    this._mf_fiscal_guard = true;
    try {
      this.setUnitPrice(this._mf_zeroed_original_price);
      if (this._mf_zeroed_original_price_type != null) {
        this.price_type = this._mf_zeroed_original_price_type;
      }
      this.discount = 0;
    } finally {
      this._mf_fiscal_guard = false;
    }
    this._mf_zeroed_original_price = null;
    this._mf_zeroed_original_price_type = null;
    this._mf_fiscal_min = false;
  },

  /**
   * Fija precio 0,01 + el descuento que deja el subtotal de la línea en 0,01
   * para la cantidad actual. Reutilizable al cambiar la cantidad.
   */
  _mfApplyLineFiscalMin() {
    const qty = Math.abs(Number(this.getQuantity?.() ?? this.qty ?? 1)) || 1;
    // subtotal = 0,01 * qty * (1 - disc/100) = 0,01  ⇒  disc = (1 - 1/qty) * 100
    let disc = qty > 1 ? round_pr((1 - 1 / qty) * 100, 0.01) : 0;
    if (disc >= 100) {
      disc = 99.99; // el descuento nunca alcanza 100% (no lo bloquea la factura)
    }
    this._mf_fiscal_guard = true;
    try {
      this.setUnitPrice(MF_MIN_LINE_PRICE);
      this.setDiscount(disc); // protegido por el guard → llama al core
      this.price_type = "manual";
    } finally {
      this._mf_fiscal_guard = false;
    }
  },

  /**
   * Devolución de una línea facturada en el mínimo fiscal. El core crea la
   * línea de la devolución copiando precio (0,01) y descuento de la original
   * sin pasar por `setDiscount`, así que no queda marcada; y con 2 unidades
   * (descuento 50%) el neto por unidad redondea a 0,01, por lo que
   * `mfEnsureNonZeroFiscalPrice` tampoco la detecta. Se reconoce por la línea
   * original: precio 0,01 con descuento.
   */
  mfIsRefundOfFiscalMin() {
    const original = this.refunded_orderline_id;
    return Boolean(
      original &&
        Math.abs(Number(original.price_unit || 0) - MF_MIN_LINE_PRICE) < 1e-9 &&
        Number(original.discount || 0) > 0
    );
  },

  /**
   * Si el descuento actual dejaría el neto de la línea en 0 (con precio base
   * positivo), factura la línea completa en el mínimo fiscal 0,01. Idempotente.
   */
  mfEnsureNonZeroFiscalPrice() {
    if (this._mf_fiscal_guard || this._mf_fiscal_min) {
      return; // ya sustituida: no re-sustituir (no sobrescribir el precio original)
    }
    if (this.mfIsRefundOfFiscalMin()) {
      // Ya trae el precio 0,01 y el descuento de la original (subtotal igual
      // al facturado): sólo se marca, sin recalcular el descuento.
      this._mf_fiscal_min = true;
      return;
    }
    const base = Number(this.price_unit || 0);
    if (base <= 0) {
      return; // producto gratuito o línea de descuento global (negativa)
    }
    const discount = Number(this.discount || 0);
    if (round_pr(base * (1 - discount / 100), MF_ROUNDING) > 0) {
      return; // el neto no llega a 0: nada que sustituir
    }
    this._mf_zeroed_original_price = base;
    this._mf_zeroed_original_price_type = this.price_type;
    this._mf_fiscal_min = true;
    this._mfApplyLineFiscalMin();
  },

  setDiscount(discount) {
    if (this._mf_fiscal_guard) {
      return super.setDiscount(discount);
    }
    // Partir del precio real para evaluar el nuevo descuento sobre la base.
    this.mfRestoreOriginalPrice();
    const result = super.setDiscount(discount);
    this.mfEnsureNonZeroFiscalPrice();
    return result;
  },

  setQuantity(quantity, keep_price) {
    const res = super.setQuantity(...arguments);
    // Recalcular el descuento para mantener el subtotal en 0,01 con la nueva
    // cantidad (el core devuelve true si la cantidad se aplicó).
    if (res === true && this._mf_fiscal_min && !this._mf_fiscal_guard) {
      this._mfApplyLineFiscalMin();
    }
    return res;
  },
});
