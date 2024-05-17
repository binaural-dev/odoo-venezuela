from odoo import api, fields, models, _


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    def _get_base_local_dict(self):
        localdict = super()._get_base_local_dict()
        localdict.update(
            {
                "dias_prestaciones_mes_config": self.company_id.benefits_days_per_month,
                "tipo_calculo_intereses_prestaciones_config": self.company_id.benefits_interest_computation_type,
            }
        )
        return localdict
