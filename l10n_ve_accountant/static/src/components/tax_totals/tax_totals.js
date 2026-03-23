/** @odoo-module **/

import { formatMonetary } from "@web/views/fields/formatters";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { registry } from "@web/core/registry";

import { TaxTotalsComponent } from "@account/components/tax_totals/tax_totals";
import { patch } from "@web/core/utils/patch";
const { Component, onPatched, onWillUpdateProps, useRef, toRaw, useState } =
  owl;

patch(TaxTotalsComponent.prototype, {
  formatData(props) {
    let totals = JSON.parse(
      JSON.stringify(toRaw(props.record.data[this.props.name])),
    );
    if (!totals) {
      return;
    }
    totals.formatted_total_amount_currency_ves =
      totals.formatted_total_amount_currency_ves;
    const foreignCurrencyFmtOpts = {
      currencyId: props.record.data.foreign_currency_id,
    };
    const currencyFmtOpts = {
      currencyId:
        props.record.data.currency_id && props.record.data.currency_id[0],
    };
    if (totals.subtotals && Array.isArray(totals.subtotals)) {
      for (let subtotal of totals.subtotals) {
        subtotal.formatted_base_amount_foreign_currency = formatMonetary(
          subtotal.base_amount_foreign_currency,
          foreignCurrencyFmtOpts,
        );
        subtotal.formatted_base_amount_currency = formatMonetary(
          subtotal.base_amount_currency,
          currencyFmtOpts,
        );
        subtotal.formatted_base_amount_currency_ves =
          totals.formatted_base_amount_currency_ves;

        if (subtotal.tax_groups && Array.isArray(subtotal.tax_groups)) {
          for (let taxGroup of subtotal.tax_groups) {
            taxGroup.formatted_tax_amount_foreign_currency = formatMonetary(
              taxGroup.tax_amount_foreign_currency,
              foreignCurrencyFmtOpts,
            );
            taxGroup.formatted_base_amount_foreign_currency = formatMonetary(
              taxGroup.base_amount_foreign_currency,
              foreignCurrencyFmtOpts,
            );

            taxGroup.formatted_tax_amount_currency = formatMonetary(
              taxGroup.tax_amount_currency,
              currencyFmtOpts,
            );

            taxGroup.formatted_base_amount_currency = formatMonetary(
              taxGroup.base_amount_currency,
              currencyFmtOpts,
            );
            // Solo VEES
            taxGroup.formatted_tax_amount_currency_ves =
              taxGroup.formatted_tax_amount_currency_ves;
          }
        }
      }
    }
    totals.formatted_total_amount_foreign_currency = formatMonetary(
      totals.total_amount_foreign_currency,
      foreignCurrencyFmtOpts,
    );
    totals.formatted_total_amount_currency = formatMonetary(
      totals.total_amount_currency,
      currencyFmtOpts,
    );
    this.totals = totals;
    return totals;
  },

  formatMonetaryForeign(value) {
    const currency = this.props.record.data.foreign_currency_id;
    let res = formatMonetary(value, { currencyId: currency.id });
    return res;
  },
});

Object.defineProperty(TaxTotalsComponent.prototype, "readonly", {
  get() {
    return true;
  },
  configurable: true,
});

export class TaxTotalsComponents extends TaxTotalsComponent {
  get readonly() {
    return true;
  }
}
TaxTotalsComponents.template = "l10n_ve_accountant.TaxForeignTotalsField";
TaxTotalsComponents.template = "l10n_ve_accountant.TaxVesTotalsField";
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

if (!fieldsRegistry.contains("account-tax-ves-totals-field")) {
  fieldsRegistry.add("account-tax-ves-totals-field", taxTotalsComponent);
}
