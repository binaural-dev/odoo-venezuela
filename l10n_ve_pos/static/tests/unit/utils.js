import { comp, EQ, GT, LT } from "@point_of_sale/app/utils/numbers";
import { roundPrecision } from "@web/core/utils/numbers";

// Moneda de prueba con la misma interfaz que ResCurrency/AbstractNumbers,
// delegando en el comp/roundPrecision nativos para que los umbrales bajo
// test sean exactamente los del core.
export function makeCurrency(rounding = 0.01) {
    return {
        rounding,
        round(a) {
            return roundPrecision(a, rounding);
        },
        comp(a, b) {
            return comp(a, b, { precision: rounding });
        },
        isZero(a) {
            return this.comp(a, 0) === EQ;
        },
        isPositive(a) {
            return this.comp(a, 0) === GT;
        },
        isNegative(a) {
            return this.comp(a, 0) === LT;
        },
    };
}

// Moneda "sin resolver": solo rounding, sin métodos AbstractNumbers.
// Fuerza la rama de respaldo manual de los parches.
export function makeBareCurrency(rounding = 0.01) {
    return { rounding };
}

export const RATE = 36.5;

// Stub mínimo de pos.order con los helpers de conversión que usan los
// parches de l10n_ve_pos. Conversión main→foreign y foreign→main con
// redondeo de la moneda destino, igual que pos_order._convert.
export function makeOrderStub({ totalDue = 0, payments = [], fc = makeCurrency(), rate = RATE } = {}) {
    return {
        totalDue,
        payment_ids: payments,
        get_foreign_currency: () => fc,
        _resolveCurrencyRecord: (c) => c,
        _getForeignCurrencyRecord: () => fc,
        localToForeign: (v) => roundPrecision(v / rate, 0.01),
        foreignToLocal: (v) => roundPrecision(v * rate, 0.01),
    };
}
