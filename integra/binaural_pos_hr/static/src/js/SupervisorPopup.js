odoo.define('binaural_pos_hr.SupervisorPopup', function(require) {
  'use strict';

  const { useRef } = owl;
  const Registries = require('point_of_sale.Registries');
  const SelectCashierMixin = require('binaural_pos.SelectCashierMixin');
  const PosComponent = require('point_of_sale.PosComponent');
  const { useBarcodeReader } = require('point_of_sale.custom_hooks');

  // const AbstractAwaitablePopup = require('point_of_sale.AbstractAwaitablePopup');

  class SupervisorPopup extends SelectCashierMixin(PosComponent) {
    setup() {
      super.setup();
      this.password = "";
      this.inputRef = useRef('input');
      useBarcodeReader({cashier: this.barcodeCashierAction}, true);
    }

    async askPin(employee) {

      if (this.password == "") return;

      if (employee.pin === Sha1.hash(this.password)) {
        return employee;
      } 

      await this.showPopup('ErrorPopup', {
          title: this.env._t('Incorrect Password'),
      });
      
    }

    async selectCashier() {
    }

    async barcodeCashierAction(code) {
      this.inputRef.el.value = code;
    }

    mounted() {
      this.inputRef.el.focus();
    }

    captureChange(event) {
      this.password = event.target.value;
      console.log('check if change on scan code fo just use this.password', this.password); 
    }

    cancel() {
      this.env.posbus.trigger('close-popup', {
        popupId: this.props.id,
        response: { confirmed: false, payload: false },
      });
    }
  
    confirm() {
      console.log('confirm',this.env.pos.employees);
      this.env.posbus.trigger('close-popup', {
        popupId: this.props.id,
        response: { confirmed: true, payload: true },
      });
    }

    checkconfirm(event){
      if (event.key == "Enter") {
        this.confirm()
      }
    }


  }

  SupervisorPopup.template = 'SupervisorPopup';
  SupervisorPopup.defaultProps = {
    confirmText: 'Confirm',
    cancelText: 'Cancel',
    title: "Insert Supervisor's Password",
    body: '',
  };

  Registries.Component.add(SupervisorPopup);

  return SupervisorPopup;
});
