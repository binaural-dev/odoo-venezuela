/** @odoo-module **/

import { MonetaryField } from "@web/views/fields/monetary/monetary_field";
import { monetaryField } from "@web/views/fields/monetary/monetary_field";
import { patch } from "@web/core/utils/patch";
import { formatMonetary } from "@web/views/fields/formatters";
import { session } from "@web/session";

// 1. Aseguramos que el componente acepte la prop 'precision'
patch(MonetaryField, {
    props: {
        ...MonetaryField.props,
        precision: { type: String, optional: true },
    },
});

patch(MonetaryField.prototype, {
    /**
     * Parcheamos el getter de dígitos, que es lo que formatMonetary
     * y el hook de input usan internamente.
     */
    get currencyDigits() {
        if (this.props.precision) {
            const dp = session.decimal_precision;
            if (dp && dp[this.props.precision] !== undefined) {
                return [16, dp[this.props.precision]];
            }
        }
        // Si no hay prop precision, usamos la lógica original (super)
        return super.currencyDigits;
    },

    get formattedValue() {
        if (this.props.inputType === "number" && this.value) {
            return this.value;
        }

        // Ahora simplemente llamamos a this.currencyDigits, que ya está parcheado
        return formatMonetary(this.value, {
            digits: this.currencyDigits,
            currencyId: this.currencyId,
            noSymbol: !this.props.readonly || this.props.hideSymbol,
        });
    }
});

// 2. Extraer la prop desde el registro del campo (Field Registry)
const originalExtractProps = monetaryField.extractProps;
monetaryField.extractProps = (fieldInfo) => {
    const props = originalExtractProps(fieldInfo);
    // IMPORTANTE: Capturar la opción desde el XML
    if (fieldInfo.options && fieldInfo.options.precision) {
        props.precision = fieldInfo.options.precision;
    }
    return props;
};