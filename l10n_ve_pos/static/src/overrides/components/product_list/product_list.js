/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ProductsWidget } from "@point_of_sale/app/screens/product_screen/product_list/product_list";

patch(ProductsWidget.prototype, {
  get productsToDisplay() {

    let list = super.productsToDisplay
    
    // Filtrar productos si la configuración lo requiere
    if (!this.pos.config.pos_show_just_products_with_available_qty) {
      return list;
    }
    
    list = list.filter(product => {
      if (product.type === 'service' || product.type === 'consu' || (this.pos.config.allow_sales_on_order && product.pos_sale_on_order)) {
        return true;
      }
      return product.qty_available > 0;
    });

    return list;
  }
});
