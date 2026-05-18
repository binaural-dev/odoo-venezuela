/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { useService } from "@web/core/utils/hooks";
import { onWillUpdateProps, onWillStart, useState } from "@odoo/owl";


patch(PaymentScreen, {
  props: {
    ...PaymentScreen.props,
    foreignDueTotalWithTaxes: { optional: true },
  },
});

patch(PaymentScreen.prototype, {

    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");
        this._lastReqId = 0;
        this.state = useState({ foreignDueTotalWithTaxes: 0 });

        onWillStart(async () => {
            await this._syncForeignAmountDisplay(this.currentOrder.priceIncl);
        });

        onWillUpdateProps(async (nextProps) => {
            await this._syncForeignAmountDisplay(nextProps.currentOrder.priceIncl);
        });

    },

    get foreignDueTotalWithTaxes() {
        return this.state.foreignDueTotalWithTaxes;
    },

    async _syncForeignAmountDisplay(amount) {
        if (!Number.isFinite(amount)) {
        return 0;
        }
        const reqId = ++this._lastReqId;
        try {
            const converted = await this.orm.call(
                "pos.order",
                "convert_amount",
                [amount],
                { context: { amount } }
            );
            if (reqId === this._lastReqId) {
                return this.state.foreignDueTotalWithTaxes = converted;
            }
            } catch (err) {
                console.log("Error converting total amount:", err);
                if (reqId === this._lastReqId) {
                    const rate = Number(this.pos?.foreing_rate || 1);
                    return this.state.foreignDueTotalWithTaxes = amount * rate;
                }
        }
  },
});