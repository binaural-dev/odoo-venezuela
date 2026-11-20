import { PosPaymentMethod } from "@point_of_sale/app/models/pos_payment_method";
import { patch } from "@web/core/utils/patch";

patch(PosPaymentMethod.prototype, {
    get availableCurrencies() {
        const currencies = [...this.currency_ids];
        const registerCurrency = this.config.currency_id;
        if (
            ["bank", "cash"].includes(this.type) &&
            currencies.length &&
            !currencies.some((currency) => currency.id === registerCurrency.id)
        ) {
            return currencies;
        }
        return super.availableCurrencies;
    },
});
