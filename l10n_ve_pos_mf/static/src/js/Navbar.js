/** @odoo-module **/

import { Navbar } from "@point_of_sale/app/navbar/navbar";
import { patch } from "@web/core/utils/patch";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";

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
      console.log(e)
      let message ;
      if (typeof response ==='undefined') {
        message = "No se ha podido conectar a la Maquina fiscal"
      }
      else{
        message = response.result.error
      }
      this.env.services.popup.add(
        ErrorPopup,
        {
          title: ("No se ha podido conectar a la Maquina fiscal"),
          body: message,
        }
      )
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
