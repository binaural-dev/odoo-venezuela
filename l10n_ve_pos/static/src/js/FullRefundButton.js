odoo.define('l10n_ve_pos.FullRefundButton', function (require) {
  'use strict';
  const { useListener } = require("@web/core/utils/hooks");
  // const { isConnectionError } = require('point_of_sale.utils');
  const PosComponent = require('point_of_sale.PosComponent');
  const Registries = require('point_of_sale.Registries');

  class FullRefundButton extends PosComponent {
    setup() {
      super.setup();
    }

  }
  FullRefundButton.template = 'FullRefundButton';

  Registries.Component.add(FullRefundButton);

  return FullRefundButton;
});
