/** @odoo-module **/

import { ClosePosPopup } from "@point_of_sale/app/navbar/closing_popup/closing_popup";
import { patch } from "@web/core/utils/patch";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";

patch(ClosePosPopup.prototype, {
  setup() {
    super.setup(...arguments)
    this.orm = useService("orm")
  },
  generate_report_x() {
    const fdm = this.pos.useFiscalMachine();
    console.log(fdm)
    if (!fdm) return
    new Promise(async (resolve, reject) => {
      await fdm.action({
        action: 'report_x',
        data: {},
      })
    });
  },
  generate_report_z() {
    const fdm = this.pos.useFiscalMachine();
    if (!fdm) return
    const promise = new Promise(async (resolve, reject) => {
      fdm.addListener(data => data.status.status === "connected" ? resolve(data) : reject(data));
      await fdm.action({
        action: 'report_z',
        data: {},
      })
      fdm.removeListener();
    });
    promise.then(async ({ value }) => {
      await this.orm.call('account.move', 'report_z', [[], this.pos.config.serial_machine, value])
      await this.orm.call('pos.session', 'set_report_z', [this.pos.pos_session.id, value],
      )
    })
  },
})
