from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    iva_supplier_retention_journal_id = fields.Many2one(
        related="company_id.iva_supplier_retention_journal_id", readonly=False
    )
    iva_customer_retention_journal_id = fields.Many2one(
        related="company_id.iva_customer_retention_journal_id", readonly=False
    )

    islr_supplier_retention_journal_id = fields.Many2one(
        related="company_id.islr_supplier_retention_journal_id", readonly=False
    )
    islr_customer_retention_journal_id = fields.Many2one(
        related="company_id.islr_customer_retention_journal_id", readonly=False
    )

    municipal_supplier_retention_journal_id = fields.Many2one(
        related="company_id.municipal_supplier_retention_journal_id", readonly=False
    )
    municipal_customer_retention_journal_id = fields.Many2one(
        related="company_id.municipal_customer_retention_journal_id", readonly=False
    )

    condition_withholding_id = fields.Many2one(
        related="company_id.condition_withholding_id", readonly=False
    )
    code_visible = fields.Boolean(
        related="company_id.code_visible", readonly=False)

    hide_patent_columns_extra = fields.Boolean(
        related="company_id.hide_patent_columns_extra", readonly=False
    )

    create_retentions_of_suppliers_in_draft = fields.Boolean(
        related="company_id.create_retentions_of_suppliers_in_draft",
        readonly=False,
    )

    hide_issue_date_of_municipal_withholding_receipt = fields.Boolean('Hide issue date of municipal withholding receipt',
        related='company_id.hide_issue_date_of_municipal_withholding_receipt', 
        readonly=False)
