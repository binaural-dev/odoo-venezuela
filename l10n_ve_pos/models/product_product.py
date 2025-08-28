from odoo import api,fields,models
import logging
_logger = logging.getLogger(__name__)

class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def _load_pos_data_fields(self, config_id):
        res = super()._load_pos_data_fields(config_id)
        return res