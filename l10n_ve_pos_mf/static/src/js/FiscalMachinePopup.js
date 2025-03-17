/** @odoo-module **/

import AbstractAwaitablePopup from 'point_of_sale.AbstractAwaitablePopup';
import Registries from 'point_of_sale.Registries';
import { _lt } from '@web/core/l10n/translation';

class FiscalMachinePopup extends AbstractAwaitablePopup {
  setup() {
    super.setup();
  }

  report_z() {
    const fdm = this.env.pos.useFiscalMachine();
    if (!fdm) return
    this.env.services.ui.block()
    const promise = new Promise(async (resolve, reject) => {
      let response = await fdm.action({
        action: 'report_z',
        data: {},
      })
      if (!response["result"]) {
        self.env.services.ui.unblock()
        return reject({ "message": "No se ha podido establecer conexion con la Maquina Fiscal", })
      }
      fdm.add_listener(data => {
        fdm.remove_listener();
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
  report_x() {
    const fdm = this.env.pos.useFiscalMachine();
    if (!fdm) return
    this.env.services.ui.block()
    fdm.action({
      action: 'report_x',
      data: {},
    }).catch().finally(() => {
      this.env.services.ui.unblock()
    })
  }

  getPayload() {
    return {}
  }
}

FiscalMachinePopup.template = 'l10n_ve_pos_mf.FiscalMachinePopup';

FiscalMachinePopup.defaultProps = {
  cancelText: _lt('Cancel'),
  title: _lt('Fiscal Reports'),
};

Registries.Component.add(FiscalMachinePopup);

return FiscalMachinePopup;
