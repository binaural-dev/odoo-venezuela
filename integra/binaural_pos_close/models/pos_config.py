from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    last_session_closing_foreign_cash = fields.Float()

    @api.depends("session_ids")
    def _compute_last_session(self):
        res = super()._compute_last_session()
        PosSession = self.env["pos.session"]
        for pos_config in self:
            session = PosSession.search_read(
                [("config_id", "=", pos_config.id), ("state", "=", "closed")],
                [
                    "cash_register_balance_end_real",
                    "stop_at",
                    "foreign_cash_register_balance_end_real",
                ],
                order="stop_at desc",
                limit=1,
            )
            if session:
                pos_config.last_session_closing_foreign_cash = session[0][
                    "foreign_cash_register_balance_end_real"
                ]
            else:
                pos_config.last_session_closing_foreign_cash = 0
        return res
