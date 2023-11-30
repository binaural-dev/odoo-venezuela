from odoo import models, fields
import logging
_logger = logging.getLogger(__name__)

class ProductProduct(models.Model):
  _inherit = 'product.product'
  
  # Used when tree view is displayed as wizard for create new order_lines and set to model
  def set_products_selected(self):

    is_trigger_from_multiselect = self.env.context.get('default_is_trigger_from_multiselect', False)
    record_id = self.env.context.get('default_record_id', None) # x_order id will set the new lines
    model = self.env.context.get('default_model_for_multiselect', None) # The model which belong to x_order
    model_line = self.env.context.get('default_model_line', None)
    field_line_related = self.env.context.get('default_field_line_related', None)
    
    selected_product_ids = self.env.context.get('active_ids', [])
    
    if record_id and is_trigger_from_multiselect and model:

      record = self.env[model].browse(int(record_id))
      
      record.set_new_order_lines(selected_product_ids, model_line, field_line_related)
