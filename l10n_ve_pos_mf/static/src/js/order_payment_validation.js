import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

patch(OrderPaymentValidation.prototype, {
    
    shouldDownloadInvoice() {
        if (this.pos.useFiscalMachine()) return false;
        return super.shouldDownloadInvoice();
    },

    async isOrderValid(isForceValidate) {
        const fdm = this.pos.useFiscalMachine();
        if (!fdm) {
            alert('No se ha detectado una máquina fiscal. Por favor, asegúrese de que esté conectada y configurada correctamente.');
            return false;
        }
        this._try_print_invoice(this.order);
        return super.isOrderValid(isForceValidate);
    },

    async _try_print_invoice(order) {
        try {
            const data = await this.get_data_invoice(order);
            if (!data?.valid) {
                this.pos.dialog.add(AlertDialog, {
                    title: _t("MF error"),
                    body: _t(data?.message || "No se pudo construir la factura fiscal"),
                });
                return;
            }
            data.iot_ip = data.iot_ip || this.pos.config.iot_ip;
            this.pos._print_via_server_proxy(data).then(response => {
                console.log('MF proxy response:', response);
            }).catch(err => {
                console.error('MF proxy error:', err);
            });
        } catch (err) {
            console.error('MF error building data:', err);
        }
    },

    async get_data_invoice(order) {
        let invoice = {
            company_id: {
                name: this.pos.company.name,
            },
            info: [],
            flag_21: this.pos.config.flag_21,
            traditional_line: this.pos.get_traditional_line,
            has_cashbox: this.pos.config.has_cashbox && order.is_paid_with_cash(),
            time: Date.now(),
            iot_ip: this.pos.config.iot_ip,
        }
        if (order.partner_id) {
            invoice['partner_id'] = {}
            let client = order.partner_id
            invoice['partner_id']['vat'] = `${client.prefix_vat || ""}${client.vat || ""}`
            invoice['partner_id']['name'] = client.name || "CONSUMIDOR FINAL"
            invoice['partner_id']['address'] = client.address || ""
            invoice['partner_id']['phone'] = client.phone || ""
        }

        invoice["info"] = this.pos.aditionalInfo()
        invoice["order_uuid"] = order?.uuid || order?.uid || false

        invoice['type'] = 'out_invoice'
        if (order.is_refund || order.get_total_with_tax() < 0) {
            invoice['type'] = 'out_refund'
            try {
                const originalOrder = this.pos.selectedOrderData;

                let serialMachine = originalOrder?.fiscal_machine;
                let invoiceNumber = originalOrder?.mf_invoice_number;
                let orderDate = originalOrder?.date_order;
                console.log("Original order data for refund:", { serialMachine, invoiceNumber, orderDate });
                if ((!serialMachine || !invoiceNumber) && originalOrder?.id) {
                    const response = await this.pos.orm.call("pos.order", "search_read", [
                        [["id", "=", originalOrder.id]],
                        ["fiscal_machine", "mf_invoice_number", "date_order"],
                    ]);
                    if (response.length > 0) {
                        serialMachine = response[0].fiscal_machine;
                        invoiceNumber = response[0].mf_invoice_number;
                        orderDate = response[0].date_order;
                    }
                }
                
                if (!serialMachine || !invoiceNumber) {
                    return { "valid": false, "message": "No se encontró la orden fiscal original para la devolución." }
                }

                if (!this.pos.is_same_mf(serialMachine)) {
                    return { "valid": false, "message": `El documento fue impreso desde la Maquina ${serialMachine}` }
                }

                const date = orderDate ? new Date(orderDate) : new Date();
                const formattedDate = Number.isNaN(date.getTime())
                    ? new Date().toLocaleDateString('es-ES')
                    : date.toLocaleDateString('es-ES');

                invoice["invoice_affected"] = {
                    "number": invoiceNumber,
                    "serial_machine": serialMachine,
                    "date": formattedDate,
                }
            } catch (err) {
                console.error("MF error: ", err)
                return { "valid": false, "message": err?.message || "Internal MF error" }
            }
        }
        if (order.lines.length > 0) {
            let vef_base = this.pos.currency.name === "VEF"

            invoice['invoice_lines'] = order.lines.map((el) => {

                if (!!el.customer_note) {
                    let split = el.customer_note.split("\n")
                    for (let i = 0; i < split.length; i++) {
                        invoice["info"].push(`${split[i]}`)
                    }
                }

                let amount = vef_base
                    ? el.product_id.lst_price
                    : (typeof el.get_foreign_unit_price === 'function' ? el.get_foreign_unit_price() : el.price_unit)
                const firstTax = el.tax_ids?.[0];
                let taxCode = 0;
                if (typeof firstTax === "number") {
                    const taxRecord = this.pos.models["account.tax"]?.getBy?.("id", firstTax);
                    taxCode = taxRecord?.fiscal_code ?? taxRecord?.raw?.fiscal_code ?? 0;
                } else if (firstTax) {
                    taxCode = firstTax.fiscal_code ?? firstTax.raw?.fiscal_code ?? 0;
                }
                return {
                    price_unit: amount,
                    quantity: Math.abs(el.qty),
                    name: el.product_id.display_name,
                    code: el.product_id.default_code,
                    tax: taxCode,
                }
            })
            invoice['payment_lines'] = (order.payment_ids || []).map((el) => {

                let amount = vef_base
                    ? el.amount
                    : (typeof el.get_foreign_amount === 'function' ? el.get_foreign_amount() : el.amount)
                return {
                    payment_method: String(el.payment_method_id?.code_fiscal_printer || "01"),
                    amount: Number(amount || 0),
                }
            })
        }
        invoice["valid"] = true
        return invoice
    },
});
