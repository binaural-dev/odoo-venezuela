/** @odoo-module */

import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import { patch } from "@web/core/utils/patch";
import { roundDecimals as round_di } from "@web/core/utils/numbers";
import { _t } from "@web/core/l10n/translation";
// OJO: se importa con alias. El resto de este fichero usa el `parseFloat`
// GLOBAL sobre cadenas producidas por `toFixed()` (siempre con punto
// decimal). El `parseFloat` de `@web/views/fields/parsers` es sensible al
// locale (en es_VE el separador decimal es la coma) y rompería esas
// llamadas si sombreara al global.
import { parseFloat as parseFloatLocale } from "@web/views/fields/parsers";

// -----------------------------------------------------------------------------
// Foreign amounts on POS orderlines (Venezuela).
//
// ROUNDING RULE (authoritative — see engram
// architecture/l10n-ve-pos/rounding-rule):
//   * foreign_price (unit price) → dp["Foreign Product Price"] (catalog dp).
//   * ALL other foreign monetary amounts (subtotal, tax, price_with_tax) →
//     foreign_currency_id.round().
//
// CONVERSION RULE:
//   * foreign = local * foreign_rate  (foreign_rate has full precision).
//   * Do NOT recompute taxes from a converted foreign price. Instead, take
//     each LOCAL price/tax from the core `get_all_prices()` and convert it
//     once via order.localToForeign(). This guarantees per-line values sum
//     to the same number as `localToForeign(order.totalDue)`.
// -----------------------------------------------------------------------------

patch(PosOrderline.prototype, {
    _is_order_in_foreign_currency() {
      const foreignCurrency = this.get_foreign_currency?.();
      const orderCurrencyId = this.order_id?.currency?.id ?? this.order_id?.currency;
      const foreignCurrencyId = foreignCurrency?.id ?? foreignCurrency;
      return (
        orderCurrencyId != null &&
        foreignCurrencyId != null &&
        orderCurrencyId === foreignCurrencyId
      );
    },

    get_foreign_currency() {
        return this.config.foreign_currency_id;
    },

    // ---- Refund rate consistency ----
    //
    // A refund line must convert to foreign currency at the rate the
    // ORIGINAL sale happened at, not at today's live PdV rate (the BCV
    // rate drifts daily in VE). `order_id.foreign_currency_rate` on an
    // already-synced order is the frozen snapshot written once when that
    // order was synced (see pos_order.py + pos_order.js's
    // `data["foreign_currency_rate"] = init_conversion_rate`). Live
    // `order.localToForeign()` always reads the CURRENT pos.config rate
    // and can't tell an order from today apart from one from last week —
    // this is the one place we deliberately bypass it.
    _refundOriginalRate() {
      const originalOrder = this.refunded_orderline_id?.order_id;
      if (!originalOrder) {
        return null;
      }
      const rate = Number(originalOrder.foreign_currency_rate);
      return Number.isFinite(rate) && rate > 0 ? rate : null;
    },

    // ---- Foreign unit price (uses catalog dp, per user directive) ----

    _foreignUnitPriceDp() {
      // "Foreign Product Price" is a Decimal Precision on the res.company
      // used for catalog-level foreign prices. Higher precision than a
      // monetary rounding (which is money-level).
      const dp = this.pos?.dp?.["Foreign Product Price"];
      if (Number.isInteger(dp) && dp >= 0) {
        return dp;
      }
      // Fallback: foreign currency decimal_places.
      const foreignCurrency = this.get_foreign_currency?.();
      const decimals = Number(foreignCurrency?.decimal_places);
      return Number.isInteger(decimals) && decimals >= 0 ? decimals : 2;
    },

    _get_raw_foreign_unit_price() {
      // Unrounded foreign unit price. Used internally by helpers that need
      // full precision before doing money-level rounding.
      const baseUnitPrice = Number(this.price_unit || 0);
      if (!Number.isFinite(baseUnitPrice) || baseUnitPrice <= 0) {
        return 0;
      }
      if (this._is_order_in_foreign_currency()) {
        return baseUnitPrice;
      }
      const frozenRate = this._refundOriginalRate();
      if (frozenRate != null) {
        return baseUnitPrice * frozenRate;
      }
      const order = this.order_id;
      if (!order || typeof order.localToForeign !== "function") {
        return 0;
      }
      // Raw (no rounding) — caller decides how to round.
      return order.localToForeign(baseUnitPrice, false);
    },

    setUnitPrice(price) {
      super.setUnitPrice(...arguments);
      const dp = this._foreignUnitPriceDp();

      if (this._is_order_in_foreign_currency()) {
        this.foreign_price = parseFloat(
          round_di(this.price_unit || 0, dp).toFixed(dp),
        );
        return;
      }
      const raw = this._get_raw_foreign_unit_price();
      this.foreign_price = parseFloat(round_di(raw, dp).toFixed(dp));
    },

    get_foreign_unit_price() {
      const dp = this._foreignUnitPriceDp();
      const stored = Number(this.foreign_price);
      if (this.foreign_price != null && Number.isFinite(stored) && stored > 0) {
        return parseFloat(round_di(stored, dp).toFixed(dp));
      }
      const baseUnitPrice = Number(this.price_unit || 0);
      if (!Number.isFinite(baseUnitPrice) || baseUnitPrice <= 0) {
        return 0;
      }
      const raw = this._get_raw_foreign_unit_price();
      return parseFloat(round_di(raw, dp).toFixed(dp));
    },

    // ---- Foreign monetary amounts (use foreign_currency.round via order helper) ----
    //
    // Instead of recomputing taxes on the foreign currency (which produced
    // drift vs the order-level total), we take the LOCAL prices from the
    // core `get_all_prices()` and convert each via order.localToForeign().
    // localToForeign already rounds with foreign_currency.round(), so
    // sum(get_foreign_price_*) matches order.get_foreign_total_with_tax().

    _localToForeignMoney(localAmount) {
      const order = this.order_id;
      if (!order || typeof order.localToForeign !== "function") {
        return 0;
      }
      const frozenRate = this._refundOriginalRate();
      if (frozenRate != null) {
        return order.roundForeignMoney(localAmount * frozenRate);
      }
      return order.localToForeign(localAmount);
    },

    // Odoo 19 exposes local monetary prices via getters:
    //   this.priceIncl / this.priceExcl → line total (with/without tax)
    //   this.priceInclNoDiscount / this.priceExclNoDiscount → no-discount variants
    //   this.prices → tax details (from order-level rounded computation)

    _conv(localAmount) {
      const n = Number(localAmount);
      if (!Number.isFinite(n)) {
        return 0;
      }
      return this._localToForeignMoney(n);
    },

    get_foreign_price_without_tax() {
      return this._conv(this.priceExcl);
    },

    get_foreign_price_with_tax() {
      return this._conv(this.priceIncl);
    },

    get_foreign_total_tax() {
      // priceIncl - priceExcl is the line tax in local (both already rounded
      // by the core with currency.round). Convert as one number to keep
      // sum(foreign_lines_tax) consistent with the total.
      const localTax = Number(this.priceIncl || 0) - Number(this.priceExcl || 0);
      return this._conv(localTax);
    },

    get_foreign_price_with_tax_before_discount() {
      return this._conv(this.priceInclNoDiscount);
    },

    get_foreign_price_without_tax_before_discount() {
      return this._conv(this.priceExclNoDiscount);
    },

    get_all_foreign_prices() {
      // Mirrors the shape older callers expected but sourced entirely from
      // local-priced core getters + a single conversion each. No double
      // rounding, no tax recomputation in foreign.
      const localTaxDetailsRaw = this.prices?.taxes_data || [];
      const taxDetails = {};
      for (const t of localTaxDetailsRaw) {
        if (!t?.tax?.id) continue;
        taxDetails[t.tax.id] = {
          amount: this._conv(t.tax_amount_currency),
          base: this._conv(t.base_amount_currency),
        };
      }
      return {
        priceWithTax: this.get_foreign_price_with_tax(),
        priceWithoutTax: this.get_foreign_price_without_tax(),
        priceWithTaxBeforeDiscount: this.get_foreign_price_with_tax_before_discount(),
        priceWithoutTaxBeforeDiscount: this.get_foreign_price_without_tax_before_discount(),
        tax: this.get_foreign_total_tax(),
        taxDetails: taxDetails,
        taxesData: localTaxDetailsRaw,
      };
    },

    get_foreign_tax_details() {
      return this.get_all_foreign_prices().taxDetails;
    },

    // "(G)" gravado / "(E)" exento badge shown next to the product name.
    get_aliquot_type() {
      const productTaxes = this.tax_ids?.length ? this.tax_ids : (this.product_id?.taxes_id || []);
      if (!productTaxes.length) {
        return "(E)";
      }
      return productTaxes[0].amount === 0 ? "(E)" : "(G)";
    },

    // -------------------------------------------------------------------------
    // Cantidades negativas: solo en líneas de reembolso (Venezuela)
    //
    // Odoo 19 permite poner en negativo CUALQUIER línea desde el numpad
    // (tecla "+/-" → `SWITCHSIGN` en numpad.js, o tecleando "-3"), lo que
    // genera una orden de VENTA con una línea negativa. En VE eso emite una
    // factura fiscal con cantidad negativa en vez de la nota de crédito que
    // corresponde. Solo puede ser negativa:
    //   * una línea de reembolso real, es decir vinculada a la línea que
    //     reembolsa (`refunded_orderline_id`, que fija
    //     `TicketScreen.onDoRefund` al crear la orden destino), o
    //   * cualquier línea de una orden con preset de devolución
    //     (`preset_id.is_return`), donde el propio core fuerza
    //     `-Math.abs(qty)` en `setQuantity` y en `addLineToOrder`; bloquearla
    //     dejaría ese modo nativo roto en silencio.
    //
    // Se intercepta en `setQuantity` porque es el único punto por el que pasan
    // TODOS los caminos de edición de cantidad (numpad, `QuantityButtons`,
    // código de barras con peso, propagación a líneas de combo). Las líneas de
    // reembolso NO se crean por aquí: `onDoRefund` las crea directamente con
    // `models["pos.order.line"].create({qty: -refundDetail.qty, ...})`, así
    // que este guard no las afecta.
    //
    // Contrato de `setQuantity` en Odoo 19: devuelve `true` si tuvo éxito, o
    // un objeto `{title, body}` que `OrderSummary._setValue` muestra como
    // `AlertDialog` y seguido resetea el `number_buffer`.
    _isRefundLine() {
      return Boolean(this.refunded_orderline_id) || Boolean(this.order_id?.preset_id?.is_return);
    },

    _quantityAsNumber(quantity) {
      // Mismo parseo que el core (pos_order_line.js `setQuantity`), pero sin
      // dejar escapar una excepción del parser sensible al locale: si no se
      // puede interpretar, se devuelve NaN y el guard delega en el core para
      // que falle exactamente igual que en Odoo estándar.
      if (typeof quantity === "number") {
        return quantity;
      }
      try {
        return parseFloatLocale("" + (quantity ? quantity : 0));
      } catch {
        return NaN;
      }
    },

    setQuantity(quantity, keep_price) {
      if (!this._isRefundLine()) {
        const quant = this._quantityAsNumber(quantity);
        // `-0 < 0` es false, así que poner una línea en cero sigue permitido
        // (es como el cajero borra una línea desde el numpad).
        if (Number.isFinite(quant) && quant < 0) {
          return {
            title: _t("Negative quantity not allowed"),
            body: _t(
              "Only refund lines can have a negative quantity. To return products, use the refund flow: Orders → select the original order → Refund."
            ),
          };
        }
      }
      return super.setQuantity(...arguments);
    },
});
