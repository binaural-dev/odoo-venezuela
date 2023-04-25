from odoo import models, fields


class ResPartner(models.Model):
    _inherit = "res.partner"

    withholding_type_id = fields.Many2one(
        "account.withholding.type",
        string="Withholding Type",
        domain=[("state", "=", True)]
    )

    iva_account = fields.Many2one(
        "account.account", string="IVA Account"
    )

    islr_account = fields.Many2one(
        "account.account", string="ISLR Account"
    )

    type_person_id = fields.Many2one(
        "type.person", "Type Person", store=True
    )

    economic_activity_id = fields.Many2one(
        "economic.activity", "Default Economic Activity", store=True
    )
