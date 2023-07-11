from odoo import models, fields, _
import logging
_logger = logging.getLogger(__name__)

class ProductTemplate(models.Model):
  _inherit = 'product.template'

  def action_product_catalog_wizard(self):
    view_id = self.env.ref('sh_product_catalog_generator.generate_product_catalog_wizard_view').id

    return {
        'name':_("Catálogo de productos"),#Name You want to display on wizard
        'view_mode': 'form',
        'view_id': view_id,
        'view_type': 'form',
        'res_model': 'product.catalog.wizard',# With . Example sale.order
        'type': 'ir.actions.act_window',
        'target': 'new',
    }
    # return self.env.ref('sh_product_catalog_generator.generate_product_catalog_wizard_action')