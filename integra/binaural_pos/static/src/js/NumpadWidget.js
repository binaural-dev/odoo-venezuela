odoo.define("binaural_pos.NumpadWidget", function (require) {
  "use strict";

  const NumpadWidget = require("point_of_sale.NumpadWidget");
  const Registries = require("point_of_sale.Registries");

  const { Gui } = require("point_of_sale.Gui");
  const { _t } = require("web.core");
  const rpc = require("web.rpc");

  const BinauralNumpadWidget = (NumpadWidget) =>
    class extends NumpadWidget {
      async setup() {
        const userHasGroupChangeQtyOnPosOrder =
          await this.env.session.user_has_group(
            "binaural_pos.group_change_qty_on_pos_order"
          );
        const userHasGroupChangePriceOnPosOrder =
          await this.env.session.user_has_group(
            "binaural_pos.group_change_price_on_pos_order"
          );
        if (userHasGroupChangeQtyOnPosOrder) return;

        let mode = "price";
        if (!userHasGroupChangePriceOnPosOrder) {
          mode = "";
        }
        this.trigger("set-numpad-mode", { mode });
      }
      async changeMode(mode) {
        const userHasGroupChangeQtyOnPosOrder =
          await this.env.session.user_has_group(
            "binaural_pos.group_change_qty_on_pos_order"
          );
        const userHasGroupChangePriceOnPosOrder =
          await this.env.session.user_has_group(
            "binaural_pos.group_change_price_on_pos_order"
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

        const currentUser = this.env.pos.get_cashier();

        try {
          const isUserAuthorized = await rpc.query({
            model: "pos.session",
            method: "is_user_authorized",
            args: [currentUser.id],
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
