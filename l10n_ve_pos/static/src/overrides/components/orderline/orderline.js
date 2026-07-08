/** @odoo-module */

import { Orderline } from "@point_of_sale/app/components/orderline/orderline";
import { patch } from "@web/core/utils/patch";

// -----------------------------------------------------------------------------
// Foreign display helpers on the Orderline component (Venezuela).
//
// This component delegates to the model helpers on PosOrderline
// (get_foreign_price_without_tax, get_foreign_price_with_tax, etc.). It does
// NOT do any conversion or rounding itself: the model layer is the single
// source of truth (see engram architecture/l10n-ve-pos/rounding-rule).
// -----------------------------------------------------------------------------

patch(Orderline.prototype, {
  setup() {
    super.setup();
  },

  get_rate() {
    if (this.order?._isRefundOrder?.() && this.get_refund_orderline()) {
      return this.get_refund_orderline().orderline.foreign_currency_rate;
    }
    if (
      this.foreign_currency_rate &&
      this.foreign_currency_rate !== this.order.init_conversion_rate
    ) {
      return this.foreign_currency_rate;
    }
    return this.order.init_conversion_rate;
  },

  get currency_rate_display() {
    return this.order.get_display_rate;
  },

  get_refund_orderline() {
    for (const id of Object.keys(this.pos.toRefundLines)) {
      if (this.refunded_orderline_id == id) {
        return this.pos.toRefundLines[id];
      }
    }
    return false;
  },

  // ---- Foreign price accessors (delegate to model helpers) ----

  get_foreign_price_without_tax() {
    return this.line?.get_foreign_price_without_tax?.() ?? 0;
  },

  get_foreign_price_with_tax() {
    return this.line?.get_foreign_price_with_tax?.() ?? 0;
  },

  get_foreign_price_with_tax_before_discount() {
    return this.line?.get_foreign_price_with_tax_before_discount?.() ?? 0;
  },

  get_foreign_tax() {
    return this.line?.get_foreign_total_tax?.() ?? 0;
  },

  get_display_foreign_price() {
    if (this.pos.config.iface_tax_included === "total") {
      return this.get_foreign_price_with_tax();
    }
    return this.get_foreign_price_without_tax();
  },

  get_unit_display_foreign_price() {
    // Foreign unit price for display: use catalog dp precision (per rule).
    // The line's get_foreign_unit_price already rounds with the catalog dp.
    return this.line?.get_foreign_unit_price?.() ?? 0;
  },

  get_foreign_total_taxes_included_in_price() {
    // Tax portion for tax-included products, in foreign currency. Sum the
    // per-tax detail from the model (which was converted from local details).
    const details = this.line?.get_foreign_tax_details?.() || {};
    const productTaxes = this._getProductTaxesAfterFiscalPosition?.() || [];
    return productTaxes
      .filter((tax) => tax?.price_include)
      .reduce((sum, tax) => sum + (details[tax.id]?.amount || 0), 0);
  },

  getForeignUnitDisplayPriceBeforeDiscount() {
    // Convert local unit price (before discount) once, using catalog dp.
    const line = this.line;
    if (!line) return 0;
    const unitPrice = this.pos.config.iface_tax_included === "total"
      ? line.priceUnitInclNoDiscount
      : line.displayPriceUnit;
    const order = line.order_id;
    if (!order || typeof order.localToForeign !== "function") {
      return 0;
    }
    return order.localToForeign(Number(unitPrice) || 0);
  },

  get_aliquot_type() {
    const product_tax = this.line?.tax_ids || this.line?.product_id?.taxes_id || [];
    if (!product_tax || product_tax.length < 1) {
      return "(E)";
    }
    const firstTax = product_tax[0];
    const taxAmount = typeof firstTax === "object" ? firstTax.amount : this.pos?.taxes_by_id?.[firstTax]?.amount;
    if (taxAmount === 0) {
      return "(E)";
    }
    return "(G)";
  },

  getDisplayData() {
    const res = super.getDisplayData(...arguments);
    res["foreignUnitPrice"] = this.env.utils.formatForeignCurrency(
      this.get_unit_display_foreign_price(),
    );
    res["foreignPrice"] =
      this.get_discount_str?.() === "100"
        ? "free"
        : this.env.utils.formatForeignCurrency(this.get_display_foreign_price());
    res["aliquot_type"] = this.get_aliquot_type();
    res["foreign_currency_rate"] = this.get_rate();
    res["foreign_currency_rate_display"] = this.env.utils.formatForeignCurrency(
      this.currency_rate_display,
    );
    return res;
  },
});
