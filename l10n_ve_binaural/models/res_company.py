from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    exempt_aliquot_sale = fields.Many2one("account.tax", domain=[("type_tax_use", "=", "sale")])
    general_aliquot_sale = fields.Many2one("account.tax", domain=[("type_tax_use", "=", "sale")])
    reduced_aliquot_sale = fields.Many2one("account.tax", domain=[("type_tax_use", "=", "sale")])
    extend_aliquot_sale = fields.Many2one("account.tax", domain=[("type_tax_use", "=", "sale")])
    exempt_aliquot_purchase = fields.Many2one("account.tax", domain=[("type_tax_use", "=", "purchase")])
    general_aliquot_purchase = fields.Many2one("account.tax", domain=[("type_tax_use", "=", "purchase")])
    reduced_aliquot_purchase = fields.Many2one("account.tax", domain=[("type_tax_use", "=", "purchase")])
    extend_aliquot_purchase = fields.Many2one("account.tax", domain=[("type_tax_use", "=", "purchase")])

    group_sales_invoicing_series = fields.Boolean()
