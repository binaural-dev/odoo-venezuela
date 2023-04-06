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
      generate_report_z() {
        const fdm = this.env.proxy.iot_device_proxies.fiscal_data_module;
        if (!fdm) return
        this.env.services.ui.block()
        const promise = new Promise(async (resolve, reject) => {
          fdm.add_listener(data => {
            fdm.remove_listener();
            this.env.services.ui.unblock()
            data.status.status === "connected" ? resolve(data["value"]) : reject(data["value"])
          })
          await fdm.action({
            action: 'report_z',
            data: {},
          })
        });
        promise.then(async (data) => {
          console.log(data)
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
