odoo.define('binaural_pos.TicketScreen', function(require) {
  "use strict";

  const Registries = require('point_of_sale.Registries');
  const TicketScreen = require('point_of_sale.TicketScreen');

  const BinauralTicketScreen = (TicketScreen) =>
    class BinauralTicketScreen extends TicketScreen {
      _prepareRefundOrderlineOptions(toRefundDetail) {
        let res = super._prepareRefundOrderlineOptions(toRefundDetail)
        const { orderline } = toRefundDetail;
        res["foreign_currency_rate"] = orderline.foreign_currency_rate
        res["foreign_price"] = orderline.foreign_price
        return res
      }

      _getToRefundDetail(orderline) {
        const partner = orderline.order.get_partner();
        const orderPartnerId = partner ? partner.id : false;
        const newToRefundDetail = {
          qty: 0,
          orderline: {
            id: orderline.id,
            productId: orderline.product.id,
            price: orderline.price,
            foreign_price: orderline.foreign_price,
            qty: orderline.quantity,
            refundedQty: orderline.refunded_qty,
            orderUid: orderline.order.uid,
            orderBackendId: orderline.order.backendId,
            foreign_currency_rate: orderline.order.foreign_currency_rate,
            orderPartnerId,
            tax_ids: orderline.get_taxes().map(tax => tax.id),
            discount: orderline.discount,
          },
          destinationOrderUid: false,
        };
        this.env.pos.toRefundLines[orderline.id] = newToRefundDetail;
        return newToRefundDetail;
      }
      async _onDoRefund() {
        const order = this.getSelectedSyncedOrder();

        if (!order) {
          this._state.ui.highlightHeaderNote = !this._state.ui.highlightHeaderNote;
          return;
        }

        if (this._doesOrderHaveSoleItem(order)) {
          if (!this._prepareAutoRefundOnOrder(order)) {
            // Don't proceed on refund if preparation returned false.
            return;
          }
        }

        const partner = order.get_partner();

        const allToRefundDetails = this._getRefundableDetails(partner);
        if (allToRefundDetails.length == 0) {
          this._state.ui.highlightHeaderNote = !this._state.ui.highlightHeaderNote;
          return;
        }

        // The order that will contain the refund orderlines.
        // Use the destinationOrder from props if the order to refund has the same
        // partner as the destinationOrder.
        const destinationOrder =
          this.props.destinationOrder &&
            partner === this.props.destinationOrder.get_partner() &&
            !this.env.pos.doNotAllowRefundAndSales()
            ? this.props.destinationOrder
            : this._getEmptyOrder(partner);

        // Add orderline for each toRefundDetail to the destinationOrder.
        for (const refundDetail of allToRefundDetails) {
          const product = this.env.pos.db.get_product_by_id(refundDetail.orderline.productId);
          const options = this._prepareRefundOrderlineOptions(refundDetail);
          await destinationOrder.add_product(product, options);
          refundDetail.destinationOrderUid = destinationOrder.uid;
        }

        // Set the partner to the destinationOrder.
        if (partner && !destinationOrder.get_partner()) {
          destinationOrder.set_partner(partner);
          destinationOrder.updatePricelist(partner);
        }

        if (this.env.pos.get_order().cid !== destinationOrder.cid) {
          this.env.pos.set_order(destinationOrder);
        }

        this._onCloseScreen();
      }
    };

  Registries.Component.extend(TicketScreen, BinauralTicketScreen);

  return BinauralTicketScreen;

});
