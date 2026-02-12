/** @odoo-module **/

import { MonetaryField } from "@web/views/fields/monetary/monetary_field";
import { patch } from "@web/core/utils/patch";
import { formatMonetary } from "@web/views/fields/formatters";
import { session } from "@web/session";

patch(MonetaryField, {
    props: {
        ...MonetaryField.props,
        precision: { type: String, optional: true },
    },
});

patch(MonetaryField.prototype, {
    /**
     * Sobrescribimos formattedValue para inyectar la precisión decimal
     */
    get formattedValue() {
        if (this.props.inputType === "number" && !this.props.readonly && this.value) {
            return this.value;
        }

        // Lógica para obtener los dígitos desde Decimal Precision
        let digits = this.currencyDigits;
        if (this.props.precision) {
            const dp = session.decimal_precision;
            if (dp && dp[this.props.precision]) {
                // dp[this.props.precision] devuelve el número (ej: 4)
                digits = [16, dp[this.props.precision]];
            }
        }

        return formatMonetary(this.value, {
            digits: digits,
            currencyId: this.currencyId,
            noSymbol: !this.props.readonly || this.props.hideSymbol,
        });
    }
});

// Modificamos el objeto de registro para capturar la opción del XML
import { monetaryField } from "@web/views/fields/monetary/monetary_field";

const originalExtractProps = monetaryField.extractProps;
monetaryField.extractProps = (fieldInfo) => {
    const props = originalExtractProps(fieldInfo);
    // Extraemos 'precision' de las opciones del XML
    props.precision = fieldInfo.options.precision;
    return props;
};