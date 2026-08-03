/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ProjectProfitability } from "@project/components/project_right_side_panel/components/project_profitability";
import { formatCurrency } from "@web/core/currency";

patch(ProjectProfitability, {
    props: {
        ...ProjectProfitability.props,
        currencyId: { type: Number, optional: true },
        foreignCurrencyId: { type: Number, optional: true },
    },
});

patch(ProjectProfitability.prototype, {
    formatLocal(value) {
        return formatCurrency(value || 0, this.props.currencyId);
    },
    formatForeign(value) {
        return formatCurrency(value || 0, this.props.foreignCurrencyId);
    }
});
