odoo.define('l10n_ve_pos.ProductsWidget', function(require) {

  const ProductsWidget = require("point_of_sale.ProductsWidget");
  const Registries = require("point_of_sale.Registries");

  const BinauralProductWidget = (ProductsWidget) => {
    class BinauralProductWidget extends ProductsWidget {
      get productsToDisplay() {
        let list = [];
        if (this.searchWord !== '') {
          list = this.env.pos.db.search_product_in_category(
            this.selectedCategoryId,
            this.searchWord
          );
        } else {
          list = this.env.pos.db.get_product_by_category(this.selectedCategoryId);
        }
        if(!this.env.pos.config.pos_show_just_products_with_available_qty){
          return super.productsToDisplay
        }

        return list.filter((el) => {
          if (el.detailed_type != 'product') {
            return true
          }
          return el.qty_available > 0
        });
      }
    }
    return BinauralProductWidget;
  };

  Registries.Component.extend(ProductsWidget, BinauralProductWidget);
})
