# Copyright 2016 Tecnativa - Antonio Espinosa
# Copyright 2017 Tecnativa - Pedro M. Baeza
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    fyc_id = fields.Many2one(
        comodel_name="account.fiscalyear.closing",
        ondelete="cascade",
        string="Fiscal year closing",
        readonly=True,
    )
    closing_type = fields.Selection(
       selection=[
            ("none", "None"),         # Opción por defecto
            ("posted", "Posted"),     # Opción para "posted"
            ("cancel", "Cancel"),     # Opción para "cancel"
        ],
        default="none",
        states={"posted": [("readonly", True)]},
    )