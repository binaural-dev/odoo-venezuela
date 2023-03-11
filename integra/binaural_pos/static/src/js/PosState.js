odoo.define("binaural_pos.PosState", function(require) {
  "use strict";

  const { PosGlobalState } = require("point_of_sale.models");
  const Registries = require("point_of_sale.Registries");

  const BinauralPosState = (PosGlobalState) =>
    class BinauralPosState extends PosGlobalState {
      constructor(obj) {
        super(obj);
        this.foreign_currency = null;
      }

      // @override
      async _processData(loadedData) {
        await super._processData(...arguments);
        this.currency = loadedData["res.currency"][0];
        this.foreign_currency = loadedData["res.currency"][1];
      }


      format_foreign_currency(amount, precision) {
        amount = this.format_currency_no_symbol(
          amount,
          precision,
          this.foreign_currency
        );
        if (this.foreign_currency.position === 'after') {
          return amount + ' ' + (this.foreign_currency.symbol || '');
        } else {
          return (this.foreign_currency.symbol || '') + ' ' + amount;
        }
      }
    };
  Registries.Model.extend(PosGlobalState, BinauralPosState);
})
