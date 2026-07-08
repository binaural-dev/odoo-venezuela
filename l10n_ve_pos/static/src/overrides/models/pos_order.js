/** @odoo-module */

import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { PosOrderAccounting } from "@point_of_sale/app/models/accounting/pos_order_accounting";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";


// New orders are now associated with the current table, if any.
patch(PosOrder.prototype, {
  setup() {
      super.setup(...arguments);
      this._missingConversionRateWarningShown = false;
      // Guard contra bug del core Odoo 19: _computeAllPrices (pos_order_accounting.js:295)
      // hace lines.map(...) sin verificar que lines no sea undefined. Aparece
      // cuando órdenes sincronizadas llegan al frontend sin líneas inicializadas
      // (común en DBs restauradas/copiadas con órdenes huérfanas).
      if (!Array.isArray(this.lines)) {
        this.lines = [];
      }
      // l10n_ve_pos: SENIAT — toda venta y nota de crédito del PoS debe emitir factura.
      // Forzamos to_invoice=true en TODAS las órdenes, incluyendo reembolsos.
      this.to_invoice = true;
  },
  setToInvoice() {
      // SENIAT: toda orden del PoS debe emitir factura, incluyendo notas de crédito.
      this.to_invoice = true;
  },
 get_foreign_currency(){
        return this.config.foreign_currency_id;
    },
  get_display_rate() {
    const rateCandidates = [
      this.config?.foreign_inverse_rate,
      this.pos?.config?.foreign_inverse_rate,
      this.config?.foreign_rate,
      this.pos?.config?.foreign_rate,
      this.foreign_currency_rate,
    ];

    const rawRate = rateCandidates
      .map((value) => Number(value))
      .find((value) => Number.isFinite(value) && value > 0);

    if (!Number.isFinite(rawRate) || rawRate <= 0) {
      return _t("N/D");
    }

    // UI semantic: show "1 foreign = X local". Some datasets provide the
    // inverse (e.g. 0.001) for serialization math; normalize for display.
    return rawRate < 1 ? 1 / rawRate : rawRate;
  },

  get_display_rate_formatted() {
    // Same as get_display_rate but formatted with the "Tasa" decimal
    // precision (same as order_summary's getConversionRateForDisplay).
    const rate = this.get_display_rate();
    if (typeof rate !== "number") return rate; // "N/D" o similar
    const rateDp = this.pos?.models?.["decimal.precision"]?.find?.(
      (dp) => dp.name === "Tasa"
    );
    const precision = Number.isFinite(Number(rateDp?.digits))
      ? Number(rateDp.digits)
      : 6;
    return rate.toFixed(precision);
  },

//   _isValidEmptyOrder() {
//     let res = super._isValidEmptyOrder(...arguments);
//     if (this.get_change() != 0) {
//       return false;
//     }
//     return res;
//   },
//   assert_editable() {},

  // -------- POS-scoped currency conversion (Venezuela) --------
  //
  // MIRROR CONTRACT:
  //   This mirrors pos.config._convert in Python (models/pos_config.py).
  //   Same inputs → same outputs on both sides. Multiply by the RAW rate
  //   (all 15 digits from `digits=(16,15)`), round only the final result
  //   via to_currency.round().
  //
  // SEMÁNTICA REAL (verificada en DB pos + core Odoo 19 res_currency.py):
  //   l10n_ve_rate.compute_rate para foreign=USD, main=VEF devuelve:
  //     pos.config.foreign_rate         = rate.inverse_company_rate  (~675, GRANDE)
  //     pos.config.foreign_inverse_rate = rate.company_rate          (~0.001481, CHICO)
  //
  //   Conversión correcta (regla del usuario):
  //     main (VEF) → foreign (USD): multiplicar por foreign_inverse_rate (0.001481)
  //     foreign (USD) → main (VEF): multiplicar por foreign_rate         (675)
  //
  //   Caso foreign=VEF, main=USD: ambos campos son iguales (company_rate).
  //
  //   NUNCA redondear la tasa antes de multiplicar; redondear solo el
  //   resultado con to_currency.round() en _convert.
  //
  // KEEP IN SYNC WITH:
  //   models/pos_config.py :: PosConfig._get_pos_conversion_rate

  _getMainCurrency() {
    return (
      this.currency ??
      this.config?.currency_id ??
      this.pos?.config?.currency_id ??
      null
    );
  },

  _getForeignCurrencyRecord() {
    // May return a res.currency record (with .round, .id) or a bare id
    // depending on the model cache path. Callers must handle both.
    return (
      this.config?.foreign_currency_id ??
      this.pos?.config?.foreign_currency_id ??
      null
    );
  },

  _currencyId(currency) {
    if (currency == null) return null;
    return typeof currency === "object" ? (currency.id ?? null) : currency;
  },

  _getPosConversionRate(fromCurrency, toCurrency) {
    // SEMÁNTICA REAL (verificada en DB pos + core Odoo 19 res_currency.py):
    //
    //   l10n_ve_rate.compute_rate para foreign=USD, main=VEF devuelve:
    //     pos.config.foreign_rate         = inverse_company_rate  (~675, GRANDE)
    //     pos.config.foreign_inverse_rate = company_rate          (~0.001481, CHICO)
    //
    //   El CHICO es el multiplicador REAL main→foreign:
    //     VEF * 0.001481 = USD ✓
    //   El GRANDE es para foreign→main:
    //     USD * 675 = VEF ✓
    //
    //   Caso foreign=VEF, main=USD: ambos campos valen company_rate y
    //   son idénticos, cualquiera funciona.
    //
    // PRECISION: foreign_inverse_rate está con digits=(16,15). NUNCA
    // redondear la tasa; redondear solo el resultado con
    // to_currency.round() en _convert.
    //
    // KEEP IN SYNC WITH:
    //   models/pos_config.py :: PosConfig._get_pos_conversion_rate
    const fromId = this._currencyId(fromCurrency);
    const toId = this._currencyId(toCurrency);
    if (fromId != null && toId != null && fromId === toId) {
      return 1;
    }
    const foreignId = this._currencyId(this._getForeignCurrencyRecord());
    if (!foreignId) {
      return 0;
    }
    // main → foreign: multiplicar por foreign_inverse_rate (CHICO)
    if (toId === foreignId && fromId !== foreignId) {
      const rate = Number(
        this.config?.foreign_inverse_rate ??
        this.pos?.config?.foreign_inverse_rate ??
        0
      );
      return rate > 0 ? rate : 0;
    }
    // foreign → main: multiplicar por foreign_rate (GRANDE)
    if (fromId === foreignId && toId !== foreignId) {
      const rate = Number(
        this.config?.foreign_rate ??
        this.pos?.config?.foreign_rate ??
        0
      );
      return rate > 0 ? rate : 0;
    }
    return 0;
  },

  _resolveCurrencyRecord(currency) {
    // Accepts a res.currency record OR a bare id, returns a record with
    // a working .round() when possible. Falls back to the input.
    if (currency == null) return null;
    if (typeof currency === "object" && typeof currency.round === "function") {
      return currency;
    }
    const id = this._currencyId(currency);
    if (id == null) return currency;
    const models = this.pos?.models || this.models;
    if (models && typeof models["res.currency"]?.get === "function") {
      const rec = models["res.currency"].get(id);
      if (rec) return rec;
    }
    return currency;
  },

  _roundWithCurrency(currency, amount) {
    // Money-rounding using res.currency.rounding step (the ONLY correct way
    // to round monetary amounts in Odoo). Do NOT use for unit prices from
    // the catalog — those use dp["Foreign Product Price"].
    const resolved = this._resolveCurrencyRecord(currency);
    if (resolved && typeof resolved.round === "function") {
      return resolved.round(amount);
    }
    // Last-resort rounding using decimal_places if present, else 2 dp.
    const dp = Number(resolved?.decimal_places);
    const digits = Number.isInteger(dp) && dp >= 0 ? dp : 2;
    const factor = Math.pow(10, digits);
    return Math.round(amount * factor) / factor;
  },

  // ---- Public helpers ----

  roundForeignMoney(amount) {
    // Canonical way to round any FOREIGN MONETARY amount. Use for subtotals,
    // taxes, totals, due, change, payment amounts. NOT for unit prices.
    return this._roundWithCurrency(this._getForeignCurrencyRecord(), amount);
  },

  roundLocalMoney(amount) {
    // Canonical way to round any LOCAL (main) MONETARY amount.
    return this._roundWithCurrency(this._getMainCurrency(), amount);
  },

  _convert(fromAmount, fromCurrency, toCurrency, doRound = true) {
    if (!fromAmount) {
      return 0;
    }
    const fromId = this._currencyId(fromCurrency);
    const toId = this._currencyId(toCurrency);
    if (fromId != null && toId != null && fromId === toId) {
      return doRound ? this._roundWithCurrency(toCurrency, fromAmount) : fromAmount;
    }
    const rate = this._getPosConversionRate(fromCurrency, toCurrency);
    if (!rate) {
      if (!this._posConvertWarningShown) {
        this._posConvertWarningShown = true;
        // eslint-disable-next-line no-console
        console.warn(
          "[l10n_ve_pos] _convert: no rate available",
          {
            fromId,
            toId,
            foreignId: this._currencyId(this._getForeignCurrencyRecord()),
            foreignRate: this.config?.foreign_rate,
            foreignInverseRate: this.config?.foreign_inverse_rate,
          }
        );
      }
      return 0;
    }
    const result = fromAmount * rate;
    return doRound ? this._roundWithCurrency(toCurrency, result) : result;
  },

  // ---- Convenience shortcuts used by payment lines and templates ----

  localToForeign(amount, doRound = true) {
    return this._convert(amount, this._getMainCurrency(), this._getForeignCurrencyRecord(), doRound);
  },

  foreignToLocal(amount, doRound = true) {
    return this._convert(amount, this._getForeignCurrencyRecord(), this._getMainCurrency(), doRound);
  },

  // ---- Backwards-compatibility shims (do NOT use in new code) ----
  // Existing callers (orderline.js, payment_status.js, some templates) still
  // reference these. They now delegate to the new API so all math is unified.

  get_foreign_multiplier() {
    // local → foreign; returns the raw multiplier (no rounding).
    return this._getPosConversionRate(this._getMainCurrency(), this._getForeignCurrencyRecord());
  },

  get_local_multiplier() {
    // foreign → local; returns the raw multiplier (no rounding).
    return this._getPosConversionRate(this._getForeignCurrencyRecord(), this._getMainCurrency());
  },

  get init_conversion_rate() {
    return this.get_foreign_multiplier();
  },
 

//   add_orderline(line) {
//     let res = super.add_orderline(...arguments);
//     this.reload_taxes();
//     return res;
//   },
  get_conversion_rate() {
    // NOTE: currency_rate_display on line is a getter on the OWL component,
    // not callable on PosOrderline model, so we removed the dead call to it.
    if (!this.init_conversion_rate) {
      this._missingConversionRateWarningShown = true;
      return _t("N/D");
    }

    return this.init_conversion_rate;
  },

  get_orderlines() {
    if (!this.cid || !this.cid) {
      return this.lines
    }

    if (this.cid != this.cid) {
      return this.lines;
    }

    if (this.lines.length < 1) {
      this.lock_toggle_receipt_invoice = false
      return this.lines
    }

    let line = this.lines[0]

    if (!line.refunded_orderline_id) {
      return this.lines
    }

    if (this.lock_toggle_receipt_invoice) {
      return this.lines
    }

    // this.pos.env.services.rpc({
    //   model: 'pos.order.line',
    //   method: 'search_read',
    //   domain: [['id', '=', line.refunded_orderline_id]],
    // }).then((el) => {
    //   this.to_receipt = el[0].to_receipt
    //   this.lock_toggle_receipt_invoice = true
    // })
    return this.lines;
  },

//   reload_taxes() {
//     this.orderlines.forEach((el) => {
//       el.product.taxes_id = el.product.originalTaxes;
//       el.tax_ids = el.product.taxes_id;
//     });
//   },
//   toggle_receipt_invoice(to_receipt) {
//     if (this.getHasRefundLines()) {
//       return;
//     }
//     if (this.lock_toggle_receipt_invoice) {
//       return;
//     }
//     this.assert_editable();
//     this.to_receipt = to_receipt;
//     this.reload_taxes();
//   },
  serializeForORM(opts = {}) {
    const data = super.serializeForORM(opts);
    data["foreign_amount_total"] = this.get_foreign_total_with_tax();
    data["foreign_currency_rate"] = Number(this.init_conversion_rate || 0);
    if (typeof this.is_to_receipt === "function") {
      data["to_receipt"] = this.is_to_receipt();
    } else if ("to_receipt" in this) {
      data["to_receipt"] = this.to_receipt;
    }
    // l10n_ve_pos: SENIAT exige factura también en notas de crédito.
    // La facturación obligatoria aplica a TODAS las órdenes, incluyendo
    // reembolsos (isRefund).
    return data;
  },
//   is_to_receipt() {
//     return this.to_receipt;
//   },
  export_for_printing() {
    const res = super.export_for_printing(...arguments);
    return {
      ...res,
      foreign_amount_total: this.get_foreign_total_with_tax(),
      foreign_total_without_tax: this.get_foreign_total_without_tax(),
      foreign_amount_tax: this.get_foreign_total_tax(),
      foreign_total_paid: this.get_foreign_total_paid(),
    };
  },
//   set_orderline_options(orderline, options) {
//     super.set_orderline_options(...arguments);
//     if (options.foreign_price !== undefined) {
//       orderline.set_foreign_unit_price(options.foreign_price);
//     }
//   },

//   calculate_foreign_base_amount(tax_ids_array, lines) {
//     // Consider price_include taxes use case
//     const has_taxes_included_in_price = tax_ids_array.filter(
//       (tax_id) => this.pos.taxes_by_id[tax_id].price_include,
//     ).length;

//     const base_amount = lines.reduce(
//       (sum, line) =>
//         sum +
//         line.get_foreign_price_without_tax() +
//         (has_taxes_included_in_price
//           ? line.get_foreign_total_taxes_included_in_price()
//           : 0),
//       0,
//     );
//     return base_amount;
//   },
//   /* ---- Payment Status --- */
//   get_foreign_subtotal() {
//     return round_pr(
//       this.orderlines.reduce(function (sum, orderLine) {
//         return sum + orderLine.get_display_foreign_price();
//       }, 0),
//       this.pos.foreign_currency.rounding,
//     );
//   },
  // ---- Foreign totals: SINGLE POINT of conversion ----
  //
  // Each foreign total is `localToForeign(local_total)`, so per-line foreign
  // amounts summed together match the total (no drift). All rounding uses
  // foreign_currency_id.round() via order.localToForeign.
  //
  // Local sources (Odoo 19):
  //   this.totalDue         → total including taxes
  //   this.prices.taxDetails.base_amount    → total excluding taxes
  //   this.prices.taxDetails.tax_amount_currency → tax amount

  _localTotalWithTax() {
    return Number(
      this.totalDue ??
      (typeof this.get_total_with_tax === "function" ? this.get_total_with_tax() : 0)
    ) || 0;
  },

  _localTotalWithoutTax() {
    return Number(this.prices?.taxDetails?.base_amount ?? 0) || 0;
  },

  _localTotalTax() {
    return Number(this.prices?.taxDetails?.tax_amount_currency ?? 0) || 0;
  },

  get_foreign_total_with_tax() {
    return this.localToForeign(this._localTotalWithTax());
  },

  get_foreign_total_without_tax() {
    return this.localToForeign(this._localTotalWithoutTax());
  },

  get_foreign_total_tax() {
    return this.localToForeign(this._localTotalTax());
  },
//   get_foreign_total_discount() {
//     const ignored_product_ids = this._get_ignored_product_ids_total_discount();
//     return round_pr(

  // ---- Foreign payment helpers (Odoo 19 migration) ----

  get_foreign_total_paid() {
    // Sum of paid foreign_amount across done payment lines, rounded with
    // foreign_currency_id.round() (money-rounding).
    const sum = Array.from(this.payment_ids).reduce((acc, line) => {
      return acc + (line.isDone?.() ? Number(line.get_foreign_amount?.() ?? 0) : 0);
    }, 0);
    return this.roundForeignMoney(sum);
  },

  get_foreign_due() {
    const remaining = this.get_foreign_total_with_tax() - this.get_foreign_total_paid();
    return this.roundForeignMoney(Math.max(0, remaining));
  },

  get_foreign_change() {
    // Change to return in foreign currency when overpaid.
    const change = this.get_foreign_total_paid() - this.get_foreign_total_with_tax();
    return this.roundForeignMoney(Math.max(0, change));
  },
//       this.orderlines.reduce((sum, orderLine) => {
//         if (!ignored_product_ids.includes(orderLine.product.id)) {
//           sum +=
//             orderLine.getForeignUnitDisplayPriceBeforeDiscount() *
//             (orderLine.get_discount() / 100) *
//             orderLine.getQuantity();
//           if (orderLine.display_discount_policy() === "without_discount") {
//             sum +=
//               (orderLine.get_taxed_lst_unit_foreign_price() -
//                 orderLine.getForeignUnitDisplayPriceBeforeDiscount()) *
//               orderLine.getQuantity();
//           }
//         }
//         return sum;
//       }, 0),
//       this.pos.foreign_currency.rounding,
//     );
//   },
  // get_foreign_total_tax defined above using localToForeign(localTotalTax).
//   get_foreign_tax_details() {
//     var details = {};
//     var fulldetails = [];

//     this.orderlines.forEach(function (line) {
//       var ldetails = line.get_foreign_tax_details();
//       for (var id in ldetails) {
//         if (Object.hasOwnProperty.call(ldetails, id)) {
//           details[id] = {
//             amount: (details[id]?.amount || 0) + ldetails[id].amount,
//             base: (details[id]?.base || 0) + ldetails[id].base,
//           };
//         }
//       }
//     });

//     for (var id in details) {
//       if (Object.hasOwnProperty.call(details, id)) {
//         fulldetails.push({
//           amount: details[id].amount,
//           base: details[id].base,
//           tax: this.pos.taxes_by_id[id],
//           name: this.pos.taxes_by_id[id].name,
//         });
//       }
//     }

//     return fulldetails;
//   },
//   get_foreign_total_for_taxes(tax_id) {
//     var total = 0;

//     if (!(tax_id instanceof Array)) {
//       tax_id = [tax_id];
//     }

//     var tax_set = {};

//     for (var i = 0; i < tax_id.length; i++) {
//       tax_set[tax_id[i]] = true;
//     }

//     this.orderlines.forEach((line) => {
//       var taxes_ids = this.tax_ids || line.getProduct().taxes_id;
//       for (var i = 0; i < taxes_ids.length; i++) {
//         if (tax_set[taxes_ids[i]]) {
//           total += line.get_foreign_price_with_tax();
//           return;
//         }
//       }
//     });

//     return total;
//   },
//   async pay() {
//     let order = this.pos.get_order();
//     let lines = order.get_orderlines();

//     if (order.getHasRefundLines()) {
//       return await super.pay();
//     }
//     await this.pos.update_products(order);

//     if (this.pos.config.amount_to_zero) {
//       let product_quantity_by_product = {};
//       let products = [];
//       for (let line of lines) {
//         let prd = this.pos.db.getProduct_by_id(line.getProduct().id);

//         if (prd.type != "product") {
//           continue;
//         }

//         if (product_quantity_by_product[prd.id] == undefined) {
//           product_quantity_by_product[prd.id] = 0;
//         }
//         product_quantity_by_product[prd.id] =
//           product_quantity_by_product[prd.id] + line.quantity;
//         if (
//           product_quantity_by_product[prd.id] > prd.qty_available ||
//           prd.qty_available <= 0
//         ) {
//           products.push(prd.display_name);
//         }
//       }

//       if (products.length > 0)
//         return this.env.services.popup.add(ErrorPopup, {
//           title: _t("Validate Product in Warehouse"),
//           body: _t(
//             "The product %s You do not have enough stock in the warehouse",
//             products,
//           ),
//         });
//     }
//     return await super.pay(...arguments);
//   },
//   get_foreign_rounding_applied() {
//     if (this.pos.config.cash_rounding) {
//       const only_cash = this.pos.config.only_round_cash_method;
//       const paymentlines = this.get_paymentlines();
//       const last_line = paymentlines
//         ? paymentlines[paymentlines.length - 1]
//         : false;
//       const last_line_is_cash = last_line
//         ? last_line.payment_method.is_cash_count == true
//         : false;
//       if (!only_cash || (only_cash && last_line_is_cash)) {
//         var rounding_method = this.pos.cash_rounding[0].rounding_method;
//         var remaining =
//           this.get_foreign_total_with_tax() - this.get_total_paid();
//         var sign = this.get_foreign_total_with_tax() > 0 ? 1.0 : -1.0;
//         if (
//           ((this.get_foreign_total_with_tax() < 0 && remaining > 0) ||
//             (this.get_foreign_total_with_tax() > 0 && remaining < 0)) &&
//           rounding_method !== "HALF-UP"
//         ) {
//           rounding_method = rounding_method === "UP" ? "DOWN" : "UP";
//         }

//         remaining *= sign;
//         var total = round_pr(remaining, this.pos.cash_rounding[0].rounding);
//         var rounding_applied = total - remaining;

//         // because floor and ceil doesn't include decimals in calculation, we reuse the value of the half-up and adapt it.
//         if (
//           floatIsZero(
//             rounding_applied,
//             this.pos.foreign_currency.decimal_places,
//           )
//         ) {
//           // https://xkcd.com/217/
//           return 0;
//         } else if (
//           Math.abs(this.get_foreign_total_with_tax()) <
//           this.pos.cash_rounding[0].rounding
//         ) {
//           return 0;
//         } else if (
//           rounding_method === "UP" &&
//           rounding_applied < 0 &&
//           remaining > 0
//         ) {
//           rounding_applied += this.pos.cash_rounding[0].rounding;
//         } else if (
//           rounding_method === "UP" &&
//           rounding_applied > 0 &&
//           remaining < 0
//         ) {
//           rounding_applied -= this.pos.cash_rounding[0].rounding;
//         } else if (
//           rounding_method === "DOWN" &&
//           rounding_applied > 0 &&
//           remaining > 0
//         ) {
//           rounding_applied -= this.pos.cash_rounding[0].rounding;
//         } else if (
//           rounding_method === "DOWN" &&
//           rounding_applied < 0 &&
//           remaining < 0
//         ) {
//           rounding_applied += this.pos.cash_rounding[0].rounding;
//         } else if (
//           rounding_method === "HALF-UP" &&
//           rounding_applied === this.pos.cash_rounding[0].rounding / -2
//         ) {
//           rounding_applied += this.pos.cash_rounding[0].rounding;
//         }
//         return sign * rounding_applied;
//       } else {
//         return 0;
//       }
//     }
//     return 0;
//   },

//   get_foreign_total_paid() {
//     return round_pr(
//       this.paymentlines.reduce(function (sum, paymentLine) {
//         if (paymentLine.is_done()) {
//           sum += paymentLine.get_foreign_amount();
//         }
//         return sum;
//       }, 0),
//       this.pos.foreign_currency.rounding,
//     );
//   },
//   get_foreign_change(paymentline) {
//     if (!paymentline) {
//       var change =
//         this.get_foreign_total_paid() -
//         this.get_foreign_total_with_tax() -
//         this.get_rounding_applied();
//     } else {
//       change = -this.get_foreign_total_with_tax();
//       var lines = this.paymentlines;
//       for (var i = 0; i < lines.length; i++) {
//         change += lines[i].get_foreign_amount();
//         if (lines[i] === paymentline) {
//           break;
//         }
//       }
//     }
//     return round_pr(Math.max(0, change), this.pos.foreign_currency.rounding);
//   },
//   get_foreign_due(paymentline) {
//     if (!paymentline) {
//       var due =
//         this.get_foreign_total_with_tax() -
//         this.get_foreign_total_paid() +
//         this.get_rounding_applied();
//     } else {
//       due = this.get_foreign_total_with_tax();
//       var lines = this.paymentlines;
//       for (var i = 0; i < lines.length; i++) {
//         if (lines[i] === paymentline) {
//           break;
//         } else {
//           due -= lines[i].get_foreign_amount();
//         }
//       }
//     }
//     return round_pr(due, this.pos.foreign_currency.rounding);
//   },

  get_qty_products() {
    let qty = 0;
    const lines  = this.get_orderlines();
    for (let i = 0; i < lines.length; i++) {
      qty += lines[i].qty;
    }
    return qty;
  },
});

// -----------------------------------------------------------------------------
// Fix: Odoo 19 core bug — _computeAllPrices lines.map() sin guard.
//
// PosOrderAccounting.setup() llama _doRecomputeAllPrices() → _computeAllPrices()
// donde hace lines.map(...) sin verificar que lines no sea undefined/null.
// El Base.setup() propio del mixin setea this.lines = vals.lines (que el server
// puede mandar como null para órdenes huérfanas). El guard en PosOrder.setup()
// corre demasiado tarde (después de super.setup), cuando el crash ya ocurrió.
//
// Patch directo al método que crashea, en lugar del setup.
// -----------------------------------------------------------------------------
patch(PosOrderAccounting.prototype, {
    _computeAllPrices(opts = {}) {
        try {
            return super._computeAllPrices(opts);
        } catch (_e) {
            // Odoo 19 core bug: lines.map() sin guard cuando lines es
            // undefined/null. Forzamos array vacío y reintentamos.
            const safeOpts = { ...opts, lines: [] };
            return super._computeAllPrices(safeOpts);
        }
    },
});
