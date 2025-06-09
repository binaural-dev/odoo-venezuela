/** @odoo-module **/

import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { ReprintInvoiceButton } from "./ReprintInvoiceButton";

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
        console.log("RESPONSE", response)
        if (!this.is_same_mf(response[0].fiscal_machine)) {
          return { "valid": false, "message": `El documento fue impreso desde la Maquina ${response[0].fiscal_machine}` }
        }
        if (response.length > 0) {
          invoice["invoice_affected"] = {
            "number": response[0].mf_invoice_number,
            "serial_machine": response[0].fiscal_machine,
            "date": response[0].date_order,
          }
        }
      } catch (e) {
      }
    }

    if (order.orderlines.length > 0) {

      let vef_base = this.currency.name === "VEF"

      invoice['invoice_lines'] = order.orderlines.map((el) => {

        if (!!el.customerNote) {
          let split = el.customerNote.split("\n")
          for (let i = 0; i < split.length; i++) {
            invoice["info"].push(`${split[i]}`)
          }
        }


        let amount = vef_base ? el.price : el.get_foreign_unit_price()

        return {
          price_unit: amount,
          discount: el.get_discount(),
          quantity: Math.abs(el.quantity),
          name: this.normalizeProductName(el.product.display_name),
          code: el.product.default_code,
          tax: el.get_taxes().length > 0 ? el.get_taxes()[0]['fiscal_code'] : 0
        }
      })
      invoice['payment_lines'] = order.paymentlines.map((el) => {

        let amount = vef_base ? el.amount : el.get_foreign_amount()
        return {
          payment_method: el.payment_method.code_fiscal_printer,
          amount: amount,
        }
      })
    }
    invoice["valid"] = true
    console.log("INvoice", invoice)
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
  
  async print_out_invoice(data) {
    
    const fdm = this.useFiscalMachine();

    if (!fdm) {
      return reject({ "valid": false, "message": "No se ha configurado una maquina fiscal", })
    }
    const request_data = {
      action: `print_${data.type}`,
      data: data,
    }

    return new Promise(async (resolve, reject) => {

      const listener = (data) => {

        if (data.request_data.action === request_data.action) {          
          if (data.status.status === "connected") {
            if (data.value && data.value.message === "No se ha completado") {
                return;
            }
            fdm.removeListener(listener);
            return resolve(data);
          } else {
            fdm.removeListener(listener);
            return reject(data);
          }
        }
      };

      fdm.addListener(listener);
      
      try {
        const response = await fdm.action(request_data);

        if (!response.result) {            
          fdm.removeListener(listener);            
          reject({  
            valid: false,
            message: _t("Error connecting to the fiscal machine, check if it is turned on or connected to the IoT"),
            printer_connection: false
          });
        }
      } catch (error) {

        fdm.removeListener(listener);
        reject({
            valid: false,
            message: error.statusText === "timeout" 
                ? _t("The tax machine did not respond in time")
                : _t("Error with the tax machine"),
            printer_connection: false
        });
      }
    });
  },

  set_data_from_fiscal_machine(order, data) {
    order.fiscal_machine = data["serial_machine"] || false;
    order.mf_invoice_number = data["sequence"] || false;
    order.mf_reportz = data["mf_reportz"] || false;
  },

  async pushToMF(order) {
    try {      
      let data = await this.get_data_invoice(order)
      if (!data["valid"]) {
        throw data["message"]
      }

      const response = await this.print_out_invoice(data)
      const { value } = response
      
      if (!value.valid) {
        throw value
      }

      this.set_data_from_fiscal_machine(order, value)
      
      return {  
        valid: true,
        message: "",
        printer_connection: true
      }
    
    } catch (err) {

      if (!err.valid) { 
        this.env.services.popup.add(ErrorPopup, {
          title: _t("MF error"),
          body: _t(err.message ? err.message : "Internal MF error"),
        });
        
        return err
      
      } else {
        this.env.services.popup.add(ErrorPopup, {
          title: _t("MF error"),
          body: _t(err.status ? err.status : "Internal MF error"),
        });
        return err;
      }
    }
  },
  async push_single_order(order, opts) {
    if (this.useFiscalMachine() && !order.mf_invoice_number) {
      
      const response = await this.pushToMF(order)

      if (response.printer_connection === false) {
        return
      }

    }
    return await super.push_single_order.apply(this, [order, opts]);
  },
})
