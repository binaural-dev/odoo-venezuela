odoo.define("binaural_pos_mf.Chrome", function(require) {
  'use strict';

  const Chrome = require('point_of_sale.Chrome');
  const Registries = require('point_of_sale.Registries');

  const BinauralChrome = (Chrome) =>
    class extends Chrome {
      async _on_click_mf_test() {
        try {
          const fdm = this.env.pos.useFiscalMachine();
          let response = await fdm.action({
            action: `test`,
            data: true,
          })
          if(!response.result){
            throw new Error()

          }
        } catch (e) {
          this.showPopup("ErrorPopup", {
            title: "No se ha podido conectar a la Maquina fiscal",
          });
        }
      }
      get access_button_mf(){
        if (!this.env.pos.config){
          return false
        }
        return this.env.pos.config.access_button_mf
      }
      async showFiscalMachinePopup(){
        await this.showPopup('FiscalMachinePopup');
      }
    }

  Registries.Component.extend(Chrome, BinauralChrome);
  return BinauralChrome
})
