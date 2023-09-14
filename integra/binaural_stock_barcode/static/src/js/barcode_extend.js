/** @odoo-module **/

import { registry } from "@web/core/registry";
import MainComponent from "@stock_barcode/components/main";

import BinauralBarcodePickingModel from './barcode_picking_model';
import BinauralBarcodeQuantModel from './barcode_quant_model';

export default class MyLineComponent extends MainComponent {
  _getModel(params) {
    const { rpc, orm, notification } = this;
    if (params.model === 'stock.picking') {
      return new BinauralBarcodePickingModel(params, { rpc, orm, notification });
    } else if (params.model === 'stock.quant') {
      return new BinauralBarcodeQuantModel(params, { rpc, orm, notification });
    } else {
      throw new Error('No JS model define');
    }
  }
}

registry.category("actions").add("stock_barcode_client_action", MyLineComponent, { force: true });
