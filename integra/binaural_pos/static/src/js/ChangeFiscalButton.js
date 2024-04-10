odoo.define('binaural_pos.ChangeFiscalButton', function(require) {
  'use strict';

  const PosComponent = require('point_of_sale.PosComponent');
  const ProductScreen = require('point_of_sale.ProductScreen');
  const { useListener } = require("@web/core/utils/hooks");
  const Registries = require('point_of_sale.Registries');

  class ChangeFiscalButton extends PosComponent {
    setup() {
      super.setup(...arguments);
      useListener('click', this.onClick);
    }
    get currentOrder() {
      return this.env.pos.get_order();
    }
    async onClick() {
      this.currentOrder.toggle_receipt_invoice(!this.currentOrder.is_to_receipt());
      this.render(true);
    }
  }

  ChangeFiscalButton.template = 'ChangeFiscalButton';

  ProductScreen.addControlButton({
    component: ChangeFiscalButton,
    position: ['before', 'SetPricelistButton'],
  });

  Registries.Component.add(ChangeFiscalButton);

  return ChangeFiscalButton;
});
