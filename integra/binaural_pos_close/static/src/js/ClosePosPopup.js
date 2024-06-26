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
