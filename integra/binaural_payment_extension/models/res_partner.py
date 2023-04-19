from odoo import models, fields


class ResPartner(models.Model):
    _inherit = "res.partner"

    withholding_type_id = fields.Many2one(
        "account.withholding.type",
        string="Withholding Type",
        domain=[("state", "=", True)],
        track_visibility="onchange",
    )

    iva_account = fields.Many2one(
        "account.account", string="IVA Account", track_visibility="onchange"
    )

    islr_account = fields.Many2one(
        "account.account", string="ISLR Account", track_visibility="onchange"
    )

    type_person_id = fields.Many2one(
        "type.person", "Type Person", track_visibility="onchange", store=True
    )

    economic_activity_id = fields.Many2one(
        "economic.activity", "Default Economic Activity", track_visibility="onchange", store=True
    )
