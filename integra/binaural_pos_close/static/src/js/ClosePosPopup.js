/** @odoo-module **/


import ClosePosPopup from "point_of_sale.ClosePosPopup";
import Registries from 'point_of_sale.Registries';
import { useState, useRef } from "@odoo/owl";
import { parse } from 'web.field_utils';
import { useValidateCashInput } from 'point_of_sale.custom_hooks';

const BinauralClosePosPopup = (ClosePosPopup) =>
  class BinauralClosePosPopup extends ClosePosPopup {
    setup() {
      super.setup();
      this.closingForeignCashInputRef = useRef('closingForeignCashInput');
      useValidateCashInput("closingForeignCashInput");
      this.state = useState({
        ...this.state,
        currencyDetails: this.env.pos.currency,
        currencyNotes: "",
        foreignCurrencyNotes: "",
      });
    }
    updateCountedCash({ total, moneyDetailsNotes, moneyDetails }) {
      var inputRef = this.closingCashInputRef
      var defaultCashDetails = this.defaultCashDetails
      var difference = "difference"
      var amount = "amount"
      if (this.state.currencyDetails.id != this.env.pos.currency.id) {
        inputRef = this.closingForeignCashInputRef
        defaultCashDetails = this.foreignDefaultCashDetails
        difference = "foreign_difference"
        amount = "foreign_amount"
        this.state.foreignCurrencyNotes = moneyDetailsNotes
      } else {
        this.state.currencyNotes = moneyDetailsNotes
      }
      inputRef.el.value = this.env.pos.format_currency_no_symbol(total);
      console.log(defaultCashDetails)
      this.state.payments[defaultCashDetails.id].counted = total;
      this.state.payments[defaultCashDetails.id][difference] =
        this.env.pos.round_decimals_currency(
          this.state.payments[defaultCashDetails.id].counted - defaultCashDetails[amount]
        );
      if (moneyDetailsNotes) {
        this.state.notes = this.state.currencyNotes + this.state.foreignCurrencyNotes;
      }
      this.manualInputCashCount = false;
      this.moneyDetails = moneyDetails;
      this.closeDetailsPopup();
    }
    openDetailsPopup() {
      super.openDetailsPopup(...arguments)
      this.state.currencyDetails = this.env.pos.currency
    }
    openForeignDetailsPopup() {
      this.state.payments[this.foreignDefaultCashDetails.id].counted = 0;
      this.state.payments[this.foreignDefaultCashDetails.id].difference = -this.foreignDefaultCashDetails.amount;
      // this.state.notes = "";
      this.state.displayMoneyDetailsPopup = true;
      this.state.currencyDetails = this.env.pos.foreign_currency
    }
    handleInputChange(paymentId, event) {
      if (event.target.classList.contains('invalid-cash-input')) return;

      let expectedAmount;
      let foreignExpectedAmount;

      if (this.defaultCashDetails && paymentId === this.defaultCashDetails.id) {
        this.manualInputCashCount = true;
        this.state.notes = '';
        expectedAmount = this.defaultCashDetails.amount;
        foreignExpectedAmount = this.defaultCashDetails.foreign_amount;
      } else if (this.foreignDefaultCashDetails && paymentId === this.foreignDefaultCashDetails.id) {
        this.manualInputCashCount = true;
        this.state.notes = '';
        expectedAmount = this.foreignDefaultCashDetails.amount;
        foreignExpectedAmount = this.foreignDefaultCashDetails.foreign_amount;
      } else {
        expectedAmount = this.otherPaymentMethods.find(pm => paymentId === pm.id).amount;
        foreignExpectedAmount = this.otherPaymentMethods.find(pm => paymentId === pm.id).foreign_amount;
      }
      this.state.payments[paymentId].counted = parse.float(event.target.value);

      this.state.payments[paymentId].difference =
        this.env.pos.round_decimals_currency(this.state.payments[paymentId].counted - expectedAmount);
      this.state.payments[paymentId].foreign_difference =
        this.env.pos.round_decimals_currency(this.state.payments[paymentId].counted - foreignExpectedAmount);
    }
    async closeSession() {
      if (!this.closeSessionClicked) {
        let response;
        if (this.cashControl) {
          response = await this.rpc({
            model: 'pos.session',
            method: 'post_closing_foreign_cash_details',
            args: [this.env.pos.pos_session.id],
            kwargs: {
              counted_cash: this.state.payments[this.foreignDefaultCashDetails.id].counted,
            }
          })
          if (!response.successful) {
            return this.handleClosingError(response);
          }
        }
      }
      return await super.closeSession()
    }

    hasDifference() {
      return Object.entries(this.state.payments).find(pm => pm[1].difference != 0 && pm[1].foreign_difference != 0);
    }

  }

Registries.Component.extend(ClosePosPopup, BinauralClosePosPopup);
return BinauralClosePosPopup
