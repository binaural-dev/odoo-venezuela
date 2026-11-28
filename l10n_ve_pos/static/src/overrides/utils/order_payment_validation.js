import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { ask } from "@point_of_sale/app/utils/make_awaitable_dialog";

patch(OrderPaymentValidation.prototype, {
    async _askForCustomerIfRequired() {
        if ((await super._askForCustomerIfRequired(...arguments)) === false) {
            return false;
        }
        const splitPayments = this.order.payment_ids.filter(
            (payment) => payment.payment_method_id.split_transactions
        );
        if (splitPayments.length && !this.order.getPartner()) {
            const paymentMethod = splitPayments[0].payment_method_id;
            const confirmed = await ask(this.pos.dialog, {
                title: _t("Customer Required"),
                body: _t("Customer is required for %s payment method.", paymentMethod.name),
            });
            if (confirmed) {
                await this.pos.selectPartner();
            }
            return false;
        }
    },
});
