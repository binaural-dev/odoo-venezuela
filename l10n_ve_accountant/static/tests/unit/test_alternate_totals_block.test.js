import { describe, expect, test } from "@odoo/hoot";

import {
    hasAlternateBlock,
    isCompanyCurrencyDocument,
} from "@l10n_ve_accountant/components/tax_totals/tax_totals";

const VES = 2;
const USD = 1;

describe.current.tags("headless");

test("documento en la moneda de la compania: el bloque muestra la moneda de referencia", () => {
    expect(isCompanyCurrencyDocument({ currency_id: VES, ves_currency_id: VES })).toBe(true);
});

test("documento en otra moneda: el bloque sigue mostrando VES", () => {
    expect(isCompanyCurrencyDocument({ currency_id: USD, ves_currency_id: VES })).toBe(false);
});

test("sin totales no se considera documento en la moneda de la compania", () => {
    expect(isCompanyCurrencyDocument(undefined)).toBe(false);
});

test("moneda de la compania con moneda de referencia: el bloque se muestra", () => {
    const totals = { currency_id: VES, ves_currency_id: VES };
    expect(hasAlternateBlock(totals, [USD, "USD"])).toBe(true);
});

test("moneda de la compania sin moneda de referencia: el bloque se oculta", () => {
    const totals = { currency_id: VES, ves_currency_id: VES };
    expect(hasAlternateBlock(totals, false)).toBe(false);
});

test("documento en otra moneda: el bloque se muestra aunque no haya moneda de referencia", () => {
    const totals = { currency_id: USD, ves_currency_id: VES };
    expect(hasAlternateBlock(totals, false)).toBe(true);
});
