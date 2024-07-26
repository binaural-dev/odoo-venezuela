import locale
import logging
from collections import defaultdict

from babel.dates import format_date
from markupsafe import Markup
from odoo import _, api, fields, models
from odoo.tools import float_compare, float_is_zero, plaintext2html

_logger = logging.getLogger(__name__)


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    date = fields.Date(compute="_compute_date", store=True, readonly=False)

    @api.depends("date_to")
    def _compute_date(self):
        for slip in self:
            slip.date = slip.date_to

    def _action_create_account_move(self):
        """
        Overrides the original method so the value of the foreign_credit and foreign_credit are
        setted accordingly for each move line created.
        """
        precision = self.env["decimal.precision"].precision_get("Payroll")

        # Add payslip without run
        payslips_to_post = self.filtered(lambda slip: not slip.payslip_run_id)

        # Adding pay slips from a batch and deleting pay slips with a batch that is not ready for validation.
        payslip_runs = (self - payslips_to_post).mapped("payslip_run_id")
        for run in payslip_runs:
            if run._are_payslips_ready():
                payslips_to_post |= run.slip_ids

        # A payslip need to have a done state and not an accounting move.
        payslips_to_post = payslips_to_post.filtered(
            lambda slip: slip.state == "done" and not slip.move_id
        )

        # Check that a journal exists on all the structures
        if any(not payslip.struct_id for payslip in payslips_to_post):
            raise ValidationError(
                _("One of the contract for these payslips has no structure type.")
            )
        if any(
            not structure.journal_id
            for structure in payslips_to_post.mapped("struct_id")
        ):
            raise ValidationError(
                _("One of the payroll structures has no account journal defined on it.")
            )

        locale = self._context.get("lang") or "es_VE"
        
        if not payslips_to_post:
            return True

        # Map all payslips by structure journal and pay slips month.
        # {'journal_id': {'month': [slip_ids]}}
        slip_mapped_data = defaultdict(
            lambda: defaultdict(lambda: self.env["hr.payslip"])
        )

        for slip in payslips_to_post:
            slip_mapped_data[slip.struct_id.journal_id.id][
                slip.date or fields.Date().end_of(slip.date_to, "month")
            ] |= slip

        month = format_date(slip.date, "MMMM Y", locale=locale).capitalize()

        if len(payslips_to_post) == 1:
            employee = slip.employee_id

        for journal_id in slip_mapped_data:  # For each journal_id.
            for slip_date in slip_mapped_data[journal_id]:  # For each month.
                line_ids = []
                debit_sum = 0.0
                credit_sum = 0.0
                foreign_debit_sum = 0.0
                foreign_credit_sum = 0.0
                date = slip_date
                move_dict = {
                    "narration": "",
                    "ref": (
                        f"{month} - {slip.number} - {employee.prefix_vat}{employee.vat}"
                        if len(payslips_to_post) == 1
                        else month
                    ),
                    "journal_id": journal_id,
                    "date": date,
                    "foreign_rate": slip.foreign_rate,
                    "foreign_inverse_rate": slip.foreign_inverse_rate,
                }

                for slip in slip_mapped_data[journal_id][slip_date]:
                    move_dict["narration"] += plaintext2html(
                        slip.number or "" + " - " + slip.employee_id.name or ""
                    )
                    move_dict["narration"] += Markup("<br/>")
                    slip_lines = slip._prepare_slip_lines(date, line_ids)
                    line_ids.extend(slip_lines)

                for line_id in line_ids:  # Get the debit and credit sum.
                    debit_sum += line_id["debit"]
                    credit_sum += line_id["credit"]
                    foreign_debit_sum += line_id["foreign_debit"]
                    foreign_credit_sum += line_id["foreign_credit"]

                # The code below is called if there is an error in the balance between credit and debit sum.
                if (
                    float_compare(credit_sum, debit_sum, precision_digits=precision)
                    == -1
                ):
                    slip._prepare_adjust_line(
                        line_ids,
                        "credit",
                        debit_sum,
                        credit_sum,
                        date,
                        foreign_debit_sum,
                        foreign_credit_sum,
                    )
                elif (
                    float_compare(debit_sum, credit_sum, precision_digits=precision)
                    == -1
                ):
                    slip._prepare_adjust_line(
                        line_ids,
                        "debit",
                        debit_sum,
                        credit_sum,
                        date,
                        foreign_debit_sum,
                        foreign_credit_sum,
                    )

                # Add accounting lines in the move
                move_dict["line_ids"] = [(0, 0, line_vals) for line_vals in line_ids]
                move = self._create_account_move(move_dict)
                for slip in slip_mapped_data[journal_id][slip_date]:
                    slip.write({"move_id": move.id, "date": date})
        return True

    def _prepare_line_values(self, line, account_id, date, debit, credit):
        """
        Overrides the original method so the value of the foreign_credit and foreign_credit are
        setted accordingly for each move line created.
        """
        values = super()._prepare_line_values(line, account_id, date, debit, credit)

        foreign_amount = abs(line.foreign_total)
        foreign_debit = foreign_amount if values["debit"] > 0.0 else 0.0
        foreign_credit = foreign_amount if values["credit"] > 0.0 else 0.0

        return {
            **values,
            "foreign_debit": foreign_debit,
            "foreign_credit": foreign_credit,
            "not_foreign_recalculate": True,
        }

    def _prepare_slip_lines(self, date, line_ids):
        """
        Overrides the original method so the value of the foreign_credit and foreign_credit are
        setted accordingly for each move line created.
        """
        self.ensure_one()
        precision = self.env["decimal.precision"].precision_get("Payroll")
        new_lines = []
        for line in self.line_ids.filtered(lambda line: line.category_id):
            amount = line.total
            foreign_amount = line.foreign_total
            if line.code == "NET":  # Check if the line is the 'Net Salary'.
                for tmp_line in self.line_ids.filtered(lambda line: line.category_id):
                    if (
                        tmp_line.salary_rule_id.not_computed_in_net
                    ):  # Check if the rule must be computed in the 'Net Salary' or not.
                        if amount > 0:
                            amount -= abs(tmp_line.total)
                        elif amount < 0:
                            amount += abs(tmp_line.total)
            if float_is_zero(amount, precision_digits=precision):
                continue
            debit_account_id = line.salary_rule_id.account_debit.id
            credit_account_id = line.salary_rule_id.account_credit.id
            if debit_account_id:  # If the rule has a debit account.
                debit = amount if amount > 0.0 else 0.0
                credit = -amount if amount < 0.0 else 0.0
                foreign_debit = foreign_amount if foreign_amount > 0.0 else 0.0
                foreign_credit = -foreign_amount if foreign_amount < 0.0 else 0.0

                debit_line = self._get_existing_lines(
                    line_ids + new_lines, line, debit_account_id, debit, credit
                )

                if not debit_line:
                    debit_line = self._prepare_line_values(
                        line, debit_account_id, date, debit, credit
                    )
                    debit_line["tax_ids"] = [
                        (4, tax_id)
                        for tax_id in line.salary_rule_id.account_debit.tax_ids.ids
                    ]
                    new_lines.append(debit_line)
                else:
                    debit_line["debit"] += debit
                    debit_line["credit"] += credit
                    debit_line["foreign_debit"] += foreign_debit
                    debit_line["foreign_credit"] += foreign_credit

            if credit_account_id:  # If the rule has a credit account.
                debit = -amount if amount < 0.0 else 0.0
                credit = amount if amount > 0.0 else 0.0
                foreign_debit = -foreign_amount if foreign_amount < 0.0 else 0.0
                foreign_credit = foreign_amount if foreign_amount > 0.0 else 0.0

                credit_line = self._get_existing_lines(
                    line_ids + new_lines, line, credit_account_id, debit, credit
                )

                if not credit_line:
                    credit_line = self._prepare_line_values(
                        line, credit_account_id, date, debit, credit
                    )
                    credit_line["tax_ids"] = [
                        (4, tax_id)
                        for tax_id in line.salary_rule_id.account_credit.tax_ids.ids
                    ]
                    new_lines.append(credit_line)
                else:
                    credit_line["debit"] += debit
                    credit_line["credit"] += credit
                    credit_line["foreign_debit"] += foreign_debit
                    credit_line["foreign_credit"] += foreign_credit
        return new_lines

    def _prepare_adjust_line(
        self,
        line_ids,
        adjust_type,
        debit_sum,
        credit_sum,
        date,
        foreign_debit_sum,
        foreign_credit_sum,
    ):
        """
        Overrides the original method so the value of the foreign_credit and foreign_credit are
        setted accordingly for the adjustment line.
        """
        acc_id = self.sudo().journal_id.default_account_id.id
        if not acc_id:
            raise UserError(
                _(
                    'The Expense Journal "%s" has not properly configured the default Account!'
                )
                % (self.journal_id.name)
            )
        existing_adjustment_line = (
            line_id for line_id in line_ids if line_id["name"] == _("Adjustment Entry")
        )
        adjust_credit = next(existing_adjustment_line, False)

        if not adjust_credit:
            adjust_credit = {
                "name": _("Adjustment Entry"),
                "partner_id": False,
                "account_id": acc_id,
                "journal_id": self.journal_id.id,
                "date": date,
                "debit": 0.0 if adjust_type == "credit" else credit_sum - debit_sum,
                "credit": debit_sum - credit_sum if adjust_type == "credit" else 0.0,
                "foreign_debit": (
                    0.0
                    if adjust_type == "credit"
                    else foreign_credit_sum - foreign_debit_sum
                ),
                "foreign_credit": (
                    foreign_debit_sum - foreign_credit_sum
                    if adjust_type == "credit"
                    else 0.0
                ),
                "not_foreign_recalculate": True,
            }
            line_ids.append(adjust_credit)
        else:
            adjust_credit["credit"] = debit_sum - credit_sum
            adjust_credit["foreign_credit"] = foreign_debit_sum - foreign_credit_sum
            adjust_credit["not_foreign_recalculate"] = True
