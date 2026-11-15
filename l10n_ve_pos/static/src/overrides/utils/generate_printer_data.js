import { GeneratePrinterData } from "@point_of_sale/app/utils/printer/generate_printer_data";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { formatMonetary } from "@web/views/fields/formatters";

patch(GeneratePrinterData.prototype, {
  get commonExtraData() {
    const data = super.commonExtraData;
    if (!this.company?.country_id?.vat_label) {
      data.vat_label = _t("Tax ID");
    }
    return data;
  },

  formatForeignAmount(amount) {
    const foreignCurrency = this.order.config.foreign_currency_id;
    return foreignCurrency ? formatMonetary(amount, { currencyId: foreignCurrency.id }) : false;
  },

  generateTaxData() {
    const data = super.generateTaxData(...arguments);
    const foreignTotal = this.formatForeignAmount(this.order.get_foreign_total_with_tax());
    if (foreignTotal) {
      data.foreign_total_amount = foreignTotal;
    }
    return data;
  },

  generateLineData() {
    const lines = super.generateLineData(...arguments);
    return this.order.lines.map((line, index) => ({
      ...lines[index],
      aliquot_type: line.get_aliquot_type(),
      foreign_price_subtotal_incl: this.formatForeignAmount(line.get_foreign_display_price()),
    }));
  },

  generateReceiptData() {
    const data = super.generateReceiptData(...arguments);
    if (!this.order.partner_id?.country_id?.vat_label) {
      data.extra_data.partner_vat_label = _t("Tax ID");
    }
    return data;
  },
});
