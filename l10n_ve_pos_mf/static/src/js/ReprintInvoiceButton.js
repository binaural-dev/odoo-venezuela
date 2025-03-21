odoo.define('point_of_sale.ReprintInvoiceButton', function(require) {
  'use strict';

  const { useListener } = require("@web/core/utils/hooks");
  const PosComponent = require('point_of_sale.PosComponent');
  const Registries = require('point_of_sale.Registries');

  class ReprintInvoiceButton extends PosComponent {
    setup() {
      super.setup();
      useListener('click', this._onClick);
    }
    async _onClick() {
      if (!this.props.order) return;
      let amount = this.props.order.paymentlines.reduce((prev, cur) => prev + cur.amount, 0)
      const type = amount >= 0 ? "out_invoice": "out_refund"

      this.env.services.ui.block()
      const fdm = this.env.proxy.iot_device_proxies.fiscal_data_module;
      new Promise(async (resolve, reject) => {
        fdm.add_listener(data => {
          fdm.remove_listener();
          this.env.services.ui.unblock()
          data.status.status === "connected" ? resolve(data["value"]) : reject(data["value"])
        })
        let response = await this.env.services.rpc({
          model: 'pos.order',
          method: 'get_order_by_uid',
          args: [[], this.props.order.uid],
          kwargs: {},
        })
        if (response.length > 0) {
          let data = {
            "type": type,
            "mf_number": response[0].mf_invoice_number,
          }
          await fdm.action({
            action: `reprint`,
            data: data,
          })
        }
      });
    }
  }
  ReprintInvoiceButton.template = 'ReprintInvoiceButton';
  Registries.Component.add(ReprintInvoiceButton);

  return ReprintInvoiceButton;
});
