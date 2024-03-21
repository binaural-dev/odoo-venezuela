odoo.define("binaural_pos_hr.PosState", function(require) {
  "use strict";

  const { PosGlobalState } = require("point_of_sale.models");
  const Registries = require("point_of_sale.Registries");

  const BinauralPosState = (PosGlobalState) =>
    class BinauralPosState extends PosGlobalState {
      constructor(obj) {
        super(obj);
      }

      async load_supervisors_data() {
        const params = {
          model: 'hr.employee',
          method: 'get_pos_hr_employee',
        };

        const supervisor_ids = await this.env.services.rpc(params);
        this.supervisor_ids = supervisor_ids;

      }

      async after_load_server_data(){
        super.after_load_server_data();
        await this.load_supervisors_data();
    }

    };
  Registries.Model.extend(PosGlobalState, BinauralPosState);
})
