/** @odoo-module **/

import { PosGlobalState } from "point_of_sale.models";
import Registries from "point_of_sale.Registries";

const BinauralPosState = (PosGlobalState) =>
  class BinauralPosState extends PosGlobalState {
    async _processData(loadedData) {
      await super._processData(...arguments)
      this.bills = loadedData["pos.bill"].filter((el) => el.currency_id[0] == this.currency.id)
      this.foreign_bills = loadedData["pos.bill"].filter((el) => el.currency_id[0] == this.foreign_currency.id)
    }
    async getClosePosInfo() {
      let res = await super.getClosePosInfo()
      const cashControl = this.config.cash_control;

      const closingData = await this.env.services.rpc({
        model: 'pos.session',
        method: 'get_closing_control_data',
        args: [[this.pos_session.id]]
      });

      let state = res.state

      const foreignDefaultCashDetails = closingData.foreign_default_cash_details;
      if (cashControl) {
        state.payments[foreignDefaultCashDetails.id] = {
          counted: 0,
          difference: -foreignDefaultCashDetails.amount,
          number: 0,
          foreign_difference: -foreignDefaultCashDetails.foreign_amount
        };
        state.payments[res.defaultCashDetails.id] = { ...state.payments[res.defaultCashDetails.id], foreign_difference: 0 };
      }

      if (cashControl) {
      }
      return { ...res, foreignDefaultCashDetails, state: state }
    }


  };
Registries.Model.extend(PosGlobalState, BinauralPosState);
