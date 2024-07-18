/** @odoo-module **/

import { bus } from 'web.core';
const { Component, onWillStart, onMounted, useRef } = owl;
import { useService } from "@web/core/utils/hooks";

export default class SupervisorCheck extends Component {

  setup() {
    this.orm = useService('orm');
    this.notificationService = useService("notification");
    this.supervisorEl = useRef('supervisor_id');
    this.passwordEl = useRef('password');
    this.supervisor_ids = []
    onMounted(() => {
      this.passwordEl.el.focus();
    })
    onWillStart(async () => {
      try {
        const action = await this.orm.call(
          "hr.employee",
          "get_supervisor_ids",
          [],
        );
        this.supervisor_ids = action;
      } catch (e) {
        this.notificationService.add(this.env._t(e), { type: 'danger' });
      }
    });
  }

  async onEnter(ev) {
    if (ev.key == "CapsLock" && this.passwordEl.el.value != "") {
      await this.checkSupervisor();
    }
    if (ev.key == "Enter" || ev.key == "NumLock") {
      await this.checkSupervisor();
    }
  }

  async cancelSupervisor() {
    this.env.model.view = 'barcodeLines';
    this.env.model.trigger("update")
  }

  async checkSupervisor() {

    let supervisor_id = this.supervisor_ids.find((el) => {
      if (el.barcode === this.passwordEl.el.value) {
        return true
      }
      return false
    })

    if(!supervisor_id){
      supervisor_id = this.supervisor_ids.find((el) => {
        if (el.id === parseInt(this.supervisorEl.el.value) && el.pin === this.passwordEl.el.value) {
          return true
        }
        return false
      })
    }

    if (!!supervisor_id) {
      this.props.setDisplay(false);
      if (this.props.type == "edit") {
        await this.orm.call(
          "stock.move.line",
          "set_supervisor_to_edit",
          [parseInt(this.props.component.state.EditLineArgs.line.id), parseInt(supervisor_id.id)],
        );
      }
      if (this.props.type == "validate") {
        await this.orm.call(
          "stock.picking",
          "set_supervisor_for_incomplete_qty",
          [parseInt(this.props.component.env.model.record.id), parseInt(supervisor_id.id)],
        );
      }

      this.env.model.view = 'barcodeLines';
      this.env.model.trigger("update")
      this.env.model.trigger("check-supervisor")
    } else {

      this.notificationService.add(this.env._t("Password Wrong"), { type: 'danger' });
      await this.cancelSupervisor();
    }
  }
}


SupervisorCheck.template = 'binaural_stock_barcode.SupervisorCheck';
