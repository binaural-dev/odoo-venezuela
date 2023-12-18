from odoo import models
import logging
_logger = logging.getLogger(__name__)

class PurchaseOrder(models.Model):
  _name = 'purchase.order'
  _inherit = ['purchase.order', 'product.multiselect.abstract']


  def select_product_view(self):

    return self.with_context(
      default_record_id=self.id,
      default_model_for_multiselect='purchase.order',
      default_model_line='purchase.order.line',
      default_field_line_related='order_line',
    ).display_select_product_view()
  
  