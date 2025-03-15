from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PosSession(models.Model):
    _inherit = "pos.session"

    serial_machine = fields.Char(related="config_id.iface_fiscal_data_module.serial_machine")
    iot_mf = fields.Many2one(related="config_id.iface_fiscal_data_module")
    report_z = fields.Char()

    def set_report_z(self, values):
        self.write({"report_z": int(values["data"]["_dailyClosureCounter"]) + 1})

    def _loader_params_pos_payment_method(self):
        res = super()._loader_params_pos_payment_method()
        res["search_params"]["fields"].append("code_fiscal_printer")
        return res

    def _loader_params_iot_device(self):
        res = super()._loader_params_iot_device()
        res["search_params"]["fields"].append("flag_21")
        res["search_params"]["fields"].append("traditional_line")
        return res

    def _loader_params_account_tax(self):
        res = super()._loader_params_account_tax()
        res["search_params"]["fields"].append("fiscal_code")
        return res
