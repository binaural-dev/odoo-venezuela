/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import * as formatters from "@web/views/fields/formatters";
import { MonetaryField, monetaryField } from "@web/views/fields/monetary/monetary_field";
import { session } from "@web/session";

/**
 * Obtiene la configuración de decimales a partir de un nombre 
 * de Precisión Decimal (decimal.precision) desde la sesión.
 */
function getDigitsFromDP(dpName) {
    if (!dpName || !session.dp_stats) {
        return null;
    }
    const precision = session.dp_stats[dpName];
    if (precision !== undefined) {
        return [16, precision]; 
    }
    return null;
}

// 1. EXTENDER LA DEFINICIÓN DE PROPS (Para que Owl las acepte)
if (MonetaryField.props) {
    MonetaryField.props = {
        ...MonetaryField.props,
        precision: { type: String, optional: true },
    };
}

// 2. MODIFICAR EL REGISTRO MANUALMENTE
// No usamos patch(monetaryField) porque no es una clase y falla el this._super.
// Guardamos la función original y la reemplazamos.
const originalExtractProps = monetaryField.extractProps;
monetaryField.extractProps = function ({ attrs }) {
    // Ejecutamos la lógica original
    const props = originalExtractProps.apply(this, arguments);
    
    // Si el usuario puso precision="X" en el XML (attrs), lo pasamos al componente
    if (attrs && attrs.precision) {
        props.precision = attrs.precision;
    }
    return props;
};

// 3. PARCHE AL COMPONENTE (Aquí sí funciona patch porque es una Clase/Prototipo)
patch(MonetaryField.prototype, {
    get formattedValue() {
        // Mantenemos la lógica original de inputs numéricos
        if (this.props.inputType === "number" && !this.props.readonly && this.value) {
            return this.value;
        }

        const formatOptions = {
            digits: this.currencyDigits,
            currencyId: this.currencyId,
            noSymbol: !this.props.readonly || this.props.hideSymbol,
        };

        // Si existe la prop precision (inyectada por el proceso de arriba)
        if (this.props.precision) {
            const dpDigits = getDigitsFromDP(this.props.precision);
            if (dpDigits) {
                formatOptions.digits = dpDigits;
            }
        }

        return formatters.formatMonetary(this.value, formatOptions);
    }
});

export default {};