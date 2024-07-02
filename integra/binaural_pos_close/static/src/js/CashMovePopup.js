/** @odoo-module **/

import CashMovePopup from "point_of_sale.CashMovePopup";
import Registries from 'point_of_sale.Registries';
import { useState, useRef } from "@odoo/owl";
import { parse } from 'web.field_utils';
import { useValidateCashInput } from 'point_of_sale.custom_hooks';

const BinauralCashMovePopup = (CashMovePopup) =>
  class BinauralCashMovePopup extends CashMovePopup {
    setup() {
      super.setup();
      this.state = useState({
        ...this.state, currency: this.env.pos.currency, is_base: true
      });
    }
    getPayload() {
      let res = super.getPayload();
      res["currency"] = this.state.currency;
      return res
    }

    onClickButtonCurrency() {
      if (this.env.pos.currency.id == this.state.currency.id) {
        this.state.currency = this.env.pos.foreign_currency
        this.state.is_base = false
      } else {
        this.state.currency = this.env.pos.currency
        this.state.is_base = true
      }
    }
  }

Registries.Component.extend(CashMovePopup, BinauralCashMovePopup);
return BinauralCashMovePopup
