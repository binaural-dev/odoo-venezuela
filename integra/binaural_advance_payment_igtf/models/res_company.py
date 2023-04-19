from odoo import api, fields, models, _

class ResCompany(models.Model):
    _inherit = "res.company"

    advance_payment_igtf_journal_id = fields.Many2one(
        "account.journal",
        string="Advance Payment IGTF Journal",
        help="Journal used for advance payments with IGTF",
    )