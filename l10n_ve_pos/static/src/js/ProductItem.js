/** @odoo-modules **/

import ProductItem from "point_of_sale.ProductItem";
import Registries from "point_of_sale.Registries";

const BinauralProductItem = (ProductItem) => {
	class BinauralProductItem extends ProductItem {
		get free_qty() {
			return this.props.product.free_qty;
		}

		get show_just_products_with_available_qty() {
			return this.env.pos.config.pos_show_just_products_with_available_qty;
		}

		get show_free_qty() {
			return this.env.pos.config.pos_show_free_qty;
		}
	}
	return BinauralProductItem;
};

Registries.Component.extend(ProductItem, BinauralProductItem);
