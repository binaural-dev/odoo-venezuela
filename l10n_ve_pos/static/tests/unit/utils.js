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
//
// `rate` es Bs por unidad foránea (local = foreign * rate). Pasar
// `refundRate` marca la orden como reembolso (`_hasRefundLines` → true) y
// hace que los helpers refund-aware (`_convertOrderAmount`,
// `_convertForeignOrderAmount`, `get_effective_foreign_multiplier`) usen esa
// tasa CONGELADA de la venta original en vez de la tasa viva `rate`, igual
// que pos_order.js real. Sin `refundRate` (venta normal), delegan en la
// tasa viva.
// `rate` es Bs por unidad foránea (local = foreign * rate).
// `refundRate`  -> reembolso con la TASA AGREGADA de la orden (camino de
//                  respaldo: `get_foreign_total_with_tax`/`totalDue`).
// `refundExactRate` -> reembolso con la TASA EXACTA del pago foráneo original
//                  (prefetch de `get_refund_foreign_rate`); dispara la rama
//                  directa de `set_foreign_amount` que espeja el pago al centavo.
export function makeOrderStub({
    totalDue = 0,
    payments = [],
    fc = makeCurrency(),
    rate = RATE,
    refundRate = null,
    refundExactRate = null,
} = {}) {
    const isRefund = refundRate != null || refundExactRate != null;
    const effRate = refundRate != null ? refundRate : rate;
    const exact = refundExactRate != null ? refundExactRate : 0;
    const round = (v) => roundPrecision(v, 0.01);
    return {
        totalDue,
        payment_ids: payments,
        get_foreign_currency: () => fc,
        _resolveCurrencyRecord: (c) => c,
        _getForeignCurrencyRecord: () => fc,
        roundLocalMoney: round,
        roundForeignMoney: round,
        // Tasa VIVA (pos.config de hoy).
        localToForeign: (v) => roundPrecision(v / rate, 0.01),
        foreignToLocal: (v) => roundPrecision(v * rate, 0.01),
        get_foreign_multiplier: () => 1 / rate,
        // Twins rate-explícitos del motor (multiplican por la tasa dada y
        // redondean, igual que _convertAtRate). La dirección la fija la tasa
        // que pasa el llamador (main→foreign chica, o foreign→local grande).
        localToForeignAtRate: (v, m, doRound = true) =>
            !v || !m ? 0 : doRound ? round(v * m) : v * m,
        foreignToLocalAtRate: (v, m, doRound = true) =>
            !v || !m ? 0 : doRound ? round(v * m) : v * m,
        // Tasa exacta del pago foráneo original (0 si no aplica).
        getRefundForeignRate: () => exact,
        // Helpers refund-aware: exacta si está, si no la agregada/viva.
        _hasRefundLines: () => isRefund,
        _convertOrderAmount: (v) =>
            exact > 0 ? round(v / exact) : round(v / effRate),
        _convertForeignOrderAmount: (v) =>
            exact > 0 ? round(v * exact) : round(v * effRate),
        get_effective_foreign_multiplier: () => (exact > 0 ? 1 / exact : 1 / effRate),
    };
}
