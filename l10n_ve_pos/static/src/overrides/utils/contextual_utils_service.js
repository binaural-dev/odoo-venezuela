/** @odoo-module **/

import { contextualUtilsService } from "@point_of_sale/app/utils/contextual_utils_service";
import { formatMonetary } from "@web/views/fields/formatters";
import { patch } from "@web/core/utils/patch";

patch(contextualUtilsService, {

  //@override
  start(env, { pos, localization }) {
    super.start(...arguments)
    const foreign_currency = pos.foreign_currency;

    const formatForeignCurrency = (value, hasSymbol = true) => {
      if (!value) {
        value = 0
      }
      return formatMonetary(value, {
        currencyId: foreign_currency.id,
        noSymbol: !hasSymbol,
      });
    };

    const formatStrForeignCurrency = (valueStr, hasSymbol = true) => {
      return formatCurrency(parseFloat(valueStr), hasSymbol);
    };

    env.utils = {
      ...env.utils,
      formatForeignCurrency,
      formatStrForeignCurrency,
    };
  }

})
