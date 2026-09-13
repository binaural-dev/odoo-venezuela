/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import { roundPrecision as round_pr } from "@web/core/utils/numbers";

/**
 * Máquina fiscal: sustitución de líneas con descuento del 100% por el mínimo
 * fiscal (0,01). Ticket #15105.
 *
 * Problema: la máquina fiscal (TFHKA) no acepta imprimir una línea con precio
 * 0,00 — el driver la descarta (`if (linePrice <= 0) continue;` en
 * `l10n_ve_mf_base/TfhkaDriver.js`), con lo que la factura fiscal saldría sin
 * esa línea. Además, la validación `_check_max_discount` (l10n_ve_accountant)
 * bloquea toda factura con descuento >= 100%. Como el campo `discount` de la
 * factura sólo admite 2 decimales, NO se puede bajar el porcentaje para dejar
 * el neto en 0,01 (redondearía a 100% y volvería a bloquear).
 *
 * Solución (definida por Producto en el ticket): cuando un descuento —de línea
 * o global— dejaría el neto de la línea en 0, se sustituye por precio unitario
 * 0,01 SIN descuento. Así el neto queda en el mínimo fiscal, la factura no se
 * bloquea (descuento 0) y la MF imprime la línea. Se guarda el precio original
 * (`_mf_zeroed_original_price`) para revertir si luego se cambia o se quita el
 * descuento.
 *
 * Punto de intercepción: `setDiscount`, por el que pasan TODOS los caminos —el
 * descuento por línea del numpad (`pos.setDiscountFromUI` → `line.setDiscount`)
 * y el descuento global de este módulo (`_applyGlobalDiscountBeforeValidation`
 * → `line.setDiscount`)—, más un respaldo en `PosStore.pay()` para órdenes
 * cargadas/reanudadas cuyas líneas ya venían al 100%.
 */

// Precio mínimo que la máquina fiscal acepta en una línea (Bs 0,01).
export const MF_MIN_LINE_PRICE = 0.01;
// Redondeo a céntimo para detectar si el neto de la línea es cero.
const MF_ROUNDING = 0.01;

patch(PosOrderline.prototype, {
  /**
   * Restaura el precio unitario real de una línea previamente sustituida por
   * el mínimo fiscal. No hace nada si la línea no fue sustituida.
   */
  mfRestoreOriginalPrice() {
    if (this._mf_zeroed_original_price == null || this._mf_fiscal_guard) {
      return;
    }
    this._mf_fiscal_guard = true;
    try {
      this.setUnitPrice(this._mf_zeroed_original_price);
      // Restaurar el tipo de precio original (p. ej. "original") para que la
      // lista de precios vuelva a recalcular si cambia la cantidad.
      if (this._mf_zeroed_original_price_type != null) {
        this.price_type = this._mf_zeroed_original_price_type;
      }
    } finally {
      this._mf_fiscal_guard = false;
    }
    this._mf_zeroed_original_price = null;
    this._mf_zeroed_original_price_type = null;
  },

  /**
   * Si el descuento actual dejaría el neto de la línea en 0 (con precio base
   * positivo), la sustituye por precio 0,01 sin descuento. Idempotente.
   */
  mfEnsureNonZeroFiscalPrice() {
    if (this._mf_fiscal_guard) {
      return;
    }
    const base = Number(this.price_unit || 0);
    if (base <= 0) {
      // Producto realmente gratuito o línea de descuento global (negativa):
      // fuera de alcance.
      return;
    }
    const discount = Number(this.discount || 0);
    const net = base * (1 - discount / 100);
    if (round_pr(net, MF_ROUNDING) > 0) {
      return; // el neto no llega a 0: nada que sustituir
    }
    this._mf_fiscal_guard = true;
    try {
      this._mf_zeroed_original_price = base;
      this._mf_zeroed_original_price_type = this.price_type;
      // setDiscount(0) queda protegido por el guard → llama al core y quita el
      // descuento sin volver a entrar en esta lógica.
      this.setDiscount(0);
      // setUnitPrice actualiza también foreign_price (override de l10n_ve_pos).
      this.setUnitPrice(MF_MIN_LINE_PRICE);
      // Fijar el precio como manual para que un cambio de cantidad no vuelva a
      // recalcularlo desde la lista de precios y pierda el 0,01.
      this.price_type = "manual";
    } finally {
      this._mf_fiscal_guard = false;
    }
  },

  setDiscount(discount) {
    if (this._mf_fiscal_guard) {
      return super.setDiscount(discount);
    }
    // Partir siempre del precio real: si la línea fue sustituida antes,
    // restaurarlo para evaluar el nuevo descuento sobre la base verdadera.
    this.mfRestoreOriginalPrice();
    const result = super.setDiscount(discount);
    // Si el descuento resultante deja la línea en 0, sustituir por 0,01.
    this.mfEnsureNonZeroFiscalPrice();
    return result;
  },
});
