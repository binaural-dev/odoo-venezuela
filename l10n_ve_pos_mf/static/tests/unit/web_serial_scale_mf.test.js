import { advanceTime, describe, expect, test, tick } from "@odoo/hoot";
import { toRaw } from "@odoo/owl";
import { patchWithCleanup } from "@web/../tests/web_test_helpers";
import { WebSerialScaleInterface } from "@point_of_sale/app/utils/scale/web_serial_scale_interface";
import "@l10n_ve_pos_mf/overrides/WebSerialScaleInterface";

const MF_VENDOR_ID = 0x067b;
const MF_PRODUCT_ID = 0x2303;

/**
 * Puerto Web Serial falso. Como el real, `readable` y `writable` son null
 * hasta abrirlo. `reply` decide qué contesta el equipo a cada escritura; si
 * devuelve null el equipo no contesta, como la máquina fiscal ante "Ehello".
 */
class FakePort {
    constructor({ vendorId = 0x1a86, productId = 0x7523, reply = () => null } = {}) {
        this.connected = true;
        this.isOpen = false;
        this.readable = null;
        this.writable = null;
        this.written = [];
        this.info = { usbVendorId: vendorId, usbProductId: productId };
        this.reply = reply;
    }

    getInfo() {
        return this.info;
    }

    async open(options) {
        this.options = options;
        this.isOpen = true;
        let controller;
        this.readable = new ReadableStream({
            start: (c) => {
                controller = c;
            },
        });
        this.writable = new WritableStream({
            write: (chunk) => {
                const message = new TextDecoder().decode(chunk);
                this.written.push(message);
                const answer = this.reply(message);
                if (answer) {
                    controller.enqueue(new TextEncoder().encode(answer));
                }
            },
        });
    }

    async close() {
        this.isOpen = false;
        this.readable = null;
        this.writable = null;
    }
}

const fiscalPrinterPort = () => new FakePort({ vendorId: MF_VENDOR_ID, productId: MF_PRODUCT_ID });

/** Balanza que habla el protocolo de `WebSerialScale` (eco "hello" y "F"). */
const scalePort = () =>
    new FakePort({
        reply: (message) => ({ Ehello: "\x02E\rhello", F: "F" })[message] ?? null,
    });

function authorizePorts(...ports) {
    patchWithCleanup(navigator, { serial: { getPorts: async () => ports } });
}

function saveFiscalPrinterIdentity() {
    localStorage.setItem(
        "fiscal_printer_device",
        JSON.stringify({ usbVendorId: MF_VENDOR_ID, usbProductId: MF_PRODUCT_ID })
    );
}

const makeScaleInterface = () => new WebSerialScaleInterface({ env: {} });

describe("l10n_ve_pos_mf: balanza Web Serial y máquina fiscal", () => {
    test("la máquina fiscal guardada no se sondea como balanza", async () => {
        const mf = fiscalPrinterPort();
        authorizePorts(mf);
        saveFiscalPrinterIdentity();

        await expect(makeScaleInterface().connectToScale()).resolves.toBe(false);
        expect(mf.isOpen).toBe(false);
        expect(mf.written).toEqual([]);
    });

    test("un puerto que no contesta no impide abrir el POS y queda cerrado", async () => {
        // Sin identidad guardada (la MF autorizada pero nunca verificada).
        const mf = fiscalPrinterPort();
        authorizePorts(mf);
        patchWithCleanup(console, { warn: (message) => expect.step(message) });

        const connecting = makeScaleInterface().connectToScale();
        await tick();
        // El sondeo de Odoo espera el eco 1000 ms y luego lanza.
        await advanceTime(1000);

        await expect(connecting).resolves.toBe(false);
        expect(mf.written).toEqual(["Ehello"]);
        expect(mf.isOpen).toBe(false);
        expect.verifySteps(["l10n_ve_pos_mf:: el puerto serie no respondió como balanza, se cierra"]);
    });

    test("con la máquina fiscal conectada la balanza se sigue detectando", async () => {
        const mf = fiscalPrinterPort();
        const scale = scalePort();
        authorizePorts(mf, scale);
        saveFiscalPrinterIdentity();

        const scaleInterface = makeScaleInterface();
        await expect(scaleInterface.connectToScale()).resolves.toBe(true);
        // ScaleInterface es reactivo: lo que se lee de él viene envuelto.
        expect(toRaw(scaleInterface.scale._serialPort)).toBe(scale);
        expect(scale.options).toEqual({ baudRate: 9600, stopBits: 1, parity: "even" });
        expect(mf.isOpen).toBe(false);
        expect(mf.written).toEqual([]);
    });

    test("un puerto ya abierto en la página no se toca", async () => {
        const busy = new FakePort();
        await busy.open({ baudRate: 9600 });
        authorizePorts(busy);

        await expect(makeScaleInterface().connectToScale()).resolves.toBe(false);
        expect(busy.isOpen).toBe(true);
        expect(busy.written).toEqual([]);
    });

    test("los puertos desconectados se ignoran", async () => {
        const unplugged = scalePort();
        unplugged.connected = false;
        authorizePorts(unplugged);

        await expect(makeScaleInterface().connectToScale()).resolves.toBe(false);
        expect(unplugged.isOpen).toBe(false);
    });
});
