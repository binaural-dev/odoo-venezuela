from odoo import models, api
import numpy as np
import logging

_logger = logging.getLogger(__name__)


class ProductCatalogReport(models.AbstractModel):
    _inherit = "report.sh_product_catalog_generator.product_catalog_doc"

    @api.model
    def _prepare_product_dict(self, record, price, data, currency_id):
        res = super()._prepare_product_dict(record, price, data, currency_id)
        res["brand"] = record.brand_id.name
        return res
