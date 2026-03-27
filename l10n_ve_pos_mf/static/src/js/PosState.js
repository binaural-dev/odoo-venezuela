/** @odoo-module **/

import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { ReprintInvoiceButton } from "./ReprintInvoiceButton";
import {
  roundDecimals as round_di,
  roundPrecision as round_pr,
  floatIsZero,
} from "@web/core/utils/numbers";

patch(TicketScreen, {
  components: {
    ...TicketScreen.components,
    ReprintInvoiceButton
  },
});

patch(PosStore.prototype, {
  open_cashbox() {
    if (this.useFiscalMachine() && this.config.has_cashbox) {
    const fdm = this.useFiscalMachine();
      fdm.action({
        action: `logger`,
        data: "0",
      })
    } else {
      return super.open_cashbox(...arguments);
    }
  },

  useFiscalMachine() {
    return this.hardwareProxy.deviceControllers.fiscal_data_module
  },
  get currentOrder() {
    return this.get_order();
  },

  aditionalInfo() {
    let res = []
    res.push(`OPERADOR: ${this.get_cashier().name}`)
    res.push(`PEDIDO: ${this.get_order().uid}`)
    return res
  },
  get get_flag_21() {
    return this.config.flag_21
  },
  get get_traditional_line() {
    return this.config.traditional_line
  },
  get has_cashbox() {
    return this.config.has_cashbox
  },

  is_same_mf(serial) {
    return true
  },
  async get_data_invoice(order) {
    let invoice = {
      company_id: {
        name: this.company.name,
      },
      flag_21: this.get_flag_21,
      traditional_line: this.get_traditional_line,
      has_cashbox: this.has_cashbox && order.is_paid_with_cash(),
      time: Date.now(),
    }
    if (order.get_partner()) {

      invoice['partner_id'] = {}
      let client = order.get_partner()

      invoice['partner_id']['vat'] = client.prefix_vat + client.vat
      invoice['partner_id']['name'] = this.normalizeProductName(client.name)
      invoice['partner_id']['address'] = client.address || false
      invoice['partner_id']['phone'] = client.phone || false
    }

    invoice["info"] = this.aditionalInfo()

    let uid = order.uid
    const values = Object.values(this.toRefundLines)
    let lines = []
    //BUSCAR EL ORDEN 
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
        const response = await this.orm.call("pos.order", "get_order_by_uid", [[], lines[0].orderline.orderUid])
        if (!this.is_same_mf(response[0].fiscal_machine)) {
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
          this.env.services.popup.add(ErrorPopup, {
            title: _t("MF error"),
            body: _t(err.message ? err.message : "Internal MF error"),
          });
          return err
        }
      }
    }

    if (order.orderlines.length > 0) {

      let vef_base = this.currency.name === "VEF"

      let rounding = vef_base ? this.currency.rounding : this.foreign_currency.rounding

      invoice['invoice_lines'] = order.orderlines.map((el) => {

        if (!!el.customerNote) {
          let split = el.customerNote.split("\n")
          for (let i = 0; i < split.length; i++) {
            invoice["info"].push(`${split[i]}`)
          }
        }

        let amount = vef_base ? el.price : el.get_foreign_unit_price()

        let discount = el.get_discount()
        if (discount > 0) {
          amount = round_pr(amount * (1 - discount / 100), rounding)
        }
        return {
          price_unit: amount,
          discount: discount,
          quantity: Math.abs(el.quantity),
          name: this.normalizeProductName(el.product.display_name),
          code: el.product.default_code,
          tax: el.get_taxes().length > 0 ? el.get_taxes()[0]['fiscal_code'] : 0
        }
      })

      let tax_rates_by_code = {};
      order.orderlines.forEach((el) => {
        let taxes = el.get_taxes();
        if (taxes.length > 0) {
          let code = taxes[0]['fiscal_code'];
          if (!(code in tax_rates_by_code)) {
            tax_rates_by_code[code] = taxes[0].amount / 100;
          }
        }
      });

      let fiscal_bases = {};
      invoice['invoice_lines'].forEach((line) => {
        let code = line.tax;
        if (!fiscal_bases[code]) fiscal_bases[code] = 0;
        fiscal_bases[code] += round_pr(line.price_unit * line.quantity, rounding);
      });

      let fiscal_total = 0;
      for (let code in fiscal_bases) {
        let base = round_pr(fiscal_bases[code], rounding);
        fiscal_total += base + round_pr(base * (tax_rates_by_code[code] || 0), rounding);
      }
      fiscal_total = round_pr(fiscal_total, rounding);

      invoice['payment_lines'] = order.paymentlines
        .filter((el) => {
          let amount = vef_base ? el.amount : el.get_foreign_amount()
          return !floatIsZero(amount, this.currency.decimal_places) && amount > 0
        })
        .map((el) => {
          let amount = vef_base ? el.amount : el.get_foreign_amount()
          return {
            payment_method: el.payment_method.code_fiscal_printer,
            amount: round_pr(amount, rounding),
          }
        })

      let payment_sum = invoice['payment_lines'].reduce((s, l) => s + l.amount, 0);
      let diff = round_pr(fiscal_total - payment_sum, rounding);
      if (!floatIsZero(diff, vef_base ? this.currency.decimal_places : this.foreign_currency.decimal_places) && invoice['payment_lines'].length > 0) {
        let last = invoice['payment_lines'][invoice['payment_lines'].length - 1];
        last.amount = round_pr(last.amount + diff, rounding);

        order.fiscal_foreign_total = fiscal_total;

        let actual_payments = order.paymentlines.filter(el => {
          let amt = vef_base ? el.amount : el.get_foreign_amount();
          return !floatIsZero(amt, this.currency.decimal_places) && amt > 0;
        });
        if (actual_payments.length > 0) {
          let last_pay = actual_payments[actual_payments.length - 1];
          if (vef_base) {
            last_pay.amount = round_pr(last_pay.amount + diff, rounding);
          } else {
            last_pay.foreign_amount = round_pr(last_pay.get_foreign_amount() + diff, rounding);
          }
        }
      }
    }
    invoice["valid"] = true
    return invoice
  },

  normalizeProductName(text) {
    if (!text) return "";

    const normalized = text.normalize("NFKD");
    const noSpecialChars = normalized
        .replace(/[\u0300-\u036f]/g, "")  
        .replace(/[^\w\s]/g, " ")
        .replace(/\s+/g, " ")
        .trim();

    return noSpecialChars;
  },

  async print_document(print_type, data) {
    try {
      const deviceResponse = await this.device_response(print_type, data);

      if (print_type == "print_invoice" && !deviceResponse?.valid) {
        return { "valid": false, "message": deviceResponse?.message || "Error al imprimir" }
      }
      return deviceResponse;

    } catch (err) {
        console.error("MF error: ", err)
        if (!err.valid) { 
          this.env.services.popup.add(ErrorPopup, {
            title: _t("MF error"),
            body: _t(err.message ? err.message : "Internal MF error"),
          });
          return { valid: false, message: "Error interno al imprimir documento"};
        }
    }
  },

  async device_response(action, data) {
    return new Promise((resolve, reject) => {
      const fdm = this.useFiscalMachine();

      if (!fdm) {
        return reject({ "valid": false, "message": "No se ha configurado una maquina fiscal", })
      }
      const listener = ({value}) => {
        fdm.removeListener(listener);
        resolve(value);
      };
  
      fdm.addListener(listener);
  
      fdm.action({
        action: action,
        data: data,
      }).catch(reject);
    });
  },

  set_data_from_fiscal_machine(order, values) {
    const data = values?.data ?? {};
    const sequence = data.sequence;
    const serial_machine = data.serial_machine;
    const mf_reportz = data.mf_reportz;
    order.fiscal_machine = serial_machine || false;
    order.mf_invoice_number = sequence || false;
    order.mf_reportz = mf_reportz || false;
  },

  async pushToMF(order) {
    try {      
      let data = await this.get_data_invoice(order)
      if (!data["valid"]) {
        throw data["message"]
      }

      const response = await this.print_document(`print_${data.type}`, data)

      if (!response?.valid) {
        throw response
      }

      this.set_data_from_fiscal_machine(order, response)
      
      return {  
        valid: true,
        message: "",
        printer_connection: true
      }
    
    } catch (err) {
      console.error("MF error: ", err)
      if (!err.valid) { 
        this.env.services.popup.add(ErrorPopup, {
          title: _t("MF error"),
          body: _t(err.message ? err.message : "Internal MF error"),
        });
        return err
      }
    }
  },
  async push_single_order(order, opts) {
    if (this.useFiscalMachine() && !order.mf_invoice_number) {
      
      const response = await this.pushToMF(order)

    if (response.printer_connection == false || !("printer_connection" in response)) {
      return
    }

    }
    return await super.push_single_order.apply(this, [order, opts]);
  },
})
