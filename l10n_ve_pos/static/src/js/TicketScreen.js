odoo.define('l10n_ve_pos.TicketScreen', function(require) {
  "use strict";

  const Registries = require('point_of_sale.Registries');
  const TicketScreen = require('point_of_sale.TicketScreen');
  const { useListener } = require("@web/core/utils/hooks");
  const NumberBuffer = require('point_of_sale.NumberBuffer');

  const BinauralTicketScreen = (TicketScreen) =>
    class BinauralTicketScreen extends TicketScreen {
      setup() {
        super.setup();
        useListener('do-fullrefund', this._onDoFullRefund);
      }

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

      // Odoo Native Ref: _onUpdateSelectedOrderline (method)
      _onUpdateAllOrderline() {
        NumberBuffer.reset() // Reset numpad widget values to avoid inconsistency

        const order = this.getSelectedSyncedOrder();
        
        if (!order) return;

        for (const orderline of order.orderlines) {
          if (!orderline) continue;
  
          const toRefundDetail = this._getToRefundDetail(orderline);
  
          // When already linked to an order, do not modify the to refund quantity.
          if (toRefundDetail.destinationOrderUid) continue;
  
          const refundableQty = toRefundDetail.orderline.qty - toRefundDetail.orderline.refundedQty;
  
  
          if (refundableQty <= 0) continue ;
  
          toRefundDetail.qty = refundableQty;
          
        }

      }

      // Odoo Native Ref: _onDoRefund (method)
      async _onDoFullRefund() {
        const order = this.getSelectedSyncedOrder();

        if (!order) {
          this._state.ui.highlightHeaderNote = !this._state.ui.highlightHeaderNote;
          return;
        }

        const { confirmed } = await this.showPopup('ConfirmPopup', {
          title: this.env._t('You want to refund all products'),
          body: _.str.sprintf(
            this.env._t('By confirming each product line will be assigned with the total amount to be reimbursed.'),
          ),
        });
        if (!confirmed) return;
        this._onUpdateAllOrderline()
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
