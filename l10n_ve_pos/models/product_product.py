from odoo import api,fields,models
import logging
_logger = logging.getLogger(__name__)

class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def _load_pos_data_fields(self, config_id):
        """Extends the list of fields to be loaded for product.product in the POS."""
        res = super()._load_pos_data_fields(config_id)
        return res