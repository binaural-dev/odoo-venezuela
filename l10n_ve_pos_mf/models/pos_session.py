from odoo import models, fields, api, _

class PosSession(models.Model):
    _inherit = "pos.session"

    serial_machine = fields.Char(related="config_id.serial_machine")
    report_z = fields.Char()

    def set_report_z(self, values):
        self.write({"report_z": int(values["data"]["_dailyClosureCounter"]) + 1})

    def _loader_params_pos_payment_method(self):
        res = super()._loader_params_pos_payment_method()
        res["search_params"]["fields"].append("code_fiscal_printer")
        return res

    def _loader_params_account_tax(self):
        res = super()._loader_params_account_tax()
        res["search_params"]["fields"].append("fiscal_code")
        return res

    def _loader_params_pos_config(self):
        return super()._loader_params_pos_config()
