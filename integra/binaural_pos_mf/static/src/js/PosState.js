odoo.define("binaural_pos_mf.PosState", function(require) {
  "use strict";

  const { PosGlobalState } = require("point_of_sale.models");
  const Registries = require("point_of_sale.Registries");

  const BinauralPosState = (PosGlobalState) =>
    class BinauralPosState extends PosGlobalState {
      constructor() {
        super(...arguments);
      }
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
      get get_flag_21(){
        return this.config.flag_21
      }
      get get_traditional_line(){
        return this.config.traditional_line
      }
      async get_data_invoice(order) {
        const currency = { symbol: 'Bs', position: 'after', rounding: 0.01, decimals: 2 };


        let invoice = {
          company_id: {
            name: this.company.name,
          },
          flag_21: this.get_flag_21,
          traditional_line: this.get_traditional_line,
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

        if (lines.length > 0) {
          try {
            let response = await this.env.services.rpc({
              model: 'pos.order',
              method: 'get_order_by_uid',
              args: [[], lines[0].orderline.orderUid],
              kwargs: {},
            })
            if (response.length > 0) {
              invoice["invoice_affected"] = {
                "number": response[0].mf_invoice_number,
                "serial_machine": response[0].fiscal_machine,
                "date": response[0].date_order,
              }
            }
          } catch (e) {
            console.log(e)
          }
        }

        invoice['type'] = 'out_invoice'
        if (order.get_total_with_tax() < 0) {
          invoice['type'] = 'out_refund'
        }
        if (order.orderlines.length > 0) {

          let vef_base = this.currency.name === "VEF"

          invoice['invoice_lines'] = order.orderlines.map((el) => {

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
        console.log(invoice)
        return invoice
      }
      async print_out_invoice(data) {
        let self = this;
        const fdm = this.useFiscalMachine();
        return new Promise(async (resolve, reject) => {
          let response = await fdm.action({
            action: `print_${data.type}`,
            data: data,
          })
          console.log("RESPONSaE 2",response)
          if (!response["result"]) {
            self.env.services.ui.unblock()
            return reject({ "valid": false, "message": "No se ha podido establecer conexion con la Maquina Fiscal", })
          }
          fdm.add_listener(data => {
            fdm.remove_listener();
            self.env.services.ui.unblock()
            data.status.status === "connected" ? resolve(data["value"]) : reject(data["value"])
          })
        });
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
          const response = await this.print_out_invoice(await this.get_data_invoice(order))
          this.env.services.ui.unblock()
          console.log("RESPONSE",response)
          if (!response.valid) {
            throw new Error(response["message"])
          }
          this.set_data_from_fiscal_machine(order, response)
        } catch (err) {
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
