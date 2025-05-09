/** @odoo-module **/

import { Navbar } from "@point_of_sale/app/navbar/navbar";
import { patch } from "@web/core/utils/patch";

patch(Navbar.prototype, {
  async _on_click_mf_test() {
    try {
      const fdm = this.pos.useFiscalMachine();
      let response = await fdm.action({
        action: `test`,
        data: true,
      })
      if (!response.result) {
        throw new Error()

      }
    } catch (e) {
      this.showPopup("ErrorPopup", {
        title: "No se ha podido conectar a la Maquina fiscal",
      });
    }
  },
  get access_button_mf() {
    if (!this.pos.config) {
      return false
    }
    return this.pos.config.access_button_mf
  },
  async showFiscalMachinePopup() {
    await this.showPopup('FiscalMachinePopup');
  }
})
