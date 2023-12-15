odoo.define("binaural_pos_mf.ClosePosPopup", function(require) {
  'use strict';

  const ClosePosPopup = require('point_of_sale.ClosePosPopup');
  const Registries = require('point_of_sale.Registries');

  const BinauralClosePosPopup = (ClosePosPopup) =>
    class extends ClosePosPopup {
      generate_report_x() {
        const fdm = this.env.proxy.iot_device_proxies.fiscal_data_module;
        if (!fdm) return
        this.env.services.ui.block()
        new Promise(async (resolve, reject) => {
          await fdm.action({
            action: 'report_x',
            data: {},
          })
        });
      }
      generate_report_z() {
        const fdm = this.env.proxy.iot_device_proxies.fiscal_data_module;
        if (!fdm) return
        this.env.services.ui.block()
        const promise = new Promise(async (resolve, reject) => {
          let response = await fdm.action({
            action: 'report_z',
            data: {},
          })
          if (!response["result"]){
            self.env.services.ui.unblock()
            return reject({"message":"No se ha podido establecer conexion con la Maquina Fiscal",})
          }
          fdm.add_listener(data => {
            fdm.remove_listener();
            self.env.services.ui.unblock()
            data.status.status === "connected" ? resolve(data["value"]) : reject(data["value"])
          })
        });
        promise.then(async (data) => {
          await this.rpc({
            model: 'account.move',
            method: 'report_z',
            args: [[], this.env.pos.config.serial_machine, data]
          })
          await this.rpc({
            model: 'pos.session',
            method: 'set_report_z',
            args: [this.env.pos.pos_session.id, data],
          })
        })
      }
    }

  Registries.Component.extend(ClosePosPopup, BinauralClosePosPopup);
  return ClosePosPopup
})
