from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    unique_tax = fields.Boolean(
        related="company_id.unique_tax", readonly=False)

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

    not_show_total_purchases_with_iva = fields.Boolean(related="company_id.not_show_total_purchases_with_iva", readonly=False)

    not_show_national_exempt_total_purchases = fields.Boolean(related="company_id.not_show_national_exempt_total_purchases", readonly=False)

    not_show_total_purchases_national = fields.Boolean(related="company_id.not_show_total_purchases_national", readonly=False)

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

    not_show_international_purchase_in_book = fields.Boolean(string ="Hide international alicuotes", related="company_id.not_show_international_purchase_in_book", readonly=False)


    @api.onchange(
        'not_show_reduced_aliquot_purchase_international',
        'not_show_extend_aliquot_purchase_international',
        'not_show_general_aliquot_purchase_international')
    def _onchange_international_purchase(self):
        for rec in self:
            all_sub_aliquots_hidden = (
                    rec.not_show_general_aliquot_purchase_international and
                    rec.not_show_reduced_aliquot_purchase_international and
                    rec.not_show_extend_aliquot_purchase_international
                )

            if all_sub_aliquots_hidden and rec.not_show_international_purchase_in_book == False:
                    rec.company_id.not_show_international_purchase_in_book = True
                    rec.not_show_international_purchase_in_book = True 

            if not all_sub_aliquots_hidden:
                 rec.company_id.not_show_international_purchase_in_book = False
                 rec.not_show_international_purchase_in_book = False


    
    def _onchange_international_purchase_all(self):
        for rec in self:
            if rec.not_show_international_purchase_in_book:
                rec.company_id.not_show_general_aliquot_purchase_international = True
                rec.company_id.not_show_reduced_aliquot_purchase_international = True
                rec.company_id.not_show_extend_aliquot_purchase_international = True
                
                rec.not_show_general_aliquot_purchase_international = True
                rec.not_show_reduced_aliquot_purchase_international = True
                rec.not_show_extend_aliquot_purchase_international = True
            else:
                rec.company_id.not_show_general_aliquot_purchase_international = False
                rec.company_id.not_show_reduced_aliquot_purchase_international = False
                rec.company_id.not_show_extend_aliquot_purchase_international = False
                
                rec.not_show_general_aliquot_purchase_international = False
                rec.not_show_reduced_aliquot_purchase_international = False
                rec.not_show_extend_aliquot_purchase_international = False


    def write(self, vals):
        result =  super().write(vals)

        result._onchange_international_purchase_all()

        return result
