import { test, expect, describe } from "@odoo/hoot";
import { PosCategory } from "@point_of_sale/app/models/pos_category";
import { SelfOrder } from "@pos_self_order/app/services/self_order_service";
import "@l10n_ve_pos_self_order/overrides/self_order_service";
import "@l10n_ve_pos_self_order/overrides/pos_category";

// TI-16064: con "Mostrar solamente los productos disponibles"
// (pos_show_just_products_with_available_qty) la cuadrícula del Kiosko no
// muestra las opciones de combo almacenables sin stock, que el servidor
// manda con self_order_available = false.

const category = { id: 1 };

function template(name, { isStorable = true, available = true } = {}) {
    return {
        id: name,
        is_storable: isStorable,
        self_order_available: available,
        pos_categ_ids: [category],
    };
}

const templates = [
    template("con stock"),
    template("opcion sin stock", { available: false }),
    template("servicio no disponible", { isStorable: false, available: false }),
];

const coreGrid = ["con stock", "opcion sin stock", "servicio no disponible"];

// Categoría real: ProductListPage.getProducts usa associatedProducts.
function associatedProducts(showOnlyAvailable = true) {
    const config = { pos_show_just_products_with_available_qty: showOnlyAvailable };
    const posCategory = {
        id: category.id,
        getAllChildren: () => [posCategory],
        models: {
            "pos.config": { getFirst: () => config },
            "product.template": { toRaw: () => ({ getBy: () => templates }) },
        },
    };
    return Object.getOwnPropertyDescriptor(PosCategory.prototype, "associatedProducts")
        .get.call(posCategory)
        .map((tmpl) => tmpl.id);
}

// Categoría sintética "Sin categoría": sale de productByCategIds.
function initProducts(showOnlyAvailable = true) {
    const selfOrder = {
        config: {
            limit_categories: false,
            iface_available_categ_ids: [],
            _pos_special_products_ids: [],
            pos_show_just_products_with_available_qty: showOnlyAvailable,
        },
        models: {
            "pos.category": { getAll: () => [category] },
            "product.template": {
                getAllBy: () => ({ [category.id]: [...templates] }),
                filter: (predicate) => templates.filter(predicate),
            },
            "product.product": { get: () => undefined },
        },
    };
    SelfOrder.prototype.initProducts.call(selfOrder);
    return selfOrder.productByCategIds[category.id].map((tmpl) => tmpl.id);
}

describe("l10n_ve_pos_self_order cuadrícula con productos disponibles", () => {
    test("ajuste activo: la opción almacenable sin stock no sale en una categoría", () => {
        expect(associatedProducts()).toEqual(["con stock", "servicio no disponible"]);
    });

    test("ajuste activo: la opción almacenable sin stock no sale en Sin categoría", () => {
        expect(initProducts()).toEqual(["con stock", "servicio no disponible"]);
    });

    test("ajuste apagado: la cuadrícula es la del core", () => {
        expect(associatedProducts(false)).toEqual(coreGrid);
        expect(initProducts(false)).toEqual(coreGrid);
    });
});
