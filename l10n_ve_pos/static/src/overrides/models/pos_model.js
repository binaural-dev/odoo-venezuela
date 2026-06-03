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

    async pushOrders(order, opts) {
        let res = await super.pushOrders(order, opts);
        await this.update_products(order)
        return res
    },

    async pushSingleOrder(order, opts) {
        let res = await super.pushSingleOrder(...arguments);
        await this.update_products(order)
        return res
    },

    format_foreign_currency(amount) {
        if (!this.foreign_currency) return amount;
        const formattedAmount = this.env.utils.formatFloat(amount, { digits: [69, 2] });
        return this.foreign_currency.position === "after"
            ? `${formattedAmount} ${this.foreign_currency.symbol || ""}`
            : `${this.foreign_currency.symbol || ""} ${formattedAmount}`;
    },

    convert_amount_to_foreign(amount, rate = null) {
        const numericAmount = Number(amount || 0);
        const resolvedRate = Number(
            rate ?? this.config?.foreign_rate ?? this.foreign_currency?.rate ?? 1
        );
        return numericAmount * (Number.isFinite(resolvedRate) ? resolvedRate : 1);
    },

    async convert_amount_to_foreign_server(amount) {
        const numericAmount = Number(amount || 0);
        console.log('Converting amount to foreign currency on server:', numericAmount);
        return this.env.services.orm.call("pos.order.line", "_convert_amount", [], {
            context: { amount: numericAmount }
        });

    }
})
