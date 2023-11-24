import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, exceptions, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_is_zero

_logger = logging.getLogger(__name__)


class AccountFiscalyearClosingConfig(models.Model):
    # _inherit = "account.fiscalyear.closing.config.abstract"
    _inherit = "account.fiscalyear.closing.config"

    @api.onchange("l_map")
    def onchange_l_map(self):
        # ('company_id','=',self.journal_id.company_id.id),
        # ('company_id','=',self.journal_id.company_id.id),

        accounts = (
            self.env["account.account"]
            .sudo()
            .search([("account_type", "in", ["income", "expenses"])])
        )

        config_a = (
            self.env["account.account"]
            .sudo()
            .search([("account_type", "=", "equity_unaffected")], limit=1)
        )  # esta es la de destino siempre es la misma preguntar cual es
        maps = []
        cont = 1
        # account_len = int(self.env['ir.config_parameter'].sudo().get_param('account_longitude_report'))
        # if not account_len:
        #     raise exceptions.UserError("Por favor configure la longitud de las cuentas contables.")
        if self.l_map:
            # sync
            _logger.info("accounts %s", accounts)
            for a in accounts:
                if len(a.code):
                    vals = {
                        "name": a.name,
                        "src_accounts": a.code,
                        "dest_account_id": config_a.id,
                        "fyc_config_id": self.id,
                    }
                    cont += 1
                    print("vals**************", vals)
                    maps.append((0, 0, vals))
            if len(maps) > 0:
                # self.update({'mapping_ids':maps})
                return {"value": {"mapping_ids": maps}}
        else:
            return {"value": {"mapping_ids": [(5, 0, 0)]}}

    l_map = fields.Boolean(string="Load Accounts")
