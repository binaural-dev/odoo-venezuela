odoo.define("binaural_pos_mf.DebugWidget", function(require) {
  'use strict';

  const DebugWidget = require('point_of_sale.DebugWidget');
  const Registries = require('point_of_sale.Registries');

  const BinauralDebugWidget = (DebugWidget) =>
    class extends DebugWidget {
      programacion() {
        const fdm = this.env.proxy.iot_device_proxies.fiscal_data_module;
        return new Promise(async (resolve, reject) => {
          fdm.add_listener(data => {
            fdm.remove_listener();
            this.env.services.ui.unblock()
            data.status.status === "connected" ? resolve(data["value"]) : reject(data["value"])
          })
          await fdm.action({
            action: 'programacion',
            data: {},
          })
        });
      }
      report_x() {
        const fdm = this.env.proxy.iot_device_proxies.fiscal_data_module;
        return new Promise(async (resolve, reject) => {
          fdm.add_listener(data => {
            fdm.remove_listener();
            this.env.services.ui.unblock()
            data.status.status === "connected" ? resolve(data["value"]) : reject(data["value"])
          })
          await fdm.action({
            action: 'report_x',
            data: {},
          })
        });
      }
      async get_order() {
        let uid = this.env.pos.get_order().uid
        const values = Object.values(this.env.pos.toRefundLines)
        let lines = []
        //BUSCAR EL ORDEN 
        for (let i = 0; i < values.length; i++) {
          if (values[i].destinationOrderUid == uid) {
            lines.push(values[i])
          }
        }

        if (lines.length > 0) {
          let response = await this.rpc({
            model: 'pos.order',
            method: 'get_order_by_uid',
            args: [[], lines[0].orderline.orderUid],
            kwargs: {},
          })
          console.log("ALO",response)
        }

      }
      logger() {
        console.log(this)
        console.log(this.env.pos.db.partner_by_id)
      }
    }

  Registries.Component.extend(DebugWidget, BinauralDebugWidget);
  return DebugWidget
})
