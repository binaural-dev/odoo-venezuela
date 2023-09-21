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
      try{
        const action = await this.orm.call(
          "res.users",
          "search_read",
          [[['role_picking', '=', 'supervisor']], ['name', 'role_picking']],
        );
        this.supervisor_ids = action;
      } catch(e){
        this.notificationService.add(this.env._t(e), { type: 'danger' });
      }
    });
  }

  async cancelSupervisor(){
    this.env.model.view = 'barcodeLines';
    this.env.model.trigger("update")
  }

  async checkSupervisor() {
    const action = await this.orm.call(
      "res.users",
      "check_password_supervisor",
      [parseInt(this.supervisorEl.el.value), this.passwordEl.el.value],
    );
    if(action){
      this.supervisor_ids = action;
      this.props.setDisplay(false);
      this.env.model.trigger("check-supervisor")
    }else{

      this.notificationService.add(this.env._t("Password Wrong"), { type: 'danger' });
      await this.cancelSupervisor();
    }
  }
}


SupervisorCheck.template = 'binaural_stock_barcode.SupervisorCheck';
