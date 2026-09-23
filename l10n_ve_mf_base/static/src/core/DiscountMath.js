/** @odoo-module */

import { roundPrecision as round_pr } from "@web/core/utils/numbers";

/**
 * Aritmética de descuentos compartida entre el PosStore (que decide el
 * descuento efectivo de cada línea) y el driver TFHKA (que lo imprime).
 *
 * Este módulo expone DOS funciones puras y ninguna lógica de "clamp" de
 * porcentaje: el descuento por línea se envía a la impresora como MONTO exacto
 * (comando `q-`, ver DISCOUNT_STRATEGY.md), ya calculado y redondeado en Odoo,
 * así que no existe el límite de 99,99% que imponía un campo de porcentaje de
 * 4 dígitos (2 enteros + 2 decimales).
 *
 *  - `composeDiscountPercent(a, b)` — composición multiplicativa de dos
 *    porcentajes. Hoy la consume `PosStore._applyGlobalDiscountBeforeValidation`
 *    (el único llamador; `_convertOrderForDriver` NO la usa: ahí la cascada se
 *    hace sobre PRECIOS, con dos aplicaciones sucesivas de `_applyDiscount`,
 *    que es aritméticamente equivalente).
 *  - `computeLineDiscountAmount({...})` — el MONTO en Bs que una línea
 *    descuenta. La consume `PosStore._convertOrderForDriver` para poblar
 *    `discount_amount`, el argumento del comando `q-`.
 *
 * Vive en `l10n_ve_mf_base/core` — y no dentro de PosStore.js — por dos
 * razones:
 *
 *  1. **Una sola implementación de cada fórmula.** Tanto la composición de
 *     porcentajes como el monto de descuento por línea son aritmética que
 *     decide si el ticket impreso cuadra con lo que cobra Odoo. Duplicarla
 *     dentro de PosStore.js (en dos caminos distintos según el flag
 *     `native_global_discount_line`) es justamente cómo se divergiría.
 *
 *  2. **Testeabilidad real.** El bundle `web.qunit_suite_tests` carga
 *     `web.assets_backend` (donde vive este módulo) pero NO
 *     `point_of_sale._assets_pos` (donde vive PosStore.js). Manteniendo las
 *     fórmulas aquí, los tests QUnit ejercitan las funciones de producción en
 *     vez de una copia espejo.
 */

/**
 * Compone dos porcentajes de descuento de forma multiplicativa (en cascada),
 * no aditiva.
 *
 * Un 10% de campaña seguido de un 10% global no es un 20%: es
 * `1 - 0.9 × 0.9 = 19%`. Esta es la única fórmula de composición del proyecto.
 *
 * @param {number} firstPct - Primer descuento (ej. el de campaña), 0-100
 * @param {number} secondPct - Descuento aplicado sobre el neto del primero
 *                             (ej. el global inferido), 0-100
 * @returns {number} Porcentaje compuesto, redondeado a 2 decimales
 */
export function composeDiscountPercent(firstPct, secondPct) {
    const first = Number(firstPct || 0);
    const second = Number(secondPct || 0);
    return round_pr(100 - ((100 - first) * (100 - second)) / 100, 0.01);
}

/**
 * Monto EXACTO en Bs que una línea descuenta: el argumento del comando `q-`.
 *
 * Se redondea CADA total por separado y recién después se restan. Es
 * deliberado, y no es lo mismo que redondear la diferencia unitaria y luego
 * multiplicar por la cantidad:
 *
 *     ✗ round((bruto − neto) × qty)      ← puede diferir 1 céntimo
 *     ✓ round(bruto × qty) − round(neto × qty)
 *
 * Odoo cobra `round(neto × cantidad)` por línea, y ese número es el que
 * alimenta los montos de pago `2XX` que la impresora compara contra su propio
 * cálculo en el cierre `199`. Con la forma ✓ se cumple SIEMPRE, por
 * construcción, la identidad que hace cuadrar el ticket:
 *
 *     round(bruto × qty) − descuento === round(neto × qty)
 *
 * Con la forma ✗ y cantidad fraccionaria (ej. 1,5 kg) el resultado puede
 * diferir en un céntimo del total real, y ese céntimo basta para que la
 * impresora rechace el `199` con NAK. Con cantidad entera ambas formas
 * coinciden.
 *
 * El `Math.max(0, …)` es una guarda defensiva: el monto nunca debe salir
 * negativo (implicaría un neto mayor que el bruto, es decir un recargo, que
 * este camino no modela).
 *
 * @param {Object} params
 * @param {number} params.grossUnitPrice - Precio unitario BRUTO (antes de todo
 *                                         descuento)
 * @param {number} params.netUnitPrice - Precio unitario NETO (después de
 *                                       campaña y global compuestos)
 * @param {number} params.quantity - Cantidad de la línea (puede ser fraccionaria)
 * @param {number} params.rounding - Precisión de la moneda (ej. 0.01)
 * @returns {number} Monto descontado por la línea completa, en Bs
 */
export function computeLineDiscountAmount({
    grossUnitPrice,
    netUnitPrice,
    quantity,
    rounding,
} = {}) {
    const r = Number(rounding || 0.01);
    const grossTotal = round_pr(Number(grossUnitPrice || 0) * Number(quantity || 0), r);
    const netTotal = round_pr(Number(netUnitPrice || 0) * Number(quantity || 0), r);
    // El `round_pr` final NO cambia el valor: los dos operandos ya son
    // múltiplos de `r`, así que sólo limpia el ruido de coma flotante de la
    // resta (7.5 − 7.13 da 0.3700000000000001 en IEEE-754). Importa porque
    // este número se compara, se registra y viaja al driver.
    return Math.max(0, round_pr(grossTotal - netTotal, r));
}
