// BiProductScreen js
odoo.define("l10n_ve_pos.ProductScreen", function (require) {
  "use strict";

  const rpc = require("web.rpc");
  const ajax = require("web.ajax");

  const Registries = require("point_of_sale.Registries");
  const ProductScreen = require("point_of_sale.ProductScreen");
  const NumberBuffer = require("point_of_sale.NumberBuffer");
  const { _t } = require("web.core");

  const BinauralProductScreen = (ProductScreen) =>
    class BinauralProductScreen extends ProductScreen {
      super() {
        super.setup();
      }
      onMounted() {
        let res = super.onMounted();
        let lines = this.env.pos.get_order().get_orderlines();
        lines.forEach((line) => {
          if (!!line.refunded_orderline_id) {
            this.env.services
              .rpc({
                model: "pos.order.line",
                method: "search_read",
                domain: [["id", "=", line.refunded_orderline_id]],
                kwargs: {},
              })
              .then((res) => {
                line.tax_ids = res[0].tax_ids;
              });
          }
        });
        return res;
      }

      is_barcode_strict_mode_invalid(barcode = -1) {
        const activate_barcode_strict_mode =
          this.env.pos.config.activate_barcode_strict_mode;

        if (!activate_barcode_strict_mode) return false;

        const order = this.env.pos.get_order();
        const selectedLine = order.get_selected_orderline();

        barcode = barcode === -1 ? selectedLine.product.barcode : barcode;

        if (barcode) return true;
      }

      async _setValue(inputValue, ignore_barcode_strict_code = false) {
        const is_barcode_strict_mode_invalid =
          this.is_barcode_strict_mode_invalid() && !ignore_barcode_strict_code;

        if (
          is_barcode_strict_mode_invalid &&
          !(inputValue == "" || inputValue == "remove")
        )
          return;

        return super._setValue(inputValue);
      }
      async _clickProduct(event) {
        let res = await super._clickProduct(event);
        const product = event.detail;
        const is_barcode_strict_mode_invalid =
          this.is_barcode_strict_mode_invalid(product.barcode);

        if (is_barcode_strict_mode_invalid) return;

        product.optional_product_ids = [];
        return res;
      }
      is_discount_product(prd) {
        if (
          this.env.pos.config.module_pos_discount &&
          this.env.pos.config.discount_product_id &&
          (this.env.pos.config.discount_product_id[0] == prd.product_tmpl_id ||
            this.env.pos.config.discount_product_id[0] ==
              prd.product_tmpl_id[0])
        ) {
          return true;
        }
        return false;
      }
      async _onClickPay() {
        var self = this;
        let order = this.env.pos.get_order();
        let lines = order.get_orderlines();
        let pos_config = self.env.pos.config;
        let call_super = true;
        let validation_negative = true;
        if (order.is_refund) {
          return super._onClickPay();
        }

        var is_out = _t(" is out of stock.");
        var is_negative = _t("the quantity cannot be negative");
        let title_wrning = "";
        let wrning = [];
        let msg_warehouse = "";

        if (pos_config.amount_to_zero) {
          for (let line of lines) {
            let prd = line.product;
            if (prd.type != "product") {
              continue;
            }

            if (this.is_discount_product(prd)) {
              continue;
            }

            // if(line.quantity > prd.qty_available || prd.qty_available <= 0){ Validacion OFFLINE de productos disponibles
            //     call_super = false;
            //     title_wrning = _t('Deny Order');
            //     wrning.push(prd.display_name)
            // }
          }

          // let product_without_stock = await this.validate_products(lines); // Validacion Online de productos disponibles

          // if(product_without_stock){
          //     call_super = false;
          //     title_wrning = _t('Deny Order');
          //     wrning.push(product_without_stock)
          // }
          msg_warehouse = await this.validateProductsInWarehouse(
            lines,
            pos_config,
          );
        }

        if (!validation_negative) {
          let message = _t(is_negative);
          return self.showPopup("ErrorPopup", {
            title: title_wrning,
            body: message,
          });
        }

        if (!call_super) {
          let message = wrning.join(", ") + _t(is_out);
          return self.showPopup("ErrorPopup", {
            title: title_wrning,
            body: message,
          });
        }

        if (msg_warehouse) {
          return self.showPopup("ErrorPopup", {
            title: _t("Validate Product in Warehouse"),
            body: msg_warehouse,
          });
        }
        return super._onClickPay();
      }

      async validate_products(lines) {
        try {
          const product_ids = lines.map((line) => line.product.id);
          const qtys = lines.map((line) => line.quantity);
          const products = await ajax.jsonRpc(
            "/validate_products_order",
            "call",
            {
              lines: product_ids,
              qty: qtys,
            },
          );
          const { msg_error } = products;
          return msg_error;
        } catch (error) {
          return false;
        }
      }

      async validateProductsInWarehouse(lines, pos_config) {
        try {
          const product_ids = lines.map((line) => line.product.id);
          const qtys = lines.map((line) => line.quantity);
          const products = await ajax.jsonRpc(
            "/validate_products_in_warehouse",
            "call",
            {
              product_ids: product_ids,
              qty: qtys,
              picking_type_id: pos_config.picking_type_id,
              sell_kit_from_another_store:
                pos_config.sell_kit_from_another_store,
            },
          );
          const { msg_error } = products;
          return msg_error;
        } catch (error) {
          return false;
        }
      }
    };

  Registries.Component.extend(ProductScreen, BinauralProductScreen);

  return BinauralProductScreen;
});
