// /** @odoo-module **/

import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";
import { floatIsZero } from "@web/core/utils/numbers";

patch(PosStore.prototype, {
    //@override

    async _processData(loadedData) {
        await super._processData(loadedData);
        this.currency = loadedData["res.currency"][0];
        this.foreign_currency = loadedData["res.currency"][1];
        this.cities = loadedData["res.country.city"];
        this.prefix_vats = loadedData["prefix_vats"];
    },

    async push_orders(order, opts) {
        let res = await super.push_orders(order, opts);
        await this.update_products(order)
        return res
    },

    async push_single_order(order, opts) {
        let res = await super.push_single_order(...arguments);
        await this.update_products(order)
        return res
    },

    format_foreign_currency(amount) {
        if (!this.foreign_currency) return amount;
        const formattedAmount = this.env.utils.formatFloat(amount, { digits: [69, 2] });
        return this.foreign_currency.position === "after"
            ? `${formattedAmount} ${this.foreign_currency.symbol || ""}`
            : `${this.foreign_currency.symbol || ""} ${formattedAmount}`;
    }
})
