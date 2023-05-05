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
        return this.config.iface_fiscal_data_module;
      }
      get currentOrder() {
        return this.get_order();
      }
      async get_data_invoice(order) {
        console.log(this)
        const currency = { symbol: 'Bs', position: 'after', rounding: 0.01, decimals: 2 };


        let invoice = {
          company_id: {
            name: this.company.name,
          },
          flag_21: this.config.flag_21
        }
        if (order.get_partner()) {

          invoice['partner_id'] = {}
          let client = order.get_partner()

          invoice['partner_id']['vat'] = client.prefix_vat + client.vat
          invoice['partner_id']['name'] = client.name
          invoice['partner_id']['address'] = client.address || false
          invoice['partner_id']['phone'] = client.phone || false
        }

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
            console.log("ALO", response)
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
              price_unit: Math.abs(amount),
              quantity: Math.abs(el.quantity),
              name: el.product.display_name,
              code: false,
              tax: el.get_taxes().length > 0 ? el.get_taxes()[0]['fiscal_code'] : 0
            }
          })
          invoice['payment_lines'] = order.paymentlines.map((el) => {

            let amount = vef_base ? el.amount : el.amount * this.config.foreign_inverse_rate 
            return {
              payment_method: el.payment_method.code_fiscal_printer,
              amount: Math.abs(amount),
            }
          })
        }
        return invoice
      }
      async print_out_invoice(data) {
        this.env.services.ui.block()
        const fdm = this.env.proxy.iot_device_proxies.fiscal_data_module;
        return new Promise(async (resolve, reject) => {
          fdm.add_listener(data => {
            fdm.remove_listener();
            this.env.services.ui.unblock()
            data.status.status === "connected" ? resolve(data["value"]) : reject(data["value"])
          })
          await fdm.action({
            action: `print_${data.type}`,
            data: data,
          })
        });
      }
      set_data_from_fiscal_machine(order, data) {
        order.fiscal_machine = data["serial_machine"] || false;
        order.mf_invoice_number = data["sequence"] || false;
      }
      async push_single_order(order, opts) {
        if (this.useFiscalMachine() && order && order.to_invoice) {
          try {
            const response = await this.print_out_invoice(await this.get_data_invoice(order))
            if (!response.valid) {
              throw new Error(response["message"])
            }
            this.set_data_from_fiscal_machine(order, response)
            return await super.push_single_order.apply(this, [order, opts]);
          } catch (err) {
            return Promise.reject({
              code: 701,
              error: {
                errorMessage: err.message,
                errorCode: "400"
              }
            });
          }
        }
        return await super.push_orders.apply(this, arguments);
      }
    };
  Registries.Model.extend(PosGlobalState, BinauralPosState);
})
