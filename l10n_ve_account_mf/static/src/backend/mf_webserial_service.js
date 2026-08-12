/** @odoo-module **/

import { TfhkaDriver } from "@l10n_ve_mf_base/drivers/TfhkaDriver";

/**
 * Singleton del driver fiscal Web Serial para el backend (Facturación/Contabilidad).
 *
 * Se comparte a nivel de pestaña del navegador (window) para no pedir el puerto
 * en cada click. El puerto queda con lock exclusivo mientras la pestaña viva.
 */
export function getBackendFiscalPrinter() {
    if (!window.mfWebSerialDriver) {
        window.mfWebSerialDriver = new TfhkaDriver();
    }
    return window.mfWebSerialDriver;
}

/**
 * Garantiza que el driver esté conectado y respondiendo.
 * Si no hay puerto autorizado, dispara el prompt de Web Serial
 * (debe invocarse desde un gesto de usuario, ej. click).
 *
 * @param {TfhkaDriver} driver
 * @returns {Promise<boolean>}
 */
export async function ensureConnected(driver) {
    if (driver.isConnected) {
        const status = await driver.getStatus();
        if (status) {
            return true;
        }
        // La conexión quedó zombie (cable desconectado, etc.)
        driver.isConnected = false;
        try {
            await driver.disconnect();
        } catch (e) {
            // noop: el puerto pudo haberse perdido físicamente
        }
    }
    // Primero reconexión silenciosa con puerto autorizado; si no hay
    // puerto autorizado, disparar el prompt de selección (fix del bug v17:
    // el backend nunca podía autorizar un puerto por primera vez).
    const connected = await driver.connect();
    if (connected) {
        return true;
    }
    return await driver.connect({ requestPermission: true });
}

/**
 * Adapta el payload que generan los métodos `check_*` de `account.move`
 * (formato heredado del flujo IoT) al formato de orden que espera TfhkaDriver.
 *
 * Payload backend (IoT legacy):
 *   { flag_21, company_id, partner_id: {name, vat, address, phone},
 *     invoice_lines: [{tax, price_unit, quantity, code, name}],
 *     payment_lines: [{amount, payment_method}],
 *     invoice_affected?: {number, serial_machine, date} }
 *
 * Orden TfhkaDriver:
 *   { flag_21, partner: {vat, name, address, phone},
 *     lines: [{price_unit, quantity, fiscal_code, product_code, product_name}],
 *     payment_lines: [{amount, payment_method_code}],
 *     invoice_affected? }
 *
 * @param {Object} payload
 * @returns {Object}
 */
export function toDriverOrder(payload) {
    const lines = (payload.invoice_lines || []).map((line) => ({
        price_unit: Number(line.price_unit || 0),
        quantity: Number(line.quantity || 1),
        fiscal_code: String(line.tax ?? "0").replace(/^t/i, "") || "0",
        product_code: line.code || "",
        product_name: line.name || "PRODUCTO",
    }));

    const payments = (payload.payment_lines || []).map((payment) => ({
        amount: Math.abs(Number(payment.amount || 0)),
        payment_method_code: String(payment.payment_method || "01").padStart(2, "0"),
    }));

    // `payload.info`: líneas informativas opcionales devueltas por
    // check_print_out_invoice/refund/debit_note (ej. NUMERO DE CONTROL,
    // REFERENCIA, tasa del día) usadas por customizaciones de cliente
    // (ej. solumedica_mf). En el flujo IoT legado estas líneas viajaban
    // dentro del payload hacia el IoT Box y el SDK Python las imprimía
    // como líneas "iXX". En Web Serial el navegador debe reenviarlas
    // explícitamente como additional_lines para que el driver las envíe.
    const additionalLines = Array.isArray(payload.info)
        ? payload.info.filter((line) => !!line).map((line) => String(line))
        : [];

    return {
        flag_21: String(payload.flag_21 || "00"),
        partner: {
            vat: payload.partner_id?.vat || "",
            name: payload.partner_id?.name || "",
            address: payload.partner_id?.address || "",
            phone: payload.partner_id?.phone || "",
        },
        lines,
        payment_lines: payments,
        invoice_affected: payload.invoice_affected || null,
        // En backend no manejamos gaveta ni líneas de encabezado/pie de POS
        has_cashbox: false,
        header_lines: [],
        footer_lines: [],
        additional_lines: additionalLines,
    };
}

/**
 * Convierte la respuesta del driver Web Serial al contrato que esperan
 * los métodos `print_out_*` de `account.move` (heredado del flujo IoT).
 *
 * @param {Object} response - Respuesta de TfhkaDriver (_buildFiscalResponse)
 * @returns {Object} - { valid, data: { sequence, serial_machine, mf_reportz } }
 */
export function toBackendValues(response) {
    return {
        valid: Boolean(response.success),
        data: {
            sequence: String(response.invoiceNumber || response.invoice_number || ""),
            serial_machine: response.serial_machine || response.serial || "",
            mf_reportz: response.mf_reportz || response.reportZ || "",
        },
    };
}
