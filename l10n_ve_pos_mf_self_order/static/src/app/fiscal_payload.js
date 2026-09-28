/** @odoo-module */

import { roundPrecision as round_pr } from "@web/core/utils/numbers";

/**
 * Armado del payload fiscal para la máquina TFHKA desde una orden del Kiosko.
 *
 * Builder AUTOCONTENIDO (no reutiliza el `PosStore` de la caja, ni carga los
 * modelos de `l10n_ve_pos` en el bundle del Kiosko). Se justifica porque el
 * Kiosko es un subconjunto mucho más simple que la caja:
 *   - solo facturas (`out_invoice`): sin notas de crédito/débito,
 *   - sin descuento global (no hay botón de descuento en el Kiosko),
 *   - sin cajero (es desatendido),
 *   - las `payment_lines` se pasan EXPLÍCITAS (el pago se registra server-side,
 *     la orden del cliente no tiene `payment_ids` al imprimir).
 *
 * Produce EXACTAMENTE la misma forma que consume `TfhkaDriver.printInvoice`:
 *   { flag_21, has_cashbox, partner:{vat,name,address,phone},
 *     lines:[{price_unit,quantity,fiscal_code,product_code,product_name}],
 *     payment_lines:[{payment_method_code,amount}],
 *     header_lines:[], footer_lines:[], additional_lines:[] }
 *
 * Moneda: la TFHKA imprime en la moneda FISCAL (VES). Si la moneda base del PdV
 * ya es VES (`vef_base`), se usan los importes locales tal cual; si no, se
 * convierte a la foránea (VES) con `order.foreign_currency_rate` — el mismo
 * criterio que la caja (`localToForeign`), redondeando con la moneda foránea.
 * El precio de línea va NETO de descuento (el driver no recibe `discount`).
 */

/** Normaliza el nombre del producto: sin acentos ni caracteres especiales. */
export function normalizeProductName(text) {
    if (!text) {
        return "";
    }
    return String(text)
        .normalize("NFKD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/[^\w\s]/g, " ")
        .replace(/\s+/g, " ")
        .trim();
}

/** Extrae hasta 10 líneas de un texto de encabezado/pie de `pos.config`. */
function extractReceiptLines(rawText) {
    const source = String(rawText || "")
        .replace(/<[^>]*>/g, " ")
        .split("\n")
        .map((line) => line.replace(/\r/g, "").trim())
        .filter((line) => line.length > 0);
    return source.slice(0, 10).map((line) => line.substring(0, 127));
}

/**
 * @param {Object} order  registro pos.order del Kiosko (currentOrder)
 * @param {Object} ctx    { config, company, currency, paymentMethodCode, paymentAmount }
 * @returns {Object|{valid:false,message:string}}
 */
export function buildKioskFiscalPayload(order, ctx) {
    const { config, currency, paymentMethodCode, paymentAmount } = ctx;

    const partner = order.partner_id;
    if (!partner) {
        return { valid: false, message: "La orden del Kiosko no tiene cliente identificado" };
    }
    if (!paymentMethodCode) {
        return {
            valid: false,
            message: "El método de pago no tiene código fiscal (code_fiscal_printer) configurado",
        };
    }

    // ¿La moneda base ya es VES? Entonces no se convierte. Si no, se usa la
    // tasa foránea de la orden (misma que fija recompute_prices).
    const currencyName = (currency?.name || "").toUpperCase();
    const vefBase = currencyName === "VEF" || currencyName === "VES";
    const rate = Number(order.foreign_currency_rate || 0);
    const foreignCurrency = config.foreign_currency_id || currency;
    const rounding = (foreignCurrency && foreignCurrency.rounding) || currency?.rounding || 0.01;
    const toFiscal = (localAmount) =>
        round_pr(vefBase ? Number(localAmount || 0) : Number(localAmount || 0) * rate, rounding);

    if (!vefBase && !(rate > 0)) {
        return {
            valid: false,
            message: "No se pudo determinar la tasa de cambio de la orden para la máquina fiscal",
        };
    }

    // Líneas: precio NETO de descuento, en moneda fiscal (VES).
    const lines = [];
    const notes = [];
    for (const line of order.lines || []) {
        const qty = Math.abs(Number(line.qty || 0));
        if (!qty) {
            continue;
        }
        const discount = Number(line.getDiscount?.() ?? line.discount ?? 0);
        const netLocalUnit = Number(line.price_unit || 0) * (1 - discount / 100);
        const priceUnit = toFiscal(netLocalUnit);
        if (!(priceUnit > 0)) {
            continue;
        }
        const taxes = line.tax_ids || [];
        const fiscalCode =
            taxes.length > 0
                ? String(taxes[0]?.fiscal_code ?? "").replace(/^t/i, "") || "0"
                : "0";
        lines.push({
            price_unit: priceUnit,
            quantity: qty,
            fiscal_code: fiscalCode,
            product_code: line.product_id?.default_code || "",
            product_name: normalizeProductName(
                String(line.product_id?.display_name || "").replace(/^\[[^\]]*\]\s*/, "")
            ),
        });
        const note = line.customer_note || line.getCustomerNote?.() || "";
        if (note) {
            for (const noteLine of String(note).split("\n")) {
                if (noteLine.trim()) {
                    notes.push(noteLine.trim());
                }
            }
        }
    }

    if (!lines.length) {
        return { valid: false, message: "La orden no tiene líneas válidas para la máquina fiscal" };
    }

    // Pago: convertido a moneda fiscal (VES) con el MISMO `toFiscal()` que las
    // líneas. `paymentAmount` llega en la moneda BASE de la orden (suma de
    // `order.payment_ids[].amount`); si la base no es VES hay que convertirlo,
    // o el pago no cuadraría con el total de líneas en la máquina fiscal
    // (pago≠total). `toFiscal` no convierte cuando la base ya es VES.
    const payAmount = toFiscal(Math.abs(Number(paymentAmount || 0)));
    if (!(payAmount > 0)) {
        return { valid: false, message: "No hay un monto de pago válido para la máquina fiscal" };
    }

    // Referencia del pedido (el Kiosko no tiene cajero → sin OPERADOR).
    const additionalLines = [];
    const reference = order.pos_reference || order.uuid || order.tracking_number;
    if (reference) {
        additionalLines.push(`PEDIDO: ${reference}`);
    }
    additionalLines.push(...notes);

    return {
        valid: true,
        flag_21: config.flag_21 || "00",
        // El Kiosko no cobra en efectivo → no se abre gaveta.
        has_cashbox: false,
        partner: {
            vat: `${partner.prefix_vat || ""}${partner.vat || ""}`,
            name: normalizeProductName(partner.name),
            address: partner.street || false,
            phone: partner.phone || partner.mobile || false,
        },
        lines,
        payment_lines: [{ payment_method_code: paymentMethodCode, amount: payAmount }],
        header_lines: extractReceiptLines(config.receipt_header),
        footer_lines: extractReceiptLines(config.receipt_footer),
        additional_lines: additionalLines,
    };
}
