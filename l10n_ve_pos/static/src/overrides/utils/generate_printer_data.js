import { GeneratePrinterData } from "@point_of_sale/app/utils/printer/generate_printer_data";
import { patch } from "@web/core/utils/patch";
import { formatMonetary } from "@web/views/fields/formatters";

patch(GeneratePrinterData.prototype, {
  generateTaxData() {
    const data = super.generateTaxData(...arguments);
    const foreignCurrency = this.order.config.foreign_currency_id;
    if (foreignCurrency) {
      data.foreign_total_amount = formatMonetary(this.order.get_foreign_total_with_tax(), {
        currencyId: foreignCurrency.id,
      });
    }
    return data;
  },
});
