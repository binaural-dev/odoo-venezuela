/** @odoo-module **/

import { contextualUtilsService } from "@point_of_sale/app/services/contextual_utils_service";
import { formatMonetary } from "@web/views/fields/formatters";
import { patch } from "@web/core/utils/patch";

patch(contextualUtilsService, {

  //@override
  start(env, { pos }) {
    const res = super.start(...arguments);
    const foreign_currency = pos.config.foreign_currency_id;
    /**
     * Formatea un valor numérico a la moneda foránea del POS.
     */
    const formatForeignCurrency = (value, hasSymbol = true) => {
      const amount = (typeof value === "string" ? (value) : value) || 0;
      return formatMonetary(amount, {
        currencyId: foreign_currency?.id,
        noSymbol: !hasSymbol,
      });
    };

    const formatStrForeignCurrency = (valueStr, hasSymbol = true) => {
      return formatForeignCurrency(valueStr, hasSymbol);
    };

    const getDecimalPrecisionModel = () => {
      return pos.models?.["decimal.precision"] || null;
    };

    const getDecimalPrecision = (precisionName = "Tasa", fallback = 2) => {
      const decimalPrecisionModel = getDecimalPrecisionModel();
      const recordsContainer = decimalPrecisionModel?.records;
      const records = recordsContainer?.values
        ? Array.from(recordsContainer.values())
        : Array.isArray(recordsContainer)
          ? recordsContainer
          : [];

      const precisionRecord = records.find((record) => record?.name === precisionName);
      const digits = precisionRecord?.digits;

      if (Number.isFinite(digits)) {
        return Math.trunc(digits);
      }

      return fallback;
    };

    // Inyectamos en env.utils para que sea accesible en OWL (vistas y componentes)
    // En Odoo 19 env es compartido, por lo que llegará a todos lados.
    env.utils = env.utils || {};
    Object.assign(env.utils, {
      formatForeignCurrency,
      formatStrForeignCurrency,
      getDecimalPrecisionModel,
        getDecimalPrecision: getDecimalPrecision,
    });

    return res;
  }

})
