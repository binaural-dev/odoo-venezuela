/** @odoo-module **/

import CashOpeningPopup from "point_of_sale.CashOpeningPopup";
import Registries from 'point_of_sale.Registries';
import { useState, useRef } from "@odoo/owl";
import { parse } from 'web.field_utils';
import { useValidateCashInput } from 'point_of_sale.custom_hooks';

const BinauralCashOpeningPopup = (CashOpeningPopup) =>
  class BinauralCashOpeningPopup extends CashOpeningPopup {
    setup() {
      super.setup()
      this.state = useState({
        ...this.state,
        openingForeignCash: this.env.pos.pos_session.foreign_cash_register_balance_start || 0,
      });
      useValidateCashInput("openingForeignCashInput", this.env.pos.pos_session.foreign_cash_register_balance_start);
      this.openingCashInputRef = useRef('openingForeignCashInput');
    }
    handleInputForeignChange(event) {
      if (event.target.classList.contains('invalid-cash-input')) return;
      this.manualInputCashCount = true;
      this.state.openingForeignCash = parse.float(event.target.value);
    }
    async confirm() {
      this.env.pos.pos_session.foreign_cash_register_balance_start = this.state.openingForeignCash;
      this.rpc({
        model: 'pos.session',
        method: 'set_foreign_cashbox_pos',
        args: [this.env.pos.pos_session.id, this.state.openingForeignCash, this.state.notes],
      });
      super.confirm();
    }
  }

Registries.Component.extend(CashOpeningPopup, BinauralCashOpeningPopup);
return BinauralCashOpeningPopup
