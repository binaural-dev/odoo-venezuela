odoo.define("l10n_ve_pos.DB", function(require) {

  const PosDB = require("point_of_sale.DB");
  const utils = require('web.utils');

  PosDB.include({
    /**
     *TODO: This function was overwritten so that when adding a product that already 
     * exists it will overwrite it
     **/
    add_products: function(products) {
      var stored_categories = this.product_by_category_id;

      if (!(products instanceof Array)) {
        products = [products];
      }
      for (var i = 0, len = products.length; i < len; i++) {
        var product = products[i];
        if (product.id in this.product_by_id) {
          /* ADDED */
          this.product_by_id[product.id] = product;
          continue;
        };
        if (product.available_in_pos) {
          var search_string = utils.unaccent(this._product_search_string(product));
          var categ_id = product.pos_categ_id ? product.pos_categ_id[0] : this.root_category_id;
          product.product_tmpl_id = product.product_tmpl_id[0];
          if (!stored_categories[categ_id]) {
            stored_categories[categ_id] = [];
          }
          stored_categories[categ_id].push(product.id);

          if (this.category_search_string[categ_id] === undefined) {
            this.category_search_string[categ_id] = '';
          }
          this.category_search_string[categ_id] += search_string;

          var ancestors = this.get_category_ancestors_ids(categ_id) || [];

          for (var j = 0, jlen = ancestors.length; j < jlen; j++) {
            var ancestor = ancestors[j];
            if (!stored_categories[ancestor]) {
              stored_categories[ancestor] = [];
            }
            stored_categories[ancestor].push(product.id);

            if (this.category_search_string[ancestor] === undefined) {
              this.category_search_string[ancestor] = '';
            }
            this.category_search_string[ancestor] += search_string;
          }
        }
        this.product_by_id[product.id] = product;
        if (product.barcode) {
          this.product_by_barcode[product.barcode] = product;
        }
      }
    }
  })

})
