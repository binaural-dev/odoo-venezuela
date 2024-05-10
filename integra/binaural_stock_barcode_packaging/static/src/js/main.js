/** @odoo-module **/

import MainComponent from '@stock_barcode/components/main';
import { patch } from '@web/core/utils/patch';
import { useService } from "@web/core/utils/hooks";

patch(MainComponent.prototype, "binaural_stock_barcode_main", {
  setup() {
    this._super(...arguments)
    this.actionService = useService('action');
  },
  get is_picking_type_out() {
    return this.env.model.record.picking_type_id.type_steps == "out"
  },
  async add_packaging() {
    let response = await this.orm.call("stock.picking", "open_packaging_qty", [this.props.id])
    return this.actionService.doAction(response);
  },
  async print_packaging() {
    let response = await this.orm.call("stock.picking", "print_packaging_from_barcode", [this.props.id])
    let { action, valid } = response
    if (!!valid) return await this.actionService.doAction(action[0], {
      additionalContext: action[1],
    });
    return this.notification.add(
      action.message,
      { type: action.type }
    );
  }
})
