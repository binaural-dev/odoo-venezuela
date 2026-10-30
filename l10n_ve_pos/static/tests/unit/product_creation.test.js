import { test, expect, describe } from "@odoo/hoot";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import "@l10n_ve_pos/overrides/services/pos_store";

// "Permitir crear productos" (allow_product_creation_in_pos): el getter que
// muestra "Crear producto" en el menú y editProduct(), que abre el formulario.

const ADD_ACTION = "point_of_sale.product_template_action_add_pos";
const EDIT_ACTION = "point_of_sale.product_template_action_edit_pos";

function makeStore({ allowed, canCreate = true }) {
    const actions = [];
    const store = {
        // module_pos_hr apagado: el getter de pos_hr delega en el core.
        config: { allow_product_creation_in_pos: allowed, module_pos_hr: false },
        canUserCreateProduct: canCreate,
        action: { doAction: (action) => actions.push(action) },
        orderContainsProduct: () => false,
    };
    // El getter que leen hasProductCreationAccess y editProduct, del parche real.
    Object.defineProperty(
        store,
        "isProductCreationAllowed",
        Object.getOwnPropertyDescriptor(PosStore.prototype, "isProductCreationAllowed")
    );
    return { store, actions };
}

function hasAccess(store) {
    return Object.getOwnPropertyDescriptor(PosStore.prototype, "hasProductCreationAccess").get.call(
        store
    );
}

describe("l10n_ve_pos creación de productos", () => {
    test("apagada oculta Crear producto aunque el usuario tenga permiso", () => {
        const { store } = makeStore({ allowed: false });
        expect(hasAccess(store)).toBe(false);
    });

    test("encendida respeta el permiso de creación del core", () => {
        expect(hasAccess(makeStore({ allowed: true }).store)).toBe(true);
        expect(hasAccess(makeStore({ allowed: true, canCreate: false }).store)).toBe(false);
    });

    test("caja en caché sin el campo (undefined) no permite crear", async () => {
        const { store, actions } = makeStore({ allowed: undefined });
        expect(hasAccess(store)).toBe(false);
        await PosStore.prototype.editProduct.call(store);
        expect(actions).toEqual([]);
    });

    test("apagada no abre el formulario de producto nuevo", async () => {
        const { store, actions } = makeStore({ allowed: false });
        await PosStore.prototype.editProduct.call(store);
        expect(actions).toEqual([]);
    });

    test("encendida abre el formulario de producto nuevo", async () => {
        const { store, actions } = makeStore({ allowed: true });
        await PosStore.prototype.editProduct.call(store);
        expect(actions).toEqual([ADD_ACTION]);
    });

    test("apagada sigue dejando editar un producto existente", async () => {
        const { store, actions } = makeStore({ allowed: false });
        await PosStore.prototype.editProduct.call(store, { id: 7 });
        expect(actions).toEqual([EDIT_ACTION]);
    });
});
