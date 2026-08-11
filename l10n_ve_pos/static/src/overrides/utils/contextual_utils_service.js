/** @odoo-module **/

import { contextualUtilsService } from "@point_of_sale/app/utils/contextual_utils_service";
import { formatMonetary } from "@web/views/fields/formatters";
import { patch } from "@web/core/utils/patch";
import { nbsp } from "@web/core/utils/strings";

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
    const formatRate = (value) => {
      const decimals = pos.dp["Tasa"];
      value = Number(value).toFixed(decimals).replace(".", ",");
      const formatted = [foreign_currency.symbol, value];
      if (foreign_currency.position === "after") {
        formatted.reverse();
      }
      return formatted.join(nbsp);

    };
    env.utils = {
      ...env.utils,
      formatForeignCurrency,
      formatStrForeignCurrency,
      formatRate,
    };
  }

})
