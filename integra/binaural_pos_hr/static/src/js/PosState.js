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
        const domain = [['pos_employee_type', '=', 'supervisor']];
        const fields = ['name', 'pos_employee_type', 'pin', 'barcode'];
        const params = {
          model: 'hr.employee',
          method: 'search_read',
          kwargs: {
            domain,
            fields
          },
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
