from odoo import models
import logging
_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
  _name = 'sale.order'
  _inherit = ['sale.order', 'product.multiselect.abstract']


  def select_product_view(self):

    return self.with_context(
      default_record_id=self.id,
      default_model_for_multiselect='sale.order',
      default_model_line='sale.order.line',
      default_field_line_related='order_line',
    ).display_select_product_view()
  
  