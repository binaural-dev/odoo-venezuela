from odoo import models
import logging
_logger = logging.getLogger(__name__)

class PosSession(models.Model):
    _inherit = 'pos.session'

    def _loader_params_hr_employee(self):
        res = super()._loader_params_hr_employee()
        res["search_params"]["fields"].append("is_seller")
        res["search_params"]["domain"] = [('company_id', '=', self.config_id.company_id.id)]
        return res
    
    def _loader_params_res_partner(self):
        res = super()._loader_params_res_partner()
        res["search_params"]["fields"].append("seller_ids")
        return res
