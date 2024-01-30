from odoo import models, fields

class SaleReportBinauralSale(models.Model):
    _inherit = 'sale.report'

    brand_id = fields.Many2one(
        related='product_id.brand_id', 
        string='Marca',
        help='Trademarks related to the product'        
    )        

    brand_name = fields.Char(string='Nombre de la Marca')

    def _select_additional_fields(self):
        res = super()._select_additional_fields()
        res['brand_id'] = "t.brand_id"
        res['brand_name'] = "br.name"
        return res

    def _group_by_sale(self):
        res = super()._group_by_sale()
        res += """,
            t.brand_id,
            br.name
            """
        return res
    
    def _from_sale(self):
        res = super()._from_sale()
        res += """ LEFT JOIN product_brand br ON t.brand_id = br.id """
        return res
