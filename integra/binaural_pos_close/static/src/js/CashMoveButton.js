
/** @odoo-module **/

import CashMoveButton from "point_of_sale.CashMoveButton";
import Registries from 'point_of_sale.Registries';
import { _t } from 'web.core';

const TRANSLATED_CASH_MOVE_TYPE = {
  in: _t('Entrada'),
  out: _t('Salida'),
};

const BinauralCashMoveButton = (CashMoveButton) =>
  class BinauralCashMoveButton extends CashMoveButton {
    async onClick() {
      const { confirmed, payload } = await this.showPopup('CashMovePopup');
      if (!confirmed) return;
      const { type, amount, reason, currency } = payload;
      const translatedType = TRANSLATED_CASH_MOVE_TYPE[type];
      let formattedAmount = this.env.pos.format_currency(amount);
      if (this.env.pos.currency.id != currency.id) {
        formattedAmount = this.env.pos.format_foreign_currency(amount);
      }
      if (!amount) {
        return this.showNotification(
          _.str.sprintf(this.env._t('Cash in/out of %s is ignored.'), formattedAmount),
          3000
        );
      }
      const extras = { formattedAmount, translatedType, currency: currency.id };
      await this.rpc({
        model: 'pos.session',
        method: 'try_cash_in_out',
        args: [[this.env.pos.pos_session.id], type, amount, reason, extras],
      });
      if (this.env.proxy.printer) {
        const renderedReceipt = renderToString('point_of_sale.CashMoveReceipt', {
          _receipt: this._getReceiptInfo({ ...payload, translatedType, formattedAmount }),
        });
        const printResult = await this.env.proxy.printer.print_receipt(renderedReceipt);
        if (!printResult.successful) {
          this.showPopup('ErrorPopup', { title: printResult.message.title, body: printResult.message.body });
        }
      }
      this.showNotification(
        _.str.sprintf(this.env._t('Successfully made a cash %s of %s.'), type, formattedAmount),
        3000
      );
    }
  }

Registries.Component.extend(CashMoveButton, BinauralCashMoveButton);
return BinauralCashMoveButton
