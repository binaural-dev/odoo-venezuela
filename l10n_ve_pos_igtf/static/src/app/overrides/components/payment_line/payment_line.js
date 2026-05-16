/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PaymentScreenPaymentLines } from "@point_of_sale/app/screens/payment_screen/payment_lines/payment_lines";
import { useService } from "@web/core/utils/hooks";
import { onWillUpdateProps, onWillStart } from "@odoo/owl";
patch(PaymentScreenPaymentLines.prototype, {
	setup() {
		super.setup(...arguments);
        this.convertAmountService = useService("convertForeignAmountService");
        onWillStart(async () => {
            await this._calculateIGTFByPaymentLines(this.props.paymentLines || []);
        });

        onWillUpdateProps(async (nextProps) => {
            await this._calculateIGTFByPaymentLines(nextProps.paymentLines || []);
        });
	},

    async _calculateIGTFByPaymentLines(paymentLines) {
        for (const line of paymentLines) {
            const amount = typeof line?.get_amount === "function" ? line.get_amount() : (line?.amount || 0);
            const igtfAmount = amount * 0.03;

            line.igtf_amount = igtfAmount;

            if (this.convertAmountService?._syncForeignAmountDisplay) {
                line.igtf_amount_converted = await this.convertAmountService._syncForeignAmountDisplay(igtfAmount);
            }
        }
    },
});

