// BiProductScreen js
odoo.define('binaural_pos.ProductScreen', function(require) {
	"use strict";

	const Registries = require('point_of_sale.Registries');
	const ProductScreen = require('point_of_sale.ProductScreen');
  const NumberBuffer = require('point_of_sale.NumberBuffer');
    const { _t } = require('web.core');

	const BinauralProductScreen = (ProductScreen) =>
		class BinauralProductScreen extends ProductScreen {
			super() {
				super.setup();
			}
      onMounted() {
        let res = super.onMounted();
        let lines = this.env.pos.get_order().get_orderlines()
        lines.forEach(line => {
          if (!!line.refunded_orderline_id) {
            this.env.services.rpc({
              model: 'pos.order.line',
              method: 'search_read',
              domain: [["id", "=", line.refunded_orderline_id]],
              kwargs: {},
            }).then(res => {
              line.tax_ids = res[0].tax_ids
            })
          }
        })
        return res
      }
      async _clickProduct(event) {
        if (!this.currentOrder) {
            this.env.pos.add_new_order();
        }
        const product = event.detail;
        const options = await this._getAddProductOptions(product);
        // Do not add product if options is undefined.
        product.optional_product_ids = [];
        if (!options) return;
        // Add the product after having the extra information.
        await this._addProduct(product, options);
        NumberBuffer.reset();
      }
			async _onClickPay() {
				var self = this;
				let order = this.env.pos.get_order();
				let lines = order.get_orderlines();
				let pos_config = self.env.pos.config;				
				let call_super = true;
        if(order.is_refund){
					return super._onClickPay();
        }

				let prod_used_qty = {};
                var order_t = _t('Deny Order')
                var is_out = _t(' is out of stock.');
				if(pos_config.amount_to_zero){
					$.each(lines, function( i, line ){
						let prd = line.product;
						if (prd.type == 'product'){
							if(prd.id in prod_used_qty){
								let old_qty = prod_used_qty[prd.id][1];
								prod_used_qty[prd.id] = [prd.qty_available,line.quantity+old_qty]
							}else{
								prod_used_qty[prd.id] = [prd.qty_available,line.quantity]
							}
						}
						if(prd.qty_available <= 0){
							call_super = false;
							let wrning = prd.display_name + _t(is_out);
							self.showPopup('ErrorPopup', {
								title: self.env._t('Zero Quantity Not allowed'),
								body: self.env._t(wrning),
							});
						}
						else{
							if(line.quantity > prd.qty_available){
								call_super = false;
								let wrning = prd.display_name + _t(is_out);
								self.showPopup('ErrorPopup', {
									title: self.env._t(order_t),
									body: self.env._t(wrning),
								});

							}	

						}
					});
				}
				if(call_super){
					super._onClickPay();
				}
			}
		};

	Registries.Component.extend(ProductScreen, BinauralProductScreen);

	return BinauralProductScreen;

});
