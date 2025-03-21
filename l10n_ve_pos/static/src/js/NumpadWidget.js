odoo.define("l10n_ve_pos.NumpadWidget", function (require) {
  "use strict";

  const NumpadWidget = require("point_of_sale.NumpadWidget");
  const Registries = require("point_of_sale.Registries");

  const { Gui } = require("point_of_sale.Gui");
  const { _t } = require("web.core");
  const rpc = require("web.rpc");

  const BinauralNumpadWidget = (NumpadWidget) =>
    class extends NumpadWidget {
      async setup() {
        const userHasGroupChangeQtyOnPosOrder = await this.env.session.user_has_group(
          "l10n_ve_pos.group_change_qty_on_pos_order"
        );
        const userHasGroupChangePriceOnPosOrder = await this.env.session.user_has_group(
          "l10n_ve_pos.group_change_price_on_pos_order"
        );
        if (userHasGroupChangeQtyOnPosOrder) return;

        let mode = "price";
        if (!userHasGroupChangePriceOnPosOrder) {
          mode = "";
        }
        this.trigger("set-numpad-mode", { mode });
      }
      
      sendInput(key) {
        const order = this.env.pos.get_order()
        const selectedLine = order.get_selected_orderline();
        if (!selectedLine){
          return Gui.showPopup("ErrorPopup", {
            title: _t("No product line selected")
            })
          }
        super.sendInput(key);
      }

      async changeMode(mode) {
        const userHasGroupChangeQtyOnPosOrder = await this.env.session.user_has_group(
          "l10n_ve_pos.group_change_qty_on_pos_order"
        );
        const userHasGroupChangePriceOnPosOrder = await this.env.session.user_has_group(
          "l10n_ve_pos.group_change_price_on_pos_order"
        );
        if (mode === "quantity" && !userHasGroupChangeQtyOnPosOrder) {
          this.trigger("set-numpad-mode", { mode: "" });
          return;
        }
        if (mode === "price" && !userHasGroupChangePriceOnPosOrder) {
          this.trigger("set-numpad-mode", { mode: "" });
          return;
        }

        if (mode !== "discount") return await super.changeMode(mode);

        const pos_session_id = this.env.pos.config.current_session_id[0];

        try {
          const isUserAuthorized = await rpc.query({
            model: "pos.session",
            method: "is_user_authorized",
            args: [pos_session_id],
          });

          if (isUserAuthorized) return await super.changeMode(mode);

          Gui.showPopup("ErrorPopup", {
            title: _t("Usuario no autorizado para aplicar descuento"),
          });
        } catch (error) {
          console.error(`Error desconocido: ${error}`);
        }
      }
    };

  Registries.Component.extend(NumpadWidget, BinauralNumpadWidget);
  return NumpadWidget;
});
