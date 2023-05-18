odoo.define('binaural_pos_sale.SaleOrderManagementScreen', function(require) {

  const SaleOrderManagementScreen = require("pos_sale.SaleOrderManagementScreen")
  const Registries = require("point_of_sale.Registries")
  const { _t } = require('web.core');

  const BinauralSaleOrderManagementScreen = (SaleOrderManagementScreen) =>
    class extends SaleOrderManagementScreen {
      async _onClickSaleOrder(event) {
        const origin = this._getSaleOrderOrigin(this.env.pos.get_order())
        if (!origin) {
          return await super._onClickSaleOrder(...arguments)
        }

        const clickedOrder = event.detail;
        let orders = []

        for (const line of this.env.pos.get_order().get_orderlines()) {
            if (line.sale_order_origin_id) {
                orders.push(line.sale_order_origin_id)
            }
        }

        orders = orders.map(el => el.id)

        if (!orders.includes(clickedOrder.id)) {
          return await super._onClickSaleOrder(...arguments)
        }
        
        return this.showPopup('ErrorPopup', {
          title: _t('You already contain this sales order'),
          body: _t(`One of the lines of this order, you already have it including the sales orde`)
        });
      }
    }

  Registries.Component.extend(SaleOrderManagementScreen, BinauralSaleOrderManagementScreen);
  return BinauralSaleOrderManagementScreen
})
