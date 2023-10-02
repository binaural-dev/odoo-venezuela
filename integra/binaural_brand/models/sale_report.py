from odoo import models, fields

class SaleReportBinauralSale(models.Model):
    _inherit = 'sale.report'

    brand_id = fields.Many2one(
        related='product_id.brand_id', 
        string='Marca',
        help='Trademarks related to the product'        
    )        

    def _select_additional_fields(self):
        res = super()._select_additional_fields()
        res['brand_id'] = "t.brand_id"
        return res

    def _group_by_sale(self):
        res = super()._group_by_sale()
        res += """,
            t.brand_id"""
        return res