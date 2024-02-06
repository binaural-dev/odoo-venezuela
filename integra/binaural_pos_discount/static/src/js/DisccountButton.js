odoo.define('binaural_pos_discount.DiscountButton', function(require) {
  'use strict';

  const DiscountButton = require('pos_discount.DiscountButton');
  const Registries = require('point_of_sale.Registries');
  const { Gui } = require("point_of_sale.Gui");
  const { _t } = require("web.core");

  const BinauralDiscountButton = (DiscountButton) =>
    class extends DiscountButton {

      async apply_discount(pc) {
        var order = this.env.pos.get_order();
        var lines = order.get_orderlines();
        var product = this.env.pos.db.get_product_by_id(this.env.pos.config.discount_product_id[0]);
        if (product === undefined) {
          await this.showPopup('ErrorPopup', {
            title: this.env._t("No discount product found"),
            body: this.env._t("The discount product seems misconfigured. Make sure it is flagged as 'Can be Sold' and 'Available in Point of Sale'."),
          });
          return;
        }

        // Remove existing discounts
        lines.filter(line => line.get_product() === product)
          .forEach(line => order.remove_orderline(line));

        // Add one discount line per tax group
        let linesByTax = order.get_orderlines_grouped_by_tax_ids();
        for (let [tax_ids, lines] of Object.entries(linesByTax)) {

          // Note that tax_ids_array is an Array of tax_ids that apply to these lines
          // That is, the use case of products with more than one tax is supported.
          let tax_ids_array = tax_ids.split(',').filter(id => id !== '').map(id => Number(id));

          let baseToDiscount = order.calculate_base_amount(
            tax_ids_array, lines.filter(ll => ll.isGlobalDiscountApplicable())
          );

          let foreignBaseToDiscount = order.calculate_foreign_base_amount(
            tax_ids_array, lines.filter(ll => ll.isGlobalDiscountApplicable())
          );

          // We add the price as manually set to avoid recomputation when changing customer.
          let discount = - pc / 100.0 * baseToDiscount;
          let foreignDiscount = - pc / 100.0 * foreignBaseToDiscount;
          if (discount < 0) {
            order.add_product(product, {
              price: discount,
              foreign_price: foreignDiscount,
              lst_price: discount,
              tax_ids: tax_ids_array,
              merge: false,
              description:
                `${pc}%, ` +
                (tax_ids_array.length ?
                  _.str.sprintf(
                    this.env._t('Tax: %s'),
                    tax_ids_array.map(taxId => this.env.pos.taxes_by_id[taxId].amount + '%').join(', ')
                  ) :
                  this.env._t('No tax')),
              extras: {
                price_automatically_set: true,
              },
            });
          }
        }
      }
    }

  Registries.Component.extend(DiscountButton, BinauralDiscountButton);

  return DiscountButton;
});
