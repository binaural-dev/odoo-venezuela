// BiProductScreen js
odoo.define('binaural_pos.ProductScreen', function(require) {
	"use strict";

  const rpc = require('web.rpc');
  const ajax = require('web.ajax');

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
      is_discount_product(prd){
        if(this.env.pos.config.module_pos_discount 
            && this.env.pos.config.discount_product_id
            && (
              this.env.pos.config.discount_product_id[0] == prd.product_tmpl_id
              || this.env.pos.config.discount_product_id[0] == prd.product_tmpl_id[0]
            )
          ){
            return true
        }
        return false

      }
			async _onClickPay() {
				var self = this;
				let order = this.env.pos.get_order();
				let lines = order.get_orderlines();
				let pos_config = self.env.pos.config;				
				let call_super = true;
        let validation_negative = true;
        if(order.is_refund){
					return super._onClickPay();
        }

        var is_out = _t(' is out of stock.');
        var is_negative = _t('the quantity cannot be negative');
        let title_wrning = ""
        let wrning = []

				if(pos_config.amount_to_zero){
          for (let line of lines) {
              let prd = line.product;
              if(prd.type != "product"){
                  continue;
              }
  
              if (this.is_discount_product(prd)){
                  continue;
              }
  
              let can_sell_product = await this.validate_products(prd.id,line.quantity);
              
              // if(line.quantity > prd.qty_available || prd.qty_available <= 0){ Validacion OFFLINE
              if(can_sell_product == false){
                  call_super = false;
                  title_wrning = _t('Deny Order');
                  wrning.push(prd.display_name)
              }	
          }
      }

        if(!validation_negative){
          let message = _t(is_negative);
          return self.showPopup('ErrorPopup', {
            title: title_wrning,
            body: message,
          });
				}

				if(!call_super){
          let message = wrning.join(", ") + _t(is_out);
          return self.showPopup('ErrorPopup', {
            title: title_wrning,
            body: message,
          });
				}
        return super._onClickPay();
			}

      async validate_products(product_id, qty){
        let can_sell_product = true;
        try {
          const products = await ajax.jsonRpc('/validate_products_order', 'call',
            {
              "line" :product_id,
              "qty" : qty,
            }
          )
          const { can_sell } = products;
          can_sell_product = can_sell

          return can_sell_product

        } catch (error) {
          return false
        }
      }
		};

	Registries.Component.extend(ProductScreen, BinauralProductScreen);

	return BinauralProductScreen;

});
