odoo.define("binaural_megasoft.PosState", function (require) {
  "use strict";

  const { PosGlobalState } = require("point_of_sale.models");
  const Registries = require("point_of_sale.Registries");

  const BinauralPosState = (PosGlobalState) =>
    class BinauralPosState extends PosGlobalState {
      constructor(obj) {
        super(obj);
        this.iot_megasoft = false
      }

      // @override
      async _processData(loadedData) {
        await super._processData(...arguments);
        this.iot_megasoft = loadedData["iot.box"].find(el => el.id == loadedData["pos.config"]["megasoft_iot_id"][0])
      }
    };
  Registries.Model.extend(PosGlobalState, BinauralPosState);
})
