import logging
from odoo import models

_logger = logging.getLogger(__name__)


class PosSession(models.Model):
    _inherit = "pos.session"

    def _loader_params_pos_payment_method(self):
        res = super()._loader_params_pos_payment_method()
        res["search_params"]["fields"].append("is_change")
        res["search_params"]["fields"].append("is_payment_p2c")
        res["search_params"]["fields"].append("is_payment_pdv")
        return res

    def _loader_params_res_company(self):
        res = super()._loader_params_res_company()
        res["search_params"]["fields"].append("url_megasoft")
        res["search_params"]["fields"].append("port_megasoft")
        return res
