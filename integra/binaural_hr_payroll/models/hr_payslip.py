from calendar import isleap
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from collections import defaultdict

from odoo import api, fields, models, _
from odoo.addons.hr_payroll.models.browsable_object import BrowsableObject
from odoo.tools import html2plaintext, is_html_empty
from odoo.exceptions import UserError
from odoo.tools.misc import format_date


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    report_title_name = fields.Char(
        string="Payslip Name",
        compute="_compute_report_title_name",
        store=True,
        readonly=False,
        states={
            "done": [("readonly", True)],
            "cancel": [("readonly", True)],
            "paid": [("readonly", True)],
        },
    )

    foreign_currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_foreign_id", store=True
    )

    foreign_rate = fields.Float(
        compute="_compute_rate",
        digits="Tasa",
        store=True,
        readonly=False,
    )
    foreign_inverse_rate = fields.Float(
        help="Rate that will be used as factor to multiply of the foreign currency for this payslip.",
        compute="_compute_rate",
        digits=(16, 15),
        store=True,
        readonly=False,
        index=True,
    )

    struct_category = fields.Selection(related="struct_id.category")

    date_from_vacation = fields.Date(
        readonly=True,
        default=lambda self: fields.Date.to_string(date.today().replace(day=1)),
        states={"draft": [("readonly", False)], "verify": [("readonly", False)]},
    )
    date_to_vacation = fields.Date(
        readonly=True,
        default=lambda self: fields.Date.to_string(
            (datetime.now() + relativedelta(months=+1, day=1, days=-1)).date()
        ),
        states={"draft": [("readonly", False)], "verify": [("readonly", False)]},
    )

    employee_prefix_vat = fields.Selection(related="employee_id.prefix_vat")
    employee_vat = fields.Char(related="employee_id.vat")
    employee_bank_account_id = fields.Many2one(
        "res.partner.bank", related="employee_id.bank_account_id"
    )

    _sql_constraints = [
        (
            "payslip_vacation_period_entry_start_before_end",
            "check (date_to_vacation > date_from_vacation)",
            "Starting time of vacation period should be before end time.",
        )
    ]

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

    @api.depends("foreign_currency_id", "payslip_run_id")
    def _compute_rate(self):
        """
        Compute the rate of the payslip using the compute_rate method of the res.currency.rate
        model.
        """
        Rate = self.env["res.currency.rate"]
        for payslip in self:
            if payslip.foreign_inverse_rate:
                continue
            run_id = payslip.payslip_run_id
            if run_id:
                rate_values = {
                    "foreign_rate": run_id.foreign_rate,
                    "foreign_inverse_rate": run_id.foreign_inverse_rate,
                }
            else:
                rate_values = Rate.compute_rate(payslip.foreign_currency_id.id, fields.Date.today())

            payslip.foreign_rate = rate_values["foreign_rate"]
            payslip.foreign_inverse_rate = rate_values["foreign_inverse_rate"]

    def _get_base_is_vef(self):
        self.ensure_one()
        return self.currency_id == self.env.ref("base.VEF")

    def _get_foreign_paid_amount(self):
        self.ensure_one()
        if self.env.context.get("no_paid_amount"):
            return 0.0
        if not self.worked_days_line_ids:
            return self._get_contract_foreign_wage()
        return sum(line.foreign_amount for line in self.worked_days_line_ids)

    def _get_worked_day_lines(self, domain=None, check_out_of_contract=True):
        worked_day_lines = super()._get_worked_day_lines(domain=domain, check_out_of_contract=True)
        work_entry_basic = self.env.ref("binaural_hr_payroll.hr_work_entry_binaural_basic").id
        worked_days_sum = sum(line["number_of_days"] for line in worked_day_lines)

        for r in worked_day_lines:
            if r["work_entry_type_id"] == work_entry_basic:
                february_day = 29 if isleap(self.date_from.year) else 28
                february_day_quincenal = 14 if isleap(self.date_from.year) else 13
                if worked_days_sum > (30 if self.date_from.month != 2 else february_day):
                    r["number_of_days"] -= worked_days_sum - (
                        30 if self.date_from.month != 2 else 28
                    )
                if self.date_from.day == 16 and worked_days_sum > (
                    15 if self.date_from.month != 2 else february_day_quincenal
                ):
                    r["number_of_days"] -= worked_days_sum - (
                        15 if self.date_from.month != 2 else 13
                    )
                if self.date_from.day == 16 and self.date_from.month == 2:
                    r["number_of_days"] += 15 - worked_days_sum
                if worked_days_sum >= february_day and self.date_from.month == 2:
                    r["number_of_days"] += 30 - worked_days_sum

        return worked_day_lines

    def _get_contract_foreign_wage(self):
        self.ensure_one()
        return self.contract_id._get_contract_foreign_wage()

    def _get_payslip_lines(self):
        """
        Overrides the original method to add the foreign amount computation on for each rule.
        """
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
        return line_vals

    def _get_base_local_dict(self):
        localdict = super()._get_base_local_dict()
        allowances = self.employee_id.mapped("allowance_line_ids")
        allowances_values_per_code = {allowance.code: allowance.value for allowance in allowances}

        localdict.update(
            {
                "salario_minimo_actual": self.company_id.law_base_wage,
                "tope_ivss": self.company_id.ivss_wage_treshold,
                "tope_pf": self.company_id.forced_unemployment_wage_treshold,
                "dias_utilidades_config": self.company_id.profit_sharing_days_qty,
                "dias_vacaciones_config": self.company_id.first_year_vacation_days,
                "compute_payroll_using": self.company_id.compute_payroll_using,
                "allowances": BrowsableObject(
                    self.employee_id.id, allowances_values_per_code, self.env
                ),
            }
        )
        return localdict

    @api.depends("employee_id", "struct_id", "date_from")
    def _compute_report_title_name(self):
        for slip in self.filtered(lambda p: p.employee_id and p.date_from):
            lang = slip.employee_id.sudo().address_home_id.lang or self.env.user.lang
            context = {"lang": lang}
            for struct_name in self:
                payslip_name = struct_name.struct_id.name
            del context

            slip.report_title_name = "%(payslip_name)s - %(employee_name)s - %(dates)s" % {
                "payslip_name": payslip_name,
                "employee_name": slip.employee_id.name,
                "dates": format_date(
                    self.env, slip.date_from, date_format="MMMM y", lang_code=lang
                ),
            }

    def _get_localdict(self):
        localdict = super()._get_localdict()
        localdict["foreign_inverse_rate"] = self.foreign_inverse_rate
        localdict["base_is_vef"] = self._get_base_is_vef()
        return localdict

    def action_payslip_done(self):
        res = super().action_payslip_done()
        for slip in self:
            slip._register_payroll_move()
        return res

    def action_payslip_cancel(self):
        res = super().action_payslip_cancel()
        payroll_moves_to_delete = self.env["hr.payroll.move"].search([("slip_id", "in", self.ids)])
        payroll_moves_to_delete.unlink()
        return res

    def _register_payroll_move(self):
        """
        Register an hr.payroll.move record based on the current hr.payslip.

        This method processes the current hr.payslip record to generate and create
        an hr.payroll.move record using the parameters retrieved from the
        _get_payroll_move_params method. It ensures that the payroll move is registered
        unless the payroll structure category is 'provision'.

        Returns
        -------
        hr.payroll.move
            The created hr.payroll.move record.

        Raises
        ------
        ValidationError
            If more than one hr.payslip record is being processed.

        Examples
        --------
        >>> payslip = self.env['hr.payslip'].browse(1)
        >>> payroll_move = payslip._register_payroll_move()
        >>> payroll_move
        <hr.payroll.move record>
        """
        self.ensure_one()
        if self.struct_id.category in ("provision", "other"):
            return
        move_params = self._get_payroll_move_params()
        return self.env["hr.payroll.move"].create(move_params)

    def _get_payroll_move_params(self):
        """
        Retrieve and return a dictionary of parameters for creating an hr.payroll.move record.

        This method processes the current hr.payslip record to generate a dictionary of
        parameters based on the category and specific codes of the payslip lines. The
        parameters are used to create an hr.payroll.move record each time the payslip
        is processed.

        Returns
        -------
        dict
            A dictionary containing the payroll move parameters with keys as defined
            by the category and specific code mappings.

        Raises
        ------
        ValidationError
            If more than one hr.payslip line is being processed.

        Examples
        --------
        >>> payslip = self.env['hr.payslip'].browse(1)
        >>> payslip._get_payroll_move_params()
        {
            'move_type': 'BASIC',
            'employee_id': 1,
            'date': '2023-05-01',
            'slip_id': 1,
            'total_basic': 1000.0,
            'foreign_total_basic': 100.0
        }
        """
        self.ensure_one()
        payroll_structure_category = self.struct_id.category

        move_params = {}
        move_params["move_type"] = payroll_structure_category
        move_params["employee_id"] = self.employee_id.id
        move_params["date"] = self.date_to
        move_params["slip_id"] = self.id

        if payroll_structure_category == "vacation":
            move_params["date_from_vacation"] = self.date_from_vacation
            move_params["date_to_vacation"] = self.date_to_vacation

        move_params_sum = defaultdict(float)
        for line in self.line_ids:
            move_params_per_line = line.get_values_for_payroll_move()
            for key, value in move_params_per_line.items():
                move_params_sum[key] += value

        return {**move_params, **move_params_sum}

    @api.model
    def _compute_monday_in_range(self, slip_id):
        count = 0

        if slip_id:
            payslip = self.env["hr.payslip"].browse(slip_id)

            date_from = date(payslip.date_from.year, payslip.date_from.month, payslip.date_from.day)
            date_to = date(payslip.date_to.year, payslip.date_to.month, payslip.date_to.day)

            for d_ord in range(date_from.toordinal(), date_to.toordinal() + 1):
                d = date.fromordinal(d_ord)
                if d.weekday() == 0:
                    count += 1
        else:
            raise UserWarning("You must add an hr.payslip id for the monday computation")
            # raise UserWarning("Debe agregar un id de hr.payslip para el calculo de lunes")

        return count
