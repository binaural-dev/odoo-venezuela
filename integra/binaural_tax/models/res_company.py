from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    module_binaural_igtf = fields.Boolean("IGTF")
    unique_tax = fields.Boolean()

    exent_aliquot_sale = fields.Many2one("account.tax", domain=[("type_tax_use", "=", "sale")])
    general_aliquot_sale = fields.Many2one("account.tax", domain=[("type_tax_use", "=", "sale")])
    reduced_aliquot_sale = fields.Many2one("account.tax", domain=[("type_tax_use", "=", "sale")])
    extend_aliquot_sale = fields.Many2one("account.tax", domain=[("type_tax_use", "=", "sale")])

    exent_aliquot_purchase = fields.Many2one("account.tax", domain=[("type_tax_use", "=", "purchase")])
    general_aliquot_purchase = fields.Many2one("account.tax", domain=[("type_tax_use", "=", "purchase")])
    reduced_aliquot_purchase = fields.Many2one("account.tax", domain=[("type_tax_use", "=", "purchase")])
    extend_aliquot_purchase = fields.Many2one("account.tax", domain=[("type_tax_use", "=", "purchase")])
