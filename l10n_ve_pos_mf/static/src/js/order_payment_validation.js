import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

patch(OrderPaymentValidation.prototype, {
    async isOrderValid(isForceValidate) {
        const fdm = this.pos.useFiscalMachine();
        if (!fdm) {
            alert('No se ha detectado una máquina fiscal. Por favor, asegúrese de que esté conectada y configurada correctamente.');
            return false;
        }
        if (!this.order.is_refund) {
            try {
                const data = await this.get_data_invoice(this.order);
                data.iot_ip = data.iot_ip || this.pos.config.iot_ip;
                const response = await this._print_via_hardware(data);
                console.log('MF response:', response);
            } catch (err) {
                console.error('MF error:', err);
            }
            return super.isOrderValid(isForceValidate);
        }else{
            //PARA NOTAS DE CREDITO
        }
        console.log('Es una orden de devolución, genera nota de credito.');
    },

    async _print_via_hardware(data) {
        const fdm = this.pos.useFiscalMachine();
        if (!fdm) throw new Error("MF no disponible");

        const request_data = {
            action: `print_${data.type || 'out_invoice'}`,
            data: data,
        };

        return new Promise((resolve, reject) => {
            fdm.action(request_data).then(response => {
                console.log('MF action response:', response);
                resolve(response);
            }).catch(error => {
                console.log('MF action error:', error);
                reject({
                    valid: false,
                    message: error.statusText === "timeout"
                        ? "The tax machine did not respond in time"
                        : "Error with the tax machine",
                    printer_connection: false,
                });
            });
        });
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

        let uid = order.uid
        const values = Object.values(this.pos.toRefundLines || {})
        let lines = []
        for (let i = 0; i < values.length; i++) {
            if (values[i].destinationOrderUid == uid) {
                lines.push(values[i])
            }
        }

        invoice['type'] = 'out_invoice'
        if (order.get_total_with_tax() < 0) {
            invoice['type'] = 'out_refund'
        }
        if (lines.length > 0 && invoice['type'] == 'out_refund') {
            try {
                const orderUid = lines?.[0]?.orderline?.orderUid
                if (!orderUid) {
                    return { "valid": false, "message": "No se encontró la orden de origen para la devolución." }
                }
                const response = await this.pos.orm.call("pos.order", "get_order_by_uid", [[], orderUid])
                if (response.length > 0 && !this.pos.is_same_mf(response[0].fiscal_machine)) {
                    return { "valid": false, "message": `El documento fue impreso desde la Maquina ${response[0].fiscal_machine}` }
                }
                if (response.length > 0) {
                    const date = new Date(response[0].date_order);
                    const format_date = date.toLocaleDateString('es-ES');

                    invoice["invoice_affected"] = {
                        "number": response[0].mf_invoice_number,
                        "serial_machine": response[0].fiscal_machine,
                        "date": format_date,
                    }
                }
            } catch (err) {
                console.error("MF error: ", err)
                if (!err.valid) {
                    this.pos.dialog.add(AlertDialog, {
                        title: _t("MF error"),
                        body: _t(err.message ? err.message : "Internal MF error"),
                    });
                    return err
                }
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
