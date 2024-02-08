odoo.define('binaural_subsidiary_pos_hr.SubsidiarySupervisorPopup', function(require) {
  'use strict';

  const Registries = require('point_of_sale.Registries');
  const SupervisorPopup = require('binaural_pos_hr.SupervisorPopup');

  const { _t } = require('web.core');

  const SupervisorPopupChild = (SupervisorPopup) => (

    class SupervisorPopupChild extends SupervisorPopup {
      setup() {
        super.setup();

        // subsidiary_id = this.pos.config.sh_analytic_account[0]
      }
    }
  )

  Registries.Component.extend(SupervisorPopup, SupervisorPopupChild);

  return SupervisorPopupChild;
});
