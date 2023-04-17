from odoo import models, fields, api
from collections import defaultdict
from odoo.tools import float_is_zero, float_compare


class PosSession(models.Model):
    _inherit = "pos.session"

    def _loader_params_pos_payment_method(self):
        res = super()._loader_params_pos_payment_method()
        res["search_params"]["fields"].append("apply_igtf")
        return res
