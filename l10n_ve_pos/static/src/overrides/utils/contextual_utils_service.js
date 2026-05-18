/** @odoo-module **/

import { contextualUtilsService } from "@point_of_sale/app/services/contextual_utils_service";
import { formatMonetary } from "@web/views/fields/formatters";
import { patch } from "@web/core/utils/patch";

patch(contextualUtilsService, {

  //@override
  start(env, { pos }) {
    const res = super.start(...arguments);
    const foreign_currency = pos.config.foreign_currency_id;

    const normalizeNumericValue = (value) => {
      if (typeof value === "number") {
        return Number.isFinite(value) ? value : 0;
      }

      if (typeof value === "string") {
        const trimmedValue = value.trim();
        if (!trimmedValue) {
          return 0;
        }

        const normalizedValue = trimmedValue.replace(/\./g, "").replace(",", ".");
        const parsedValue = Number(normalizedValue);
        return Number.isFinite(parsedValue) ? parsedValue : 0;
      }

      return 0;
    };

    const truncateDecimals = (value, digits = 2) => {
      const numericValue = normalizeNumericValue(value);
      const factor = 10 ** digits;

      if (!Number.isFinite(numericValue)) {
        return 0;
      }

      return numericValue < 0
        ? Math.ceil(numericValue * factor) / factor
        : Math.floor(numericValue * factor) / factor;
    };

    const formatTruncatedAmount = (value, digits = 2) => {
      const truncatedValue = truncateDecimals(value, digits);
      const sign = truncatedValue < 0 ? "-" : "";
      const absoluteValue = Math.abs(truncatedValue);
      const [integerPart, decimalPart = ""] = absoluteValue.toFixed(digits).split(".");
      const groupedIntegerPart = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, ".");

      return `${sign}${groupedIntegerPart},${decimalPart}`;
    };

    /**
     * Formatea sin redondear: trunca a 2 decimales y conserva el símbolo de la moneda foránea.
     */
    const formatForeignCurrency = (value, hasSymbol = true) => {
      const formattedAmount = formatTruncatedAmount(value, 2);
      const currencySymbol = foreign_currency?.symbol || "";

      if (!hasSymbol || !currencySymbol) {
        return formattedAmount;
      }

      return `${currencySymbol} ${formattedAmount}`;
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
