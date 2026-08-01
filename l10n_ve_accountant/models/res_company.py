from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    taxpayer_type = fields.Selection(
        [
            ("formal", "Formal"),
            ("special", "Special"),
            ("ordinary", "Ordinary"),
        ],
        default="special",
        tracking=True,
    )

    vat = fields.Char(
        string="RIF",
        tracking=True,
    )

    street = fields.Char(tracking=True)

    country_id = fields.Many2one(
        tracking=True,
        default=lambda self: self.env["res.country"].search([("code", "=", "VE")], limit=1),
    )

    unique_tax = fields.Boolean(default=True)
    show_discount_on_moves = fields.Boolean()

    exent_aliquot_sale = fields.Many2one("account.tax", domain=[("type_tax_use", "=", "sale")])
    general_aliquot_sale = fields.Many2one("account.tax", domain=[("type_tax_use", "=", "sale")])
    reduced_aliquot_sale = fields.Many2one("account.tax", domain=[("type_tax_use", "=", "sale")])
    extend_aliquot_sale = fields.Many2one("account.tax", domain=[("type_tax_use", "=", "sale")])
    not_show_reduced_aliquot_sale = fields.Boolean()
    not_show_extend_aliquot_sale = fields.Boolean()

    exent_aliquot_purchase = fields.Many2one(
        "account.tax", domain=[("type_tax_use", "=", "purchase")]
    )
    general_aliquot_purchase = fields.Many2one(
        "account.tax", domain=[("type_tax_use", "=", "purchase")]
    )
    reduced_aliquot_purchase = fields.Many2one(
        "account.tax", domain=[("type_tax_use", "=", "purchase")]
    )
    extend_aliquot_purchase = fields.Many2one(
        "account.tax", domain=[("type_tax_use", "=", "purchase")]
    )
    not_show_reduced_aliquot_purchase = fields.Boolean()
    not_show_extend_aliquot_purchase = fields.Boolean()

    config_deductible_tax = fields.Boolean()

    no_deductible_general_aliquot_purchase = fields.Many2one(
        "account.tax", domain=[("type_tax_use", "=", "purchase")]
    )
    no_deductible_reduced_aliquot_purchase = fields.Many2one(
        "account.tax", domain=[("type_tax_use", "=", "purchase")]
    )
    no_deductible_extend_aliquot_purchase = fields.Many2one(
        "account.tax", domain=[("type_tax_use", "=", "purchase")]
    )

    exent_aliquot_purchase_international = fields.Many2one("account.tax", domain=[("type_tax_use", "=", "purchase")])
    general_aliquot_purchase_international = fields.Many2one("account.tax", domain=[("type_tax_use", "=", "purchase")])
    reduced_aliquot_purchase_international = fields.Many2one("account.tax", domain=[("type_tax_use", "=", "purchase")])
    extend_aliquot_purchase_international = fields.Many2one("account.tax", domain=[("type_tax_use", "=", "purchase")])

    not_show_general_aliquot_purchase_international = fields.Boolean()

    not_show_reduced_aliquot_purchase_international = fields.Boolean()

    not_show_extend_aliquot_purchase_international = fields.Boolean()

    not_show_total_purchases_with_international_iva = fields.Boolean()

    not_show_exempt_total_purchases = fields.Boolean()

    not_show_total_purchases_international = fields.Boolean()

    index_payment_in_wizard = fields.Boolean('index_payment_in_wizard',default=True,help='Apply Indexacion to payment from wizard of invoice')

    indexaxion_payment_mode = fields.Selection([
        ('indexed', 'Indexed (Payment Date Rate)'),
        ('not_indexed', 'Non-Indexed (Invoice Date Rate)'),
        ('to_agreed', 'To be Agreed (Mutual Agreement)'),
    ], string='Type indexacion', default='indexed', help='Defines the exchange rate criteria applied at the time of payment wizard.')

    indexed_default = fields.Boolean('Default indexacion',default=True)

    
