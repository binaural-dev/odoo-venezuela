from odoo import models
import logging
_logger = logging.getLogger(__name__)

class PosSession(models.Model):
    _inherit = 'pos.session'

    def _pos_data_process(self, loaded_data):
        super()._pos_data_process(loaded_data)
        if not self.config_id.module_pos_hr:
            loaded_data['employee_by_id'] = {employee['id']: employee for employee in loaded_data['hr.employee']}

    def _pos_ui_models_to_load(self):
        result = super()._pos_ui_models_to_load()
        if not self.config_id.module_pos_hr:
            new_model = 'hr.employee'
            if new_model not in result:
                result.append(new_model)
        return result

    def _loader_params_hr_employee(self):
        res = super()._loader_params_hr_employee()
        res["search_params"]["fields"].append("is_seller")
        res["search_params"]["domain"] = [('company_id', '=', self.config_id.company_id.id)]
        return res
    
    def _loader_params_res_partner(self):
        res = super()._loader_params_res_partner()
        res["search_params"]["fields"].append("seller_ids")
        return res
