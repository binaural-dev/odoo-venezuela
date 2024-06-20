odoo.define("binaural_pos.PosState", function(require) {
  "use strict";

  const { PosGlobalState } = require("point_of_sale.models");
  const Registries = require("point_of_sale.Registries");

  const BinauralPosState = (PosGlobalState) =>
    class BinauralPosState extends PosGlobalState {
      constructor(obj) {
        super(obj);
        this.foreign_currency = null;
        this.prefix_vats = []
      }
      open_cashbox() {
        if (this.env.pos.config.iface_cashdrawer){
          this.env.proxy.printer.open_cashbox();
        }
      }

      // @override
      async _processData(loadedData) {
        await super._processData(...arguments);
        this.currency = loadedData["res.currency"][0];
        this.foreign_currency = loadedData["res.currency"][1];
        this.prefix_vats = loadedData["prefix_vats"];
        this.cities = loadedData["res.country.city"];
        this.cities.sort((a, b) => a.name.localeCompare(b.name));
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
      async push_orders(order, opts) {
        let res = await super.push_orders(order, opts);
        await this.update_products(order)
        return res
      }
      async push_single_order(order, opts) {
        let res = await super.push_single_order(...arguments);
        await this.update_products(order)
        return res
      }
      async update_products(order) {
        if (!order) {
          return
        }
        let product_ids = []
        order.get_orderlines().forEach(line => {
          if (line.product.id in product_ids) {
            return
          }
          product_ids.push(line.product.id)
        })
        let products = await this.env.services.rpc({
          model: 'pos.session',
          method: 'get_pos_ui_product_product_by_params',
          args: [odoo.pos_session_id, { domain: [['id', 'in', product_ids]] }],
        });
        this._loadProductProduct(products);
      }

    };
  Registries.Model.extend(PosGlobalState, BinauralPosState);
})
