import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
/** @odoo-module */
/**
 * Inherit native Odoo 19 POS store.
 */
//esto es un modelo de servicios
patch(PosStore.prototype, {
    async setup() {
        await super.setup(...arguments);
        
    },
    apply_igtf(paymentMethodId) {
        return this.env.services.orm.searchRead("pos.payment.method", [["id", "=", Number(paymentMethodId)]], ["id", "name", "apply_igtf"]).then((rows) => {
            return rows[0]?.apply_igtf || false;
        });
    },
});
