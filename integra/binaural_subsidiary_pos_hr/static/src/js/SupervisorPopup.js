odoo.define('binaural_subsidiary_pos_hr.SubsidiarySupervisorPopup', function(require) {
  'use strict';

  const Registries = require('point_of_sale.Registries');
  const SupervisorPopup = require('binaural_pos_hr.SupervisorPopup');

  const { _t } = require('web.core');

  console.log("SupervisorPopupChild");

  const SupervisorPopupChild = (SupervisorPopup) => (
    class extends SupervisorPopup {
      setup() {
        super.setup();

        this.pos_setting_subsidiary_id = this.env.pos.config.sh_analytic_account[0]

      }

      is_passkey_valid (key, value) {
        /**
         * Return the posible options below:
         * 
         * -1: There are errors caused by empty data.
         * -2: There are supervisors matching with the value (pass), but there aren't matching with the current subsidiary specified from pos_config.
         *  0: There aren't supervisor matching with the value (pass).
         *  1: Success -> There are at least one supervisor matching either value and subsidiary.
         * 
         */

        if (value == "") return -1;
        if (!this.supervisor_ids) return -1;

        const supervisor_ids = this.supervisor_ids.filter(
          (emp) => (emp[key] === value)
        );

        if (!supervisor_ids.length) return 0;

        const exist_supervisor_on_subsidiary = supervisor_ids.filter(emp => (
          emp.subsidiary_ids.includes(this.pos_setting_subsidiary_id)
        ))

        if (!exist_supervisor_on_subsidiary.length) return -2;

        return 1
      }

      async askPassKey(key, value) {
        const employee = this.is_passkey_valid(key, value);
  
        if (employee === 1) {
          this.close({}, true);
          return;
        }
  
        if (employee === -1) return;
  
        let msg_error = this.env._t('Incorrect Password');
  
        if (employee === -2) {
          msg_error = this.env._t('You do not have permission for this subsidiary')
        }
  
        await this.showPopup('ErrorPopup', {
            title: msg_error,
        });
      }
    }
  )

  Registries.Component.extend(SupervisorPopup, SupervisorPopupChild);

  return SupervisorPopup;
});
