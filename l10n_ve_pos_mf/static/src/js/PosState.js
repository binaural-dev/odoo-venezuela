odoo.define("l10n_ve_pos_mf.PosState", function(require) {
  "use strict";

  const { PosGlobalState } = require("point_of_sale.models");
  const Registries = require("point_of_sale.Registries");
  const core = require('web.core');
  const { Gui } = require('point_of_sale.Gui');
  const _t = core._t;

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
          time: Date.now(),
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
          let message_in_head = this.env.pos.config.message_in_head
              
            if (!!el.customerNote && message_in_head) {
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
        const request_data = {
          action: `print_${data.type}`,
          data: data,
        }
        return new Promise(async (resolve, reject) => {
          fdm.add_listener(data => {
            if (JSON.stringify(request_data) == JSON.stringify(data.request_data)) {
              if (data.status.status === "connected") {
                fdm.remove_listener();
                return resolve(data)
              } else {
                fdm.remove_listener();
                return reject(data)
              }
            }
          });
          await fdm.action({
            action: `print_${data.type}`,
            data: data,
          }).then((data) => {
            if (!data.result) {
              reject({
                "valid": false,
                "message": "Ha ocurrido un error con la conexion a la maquina fiscal, verifique si esta encendida o conectada al IoT"
              })
            }
          }).catch((data) => {
            if (data.statusText != "timeout") {
              reject({ "valid": false, "message": "Ha ocurrido un error con la maquina fiscal" })
            }
          })
          // fdm.remove_listener();
        })
      }
      set_data_from_fiscal_machine(order, data) {
        order.fiscal_machine = data["serial_machine"] || false;
        order.mf_invoice_number = data["sequence"] || false;
        order.mf_reportz = data["mf_reportz"] || false;
      }
      async pushToMF(order) {
        try {
          let data = await this.get_data_invoice(order)
          if (!data["valid"]) {
            throw data["message"]
          }
          const response = await this.print_out_invoice(data)
          console.log(response)
          const { value } = response
          if (!value.valid) {
            throw value
          }
          this.set_data_from_fiscal_machine(order, value)
          return { code: 200 }
        } catch (err) {
          if (!err.valid) { // need to be tested
            return {
              code: 700,
              data: {
                error: {
                  status: _t(err.message ? err.message : "Error de Conexion con la Maquina Fiscal #1")
                }
              }
            }

          } else {
            // other errors
            return {
              code: 700,
              data: {
                error: {
                  status: _t(err.status ? err.status : "Error de Conexion con la Maquina Fiscal #2")
                }
              }
            }
          }
        }
      }
      async push_single_order(order, opts) {
        if (this.useFiscalMachine() && !order.to_receipt && !order.mf_invoice_number) {
          let response = await this.pushToMF(order)
          if (response.code != 200) throw response
          let value = await super.push_single_order.apply(this, [order, opts]);
          return value
        }
        return await super.push_single_order.apply(this, [order, opts]);
      }
    }

  Registries.Model.extend(PosGlobalState, BinauralPosState);
})
