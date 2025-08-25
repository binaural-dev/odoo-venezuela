/** @odoo-module **/

import { formatFloat, formatMonetary } from "@web/views/fields/formatters";
import { parseFloat } from "@web/views/fields/parsers";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { registry } from "@web/core/registry";

import { TaxTotalsComponent } from "@account/components/tax_totals/tax_totals";
import { patch } from "@web/core/utils/patch";
const { Component, onPatched, onWillUpdateProps, useRef, toRaw, useState } = owl;

patch(TaxTotalsComponent.prototype, {
  formatData(props) {
    let totals = JSON.parse(JSON.stringify(toRaw(props.record.data[this.props.name])));
    if (!totals) {
      return;
    }
    const foreignCurrencyFmtOpts = { currencyId: props.record.data.foreign_currency_id && props.record.data.foreign_currency_id[0] };
    const currencyFmtOpts = { currencyId: props.record.data.currency_id && props.record.data.currency_id[0] };
    if (totals.subtotals && Array.isArray(totals.subtotals)) {
      for (let subtotal of totals.subtotals) {
        subtotal.formatted_base_amount_foreign_currency = formatMonetary(subtotal.base_amount_foreign_currency, foreignCurrencyFmtOpts);
        subtotal.formatted_base_amount_currency = formatMonetary(subtotal.base_amount_currency, currencyFmtOpts);
        if (subtotal.tax_groups && Array.isArray(subtotal.tax_groups)) {
          for (let taxGroup of subtotal.tax_groups) {
            taxGroup.formatted_tax_amount_foreign_currency = formatMonetary(taxGroup.tax_amount_foreign_currency, foreignCurrencyFmtOpts);
            taxGroup.formatted_base_amount_foreign_currency = formatMonetary(taxGroup.base_amount_foreign_currency, foreignCurrencyFmtOpts);
            taxGroup.formatted_tax_amount_currency = formatMonetary(taxGroup.tax_amount_currency, currencyFmtOpts);
            taxGroup.formatted_base_amount_currency = formatMonetary(taxGroup.base_amount_currency, currencyFmtOpts);
          }
        }
      }
    }
    totals.formatted_total_amount_foreign_currency = formatMonetary(totals.total_amount_foreign_currency, foreignCurrencyFmtOpts);
    totals.formatted_total_amount_currency = formatMonetary(totals.total_amount_currency, currencyFmtOpts);
    this.totals = totals;
    return totals;
  }
});
export class TaxTotalsComponents extends TaxTotalsComponent {
}
TaxTotalsComponents.template = "l10n_ve_tax.TaxForeignTotalsField";
TaxTotalsComponents.props = {
  ...standardFieldProps,
};

export const taxTotalsComponent = {
  component: TaxTotalsComponents,
};

const fieldsRegistry = registry.category("fields");

if (!fieldsRegistry.contains("account-tax-foreign-totals-field")) {
    fieldsRegistry.add("account-tax-foreign-totals-field", taxTotalsComponent);
}
