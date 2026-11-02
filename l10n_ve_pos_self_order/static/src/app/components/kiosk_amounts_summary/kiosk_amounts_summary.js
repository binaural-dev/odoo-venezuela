import { Component } from "@odoo/owl";
import { useSelfOrder } from "@pos_self_order/app/services/self_order_service";
import { formatCurrency } from "@point_of_sale/app/models/utils/currency";
import { CartPage } from "@pos_self_order/app/pages/cart_page/cart_page";
import { ProductListPage } from "@pos_self_order/app/pages/product_list_page/product_list_page";

/**
 * Amounts summary of the Kiosk order (task 80343, points 7+8): taxable base,
 * per-rate tax breakdown, local total and — when the company has a foreign
 * currency configured — the foreign-currency total.
 *
 * Shown BEFORE the customer presses "Pay" (cart page, or the in-place summary
 * of the scan/search-only mode), not on the payment page: with a single
 * payment method — the recommended Kiosk setup, one Megasoft method whose VPOS
 * lets the customer pick card/pago móvil/etc. — the core auto-selects it and
 * the terminal opens right away, so nothing on the payment page is readable.
 *
 * The foreign amounts come from l10n_ve_pos's PosOrder helpers
 * (get_foreign_total_with_tax & co., static/src/overrides/models/pos_order.js),
 * which this module's manifest loads into the Kiosk bundle: same conversion,
 * rounding and frozen/refund-rate rules as the cashier, nothing re-implemented
 * here. Local amounts come from the core `order.prices.taxDetails`.
 */
export class KioskAmountsSummary extends Component {
    static template = "l10n_ve_pos_self_order.KioskAmountsSummary";
    static props = {};

    setup() {
        this.selfOrder = useSelfOrder();
    }

    get order() {
        return this.selfOrder.currentOrder;
    }

    get taxDetails() {
        return this.order?.prices?.taxDetails;
    }

    get baseAmount() {
        return this.taxDetails?.base_amount_currency ?? 0;
    }

    get localTotal() {
        return this.taxDetails?.total_amount_currency ?? 0;
    }

    // One row per tax group actually present on the order (e.g. "IVA 16%",
    // "IVA 8%", "Exento" — whatever account.tax.group the sale's taxes use).
    get taxGroups() {
        const subtotals = this.taxDetails?.subtotals || [];
        return subtotals.flatMap((subtotal) => subtotal.tax_groups || []);
    }

    formatTaxGroupLabel(taxGroup) {
        return taxGroup.group_label || taxGroup.group_name;
    }

    formatAmount(amount) {
        return this.selfOrder.formatMonetary(amount || 0);
    }

    get foreignCurrency() {
        return this.order?._getForeignCurrencyRecord?.();
    }

    get showForeignTotal() {
        return Boolean(this.foreignCurrency && this.order?.get_foreign_multiplier?.());
    }

    formatForeignTotal() {
        const currency = this.foreignCurrency;
        if (!currency) {
            return "";
        }
        return formatCurrency(this.order.get_foreign_total_with_tax(), currency);
    }
}

// Registered here (not in each page's patch) so both hosts of the summary
// share one declaration: the cart page, and the in-place summary of the
// scan/search-only mode (overrides/product_list_page.xml).
CartPage.components = { ...CartPage.components, KioskAmountsSummary };
ProductListPage.components = { ...ProductListPage.components, KioskAmountsSummary };
