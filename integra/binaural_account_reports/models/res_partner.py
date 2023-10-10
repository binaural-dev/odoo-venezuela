import json

from odoo import models, _


class ResPartner(models.Model):
    _inherit = "res.partner"

    def open_partner_ledger(self):
        """
        Ensures that the partner ledger opened from the partner form is the base currency's one.
        """
        res = super().open_partner_ledger()
        is_usd = self.env.company.currency_foreign_id != self.env.ref("base.USD")
        if not is_usd:
            return res
        res["name"] = _("Partner Ledger USD")
        context = json.loads(res["context"].replace("'", '"'))
        context["usd_report"] = is_usd
        res["context"] = json.dumps(context)
        return res
