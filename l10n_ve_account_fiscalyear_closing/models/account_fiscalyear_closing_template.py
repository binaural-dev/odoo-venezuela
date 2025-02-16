import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, exceptions, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_is_zero

_logger = logging.getLogger(__name__)


class AccountFiscalyearClosingConfigTemplate(models.Model):
    _inherit = "account.fiscalyear.closing.config.template"

    l_map = fields.Boolean(string="Load accounts")

    @api.onchange("l_map")
    def inchange_l_map(self):
        accounts = (
            self.env["account.account"]
            .sudo()
            .search(
                [
                    (
                        "account_type",
                        "in",
                        [
                            "income",
                            "expense",
                            "income_other",
                            "expense_depreciation",
                            "expense_direct_cost",
                        ],
                    ),
                    ("company_id", "in", [self.env.company.id, False]),
                ]
            )
        )

        config_a = (
            self.env["account.account"]
            .sudo()
            .search(
                [
                    ("account_type", "=", "equity_unaffected"),
                    ("company_id", "in", [self.env.company.id, False]),
                ],
                limit=1,
            )
        )

        maps = []
        cont = 1
        if self.l_map:
            # sync

            for a in accounts:
                # en este caso el campo dest_account es string no one2many
                # validar que sean auxiliares
                if len(a.code):
                    vals = {
                        "name": a.name,
                        "src_accounts": a.code,
                        "dest_account": config_a.code,
                        "template_config_id": self.id,
                    }  # fyc_config_id
                    cont += 1
                    maps.append((0, 0, vals))
            if len(maps) > 0:
                # self.update({'mapping_ids':maps})
                return {"value": {"mapping_ids": maps}}
        else:
            return {"value": {"mapping_ids": [(5, 0, 0)]}}
