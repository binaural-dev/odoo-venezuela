/** @odoo-module */

import { Payment } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";
import {
	formatFloat,
	roundDecimals as round_di,
	roundPrecision as round_pr,
	floatIsZero,
} from "@web/core/utils/numbers";

// New orders are now associated with the current table, if any.
patch(Payment.prototype, {
	setup(_defaultObj, options) {
		super.setup(...arguments);
	},
	init_from_JSON(json) {
		super.init_from_JSON(...arguments);
		this.foreign_amount = json.foreign_amount || this.foreign_amount;
		this.foreign_rate = json.foreign_rate || this.foreign_rate;
	},
	export_as_JSON() {
		let res = super.export_as_JSON(...arguments);
		res["foreign_amount"] = this.foreign_amount;
		res["foreign_rate"] = this.order.get_conversion_rate();
		return res;
	},
	get_foreign_amount() {
		return this.foreign_amount || 0;
	},
	set_amount(amount, only = false) {
		let is_due = amount == this.order.get_due();
		let res = super.set_amount(...arguments);
		if (!only) {
			if (is_due) {
				this.set_foreign_amount(this.order.get_foreign_due(), true);
				return res;
			}
			this.foreign_amount = amount * this.pos.foreign_currency.rate; 
		}
		return res;
	},
	set_foreign_amount(amount, only = false) {
		this.foreign_amount = amount;
		if (!only) {
			if (this.pos.currency.name == "VEF") {
				if (this.payment_method.is_foreign_currency) {
					this.amount=this.foreign_amount / this.pos.foreign_currency.rate
					return;
				}
				this.amount = amount / this.order.get_conversion_rate();
			}
			if (this.pos.currency.name == "USD") {
				if (this.payment_method.is_foreign_currency) {
					this.set_amount(
						this.foreign_amount * this.pos.foreign_currency.inverse_rate,
					);
					return;
				}
				this.set_amount(
					this.foreign_amount * this.order.init_conversion_rate,
					true,
				);
			}
		}
	},
});
