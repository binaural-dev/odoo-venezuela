from odoo import api, fields, models


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
        compute="_compute_rate_systray_currency_id",
        store=True,
        readonly=False,
    )

    @api.depends("currency_id")
    def _compute_rate_systray_currency_id(self):
        """USD por defecto; si la compañía ya está en USD, el bolívar (VEF).

        Solo se propone cuando no hay moneda elegida o coincide con la de la
        compañía: no pisa una elección hecha en Ajustes.
        """
        usd = self.env.ref("base.USD", raise_if_not_found=False)
        vef = self.env.ref("base.VEF", raise_if_not_found=False)
        for company in self:
            current = company.rate_systray_currency_id
            if current and current != company.currency_id:
                continue
            company.rate_systray_currency_id = vef if company.currency_id == usd else usd
