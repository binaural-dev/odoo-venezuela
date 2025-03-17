odoo.define("l10n_ve_pos_mf.ClosePosPopup", function(require) {
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
        const promise = new Promise(async (resolve, reject) => {
          fdm.add_listener(data => data.status.status === "connected"? resolve(data): reject(data));
          await fdm.action({
            action: 'report_z',
            data: {},
          })
          fdm.remove_listener();
        });
        promise.then(async ({value}) => {
          await this.rpc({
            model: 'account.move',
            method: 'report_z',
            args: [[], this.env.pos.config.serial_machine, value]
          })
          await this.rpc({
            model: 'pos.session',
            method: 'set_report_z',
            args: [this.env.pos.pos_session.id, value],
          })
        }).finally(() => {
          this.env.services.ui.unblock()
        })
      }
    }

  Registries.Component.extend(ClosePosPopup, BinauralClosePosPopup);
  return ClosePosPopup
})
