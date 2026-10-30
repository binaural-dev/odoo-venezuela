import { test, expect, describe } from "@odoo/hoot";
import { ProductTemplate } from "@point_of_sale/app/models/product_template";
import "@l10n_ve_pos/overrides/models/product_template";

// TI-16064: con "Mostrar solamente los productos disponibles"
// (pos_show_just_products_with_available_qty) la cuadrícula oculta los
// almacenables sin stock a mano en la ubicación de origen de la caja.

function makeTemplate({
    showOnlyAvailable = true,
    isStorable = true,
    quantities = [0],
    active = true,
    availableInPos = true,
    withConfig = true,
} = {}) {
    const config = withConfig
        ? { pos_show_just_products_with_available_qty: showOnlyAvailable }
        : undefined;
    return {
        active,
        available_in_pos: availableInPos,
        is_storable: isStorable,
        product_variant_ids: quantities.map((qty_available) => ({ qty_available })),
        models: { "pos.config": { getFirst: () => config } },
    };
}

function canBeDisplayed(template) {
    return Object.getOwnPropertyDescriptor(ProductTemplate.prototype, "canBeDisplayed").get.call(
        template
    );
}

describe("l10n_ve_pos ProductTemplate canBeDisplayed", () => {
    test("ajuste activo: el almacenable sin stock no se muestra", () => {
        expect(canBeDisplayed(makeTemplate({ quantities: [0] }))).toBe(false);
        expect(canBeDisplayed(makeTemplate({ quantities: [-13] }))).toBe(false);
    });

    test("ajuste activo: el almacenable con stock se muestra", () => {
        expect(canBeDisplayed(makeTemplate({ quantities: [0.3] }))).toBe(true);
    });

    test("ajuste activo: basta una variante con stock", () => {
        expect(canBeDisplayed(makeTemplate({ quantities: [0, -2, 4] }))).toBe(true);
        expect(canBeDisplayed(makeTemplate({ quantities: [0, -2] }))).toBe(false);
    });

    test("ajuste activo: lo no almacenable se muestra sin stock", () => {
        // Servicios, consumibles sin control de stock y combos.
        expect(canBeDisplayed(makeTemplate({ isStorable: false, quantities: [0] }))).toBe(true);
    });

    test("ajuste apagado: el almacenable sin stock se muestra", () => {
        expect(canBeDisplayed(makeTemplate({ showOnlyAvailable: false }))).toBe(true);
    });

    test("sin caja cargada no se filtra", () => {
        expect(canBeDisplayed(makeTemplate({ withConfig: false }))).toBe(true);
    });

    test("con stock no se muestra lo que el core ya oculta", () => {
        const quantities = [5];
        expect(canBeDisplayed(makeTemplate({ quantities, active: false }))).toBe(false);
        expect(canBeDisplayed(makeTemplate({ quantities, availableInPos: false }))).toBe(false);
    });
});
