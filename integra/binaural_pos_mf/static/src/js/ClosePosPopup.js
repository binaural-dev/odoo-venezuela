odoo.define("binaural_pos_mf.ClosePosPopup", function(require) {
  'use strict';

  const ClosePosPopup = require('point_of_sale.ClosePosPopup');
  const Registries = require('point_of_sale.Registries');

  const BinauralClosePosPopup = (ClosePosPopup) =>
    class extends ClosePosPopup {
      generate_report_x() {
        const fdm = this.env.pos.useFiscalMachine();
        if (!fdm) return
        new Promise(async (resolve, reject) => {
          await fdm.action({
            action: 'report_x',
            data: {},
          })
        });
      }
      generate_report_z() {
        const fdm = this.env.pos.useFiscalMachine();
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
            console.log(data.value)
            !!data.value.valid ? resolve(data["value"]) : reject(data["value"])
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
        }).finally(() => {
          this.env.services.ui.unblock()
        })
      }
    }

  Registries.Component.extend(ClosePosPopup, BinauralClosePosPopup);
  return ClosePosPopup
})
