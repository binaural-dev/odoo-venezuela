from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    iva_supplier_retention_journal_id = fields.Many2one(
        "account.journal",
        string="Journal for Supplier I.V.A Retentions",
        domain="[('fiscal', '=', True)]",
    )
    iva_customer_retention_journal_id = fields.Many2one(
        "account.journal",
        string="Journal for Customer I.V.A Retentions",
        domain="[('fiscal', '=', True)]",
    )

    islr_supplier_retention_journal_id = fields.Many2one(
        "account.journal",
        string="Journal for Supplier I.S.L.R Retentions",
        domain="[('fiscal', '=', True)]",
    )
    islr_customer_retention_journal_id = fields.Many2one(
        "account.journal",
        string="Journal for Customer I.S.L.R Retentions",
        domain="[('fiscal', '=', True)]",
    )

    municipal_supplier_retention_journal_id = fields.Many2one(
        "account.journal",
        string="Journal for Supplier Municipal Retentions",
        domanin="[('fiscal', '=', True)]",
    )
    municipal_customer_retention_journal_id = fields.Many2one(
        "account.journal",
        string="Journal for Customer Municipal Retentions",
        domain="[('fiscal', '=', True)]",
    )
