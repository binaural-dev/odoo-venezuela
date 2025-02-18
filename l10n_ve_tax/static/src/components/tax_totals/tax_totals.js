/** @odoo-module **/

import { formatFloat, formatMonetary } from "@web/views/fields/formatters";
import { parseFloat } from "@web/views/fields/parsers";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { registry } from "@web/core/registry";

import { TaxTotalsComponent } from "@account/components/tax_totals/tax_totals";

const { Component, onPatched, onWillUpdateProps, useRef, toRaw, useState } = owl;


export class TaxTotalsComponents extends TaxTotalsComponent {
  get currencyId() {
    return this.props.record.data.foreign_currency_id;
  }

  formatData(props) {
    let totals = JSON.parse(JSON.stringify(toRaw(props.record.data[this.props.name])));
    if (!totals) {
      return;
    }
    const currencyFmtOpts = { currencyId: props.record.data.currency_id && props.record.data.currency_id[0] };

    let amount_untaxed = totals.amount_untaxed;
    let amount_tax = 0;
    let subtotals = [];
    for (let subtotal_title of totals.subtotals_order) {
      let amount_total = amount_untaxed + amount_tax;
      subtotals.push({
        'name': subtotal_title,
        'amount': amount_total,
        'formatted_amount': formatMonetary(amount_total, currencyFmtOpts),
      });
      let group = totals.groups_by_subtotal[subtotal_title];
      for (let i in group) {
        amount_tax = amount_tax + group[i].tax_group_amount;
      }
    }
    totals.subtotals = subtotals;
    let rounding_amount = totals.display_rounding && totals.rounding_amount || 0;
    let amount_total = amount_untaxed + amount_tax + rounding_amount;
    totals.amount_total = amount_total;
    totals.formatted_amount_total = formatMonetary(amount_total, currencyFmtOpts);
    for (let group_name of Object.keys(totals.groups_by_subtotal)) {
      let group = totals.groups_by_subtotal[group_name];
      for (let key in group) {
        group[key].formatted_tax_group_amount = formatMonetary(group[key].tax_group_amount, currencyFmtOpts);
        group[key].formatted_tax_group_base_amount = formatMonetary(group[key].tax_group_base_amount, currencyFmtOpts);
      }
    }
    this.totals = totals;
  }
}
TaxTotalsComponents.template = "l10n_ve_tax.TaxForeignTotalsField";
TaxTotalsComponents.props = {
  ...standardFieldProps,
};

export const taxTotalsComponent = {
  component: TaxTotalsComponents,
};

registry.category("fields").add("account-tax-foreign-totals-field", taxTotalsComponent);
