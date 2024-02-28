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
          "res.users",
          "search_read",
          [[['role_picking', '=', 'supervisor']], ['name', 'role_picking','pin','barcode']],
        );
        this.supervisor_ids = action;
      } catch (e) {
        this.notificationService.add(this.env._t(e), { type: 'danger' });
      }
    });
  }

  async onEnter(ev){
    if(ev.key ==  "Enter" || ev.key == "NumLock"){
      await this.checkSupervisor();
    }
  }

  async cancelSupervisor() {
    this.env.model.view = 'barcodeLines';
    this.env.model.trigger("update")
  }

  async checkSupervisor() {
    const action = await this.orm.call(
      "res.users",
      "check_password_supervisor",
      [parseInt(this.supervisorEl.el.value), this.passwordEl.el.value],
    );
    if (action) {
      this.supervisor_ids = action;
      this.props.setDisplay(false);
      let function_to_call = ""

      if(this.props.type == "edit"){
        function_to_call = "set_supervisor_to_edit"
      }
      if(this.props.type == "validate"){
        function_to_call = "set_supervisor_for_incomplete_qty"
      }
      if (function_to_call !== "" ){
        await this.orm.call(
          "stock.picking",
          function_to_call,
          [parseInt(this.props.component.env.model.record.id), parseInt(this.supervisorEl.el.value)],
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
