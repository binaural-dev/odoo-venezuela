import { patch } from "@web/core/utils/patch";
import { PaymentPage } from "@pos_self_order/app/pages/payment_page/payment_page";
import { formatCurrency } from "@point_of_sale/app/models/utils/currency";

/**
 * Amounts summary on the Kiosk's payment screen (task 80343, points 7+8):
 * taxable base, per-rate tax breakdown, local total and — when the company
 * has a foreign currency configured — the foreign-currency total.
 *
 * The foreign amounts come from l10n_ve_pos's PosOrder helpers
 * (get_foreign_total_with_tax & co., static/src/overrides/models/pos_order.js),
 * which this module's manifest loads into the Kiosk bundle: same conversion,
 * rounding and frozen/refund-rate rules as the cashier, nothing re-implemented
 * here. Local amounts come from the core `order.prices.taxDetails`.
 *
 * COMPATIBILITY: binaural_megasoft_self_order also patches PaymentPage (JS
 * only, no template override) to run the Megasoft VPOS flow. Both patches
 * add independent, non-overlapping members to the same prototype.
 */
patch(PaymentPage.prototype, {
    get l10nVeOrder() {
        return this.selfOrder.currentOrder;
    },

    get l10nVeTaxDetails() {
        return this.l10nVeOrder?.prices?.taxDetails;
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

    get l10nVeForeignCurrency() {
        return this.l10nVeOrder?._getForeignCurrencyRecord?.();
    },

    get l10nVeShowForeignTotal() {
        return Boolean(
            this.l10nVeForeignCurrency && this.l10nVeOrder?.get_foreign_multiplier?.()
        );
    },

    formatL10nVeForeignTotal() {
        const currency = this.l10nVeForeignCurrency;
        if (!currency) {
            return "";
        }
        return formatCurrency(this.l10nVeOrder.get_foreign_total_with_tax(), currency);
    },
});
