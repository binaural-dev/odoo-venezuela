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
   * Precio y descuento que dejan el subtotal de la línea en 0,01 para `qty`:
   * - qty > 1: precio 0,01 y descuento (1 − 1/qty) × 100, de modo que
   *   0,01 × qty × (1/qty) = 0,01. Nunca llega a 100% (tope 99,99).
   * - 0,5 ≤ qty ≤ 1: precio 0,01 sin descuento (0,01 × qty redondea a 0,01).
   * - qty < 0,5 (pesados): 0,01 × qty redondearía a 0,00, así que el precio
   *   sube al céntimo siguiente de 0,01 / qty, sin descuento (0,3 kg → 0,04).
   */
  _mfFiscalMinTarget(qty) {
    if (qty > 1) {
      let discount = round_pr((1 - 1 / qty) * 100, 0.01);
      if (discount >= 100) {
        discount = 99.99; // el descuento nunca alcanza 100% (no lo bloquea la factura)
      }
      return { price: MF_MIN_LINE_PRICE, discount };
    }
    if (qty > 0 && qty < 0.5) {
      return { price: Math.ceil((MF_MIN_LINE_PRICE / qty) * 100 - 1e-9) / 100, discount: 0 };
    }
    return { price: MF_MIN_LINE_PRICE, discount: 0 };
  },

  /**
   * Fija el precio y el descuento que dejan el subtotal de la línea en 0,01
   * para la cantidad actual. Reutilizable al cambiar la cantidad.
   */
  _mfApplyLineFiscalMin() {
    const qty = Math.abs(Number(this.getQuantity?.() ?? this.qty ?? 1)) || 1;
    const { price, discount } = this._mfFiscalMinTarget(qty);
    this._mf_fiscal_guard = true;
    try {
      this.setUnitPrice(price);
      this.setDiscount(discount); // protegido por el guard → llama al core
      this.price_type = "manual";
    } finally {
      this._mf_fiscal_guard = false;
    }
  },

  /**
   * ¿Los datos de la línea son los de una línea en el mínimo fiscal con
   * cantidad > 1 (precio 0,01 con el descuento que corresponde a su
   * cantidad)? Esa combinación sólo la produce este módulo y, a diferencia de
   * la marca `_mf_fiscal_min` (que vive sólo en memoria), sobrevive a
   * recargar la caja y a la reimpresión de pedidos pendientes, donde la orden
   * viene del servidor. Con cantidad ≤ 1 no hay descuento que la distinga de
   * un precio normal, así que no se reconoce.
   */
  _mfMatchesFiscalMinData() {
    const qty = Math.abs(Number(this.qty || 0));
    if (!(qty > 1)) {
      return false;
    }
    const target = this._mfFiscalMinTarget(qty);
    return (
      Math.abs(Number(this.price_unit || 0) - target.price) < 1e-9 &&
      Math.abs(Number(this.discount || 0) - target.discount) < 1e-6
    );
  },

  /**
   * ¿La línea está facturada en el mínimo fiscal? Por la marca de esta sesión,
   * por sus datos o por ser la devolución de una línea en el mínimo fiscal.
   */
  mfIsFiscalMinLine() {
    return Boolean(
      this._mf_fiscal_min || this._mfMatchesFiscalMinData() || this.mfIsRefundOfFiscalMin()
    );
  },

  /**
   * Devolución de una línea facturada en el mínimo fiscal. El core crea la
   * línea de la devolución copiando precio (0,01) y descuento de la original
   * sin pasar por `setDiscount`, así que no queda marcada; y con 2 unidades
   * (descuento 50%) el neto por unidad redondea a 0,01, por lo que
   * `mfEnsureNonZeroFiscalPrice` tampoco la detecta. Se reconoce por los
   * datos de la línea original, que sirve también en devoluciones parciales.
   */
  mfIsRefundOfFiscalMin() {
    return Boolean(this.refunded_orderline_id?._mfMatchesFiscalMinData?.());
  },

  /**
   * Si el descuento actual dejaría el neto de la línea en 0 (con precio base
   * positivo), factura la línea completa en el mínimo fiscal 0,01. Idempotente.
   */
  mfEnsureNonZeroFiscalPrice() {
    if (this._mf_fiscal_guard || this._mf_fiscal_min) {
      return; // ya sustituida: no re-sustituir (no sobrescribir el precio original)
    }
    if (this._mfMatchesFiscalMinData() || this.mfIsRefundOfFiscalMin()) {
      // Ya trae los datos del mínimo fiscal (orden recargada, pedido pendiente
      // o devolución): sólo se marca, sin recalcular. El precio original no se
      // conoce, así que quitar el descuento después no lo restaura.
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
    // Si la línea estaba marcada sin precio original guardado (reconocida por
    // sus datos), se desmarca y se vuelve a evaluar con el nuevo descuento.
    this.mfRestoreOriginalPrice();
    this._mf_fiscal_min = false;
    const result = super.setDiscount(discount);
    this.mfEnsureNonZeroFiscalPrice();
    return result;
  },

  setQuantity(quantity, keep_price) {
    // Se evalúa antes de cambiar la cantidad: el reconocimiento por datos
    // depende de la cantidad actual.
    const wasFiscalMin = !this._mf_fiscal_guard && this.mfIsFiscalMinLine();
    const res = super.setQuantity(...arguments);
    // Recalcular precio y descuento para mantener el subtotal en 0,01 con la
    // nueva cantidad (el core devuelve true si la cantidad se aplicó).
    if (res === true && wasFiscalMin) {
      this._mf_fiscal_min = true;
      this._mfApplyLineFiscalMin();
    }
    return res;
  },

  setUnitPrice(price) {
    const res = super.setUnitPrice(...arguments);
    if (!this._mf_fiscal_guard) {
      // Precio cambiado a mano (numpad, lista de precios…): la línea deja de
      // estar en el mínimo fiscal y el precio original guardado ya no aplica.
      this._mf_fiscal_min = false;
      this._mf_zeroed_original_price = null;
      this._mf_zeroed_original_price_type = null;
    }
    return res;
  },
});
