/** @odoo-module */

/**
 * LocalOrderHistory - Historial local de pedidos fiscales impresos.
 *
 * Guarda metadata minima por pedido para soportar reembolsos offline:
 * - uid
 * - datos fiscales (serial, nro fiscal, reporte Z)
 * - fecha
 * - metodos de pago usados
 */
export class LocalOrderHistory {
    static STORAGE_KEY = "l10n_ve_pos_mf_printed_orders_history";
    static MAX_HISTORY_SIZE = 200;

    static add(order) {
        const history = this.getAll();
        const uid = order.uid;

        const existingIndex = history.findIndex((entry) => entry.uid === uid);
        if (existingIndex !== -1) {
            history.splice(existingIndex, 1);
        }

        if (history.length >= this.MAX_HISTORY_SIZE) {
            history.shift();
        }

        const paymentLines =
            order.payment_lines ||
            (order.paymentlines || []).map((paymentLine) => ({
                amount: paymentLine.amount,
                payment_method_code: paymentLine.payment_method?.code_fiscal_printer || false,
                payment_method_name: paymentLine.payment_method?.name || "",
            }));

        const dateOrder =
            order.date_order ||
            order.validation_date ||
            new Date().toISOString();

        history.push({
            uid,
            date_order: dateOrder,
            fiscal_machine: order.fiscal_machine || "",
            mf_invoice_number: order.mf_invoice_number || "",
            mf_reportz: order.mf_reportz || "",
            payment_lines: paymentLines,
        });

        try {
            localStorage.setItem(this.STORAGE_KEY, JSON.stringify(history));
        } catch (error) {
            console.error("LocalOrderHistory:: Error saving local history", error);
        }
    }

    static getAll() {
        try {
            const raw = localStorage.getItem(this.STORAGE_KEY);
            return raw ? JSON.parse(raw) : [];
        } catch {
            return [];
        }
    }

    static getByUid(uid) {
        const history = this.getAll();
        return history.find((entry) => entry.uid === uid) || null;
    }
}
