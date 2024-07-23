odoo.define("binaural_pos_seller.TicketScreen", function(require) {
  const TicketScreen = require("point_of_sale.TicketScreen");
  const Registries = require("point_of_sale.Registries");

  const BinauralPosSellerTicketScreen = (TicketScreen) =>
    class BinauralPosSellerTicketScreen extends TicketScreen {
      _getToRefundDetail(orderline) {
        let res = super._getToRefundDetail(...arguments)
        res["seller_id"] = orderline.order.get_seller()
        return res
      }
    };

  Registries.Component.extend(TicketScreen, BinauralPosSellerTicketScreen);
  return TicketScreen;
});
