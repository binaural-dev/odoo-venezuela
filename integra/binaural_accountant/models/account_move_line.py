from odoo import api, fields, models, _
from odoo.tools import float_compare


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    foreign_currency_id = fields.Many2one(related="move_id.foreign_currency_id", store=True)
    foreign_rate = fields.Float(related="move_id.foreign_rate", store=True)
    foreign_inverse_rate = fields.Float(related="move_id.foreign_inverse_rate", store=True)

    foreign_price = fields.Float(
        help="Foreign Price of the line",
        compute="_compute_foreign_price",
        digits="Tasa",
        store=True,
        readonly=False,
    )
    foreign_subtotal = fields.Monetary(
        help="Foreign Subtotal of the line",
        compute="_compute_foreign_subtotal",
        currency_field="foreign_currency_id",
        store=True,
    )
    foreign_price_total = fields.Monetary(
        help="Foreign Total of the line",
        compute="_compute_foreign_subtotal",
        currency_field="foreign_currency_id",
        store=True,
    )

    # Report fields
    foreign_debit = fields.Monetary(currency_field="foreign_currency_id")
    foreign_credit = fields.Monetary(currency_field="foreign_currency_id")
    foreign_balance = fields.Monetary(
        currency_field="foreign_currency_id",
        compute="_compute_foreign_balance",
        store=True,
        precompute=True,
    )

    foreign_debit_adjustment = fields.Monetary(
        currency_field="foreign_currency_id",
        help="When setted, this field will be used to fill the foreign debit field",
    )
    foreign_credit_adjustment = fields.Monetary(
        currency_field="foreign_currency_id",
        help="When setted, this field will be used to fill the foreign credit field",
    )

    @api.depends("price_unit", "foreign_inverse_rate")
    def _compute_foreign_price(self):
        for line in self:
            line.foreign_price = line.price_unit * line.foreign_inverse_rate

    @api.depends("foreign_price", "quantity", "discount", "tax_ids", "price_unit")
    def _compute_foreign_subtotal(self):
        for line in self:
            line_discount_price_unit = line.foreign_price * (1 - (line.discount / 100.0))
            foreign_subtotal = line_discount_price_unit * line.quantity

            if line.tax_ids:
                taxes_res = line.tax_ids.compute_all(
                    line_discount_price_unit,
                    quantity=line.quantity,
                    currency=line.foreign_currency_id,
                    product=line.product_id,
                    partner=line.partner_id,
                    is_refund=line.is_refund,
                )
                line.foreign_subtotal = taxes_res["total_excluded"]
                line.foreign_price_total = taxes_res["total_included"]
            else:
                line.foreign_price_total = line.foreign_subtotal = foreign_subtotal

    @api.depends("foreign_credit", "foreign_debit")
    def _compute_foreign_balance(self):
        for line in self:
            if line.move_id.is_invoice(include_receipts=True):
                # This may be needed to be changed in the future, when taking into account
                # moves that are not invoices.
                line.foreign_balance = 0.0
            line.foreign_balance = line.foreign_debit - line.foreign_credit

    def _prepare_analytic_distribution_line(
        self, distribution, account_id, distribution_on_each_plan
    ):
        """
        This method adds the foreign_amount in the foreign currency to the analytical account line
        """
        self.ensure_one()
        res = super()._prepare_analytic_distribution_line(
            distribution, account_id, distribution_on_each_plan
        )
        account_id = int(account_id)
        account = self.env["account.analytic.account"].browse(account_id)
        distribution_plan = distribution_on_each_plan.get(account.root_plan_id, 0) + distribution
        decimal_precision = self.env["decimal.precision"].precision_get("Percentage Analytic")
        if float_compare(distribution_plan, 100, precision_digits=decimal_precision) == 0:
            foreign_amount = (
                -self.foreign_balance
                * (100 - distribution_on_each_plan.get(account.root_plan_id, 0))
                / 100.0
            )
        else:
            foreign_amount = -self.foreign_balance * distribution / 100.0

        res["foreign_amount"] = foreign_amount
        return res
