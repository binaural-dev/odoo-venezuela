odoo.define('binaural_pos_sale.SaleOrderManagementScreen', function(require) {

  const SaleOrderManagementScreen = require("pos_sale.SaleOrderManagementScreen")
  const Registries = require("point_of_sale.Registries")
  const { _t } = require('web.core');
  const { Orderline } = require('point_of_sale.models');

  const BinauralSaleOrderManagementScreen = (SaleOrderManagementScreen) =>
    class extends SaleOrderManagementScreen {

      async _getSaleOrder(id) {
        const sale_order = await this.rpc({
          model: 'sale.order',
          method: 'read',
          args: [[id], ['order_line', 'partner_id', 'pricelist_id', 'fiscal_position_id', 'amount_total', 'amount_untaxed', 'amount_unpaid', 'partner_shipping_id', 'partner_invoice_id']],
          context: this.env.session.user_context,
        });

        const sale_lines = await this._getSOLines(sale_order[0].order_line);

        if (!this.env.pos.config.available_pricelist_ids.includes(sale_order[0].pricelist_id[0])) {
          const { confirmed } = await Gui.showPopup(
            'ConfirmPopup',
            {
              title: this.env._t(`Are you sure to process the order with ${sale_order[0].pricelist_id[0]} since your checkout currently does not allow that rate?`),
            }
          );
          if (!confirmed) {
            throw new Error()
          }
        }

        sale_order[0].order_line = sale_lines;

        return sale_order[0];
      }
      async _onClickSaleOrder(event) {
        try {
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
        } catch (error) {
          this.close()
        }
      }
    }

  Registries.Component.extend(SaleOrderManagementScreen, BinauralSaleOrderManagementScreen);
  return BinauralSaleOrderManagementScreen
})
