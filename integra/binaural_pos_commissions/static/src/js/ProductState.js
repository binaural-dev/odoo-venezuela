/** @odoo-module **/

import { Product } from "point_of_sale.models"
import Registries from "point_of_sale.Registries"

import core from 'web.core';
var _t = core._t;

const BinauralProduct = (Product) =>
  class extends Product {
    get_pricelist_item(pricelist) {
      var self = this;
      var date = moment();

      // In case of nested pricelists, it is necessary that all pricelists are made available in
      // the POS. Display a basic alert to the user in this case.
      if (!pricelist) {
        alert(_t(
          'An error occurred when loading product prices. ' +
          'Make sure all pricelists are available in the POS.'
        ));
      }

      var pricelist_items = _.filter(
        self.applicablePricelistItems[pricelist.id],
        function(item) {
          return self.isPricelistItemUsable(item, date);
        }
      );

      return _.find(pricelist_items, function(rule) {
        if (rule.min_quantity && quantity < rule.min_quantity) {
          return false;
        }

        if (rule.base === 'pricelist') {
          let base_pricelist = _.find(self.pos.pricelists, function(pricelist) {
            return pricelist.id === rule.base_pricelist_id[0];
          });
          if (base_pricelist) {
          }
        }

        if (rule.compute_price === 'fixed') {
          return true;
        } else if (rule.compute_price === 'percentage') {
          return true;
        } else {
          return true;
        }

        return false;
      })
    }
  };
Registries.Model.extend(Product, BinauralProduct)
