import { patch } from "@web/core/utils/patch";
import { PaymentPage } from "@pos_self_order/app/pages/payment_page/payment_page";
import { formatCurrency } from "@point_of_sale/app/models/utils/currency";

/**
 * Amounts summary on the Kiosk's payment screen (ticket 80343, points 7+8):
 * taxable base, per-rate tax breakdown, local total and — when the company
 * has a foreign currency configured — the foreign-currency total.
 *
 * WHY THIS LIVES HERE AND NOT IN l10n_ve_pos: the cashier's foreign-currency
 * helpers (pos.order.get_foreign_total_with_tax, env.utils.formatForeignCurrency,
 * see l10n_ve_pos/static/src/overrides/models/pos_order.js and
 * .../utils/contextual_utils_service.js) live in the
 * `point_of_sale._assets_pos` bundle, which is CASHIER-ONLY: the Kiosk loads
 * a different bundle (`pos_self_order.assets`, see this module's manifest)
 * that never includes those files. So the logic is ported here, using only
 * what the Kiosk bundle actually has:
 *   - `order.prices.taxDetails` (base_amount_currency / subtotals[].tax_groups
 *     / total_amount_currency): this getter comes from PosOrderAccounting,
 *     part of `point_of_sale.base_app` (included by `pos_self_order.assets`),
 *     so it IS available here.
 *   - `pos.config.foreign_rate` / `foreign_inverse_rate`: exposed to the
 *     Kiosk by models/pos_config.py (same fields l10n_ve_pos already computes
 *     and pos.order.recompute_prices — models/pos_order.py — uses server-side
 *     to set foreign_amount_total on the finished order). Multiplying the
 *     local total by `foreign_inverse_rate` here mirrors
 *     pos.config._get_pos_conversion_rate/_convert exactly (main -> foreign),
 *     so the total shown BEFORE paying matches what ends up on the invoice.
 *
 * COMPATIBILITY: binaural_megasoft_self_order also patches PaymentPage (JS
 * only, no template override) to run the Megasoft VPOS flow. Both patches
 * add independent, non-overlapping members to the same prototype.
 */
patch(PaymentPage.prototype, {
    get l10nVeTaxDetails() {
        return this.selfOrder.currentOrder?.prices?.taxDetails;
    },

    get l10nVeBaseAmount() {
        return this.l10nVeTaxDetails?.base_amount_currency ?? 0;
    },

    get l10nVeLocalTotal() {
        return this.l10nVeTaxDetails?.total_amount_currency ?? 0;
    },

    // One row per tax group actually present on the order (e.g. "IVA 16%",
    // "IVA 8%", "Exento" — whatever account.tax.group the sale's taxes use).
    get l10nVeTaxGroups() {
        const subtotals = this.l10nVeTaxDetails?.subtotals || [];
        return subtotals.flatMap((subtotal) => subtotal.tax_groups || []);
    },

    formatL10nVeTaxGroupLabel(taxGroup) {
        return taxGroup.group_label || taxGroup.group_name;
    },

    formatL10nVeAmount(amount) {
        return this.selfOrder.formatMonetary(amount || 0);
    },

    // res.company.foreign_currency_id is already loaded for the Kiosk
    // (l10n_ve_pos's res.company._load_pos_data_fields, reused as-is by the
    // self-data mixin's default — see this.selfOrder.company usage in
    // binaural_megasoft_self_order/static/src/app/pages/payment_page/payment_page.js).
    get l10nVeForeignCurrency() {
        return this.selfOrder.company?.foreign_currency_id;
    },

    get l10nVeForeignRate() {
        return Number(this.selfOrder.config?.foreign_inverse_rate) || 0;
    },

    get l10nVeShowForeignTotal() {
        return Boolean(this.l10nVeForeignCurrency && this.l10nVeForeignRate);
    },

    // Mirrors pos.config._get_pos_conversion_rate/_convert (main -> foreign:
    // multiply by foreign_inverse_rate) and pos.order.recompute_prices
    // (models/pos_order.py), which derives foreign_amount_total from the
    // same local total this getter starts from — so this stays consistent
    // with the invoice once the order is paid.
    get l10nVeForeignTotal() {
        const currency = this.l10nVeForeignCurrency;
        const rate = this.l10nVeForeignRate;
        if (!currency || !rate) {
            return 0;
        }
        const amount = this.l10nVeLocalTotal * rate;
        return typeof currency.round === "function" ? currency.round(amount) : amount;
    },

    formatL10nVeForeignTotal() {
        const currency = this.l10nVeForeignCurrency;
        if (!currency) {
            return "";
        }
        return formatCurrency(this.l10nVeForeignTotal, currency);
    },
});
