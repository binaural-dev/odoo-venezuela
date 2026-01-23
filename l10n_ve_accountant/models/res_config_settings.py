from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    unique_tax = fields.Boolean(related="company_id.unique_tax", readonly=False)

    show_discount_on_moves = fields.Boolean(
        related="company_id.show_discount_on_moves", readonly=False
    )

    exent_aliquot_sale = fields.Many2one(
        "account.tax", related="company_id.exent_aliquot_sale", readonly=False
    )
    general_aliquot_sale = fields.Many2one(
        "account.tax", related="company_id.general_aliquot_sale", readonly=False
    )
    reduced_aliquot_sale = fields.Many2one(
        "account.tax", related="company_id.reduced_aliquot_sale", readonly=False
    )
    extend_aliquot_sale = fields.Many2one(
        "account.tax", related="company_id.extend_aliquot_sale", readonly=False
    )
    not_show_reduced_aliquot_sale = fields.Boolean(
        related="company_id.not_show_reduced_aliquot_sale", readonly=False
    )
    not_show_extend_aliquot_sale = fields.Boolean(
        related="company_id.not_show_extend_aliquot_sale", readonly=False
    )

    exent_aliquot_purchase = fields.Many2one(
        "account.tax", related="company_id.exent_aliquot_purchase", readonly=False
    )
    general_aliquot_purchase = fields.Many2one(
        "account.tax", related="company_id.general_aliquot_purchase", readonly=False
    )
    reduced_aliquot_purchase = fields.Many2one(
        "account.tax", related="company_id.reduced_aliquot_purchase", readonly=False
    )
    extend_aliquot_purchase = fields.Many2one(
        "account.tax", related="company_id.extend_aliquot_purchase", readonly=False
    )
    not_show_reduced_aliquot_purchase = fields.Boolean(
        related="company_id.not_show_reduced_aliquot_purchase", readonly=False
    )
    not_show_extend_aliquot_purchase = fields.Boolean(
        related="company_id.not_show_extend_aliquot_purchase", readonly=False
    )

    config_deductible_tax = fields.Boolean(
        related="company_id.config_deductible_tax", readonly=False
    )

    no_deductible_general_aliquot_purchase = fields.Many2one(
        "account.tax",
        related="company_id.no_deductible_general_aliquot_purchase",
        readonly=False,
    )
    no_deductible_reduced_aliquot_purchase = fields.Many2one(
        "account.tax",
        related="company_id.no_deductible_reduced_aliquot_purchase",
        readonly=False,
    )
    no_deductible_extend_aliquot_purchase = fields.Many2one(
        "account.tax",
        related="company_id.no_deductible_extend_aliquot_purchase",
        readonly=False,
    )


    exent_aliquot_purchase_international = fields.Many2one("account.tax",
        related="company_id.exent_aliquot_purchase_international", readonly=False)
    general_aliquot_purchase_international = fields.Many2one("account.tax",
        related="company_id.general_aliquot_purchase_international", readonly=False)
    reduced_aliquot_purchase_international = fields.Many2one("account.tax",
        related="company_id.reduced_aliquot_purchase_international", readonly=False)
    extend_aliquot_purchase_international = fields.Many2one("account.tax",
        related="company_id.extend_aliquot_purchase_international", readonly=False)

    not_show_general_aliquot_purchase_international = fields.Boolean(related="company_id.not_show_general_aliquot_purchase_international", readonly=False)
    not_show_reduced_aliquot_purchase_international = fields.Boolean(related="company_id.not_show_reduced_aliquot_purchase_international", readonly=False)

    not_show_extend_aliquot_purchase_international = fields.Boolean(related="company_id.not_show_extend_aliquot_purchase_international", readonly=False)

    not_show_total_purchases_with_international_iva = fields.Boolean(related="company_id.not_show_total_purchases_with_international_iva", readonly=False)

    not_show_exempt_total_purchases = fields.Boolean(related="company_id.not_show_exempt_total_purchases", readonly=False)

    not_show_total_purchases_international = fields.Boolean(related="company_id.not_show_total_purchases_international", readonly=False)
