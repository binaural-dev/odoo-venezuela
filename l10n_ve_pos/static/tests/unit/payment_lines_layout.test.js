import { test, expect, describe, after, animationFrame, getFixture } from "@odoo/hoot";
import { queryAll } from "@odoo/hoot-dom";
import { App, Component, t, useProps, xml } from "@odoo/owl";
import { patchWithCleanup } from "@web/../tests/web_test_helpers";
import { getTemplate } from "@web/core/templates";
import { PaymentScreenPaymentLines } from "@point_of_sale/app/screens/payment_screen/payment_lines/payment_lines";
import "@l10n_ve_pos/overrides/screens/payment_line/payment_line";

// H10: la línea de un pago en moneda foránea muestra dos montos ("$ 70,00 /
// 56.233,80 Bs.F"). El contenedor copiado del core (`text-truncate`, una sola
// fila) los cortaba con "…" cuando no cabían junto al nombre; ahora el nombre se
// trunca y los montos no: bajan a una segunda fila y, si el par no cabe, se
// parte por el " / ". El bundle de tests carga Bootstrap, así que se mide la
// geometría real con el ancho de la columna de pagos medido en el PdV (427 px,
// de los que 360 son de .payment-infos).

function makeLine({ uuid, name, selected, foreign, amount = 56233.8, foreignAmount = 70 }) {
    const currency = { id: foreign ? 1 : 2, name: foreign ? "USD" : "VEF" };
    return {
        uuid,
        payment_status: false,
        displayName: name,
        currency,
        amount_currency: foreignAmount,
        isForeignPayment: foreign,
        useQr: false,
        payment_method_id: { name, availableCurrencies: [{ id: 2 }, { id: 1 }] },
        isSelected: () => selected,
        isProcessing: () => false,
        isForceDoneAllowed: () => true,
        isDone: () => true,
        getPaymentStatus: () => false,
        getAmount: () => amount,
        get_foreign_amount: () => foreignAmount,
    };
}

// PriceFormatter necesita la localización de web; aquí basta el texto.
class PlainPrice extends Component {
    static template = xml`<span t-out="this.props.price"/>`;
    props = useProps({ price: t.string() });
}

// Se monta con una App de Owl 3 y un env mínimo, no con mountWithCleanup: el
// entorno simulado de web arranca todos los servicios del bundle de tests
// (pos, pos_data, mail…), que piden datos al mock server.
async function mountLines(paymentLines) {
    patchWithCleanup(PaymentScreenPaymentLines, {
        components: { ...PaymentScreenPaymentLines.components, PriceFormatter: PlainPrice },
    });
    const noop = () => {};
    const pos = {
        formatCurrency: (v, id) => (id === 1 ? `$ ${v}` : `${v} Bs.F`),
        config: { currency_id: { id: 2 } },
    };
    const env = {
        services: { ui: { isSmall: false }, dialog: { add: noop }, pos },
    };
    const app = new App({
        config: { env },
        getTemplate,
        translateFn: (s) => s,
    });
    after(() => app.destroy());
    const fixture = getFixture();
    fixture.style.width = "427px";
    await app.createRoot(PaymentScreenPaymentLines, {
        props: {
            paymentLines,
            deleteLine: noop,
            selectLine: noop,
            sendForceDone: noop,
            sendForceCancel: noop,
            sendPaymentCancel: noop,
            sendPaymentRequest: noop,
            updateSelectedPaymentline: noop,
            isRefundOrder: false,
        },
    }).mount(fixture);
    await animationFrame();
    return queryAll(".paymentline .payment-infos");
}

// Los montos caben enteros dentro de su contenedor (nada recortado).
function expectAmountsWhole(info) {
    const amount = info.querySelector(".payment-amount");
    expect(info.scrollWidth).toBeLessThan(info.clientWidth + 1);
    expect(amount.getBoundingClientRect().right).toBeLessThan(
        info.getBoundingClientRect().right + 1
    );
}

describe("l10n_ve_pos línea de pago (H10)", () => {
    test("los dos montos de un método foráneo se ven enteros, en otra fila si no caben", async () => {
        const [cash, foreign] = await mountLines([
            makeLine({ uuid: "a", name: "Efectivo", selected: false, foreign: false, amount: 70 }),
            makeLine({ uuid: "b", name: "Efectivo USD (Caja VES)", selected: true, foreign: true }),
        ]);
        // El core agrega la moneda al nombre de un método con varias monedas.
        expect(foreign.querySelector(".payment-name")).toHaveText("Efectivo USD (Caja VES) USD");
        expect(foreign.querySelector(".payment-amount")).toHaveText(/\$\s*70\s*\/\s*56233\.8\s*Bs\.F/);
        expectAmountsWhole(foreign);
        // No caben junto al nombre: los montos bajan a una segunda fila.
        expect(foreign.querySelector(".payment-amount").getBoundingClientRect().top).toBeGreaterThan(
            foreign.querySelector(".payment-name").getBoundingClientRect().bottom - 1
        );
        // Los dos montos van en la misma fila, separados (el espacio antes del
        // "/" es un margen: dentro de un inline-block se perdería).
        const [first, second] = foreign.querySelectorAll(".payment-amount > span");
        expect(second.getBoundingClientRect().top).toBeLessThan(first.getBoundingClientRect().bottom);
        expect(second.getBoundingClientRect().left).toBeGreaterThan(first.getBoundingClientRect().right);
        // La línea corta sigue en una sola fila.
        expect(cash.querySelector(".payment-name")).toHaveText("Efectivo VEF");
        expectAmountsWhole(cash);
        expect(cash.querySelector(".payment-amount").getBoundingClientRect().top).toBeLessThan(
            cash.querySelector(".payment-name").getBoundingClientRect().bottom
        );
    });

    test("un par de montos muy largo se parte por el \" / \" en vez de recortarse", async () => {
        const [foreign] = await mountLines([
            makeLine({
                uuid: "b",
                name: "Efectivo USD (Caja VES)",
                selected: true,
                foreign: true,
                // Montos extremos a propósito: el par no cabe en una fila.
                amount: 99999999999999.99,
                foreignAmount: 99999999999.99,
            }),
        ]);
        expectAmountsWhole(foreign);
        const [first, second] = foreign.querySelectorAll(".payment-amount > span");
        expect(second.getBoundingClientRect().top).toBeGreaterThan(
            first.getBoundingClientRect().bottom - 1
        );
    });
});
