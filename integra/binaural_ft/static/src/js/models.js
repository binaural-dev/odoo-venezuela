/** @odoo-module **/

import { PosGlobalState } from "point_of_sale.models";
import Registries from "point_of_sale.Registries";

const BinauralPosState = (PosGlobalState) =>
  class BinauralPosState extends PosGlobalState {

    async _processData(loadedData) {
      await super._processData(...arguments);
      this.reports_mf = loadedData["reports_mf"];
      this.iot_device_by_identifier = this.set_iot_device_by_identifier(loadedData["iot.device"])
    }

    get_iot_device_by_identifier(identifier) {
      return this.iot_device_by_identifier[identifier]
    }

    set_iot_device_by_identifier(iot_device_ids) {
      let values = {}
      iot_device_ids.forEach((el) => {
        values[el.identifier] = el
      })
      return values
    }
    
  };

Registries.Model.extend(PosGlobalState, BinauralPosState);
