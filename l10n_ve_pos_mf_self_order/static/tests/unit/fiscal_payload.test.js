import { test, expect, describe } from "@odoo/hoot";
import {
    buildKioskFiscalPayload,
    normalizeProductName,
} from "@l10n_ve_pos_mf_self_order/app/fiscal_payload";

// Unit tests del builder fiscal AUTOCONTENIDO del Kiosko (fiscal_payload.js).
// Cubre las ramas de validación, la conversión a moneda fiscal (líneas Y pago),
// el neteo de descuento, el strip de la 't' del fiscal_code y la concatenación
// prefix_vat+vat. `buildKioskFiscalPayload`/`normalizeProductName` son puras y
// exportadas, así que se prueban sin PosStore ni RPC.

function makeCurrency(name, rounding = 0.01) {
    return { name, rounding };
}

function makeConfig(overrides = {}) {
    return {
        flag_21: "00",
        foreign_currency_id: { rounding: 0.01 },
        receipt_header: "",
        receipt_footer: "",
        ...overrides,
    };
}

function makeLine(overrides = {}) {
    return {
        qty: 1,
        price_unit: 100,
        discount: 0,
        tax_ids: [{ fiscal_code: "t01" }],
        product_id: { default_code: "P1", display_name: "Producto Uno" },
        ...overrides,
    };
}

function makeOrder(overrides = {}) {
    return {
        partner_id: { prefix_vat: "V", vat: "12345678", name: "Juan Perez" },
        lines: [makeLine()],
        pos_reference: "Order 0001",
        foreign_currency_rate: 40,
        ...overrides,
    };
}

describe("normalizeProductName", () => {
    test("quita acentos y caracteres especiales", () => {
        expect(normalizeProductName("Café Ñandú #2")).toBe("Cafe Nandu 2");
    });
    test("vacío/nulo devuelve cadena vacía", () => {
        expect(normalizeProductName("")).toBe("");
        expect(normalizeProductName(null)).toBe("");
    });
});

describe("buildKioskFiscalPayload — validación", () => {
    test("sin cliente → inválido", () => {
        const res = buildKioskFiscalPayload(makeOrder({ partner_id: null }), {
            config: makeConfig(),
            currency: makeCurrency("VES"),
            paymentMethodCode: "01",
            paymentAmount: 100,
        });
        expect(res.valid).toBe(false);
    });

    test("sin código fiscal del método de pago → inválido", () => {
        const res = buildKioskFiscalPayload(makeOrder(), {
            config: makeConfig(),
            currency: makeCurrency("VES"),
            paymentMethodCode: "",
            paymentAmount: 100,
        });
        expect(res.valid).toBe(false);
    });

    test("base no-VES sin tasa válida → inválido", () => {
        const res = buildKioskFiscalPayload(makeOrder({ foreign_currency_rate: 0 }), {
            config: makeConfig(),
            currency: makeCurrency("USD"),
            paymentMethodCode: "01",
            paymentAmount: 100,
        });
        expect(res.valid).toBe(false);
    });

    test("sin líneas válidas → inválido", () => {
        const res = buildKioskFiscalPayload(makeOrder({ lines: [] }), {
            config: makeConfig(),
            currency: makeCurrency("VES"),
            paymentMethodCode: "01",
            paymentAmount: 100,
        });
        expect(res.valid).toBe(false);
    });
});

describe("buildKioskFiscalPayload — moneda fiscal", () => {
    test("base VES: importes sin convertir", () => {
        const res = buildKioskFiscalPayload(makeOrder(), {
            config: makeConfig(),
            currency: makeCurrency("VES"),
            paymentMethodCode: "01",
            paymentAmount: 100,
        });
        expect(res.valid).toBe(true);
        expect(res.lines[0].price_unit).toBe(100);
        expect(res.payment_lines[0].amount).toBe(100);
    });

    test("base no-VES: líneas Y pago convertidos con la misma tasa (§3.2)", () => {
        // price_unit 100 * rate 40 = 4000 en la línea; el PAGO debe convertirse
        // igual (100 → 4000). Antes del fix el pago quedaba en 100 (descuadre).
        const res = buildKioskFiscalPayload(makeOrder({ foreign_currency_rate: 40 }), {
            config: makeConfig(),
            currency: makeCurrency("USD"),
            paymentMethodCode: "01",
            paymentAmount: 100,
        });
        expect(res.valid).toBe(true);
        expect(res.lines[0].price_unit).toBe(4000);
        expect(res.payment_lines[0].amount).toBe(4000);
    });
});

describe("buildKioskFiscalPayload — líneas", () => {
    test("neto de descuento", () => {
        // 100 con 10% de descuento = 90 (base VES, sin conversión).
        const order = makeOrder({ lines: [makeLine({ discount: 10 })] });
        const res = buildKioskFiscalPayload(order, {
            config: makeConfig(),
            currency: makeCurrency("VES"),
            paymentMethodCode: "01",
            paymentAmount: 90,
        });
        expect(res.lines[0].price_unit).toBe(90);
    });

    test("fiscal_code sin la 't' inicial", () => {
        const res = buildKioskFiscalPayload(makeOrder(), {
            config: makeConfig(),
            currency: makeCurrency("VES"),
            paymentMethodCode: "01",
            paymentAmount: 100,
        });
        expect(res.lines[0].fiscal_code).toBe("01");
    });

    test("línea sin impuestos → fiscal_code '0'", () => {
        const order = makeOrder({ lines: [makeLine({ tax_ids: [] })] });
        const res = buildKioskFiscalPayload(order, {
            config: makeConfig(),
            currency: makeCurrency("VES"),
            paymentMethodCode: "01",
            paymentAmount: 100,
        });
        expect(res.lines[0].fiscal_code).toBe("0");
    });
});

describe("buildKioskFiscalPayload — partner", () => {
    test("vat concatena prefix_vat + vat", () => {
        const res = buildKioskFiscalPayload(makeOrder(), {
            config: makeConfig(),
            currency: makeCurrency("VES"),
            paymentMethodCode: "01",
            paymentAmount: 100,
        });
        expect(res.partner.vat).toBe("V12345678");
    });
});
