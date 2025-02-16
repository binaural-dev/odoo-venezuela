from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    module_l10n_ve_igtf = fields.Boolean(readonly=False)

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
        "account.tax", related="company_id.no_deductible_general_aliquot_purchase", readonly=False
    )
    no_deductible_reduced_aliquot_purchase = fields.Many2one(
        "account.tax", related="company_id.no_deductible_reduced_aliquot_purchase", readonly=False
    )
    no_deductible_extend_aliquot_purchase = fields.Many2one(
        "account.tax", related="company_id.no_deductible_extend_aliquot_purchase", readonly=False
    )
