from odoo import api, fields, models, _
from odoo.tools.safe_eval import safe_eval


class HrSalaryRule(models.Model):
    _inherit = "hr.salary.rule"

    foreign_amount_fix = fields.Float()
    foreign_amount_percentage_base = fields.Char()
    amount_python_compute = fields.Text(
        default="""
            # Available variables:
            #----------------------
            # payslip: object containing the payslips
            # employee: hr.employee object
            # contract: hr.contract object
            # rules: object containing the rules code (previously computed)
            # categories: object containing the computed salary rule categories (sum of amount of all rules belonging to that category).
            # worked_days: object containing the computed worked days.
            # inputs: object containing the computed inputs.

            # foreign_inverse_rate: Tasa inversa del recibo.
            # salario_minimo_actual: salario minimo actual en BS asignado por configuracion general
            # tope_ivss: float con tope de salarios en BS para deduccion IVSS asignado por configuracion
            # tope_pf: float con tope de salarios en BS para deduccion paro forzoso asignado por configuracion
            # dias_utilidades_config: int con cantidad de días de utilidades
            # dias_vacaciones_config: int con días de vacaciones del primer año
            # dias_prestaciones_mes_config: int con días de prestaciones por mes
            # tipo_calculo_intereses_prestaciones_config: str con el tipo de cálculo de intereses de prestaciones
            # compute_payroll_using: str conteniendo la información de como se va a calcular el
                                     salario. Los valores posibles son ("base_wage", "foreign_wage")
            # base_is_vef: Booleano que dice si la moneda base es BS


            # Note: returned value have to be set in the variable 'result'
            # El valor alterno a devolver tiene que ser colocado en la variable "foreign_result"

            # El salario alterno del contrato puede ser accedido usando "contract.foreign_wage"

            result = contract.wage * 0.10
            foreign_result = contract.wage * foreign_inverse_rate"""
    )

    def _compute_rule_foreign_result(self, localdict):
        """
        :param localdict: dictionary containing the current computation environment
        :return: returns a tuple (amount, qty, rate)
        :rtype: (float, float, float)
        """
        self.ensure_one()
        if self.amount_select == "fix":
            if not self.foreign_amount_fix:
                return self.amount_fix * localdict["foreign_inverse_rate"] or 0.0
            return self.foreign_amount_fix or 0.0
        if self.amount_select == "percentage":
            if not self.foreign_amount_percentage_base:
                return (
                    float(safe_eval(self.amount_percentage_base, localdict))
                    * localdict["foreign_inverse_rate"]
                )
            return float(safe_eval(self.foreign_amount_percentage_base, localdict))
        else:  # python code
            try:
                safe_eval(self.amount_python_compute or 0.0, localdict, mode="exec", nocopy=True)
                if not "foreign_result" in localdict.keys():
                    localdict["foreign_result"] = (
                        localdict["result"] * localdict["foreign_inverse_rate"]
                    )
                return float(localdict["foreign_result"])
            except Exception as e:
                self._raise_error(localdict, _("Wrong python code defined for:"), e)

    def _compute_rule(self, localdict):
        """
        :param localdict: dictionary containing the current computation environment
        :return: returns a tuple (amount, qty, rate)
        :rtype: (float, float, float)
        """
        self.ensure_one()
        if self.amount_select == "fix":
            try:
                return (
                    self.amount_fix or 0.0,
                    self.foreign_amount_fix,
                    float(safe_eval(self.quantity, localdict)),
                    100.0,
                )
            except Exception as e:
                self._raise_error(localdict, _("Wrong quantity defined for:"), e)
        if self.amount_select == "percentage":
            try:
                return (
                    float(safe_eval(self.amount_percentage_base, localdict)),
                    float(safe_eval(self.foreign_amount_percentage_base, localdict)),
                    float(safe_eval(self.quantity, localdict)),
                    self.amount_percentage or 0.0,
                )
            except Exception as e:
                self._raise_error(localdict, _("Wrong percentage base or quantity defined for:"), e)
        else:  # python code
            try:
                safe_eval(self.amount_python_compute or 0.0, localdict, mode="exec", nocopy=True)
                if localdict.get("foreign_result", None) is None:
                    foreign_result = float(localdict["result"]) * localdict["foreign_inverse_rate"]
                else:
                    foreign_result = float(localdict["foreign_result"])

                return (
                    float(localdict["result"]),
                    foreign_result,
                    localdict.get("result_qty", 1.0),
                    localdict.get("result_rate", 100.0),
                )
            except Exception as e:
                self._raise_error(localdict, _("Wrong python code defined for:"), e)
