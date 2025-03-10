from odoo import _, api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # customer_journal_id = fields.Many2one(
    #     related="company_id.customer_journal_id", readonly=False
    # )

    # vendor_journal_id = fields.Many2one(
    #     related="company_id.vendor_journal_id", readonly=False
    # )

    date_type_of_month = fields.Selection(related="company_id.date_type_of_month", readonly=False)
