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
    }

    async askPin(code) {
      if (code == "") return;
      if (!this.env.pos.supervisor_ids) return;

      const employee = this.env.pos.supervisor_ids.find(
        (emp) => (
          emp.pin === code
        )
      );

      if (employee) {
        this.close({}, true);
        return;
      }

      await this.showPopup('ErrorPopup', {
          title: this.env._t('Incorrect Password'),
      });
      
    }

    async askBarcode(code) {
      if (!this.env.pos.supervisor_ids) return;

      const employee = this.env.pos.supervisor_ids.find(
        (emp) => (
          emp.barcode === code.code
        )
      );

      if (employee) {
        this.close({}, true);

        return
      }

      await this.showPopup('ErrorPopup', {
          title: this.env._t('Incorrect Password'),
      });
      
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
