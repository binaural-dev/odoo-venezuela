import { test, expect, describe } from "@odoo/hoot";
import { allowTranslations, patchWithCleanup } from "@web/../tests/web_test_helpers";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { localization } from "@web/core/l10n/localization";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { PaymentScreenStatus } from "@point_of_sale/app/screens/payment_screen/payment_status/payment_status";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import "@l10n_ve_pos/overrides/models/pos_order";
import "@l10n_ve_pos/overrides/models/payment_model";
import "@l10n_ve_pos/overrides/screens/payment_screen/payment_screen";
import "@l10n_ve_pos/overrides/screens/payment_status/payment_status";
import "@l10n_ve_pos/overrides/screens/order_receipt/order_receipt";
import { makeCurrency } from "./utils";

// Método de pago en una tercera moneda (moneda de cobro, p. ej. EUR) en una
// caja en Bs con alterna USD — tarea 86066.
//
// Tasas del 02-nov de la prueba: 1 € = 1.003,8765 Bs, 1 $ = 860,4321 Bs.

const BS_PER_EUR = 1003.8765;
const BS_PER_USD = 860.4321;

function makeOrderThis(props = {}) {
    const order = Object.create(PosOrder.prototype);
    for (const [key, value] of Object.entries(props)) {
        Object.defineProperty(order, key, { value, configurable: true, writable: true });
    }
    return order;
}

const withId = (id, name) => ({ id, name, ...makeCurrency(0.01) });
const VEF = withId(2, "VEF");
const USD = withId(1, "USD");
const EUR = withId(126, "EUR");

function makeEngineOrder({ eurRate = BS_PER_EUR } = {}) {
    return makeOrderThis({
        currency: VEF,
        config: {
            foreign_currency_id: USD,
            foreign_rate: BS_PER_USD,
            foreign_inverse_rate: 1 / BS_PER_USD,
            tender_currency_rates: {
                [EUR.id]: { foreign_rate: eurRate, foreign_inverse_rate: eurRate ? 1 / eurRate : 0 },
            },
        },
    });
}

describe("l10n_ve_pos _getPosConversionRate con moneda de cobro", () => {
    test("Bs ↔ EUR usa las tasas de la moneda de cobro", () => {
        const order = makeEngineOrder();
        expect(order._getPosConversionRate(EUR, VEF)).toBe(BS_PER_EUR);
        expect(order._getPosConversionRate(VEF, EUR)).toBe(1 / BS_PER_EUR);
        expect(order._convert(100, EUR, VEF)).toBe(100387.65);
        expect(order._convert(8500, VEF, EUR)).toBe(8.47);
    });

    test("EUR → USD pasa por la caja multiplicando las dos tasas sin redondear", () => {
        const order = makeEngineOrder();
        expect(order._getPosConversionRate(EUR, USD)).toBe(BS_PER_EUR * (1 / BS_PER_USD));
        expect(order._getPosConversionRate(USD, EUR)).toBe(BS_PER_USD * (1 / BS_PER_EUR));
    });

    test("el par caja ↔ alterna no cambia", () => {
        const order = makeEngineOrder();
        expect(order._getPosConversionRate(VEF, USD)).toBe(1 / BS_PER_USD);
        expect(order._getPosConversionRate(USD, VEF)).toBe(BS_PER_USD);
    });

    test("sin tasa del día de la moneda de cobro → 0", () => {
        const order = makeEngineOrder({ eurRate: 0 });
        expect(order._getPosConversionRate(EUR, VEF)).toBe(0);
        expect(order._getPosConversionRate(VEF, EUR)).toBe(0);
        expect(order._convert(10, EUR, VEF)).toBe(0);
    });

    test("una moneda que no es de cobro sigue sin tasa", () => {
        const order = makeEngineOrder();
        const gbp = withId(3);
        expect(order._getPosConversionRate(gbp, VEF)).toBe(0);
        expect(order._getPosConversionRate(EUR, gbp)).toBe(0);
    });
});

// ---- setTenderAmount ----

function donePayment(amount, isChange = false) {
    return { getAmount: () => amount, isDone: () => true, is_change: isChange };
}

// Pedido con la tasa EUR del día (o la de un reembolso, `refundRate` Bs por €).
function makeTenderOrder({ totalDue, paid = [], changes = [], refundRate = 0 }) {
    return {
        totalDue,
        payment_ids: [...paid.map((a) => donePayment(a)), ...changes.map((a) => donePayment(a, true))],
        _getMainCurrency: () => VEF,
        _getPosConversionRate: (from) => (from === EUR ? BS_PER_EUR : 1 / BS_PER_EUR),
        _convertAtRate: (v, r, currency) => (!v || !r ? 0 : currency.round(v * r)),
        getRefundTenderRate: () => refundRate,
    };
}

function tender(order, requested) {
    const proto = PosPayment.prototype;
    const payment = {
        pos_order_id: order,
        amount: 0,
        tender_amount: 0,
        getTenderCurrency: () => EUR,
        _getTenderRates: proto._getTenderRates,
        _getLocalDueBefore: proto._getLocalDueBefore,
        _getTenderDue: proto._getTenderDue,
        _getPartialTenderLocalAmount: proto._getPartialTenderLocalAmount,
        setAmount(value) {
            this.amount = VEF.round(value);
        },
    };
    order.payment_ids.push(payment);
    proto.setTenderAmount.call(payment, requested);
    return payment;
}

describe("l10n_ve_pos setTenderAmount (moneda de cobro)", () => {
    test("lo adeudado en euros cubre la venta exacta, sin céntimos fantasma", () => {
        // 8.500 Bs = 8,4672 € → se propone 8,47 €; estricto serían 8.502,83 Bs.
        const payment = tender(makeTenderOrder({ totalDue: 8500 }), 8.47);
        expect(payment.amount).toBe(8500);
        expect(payment.tender_amount).toBe(8.47);
    });

    test("pagar de más en euros: la caja vale lo adeudado más el excedente convertido (vuelto en Bs)", () => {
        const payment = tender(makeTenderOrder({ totalDue: 8500 }), 10);
        // 10 − 8,47 = 1,53 € → 1.535,93 Bs de vuelto.
        expect(payment.amount).toBe(8500 + VEF.round(1.53 * BS_PER_EUR));
        expect(payment.tender_amount).toBe(10);
    });

    test("pago parcial: la conversión de lo tecleado", () => {
        const payment = tender(makeTenderOrder({ totalDue: 17000 }), 5);
        expect(payment.amount).toBe(VEF.round(5 * BS_PER_EUR));
        expect(payment.tender_amount).toBe(5);
    });

    test("pago parcial después de otro pago: lo adeudado descuenta lo ya pagado", () => {
        const order = makeTenderOrder({ totalDue: 17000, paid: [5019.38] });
        // Restante 11.980,62 Bs = 11,93 €.
        const payment = tender(order, 11.93);
        expect(payment.amount).toBe(11980.62);
    });

    test("los vueltos no cuentan en lo adeudado", () => {
        const payment = tender(makeTenderOrder({ totalDue: 8500, changes: [-1000] }), 8.47);
        expect(payment.amount).toBe(8500);
    });

    test("reembolso tecleado sin signo: sale negativo", () => {
        const payment = tender(makeTenderOrder({ totalDue: -17000 }), 5);
        expect(payment.amount).toBe(-VEF.round(5 * BS_PER_EUR));
        expect(payment.tender_amount).toBe(-5);
    });

    test("reembolso con la tasa original: devuelve los mismos euros", () => {
        // Venta original cobrada a 1.000 Bs/€; hoy el € vale 1.003,8765 Bs.
        const payment = tender(makeTenderOrder({ totalDue: -8000, refundRate: 1000 }), 8);
        expect(payment.amount).toBe(-8000);
        expect(payment.tender_amount).toBe(-8);
    });
});

describe("l10n_ve_pos moneda de cobro de la línea", () => {
    test("un método sin moneda de cobro no tiene moneda de cobro", () => {
        const order = makeEngineOrder();
        const line = { pos_order_id: order, payment_method_id: { tender_currency_id: false } };
        expect(PosPayment.prototype.getTenderCurrency.call(line)).toBe(null);
    });

    test("la moneda de cobro igual a la de la caja no cuenta", () => {
        const order = makeEngineOrder();
        const line = { pos_order_id: order, payment_method_id: { tender_currency_id: VEF } };
        expect(PosPayment.prototype.getTenderCurrency.call(line)).toBe(null);
    });

    test("el monto de la caja recalcula lo cobrado en la moneda de cobro", () => {
        const order = makeTenderOrder({ totalDue: 8500 });
        const line = {
            pos_order_id: order,
            amount: 8500,
            tender_amount: 0,
            getTenderCurrency: () => EUR,
            _getTenderRates: PosPayment.prototype._getTenderRates,
        };
        PosPayment.prototype._recomputeTenderFromLocal.call(line);
        expect(line.tender_amount).toBe(8.47);
    });
});

describe("l10n_ve_pos moneda de cobro de un pago guardado", () => {
    // Un pago sincronizado trae su `tender_currency_id`: al reimprimir un
    // recibo viejo salen los euros cobrados aunque el método haya cambiado.
    test("prefiere la moneda guardada en el pago a la actual del método", () => {
        const order = makeEngineOrder();
        const GBP = withId(3, "GBP");
        const line = {
            pos_order_id: order,
            tender_currency_id: EUR,
            payment_method_id: { tender_currency_id: GBP },
        };
        expect(PosPayment.prototype.getTenderCurrency.call(line)).toBe(EUR);
    });

    test("un método al que se le quitó la moneda no borra la del pago", () => {
        const order = makeEngineOrder();
        const line = {
            pos_order_id: order,
            tender_currency_id: EUR,
            payment_method_id: { tender_currency_id: false },
        };
        expect(PosPayment.prototype.getTenderCurrency.call(line)).toBe(EUR);
    });

    test("una línea nueva, sin moneda guardada, toma la del método", () => {
        const order = makeEngineOrder();
        const line = { pos_order_id: order, payment_method_id: { tender_currency_id: EUR } };
        expect(PosPayment.prototype.getTenderCurrency.call(line)).toBe(EUR);
    });
});

// ---- Pantalla de pago: sin tasa del día no se cobra en la moneda de cobro ----

function makeAddLineScreen({ eurRate }) {
    const calls = { deleted: [], dialogs: [], buffer: [] };
    const method = { id: 80, name: "Efectivo EUR", type: "cash", tender_currency_id: EUR };
    const line = {
        uuid: "eur-line",
        amount: 8500,
        payment_method_id: method,
        getTenderCurrency: () => EUR,
        getTenderAmount: () => 8.47,
    };
    const order = makeOrderThis({
        currency: VEF,
        config: makeEngineOrder({ eurRate }).config,
        remainingDue: 8500,
        payment_ids: [],
        addPaymentline(paymentMethod) {
            this.payment_ids.push(line);
            return { status: true, data: line };
        },
        // l10n_ve_pos_igtf, si su parche está cargado en la suite.
        update_igtf() {},
    });
    const screen = {
        pos: { paymentTerminalInProgress: false },
        currentOrder: order,
        paymentLines: [],
        selectedPaymentLine: line,
        makeAnimation() {},
        render() {},
        numberBuffer: { set: (value) => calls.buffer.push(value) },
        dialog: { add: (component, props) => calls.dialogs.push({ component, props }) },
        env: { utils: { formatCurrencyById: (amount, id) => `${id}:${amount}` } },
        deletePaymentLine: (uuid) => calls.deleted.push(uuid),
    };
    return { screen, method, calls };
}

describe("l10n_ve_pos addNewPaymentLine con moneda de cobro", () => {
    test("sin tasa del día del EUR quita la línea y avisa", async () => {
        allowTranslations();
        const { screen, method, calls } = makeAddLineScreen({ eurRate: 0 });
        const result = await PaymentScreen.prototype.addNewPaymentLine.call(screen, method);
        expect(result).toBe(false);
        expect(calls.deleted).toEqual(["eur-line"]);
        expect(calls.dialogs.length).toBe(1);
        expect(calls.dialogs[0].component).toBe(AlertDialog);
        const body = String(calls.dialogs[0].props.body);
        expect(body).toInclude("EUR");
        expect(body).toInclude("Efectivo EUR");
    });

    test("con tasa del día la línea queda y el teclado muestra los euros", async () => {
        const { screen, method, calls } = makeAddLineScreen({ eurRate: BS_PER_EUR });
        const result = await PaymentScreen.prototype.addNewPaymentLine.call(screen, method);
        expect(result).toBe(true);
        expect(calls.deleted).toEqual([]);
        expect(calls.dialogs).toEqual([]);
        expect(calls.buffer.at(-1)).toBe("126:8.47");
    });
});

// ---- Panel de estado y recibo ----

function tenderRemaining(order) {
    const getter = Object.getOwnPropertyDescriptor(
        PaymentScreenStatus.prototype,
        "tenderRemaining"
    ).get;
    return getter.call({
        props: { order },
        env: { utils: { formatCurrencyById: (amount, id) => `${id}:${amount}` } },
    });
}

function makeStatusOrder({ totalDue, remainingDue, currency = EUR }) {
    const line = {
        getTenderCurrency: () => currency,
        _getTenderRates: () => ({ toTender: 1 / BS_PER_EUR, toLocal: BS_PER_EUR }),
    };
    return {
        totalDue,
        remainingDue,
        getSelectedPaymentline: () => line,
        _convertAtRate: (v, r, c) => (!v || !r ? 0 : c.round(v * r)),
    };
}

describe("l10n_ve_pos restante en la moneda de cobro", () => {
    test("el restante de la caja convertido a euros", () => {
        const tender = tenderRemaining(makeStatusOrder({ totalDue: 8500, remainingDue: 8500 }));
        expect(tender).toEqual({ currencyName: "EUR", text: "126:8.47" });
    });

    test("en un reembolso, el restante en positivo", () => {
        const tender = tenderRemaining(makeStatusOrder({ totalDue: -8500, remainingDue: -8500 }));
        expect(tender.text).toBe("126:8.47");
    });

    test("pagado de más, el restante es 0", () => {
        const tender = tenderRemaining(makeStatusOrder({ totalDue: 8500, remainingDue: -100 }));
        expect(tender.text).toBe("126:0");
    });

    test("sin moneda de cobro en la línea seleccionada, nada", () => {
        expect(tenderRemaining(makeStatusOrder({ totalDue: 1, remainingDue: 1, currency: null }))).toBe(null);
    });
});

describe("l10n_ve_pos monto cobrado en el recibo", () => {
    const format = (line) => OrderReceipt.prototype.formatTenderAmount.call({}, line);

    test("un pago sin moneda de cobro no muestra nada", () => {
        expect(format({ getTenderCurrency: () => null })).toBe("");
        expect(format(undefined)).toBe("");
    });

    test("un pago en euros muestra lo cobrado en euros", () => {
        // formatCurrency lee la localización (separadores de es_VE).
        patchWithCleanup(localization, { decimalPoint: ",", thousandsSep: ".", grouping: [3, 0] });
        const text = format({ getTenderCurrency: () => EUR, getTenderAmount: () => 1008.47 });
        expect(text).toInclude("1.008,47");
    });
});
