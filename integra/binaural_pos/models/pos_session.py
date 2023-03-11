from odoo import models, fields, api

import logging
_logger = logging.getLogger(__name__)


class PosSession(models.Model):
    _inherit = "pos.session"

    def _loader_params_res_currency(self):
        """
        This method is used to get the params for the search_read of res.currency
        """
        res = super()._loader_params_res_currency()
        res["search_params"]["domain"] = [
            ("id", "in", [self.config_id.currency_id.id,self.config_id.foreign_currency_id.id])
        ]
        return res

    def _get_pos_ui_res_currency(self, params):
        """
        This method is used to get the res.currency for the pos
        is override to change the order of the currencies
        ------
        Return:
        Array:
            0: company currency
            1: foreign currency
        """
        res = self.env['res.currency'].search_read(**params['search_params'])
        if res[0]["id"] != self.config_id.currency_id.id:
            return [res[1], res[0]] 
        return res 
