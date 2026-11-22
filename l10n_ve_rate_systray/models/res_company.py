from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    show_rate_systray = fields.Boolean(
        string="Show Rate in Top Bar",
        help="Shows the latest exchange rate of the selected currency in the top bar of the "
        "backend: green when it is today's rate, red when it is from a previous date or "
        "there is no rate.",
    )
    rate_systray_currency_id = fields.Many2one(
        "res.currency",
        string="Currency to Show",
        help="Currency whose rate against the company currency is shown in the top bar "
        "(e.g. USD for a company in VES).",
        default=lambda self: self.env.ref("base.USD", raise_if_not_found=False),
    )
