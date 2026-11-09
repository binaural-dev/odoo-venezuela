import { test, expect, describe, beforeEach } from "@odoo/hoot";
import { allowTranslations, patchWithCleanup } from "@web/../tests/web_test_helpers";
import { localization } from "@web/core/l10n/localization";
import { Orderline } from "@point_of_sale/app/components/orderline/orderline";
import { formatCurrency } from "@web/core/currency";
import "@l10n_ve_pos/overrides/components/orderline/orderline";

// Ticket 15725: el core no pinta el precio de las líneas hijas de un combo
// (`price: !line.combo_parent_id && ...`), solo el del padre. Cada hija muestra
// su parte del precio como una línea normal; con `vals.price`, orderline.xml
// agrega el monto secundario.

// lineScreenValues formatea montos (formatCurrency) y traduce ("Free"): en un
// test sin servicios ni la localización ni las traducciones están cargadas.
beforeEach(() => {
    allowTranslations();
    patchWithCleanup(localization, { decimalPoint: ",", thousandsSep: ".", grouping: [3, 0] });
});

function makeLine(props = {}) {
    return {
        order_id: {},
        product_id: { getImageUrl: () => "", uom_id: { name: "Unidades" }, tracking: "none" },
        getQuantityStr: () => ({ unitPart: "1", decimalPart: "", decimalPoint: "," }),
        getDiscountStr: () => "0",
        getDiscount: () => 0,
        orderDisplayProductName: { name: "Producto", attributeString: "" },
        taxGroupLabels: "",
        price_type: "original",
        combo_parent_id: false,
        currencyDisplayPrice: "Bs 100,00",
        currencyDisplayPriceUnit: "Bs 100,00",
        displayPriceNoDiscount: 100,
        displayPrice: 100,
        currency: { id: 1 },
        full_product_name: "Producto",
        price: 100,
        packLotLines: [],
        ...props,
    };
}

function screenValues(line, props = {}) {
    const orderline = Object.create(Orderline.prototype);
    Object.defineProperty(orderline, "props", { value: { mode: "display", ...props } });
    Object.defineProperty(orderline, "line", { value: line });
    return orderline.lineScreenValues;
}

describe("l10n_ve_pos precio de las hijas de un combo (ticket 15725)", () => {
    test("la hija muestra su parte del precio, como una línea normal", () => {
        const child = makeLine({ combo_parent_id: { id: 1 }, currencyDisplayPrice: "", displayPrice: 8033.4 });
        expect(screenValues(child).price).toBe(formatCurrency(8033.4, 1));
    });

    test("hija con descuento del 100 %: Free, como el core", () => {
        const child = makeLine({ combo_parent_id: { id: 1 }, currencyDisplayPrice: "", getDiscount: () => 100 });
        expect(screenValues(child).price).toBe("Free");
    });

    test("recibo básico: la hija sigue sin precio, como el resto de líneas", () => {
        const child = makeLine({ combo_parent_id: { id: 1 }, currencyDisplayPrice: "" });
        expect(screenValues(child, { basic_receipt: true }).price).toBe(false);
    });

    test("línea normal y padre del combo: sin cambios respecto al core", () => {
        expect(screenValues(makeLine()).price).toBe("Bs 100,00");
    });
});
