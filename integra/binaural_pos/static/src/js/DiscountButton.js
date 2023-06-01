odoo.define("binaural_pos.NumpadWidget", function(require) {
    'use strict';
  
    const NumpadWidget = require('point_of_sale.NumpadWidget');
    const Registries = require('point_of_sale.Registries');
  
    const { Gui } = require('point_of_sale.Gui');
    const { _t } = require('web.core');
    const rpc = require('web.rpc');

    const BinauralNumpadWidget = (NumpadWidget) =>
      class extends NumpadWidget {
  
        async changeMode(mode) {
          const currentUser = this.env.pos.get_cashier();

          if (mode !== 'discount') return await super.changeMode(mode);

          try {
            const isUserAuthorized = await rpc.query({
              model: 'pos.session',
              method: 'is_user_authorized',
              args: [currentUser.id],
            })
            
            if(isUserAuthorized) return await super.changeMode(mode);

            Gui.showPopup('ErrorPopup', {
              title: _t("Usuario no autorizado para aplicar descuento"),
            });
          } catch (error) {
            console.error(`Error desconocido: ${error}`);
          }
        }
      };
    
    Registries.Component.extend(NumpadWidget, BinauralNumpadWidget);
    return NumpadWidget
  
  });
  