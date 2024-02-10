odoo.define('binaural_pos_hr.SupervisorPopup', function(require) {
  'use strict';

  const { useRef } = owl;
  const Registries = require('point_of_sale.Registries');
  const SelectCashierMixin = require('pos_hr.SelectCashierMixin');
  const PosComponent = require('point_of_sale.PosComponent');
  const { useBarcodeReader } = require('point_of_sale.custom_hooks');
  const { _t } = require('web.core');

  class SupervisorPopup extends SelectCashierMixin(PosComponent) {
    setup() {
      super.setup();
      this.inputRef = useRef('input');
      useBarcodeReader({cashier: this.barcodeCashierAction}, true);

      this.supervisor_ids = this.env.pos.supervisor_ids
    }

    is_passkey_valid (key, value) {
      if (value == "") return -1;
      if (!this.supervisor_ids) return -1;

      const employee = this.supervisor_ids.find(
        (emp) => (
          emp[key] === value
        )
      );

      return employee;

    }

    async askPassKey(key, value) {
      const employee = this.is_passkey_valid(key, value);

      if (employee === -1) return;

      if (employee) {
        this.close({}, true);
        return;
      }

      let msg_error = this.env._t('Incorrect Password');

      await this.showPopup('ErrorPopup', {
          title: msg_error,
      });
    }

    async askPin(code) {

      await this.askPassKey('pin', code)
      
    }

    async askBarcode(code) {

      await this.askPassKey('barcode', code.code)

    }

    async selectCashier() {
    }

    async barcodeCashierAction(code) {
      this.inputRef.el.value = '';
      this.askBarcode(code);
    }

    mounted() {
      this.inputRef.el.focus();
    }

    close(event, confirmed = false) {
      this.env.posbus.trigger('close-popup', {
        popupId: this.props.id,
        response: { confirmed: confirmed, payload: confirmed },
      });
    }
  
    confirm() {
      this.askPin(this.inputRef.el.value);
    }

    checkconfirm(event){
      if (event.key == "Enter") {
        this.confirm()
      }
    }

  }

  SupervisorPopup.template = 'SupervisorPopup';
  SupervisorPopup.defaultProps = {
    confirmText: _t('Confirm'),
    cancelText: _t('Cancel'),
    title: _t("Insert Supervisor's Password"),
    body: '',
  };

  Registries.Component.add(SupervisorPopup);

  return SupervisorPopup;
});
