from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class HrPayslipLine(models.Model):
    _inherit = "hr.payslip.line"

    def get_values_for_payroll_move(self):
        """
        Retrieve and return a dictionary of payroll move parameters.

        This method extends the parent class's `get_values_for_payroll_move` method by adding
        support for the "liquidation" category code. It adds specific key-value pairs to the
        result dictionary based on the `self.code` attribute when the `self.category_id.code`
        is "liquidation".

        Parameters
        ----------
        self : hr.payslip.line
            The current hr.payslip.line record being processed.

        Returns
        -------
        dict
            A dictionary containing the payroll move parameters with keys as defined by
            the category and specific code mappings.

        Raises
        ------
        ValidationError
            If more than one hr.payslip line is being processed.

        Examples
        --------
        >>> line = self.env['hr.payslip.line'].browse(1)
        >>> line.category_id.code
        'liquidation'
        >>> line.code
        'PDDVMLIQ'
        >>> line.total
        500.0
        >>> line.foreign_total
        50.0
        >>> line.get_values_for_payroll_move()
        {
            'total_vacation': 500.0,
            'foreign_total_vacation': 50.0
        }

        >>> line.code = 'UTILLIQ'
        >>> line.total = 300.0
        >>> line.foreign_total = 30.0
        >>> line.get_values_for_payroll_move()
        {
            'profit_sharing_payment': 300.0,
            'foreign_profit_sharing_payment': 30.0
        }
        """
        result = super().get_values_for_payroll_move()

        if self.category_id.code != "liquidation":
            return result

        code_mappings = {
            "DDVMLIQ": {"vacation_days": "total"},
            "DDVBMLIQ": {"vacation_bonus_days": "total"},
            "PDDVMLIQ": {"total_vacation": "total", "foreign_total_vacation": "foreign_total"},
            "PDDVBMLIQ": {
                "total_vacation_bonus": "total",
                "foreign_total_vacation_bonus": "foreign_total",
            },
            "UTILLIQ": {
                "profit_sharing_payment": "total",
                "foreign_profit_sharing_payment": "foreign_total",
            },
            "PRESTA": {"benefits_payment": "total", "foreign_benefits_payment": "foreign_total"},
        }

        if self.code in code_mappings:
            for key, attr in code_mappings[self.code].items():
                result[key] = getattr(self, attr)

        _logger.warning("Result: %s", result)
        return result
