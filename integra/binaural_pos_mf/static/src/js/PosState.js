odoo.define("binaural_pos_mf.PosState", function(require) {
  "use strict";

  const { PosGlobalState } = require("point_of_sale.models");
  const Registries = require("point_of_sale.Registries");

  const BinauralPosState = (PosGlobalState) =>
    class BinauralPosState extends PosGlobalState {
      constructor() {
        super(...arguments);
      }
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
      };

      useFiscalMachine() {
        return this.env.proxy.iot_device_proxies["fiscal_data_module"];
      }
      get currentOrder() {
        return this.get_order();
      }

      aditionalInfo() {
        let res = []
        res.push(`OPERADOR: ${this.env.pos.get_cashier().name}`)
        res.push(`PEDIDO: ${this.env.pos.get_order().uid}`)
        return res
      }
      get get_flag_21() {
        return this.config.flag_21
      }
      get get_traditional_line() {
        return this.config.traditional_line
      }
      get has_cashbox() {
        return this.config.has_cashbox
      }

      is_same_mf(serial) {
        return true
      }
      async get_data_invoice(order) {
        const currency = { symbol: 'Bs', position: 'after', rounding: 0.01, decimals: 2 };


        let invoice = {
          company_id: {
            name: this.company.name,
          },
          flag_21: this.get_flag_21,
          traditional_line: this.get_traditional_line,
          has_cashbox: this.has_cashbox && order.is_paid_with_cash(),
        }
        if (order.get_partner()) {

          invoice['partner_id'] = {}
          let client = order.get_partner()

          invoice['partner_id']['vat'] = client.prefix_vat + client.vat
          invoice['partner_id']['name'] = client.name
          invoice['partner_id']['address'] = client.address || false
          invoice['partner_id']['phone'] = client.phone || false
        }

        invoice["info"] = this.aditionalInfo()

        let uid = order.uid
        const values = Object.values(this.env.pos.toRefundLines)
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
            let response = await this.env.services.rpc({
              model: 'pos.order',
              method: 'get_order_by_uid',
              args: [[], lines[0].orderline.orderUid],
              kwargs: {},
            })
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
              name: el.product.display_name,
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
        return invoice
      }
      async print_out_invoice(data) {
        const fdm = this.useFiscalMachine();
        if (!fdm) {
          return reject({ "valid": false, "message": "No se ha configurado una maquina fiscal", })
        }
        return new Promise(async (resolve, reject) => {
          try {
            let response = await fdm.action({
              action: `print_${data.type}`,
              data: data,
            })
            if (!response) {
              return reject({ "valid": false, "message": "No se ha podido establecer conexion con la Maquina Fiscal", })
            }

            if (!response["result"]) {
              return reject({ "valid": false, "message": "No se ha podido establecer conexion con la Maquina Fiscal", })
            }

            fdm.add_listener((iot_response) => {
              fdm.remove_listener();
              let { value, status } = iot_response
              if (!!status && status.status == "error") {
                reject({ valid: false, message: status.message_body })
              }
              if (!!value.valid) {
                resolve(value)
              } else {
                reject(value)
              }
            })
          } catch (err) {
            reject({ "valid": false, "message": "No se ha podido establecer conexion con la Maquina Fiscal", })
          }
        })
      }
      set_data_from_fiscal_machine(order, data) {
        order.fiscal_machine = data["serial_machine"] || false;
        order.mf_invoice_number = data["sequence"] || false;
      }
      async push_single_order(order, opts) {
        if (!(this.useFiscalMachine() && order && !order.to_receipt && !order.mf_invoice_number)) {
          return await super.push_single_order(...arguments);
        }
        let valid = true
        try {
          this.env.services.ui.block()
          let data = await this.get_data_invoice(order)
          if (!data["valid"]) {
            throw new Error(data["message"])
          }
          const response = await this.print_out_invoice(data)
          this.env.services.ui.unblock()
          if (!response.valid) {
            throw new Error(response["message"])
          }
          this.set_data_from_fiscal_machine(order, response)
        } catch (err) {
          this.env.services.ui.unblock()
          valid = false
          return Promise.reject({
            code: 701,
            error: {
              errorMessage: err.message,
              errorCode: "400"
            }
          });
        } finally {
          this.env.services.ui.unblock()
          if (valid) {
            return await super.push_single_order(...arguments);
          }
        }
      }
    };
  Registries.Model.extend(PosGlobalState, BinauralPosState);
})
