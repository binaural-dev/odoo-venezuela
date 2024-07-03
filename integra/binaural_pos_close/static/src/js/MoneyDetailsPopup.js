/** @odoo-module **/

import MoneyDetailsPopup from "point_of_sale.MoneyDetailsPopup";
import Registries from 'point_of_sale.Registries';
import { useState, useRef } from "@odoo/owl";
import { parse } from 'web.field_utils';
import { useValidateCashInput } from 'point_of_sale.custom_hooks';


const BinauralMoneyDetailsPopup = (MoneyDetailsPopup) =>
  class BinauralMoneyDetailsPopup extends MoneyDetailsPopup {
    setup() {
      super.setup();
      this.currency = this.props.currency;
      if (this.currency.id != this.env.pos.currency.id) {
        this.state = useState({
          moneyDetails: Object.fromEntries(this.env.pos.foreign_bills.map(bill => ([bill.value, 0]))),
          total: 0,
        });
      }
    }

    confirm() {
      let moneyDetailsNotes = this.state.total ? 'Money details: \n' : null;
      if (this.currency.id != this.env.pos.currency.id) {
        this.env.pos.foreign_bills.forEach(bill => {
          if (this.state.moneyDetails[bill.value]) {
            moneyDetailsNotes += `  - ${this.state.moneyDetails[bill.value]} x ${this.env.pos.format_foreign_currency(bill.value)}\n`;
          }
        })
      } else {
        this.env.pos.bills.forEach(bill => {
          if (this.state.moneyDetails[bill.value]) {
            moneyDetailsNotes += `  - ${this.state.moneyDetails[bill.value]} x ${this.env.pos.format_currency(bill.value)}\n`;
          }
        })
      }
      const payload = { total: this.state.total, moneyDetailsNotes, moneyDetails: { ...this.state.moneyDetails } };
      this.props.onConfirm(payload);
    }
  }

Registries.Component.extend(MoneyDetailsPopup, BinauralMoneyDetailsPopup);
return BinauralMoneyDetailsPopup
