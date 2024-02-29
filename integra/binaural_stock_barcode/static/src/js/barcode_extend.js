/** @odoo-module **/

import { registry } from "@web/core/registry";
import MainComponent from "@stock_barcode/components/main";
import SupervisorCheck from "./SupervisorCheck";

import BinauralBarcodePickingModel from './barcode_picking_model';
import BinauralBarcodeQuantModel from './barcode_quant_model';

const { useState, onWillStart } = owl;

export default class BinauralMainComponent extends MainComponent {
  setup() {
    super.setup();
    this.state = useState({ displaySupervisorCheck: false, EditLineArgs: [], type_supervisor: false });
    onWillStart(async () => {
      this.env.model.on('check-supervisor', this, this.openclose)
    });
  }

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

  async openclose() {
    if (this.state.type_supervisor == "validate") {
      this.state.EditLineArgs.stopPropagation();
      await this.env.model.validate();
    }
    if (this.state.type_supervisor == "edit") {
      super._onEditLine(this.state.EditLineArgs)
    }

  }

  get displaySupervisorChecker() {
    return this.env.model.view === "supervisorCheck";
  }

  setDisplaySupervisorChecker(val) {
    this.state.displaySupervisorCheck = val;
  }

  async _onEditLine(ev) {
    if (!this.env.model.config.supervisor_required_to_edit) {
      return await super._onEditLine(...arguments)
    }
    this.state.EditLineArgs = ev;
    this.state.type_supervisor = "edit"
    this.ShowSupervisorPopup(this);
  }

  async validate(ev) {
    if (!this.env.model.config.supervisor_required_for_incomplete_qty
      || !!this.highlightValidateButton) {
      return await super.validate(...arguments)
    }
    this.state.EditLineArgs = ev;
    this.state.type_supervisor = "validate"
    this.ShowSupervisorPopup(this)
  }

  async ShowSupervisorPopup(self) {
    this.state.displaySupervisorCheck = true;
    this.env.model.displaySupervisorCheck();
  }

}

BinauralMainComponent.components = {
  ...MainComponent.components,
  SupervisorCheck,
};

registry.category("actions").add("stock_barcode_client_action", BinauralMainComponent, { force: true });
