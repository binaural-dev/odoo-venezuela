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
        currencyDetails: this.env.pos.currency,
        currencyNotes: "",
        foreignCurrencyNotes: "",
      });
      useValidateCashInput("openingForeignCashInput", this.env.pos.pos_session.foreign_cash_register_balance_start);
      this.openingForeignCashInputRef = useRef('openingForeignCashInput');
    }
    updateCashOpening({ total, moneyDetailsNotes }) {
      var inputRef = this.openingCashInputRef
      var stateTotal = this.state.openingCash
      if (this.state.currencyDetails.id != this.env.pos.currency.id) {
        inputRef = this.openingForeignCashInputRef
        this.state.foreignCurrencyNotes = moneyDetailsNotes
        this.state.openingForeignCash = total;
      } else {
        this.state.openingCash = total;
        this.state.currencyNotes = moneyDetailsNotes
      }
      inputRef.el.value = this.env.pos.format_currency_no_symbol(total);
      if (moneyDetailsNotes) {
        this.state.notes = this.state.currencyNotes + this.state.foreignCurrencyNotes;
      }
      this.manualInputCashCount = false;
      this.closeDetailsPopup();
    }
    openDetailsPopup() {
      super.openDetailsPopup(...arguments)
      this.state.currencyDetails = this.env.pos.currency
    }
    openForeignDetailsPopup() {
      this.state.openingForeignCash = 0;
      this.state.displayMoneyDetailsPopup = true;
      this.state.currencyDetails = this.env.pos.foreign_currency
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
