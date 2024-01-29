odoo.define('binaural_pos.SupervisorPopup', function(require) {
  'use strict';

  console.log('loooooog');
  const { useRef } = owl;
  const AbstractAwaitablePopup = require('point_of_sale.AbstractAwaitablePopup');
  const Registries = require('point_of_sale.Registries');

  // formerly SelectionPopupWidget
  class SupervisorPopup extends AbstractAwaitablePopup {
    constructor() {
      super(...arguments);
      this.password = "";
      this.inputRef = useRef('input');
    }
    mounted() {
      this.inputRef.el.focus();
    }
    captureChange(event) {
      this.password = event.target.value;
    }
    checkconfirm(event){
      if (event.key == "Enter") {
        this.confirm()
      }
    }
    confirm() {
      if (true) {
        super.confirm()
        return
      }
      this.showPopup('ErrorPopup', {
        title: 'Wrong Password',
        body: 'The password is incorrect',
      });
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
