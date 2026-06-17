/** @odoo-module **/

import { MonetaryField } from "@web/views/fields/monetary/monetary_field";
import { monetaryField } from "@web/views/fields/monetary/monetary_field";
import { patch } from "@web/core/utils/patch";
import { formatMonetary } from "@web/views/fields/formatters";
import { onWillStart } from "@odoo/owl";
import { getCurrency } from "@web/core/currency";

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
    setup() {
        super.setup();
        // Creamos un estado para guardar los dígitos encontrados
        this.customDigits = null;

        onWillStart(async () => {
            if (this.props.precision) {
                // Buscamos directamente en el modelo decimal.precision
                const dp = await this.env.services.orm.searchRead(
                    "decimal.precision",
                    [["name", "=", this.props.precision]],
                    ["digits"]
                );
                
                if (dp.length > 0) {
                    this.customDigits = [16, dp[0].digits];
                }
            }
        });
    },
    
    get currencyDigits() {
        if (this.props.precision) {
            
            if (this.customDigits) {
                return this.customDigits;
            }
            // Si no, fallback al original
            try {
                return super.currencyDigits;
            } catch (e) {
                return this.currency ? this.currency.digits : [16, 2];
            }
        }
        if (this.props.useFieldDigits) {
            return this.props.record.fields[this.props.name].digits;
        }
        if (!this.currency) {
            return null;
        }
        return getCurrency(this.currencyId).digits;
    },

    get formattedValue() {
        if (this.props.inputType === "number" && this.value) {
            return this.value;
        }
        let digitos = this.currencyDigits
        return formatMonetary(this.value, {
            digits: digitos,
            currencyId: this.currencyId,
            noSymbol: !this.props.readonly || this.props.hideSymbol,
        });
    }
});
const originalExtractProps = monetaryField.extractProps;
monetaryField.extractProps = (fieldInfo) => {
    const props = originalExtractProps(fieldInfo);
    
    
    if (fieldInfo.options && fieldInfo.options.precision) {
        props.precision = fieldInfo.options.precision;
        
    }
    return props;
};