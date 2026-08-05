/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ProjectProfitabilitySection } from "@sale_project/components/project_right_side_panel/components/project_profitability_section";
import { formatCurrency } from "@web/core/currency";

patch(ProjectProfitabilitySection, {
    props: {
        ...ProjectProfitabilitySection.props,
        currencyId: { type: Number, optional: true },
        foreignCurrencyId: { type: [Number, Boolean], optional: true },
    },
});

patch(ProjectProfitabilitySection.prototype, {
    formatLocal(value) {
        return formatCurrency(value || 0, this.props.currencyId);
    },
    formatForeign(value) {
        return formatCurrency(value || 0, this.props.foreignCurrencyId);
    }
});
