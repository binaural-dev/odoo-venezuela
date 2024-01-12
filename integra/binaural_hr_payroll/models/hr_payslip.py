from odoo import api, fields, models, _
from odoo.tools import html2plaintext, is_html_empty
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    foreign_currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_foreign_id", store=True
    )

    foreign_rate = fields.Float(
        compute="_compute_rate",
        digits="Tasa",
        default=0.0,
        store=True,
        readonly=False,
    )
    foreign_inverse_rate = fields.Float(
        help="Rate that will be used as factor to multiply of the foreign currency for this move.",
        compute="_compute_rate",
        digits=(16, 15),
        default=0.0,
        store=True,
        readonly=False,
        index=True,
    )

    def _compute_foreign_currency_id(self):
        for slip in self:
            slip.foreign_currency_id = self.env.company.currency_foreign_id

    @api.onchange("foreign_rate")
    def _onchange_foreign_rate(self):
        """
        Onchange the foreign rate and compute the foreign inverse rate
        """
        Rate = self.env["res.currency.rate"]
        for payslip in self:
            if not payslip.foreign_rate:
                return
            payslip.foreign_inverse_rate = Rate.compute_inverse_rate(payslip.foreign_rate)

    @api.depends("date_to")
    def _compute_rate(self):
        """
        Compute the rate of the invoice using the compute_rate method of the res.currency.rate model.
        """
        Rate = self.env["res.currency.rate"]
        for payslip in self:
            if payslip.foreign_inverse_rate:
                continue

            rate_values = Rate.compute_rate(
                self.foreign_currency_id.id, payslip.date_to or fields.Date.today()
            )
            payslip.update(rate_values)

    def _get_foreign_paid_amount(self):
        self.ensure_one()
        if self.env.context.get("no_paid_amount"):
            return 0.0
        if not self.worked_days_line_ids:
            return self._get_contract_foreign_wage()
        return sum(line.foreign_amount for line in self.worked_days_line_ids)

    def _get_worked_day_lines(self, domain=None, check_out_of_contract=True):
        worked_day_lines = super()._get_worked_day_lines(domain=domain, check_out_of_contract=True)
        _logger.warning("WORKEd DAY LINES: %s", worked_day_lines)
        worked_days_sum = sum(line["number_of_days"] for line in worked_day_lines)
        # for line in work
        return worked_day_lines

    # def _get_new_worked_days_lines(self):
    # if not self.struct_id.use_worked_day_lines or self.struct_id.category == "profit_sharing":
    #     return [(5, False, False)]

    # if self.struct_id.category == "liquidation":
    #     last_move_date_to_now = self.employee_id._get_date_range_since_last_salary_move()
    #     domain = [
    #         ("date_start", "in", last_move_date_to_now),
    #         ("date_stop", "in", last_move_date_to_now),
    #     ]
    #     worked_days_line_values = self._get_worked_day_lines(
    #         check_out_of_contract=False, domain=domain
    #     )
    # else:
    #     worked_days_line_values = self._get_worked_day_lines(check_out_of_contract=False)

    # worked_days_lines = self.worked_days_line_ids.browse([])
    # work_entry_basic = self.env.ref("binaural_nomina.hr_work_entry_binaural_basic").id
    # sum_worked_days = sum(x["number_of_days"] for x in worked_days_line_values)

    # for r in worked_days_line_values:
    #     r["payslip_id"] = self.id
    #     if (
    #         r["work_entry_type_id"] == work_entry_basic
    #         and self.struct_id.category == "salary"
    #         and self.schedule_payment != "days"
    #     ):
    #         if sum_worked_days > (30 if self.date_from.month != 2 else 28):
    #             r["number_of_days"] -= sum_worked_days - (
    #                 30 if self.date_from.month != 2 else 28
    #             )
    #         if sum_worked_days >= 28 and self.date_from.month == 2:
    #             r["number_of_days"] += 30 - sum_worked_days
    #     worked_days_lines |= worked_days_lines.new(r)

    # return worked_days_lines

    def _get_contract_foreign_wage(self):
        self.ensure_one()
        return self.contract_id._get_contract_foreign_wage()

    def _get_payslip_lines(self):
        line_vals = []
        for payslip in self:
            if not payslip.contract_id:
                raise UserError(
                    _(
                        "There's no contract set on payslip {name} for {empoyee_name}. "
                        "Check that there is at least a contract set on the employee form."
                    ).format(
                        name=payslip.name,
                        employee_name=payslip.employee_id.name,
                    )
                )

            localdict = self.env.context.get("force_payslip_localdict", None)
            if localdict is None:
                localdict = payslip._get_localdict()

            rules_dict = localdict["rules"].dict
            result_rules_dict = localdict["result_rules"].dict

            blacklisted_rule_ids = self.env.context.get("prevent_payslip_computation_line_ids", [])

            result = {}
            for rule in sorted(payslip.struct_id.rule_ids, key=lambda x: x.sequence):
                if rule.id in blacklisted_rule_ids:
                    continue
                localdict.update(
                    {
                        "result_qty": 1.0,
                        "result_rate": 100,
                        "result_name": False,
                        "foreing_result": None,
                    }
                )
                if rule._satisfy_condition(localdict):
                    # Retrieve the line name in the employee's lang
                    employee_lang = payslip.employee_id.sudo().address_home_id.lang
                    # This actually has an impact, don't remove this line
                    context = {"lang": employee_lang}
                    if rule.code in localdict["same_type_input_lines"]:
                        for multi_line_rule in localdict["same_type_input_lines"][rule.code]:
                            localdict.update({"foreign_result": None})
                            localdict["inputs"].dict[rule.code] = multi_line_rule
                            amount, foreign_amount, qty, rate = rule._compute_rule(localdict)
                            _logger.warning("Foreign amount: %s", foreign_amount)
                            tot_rule = amount * qty * rate / 100.0
                            localdict = rule.category_id._sum_salary_rule_category(
                                localdict, tot_rule
                            )
                            rule_name = payslip._get_rule_name(localdict, rule, employee_lang)
                            line_vals.append(
                                {
                                    "sequence": rule.sequence,
                                    "code": rule.code,
                                    "name": rule_name,
                                    "note": html2plaintext(rule.note)
                                    if not is_html_empty(rule.note)
                                    else "",
                                    "salary_rule_id": rule.id,
                                    "contract_id": localdict["contract"].id,
                                    "employee_id": localdict["employee"].id,
                                    "amount": amount,
                                    "foreign_amount": foreign_amount,
                                    "quantity": qty,
                                    "rate": rate,
                                    "slip_id": payslip.id,
                                }
                            )
                    else:
                        localdict.update({"foreign_result": None})
                        amount, foreign_amount, qty, rate = rule._compute_rule(localdict)
                        _logger.warning("Foreign amount: %s", foreign_amount)
                        # check if there is already a rule computed with that code
                        previous_amount = rule.code in localdict and localdict[rule.code] or 0.0
                        # set/overwrite the amount computed for this rule in the localdict
                        tot_rule = amount * qty * rate / 100.0
                        localdict[rule.code] = tot_rule
                        result_rules_dict[rule.code] = {
                            "total": tot_rule,
                            "amount": amount,
                            "foreign_amount": foreign_amount,
                            "quantity": qty,
                        }
                        rules_dict[rule.code] = rule
                        # sum the amount for its salary category
                        localdict = rule.category_id._sum_salary_rule_category(
                            localdict, tot_rule - previous_amount
                        )
                        rule_name = payslip._get_rule_name(localdict, rule, employee_lang)
                        # create/overwrite the rule in the temporary results
                        result[rule.code] = {
                            "sequence": rule.sequence,
                            "code": rule.code,
                            "name": rule_name,
                            "note": html2plaintext(rule.note)
                            if not is_html_empty(rule.note)
                            else "",
                            "salary_rule_id": rule.id,
                            "contract_id": localdict["contract"].id,
                            "employee_id": localdict["employee"].id,
                            "amount": amount,
                            "foreign_amount": foreign_amount,
                            "quantity": qty,
                            "rate": rate,
                            "slip_id": payslip.id,
                        }
            line_vals += list(result.values())
        _logger.warning("LINE VALS: %s", line_vals)
        return line_vals

        # line_vals = super()._get_payslip_lines()
        # HrPayslip = self.env["hr.payslip"]
        # HrSalaryRule = self.env["hr.salary.rule"]
        # for vals in line_vals:
        #     localdict = self.env.context.get("force_payslip_localdict", None)
        #     payslip = HrPayslip.browse(vals["slip_id"])
        #     if localdict is None:
        #         localdict = payslip._get_localdict()
        #     rule = HrSalaryRule.browse(vals["salary_rule_id"])
        #     if rule._satisfy_condition(localdict):
        #         if rule.id in localdict["same_type_input_lines"]:
        #             for multi_line_rule in localdict["same_type_input_lines"][rule.code]:
        #                 localdict["inputs"].dict[rule.code] = multi_line_rule
        #                 amount, qty, rate = rule._compute_rule(localdict)
        #                 tot_rule = amount * qty * rate / 100.0
        #                 localdict = rule.category_id._sum_salary_rule_category(localdict, tot_rule)
        #         vals["foreign_amount"] = rule._compute_rule_foreign_result(localdict)
        # return line_vals

    def _get_localdict(self):
        localdict = super()._get_localdict()
        localdict["foreign_inverse_rate"] = self.foreign_inverse_rate
        return localdict
