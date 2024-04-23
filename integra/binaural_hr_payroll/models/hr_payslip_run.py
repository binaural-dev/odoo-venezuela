from odoo import api, fields, models, _


class HrPayslipRun(models.Model):
    _inherit = "hr.payslip.run"

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
        compute="_compute_rate",
        digits=(16, 15),
        store=True,
        readonly=False,
        index=True,
    )

    @api.onchange("foreign_rate")
    def _onchange_foreign_rate(self):
        """
        Onchange the foreign rate and compute the foreign inverse rate
        """
        Rate = self.env["res.currency.rate"]
        for run in self:
            if not run.foreign_rate:
                return
            run.foreign_inverse_rate = Rate.compute_inverse_rate(run.foreign_rate)

    @api.depends("foreign_currency_id")
    def _compute_rate(self):
        """
        Compute the rate of the payslip using the compute_rate method of the res.currency.rate
        model.
        """
        Rate = self.env["res.currency.rate"]
        for run in self:
            if run.foreign_inverse_rate:
                continue

            rate_values = Rate.compute_rate(run.foreign_currency_id.id, fields.Date.today())
            run.foreign_rate = rate_values["foreign_rate"]
            run.foreign_inverse_rate = rate_values["foreign_inverse_rate"]
