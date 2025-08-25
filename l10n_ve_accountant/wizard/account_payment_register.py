from odoo import api, fields, models, _
import logging
_logger = logging.getLogger(__name__)

class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    def default_alternate_currency(self):
        """
        This method is used to get the foreign currency of the company and set it as the default value of the foreign currency field

        Returns
        -------
        type = int
            The id of the foreign currency of the company

        """
        alternate_currency = self.env.company.foreign_currency_id.id
        if alternate_currency:
            return alternate_currency
        return False

    foreign_currency_id = fields.Many2one(
        "res.currency",
        default=default_alternate_currency,
    )

    foreign_rate = fields.Float(
        help="The rate of the payment",
        digits="Tasa",
    )
    foreign_inverse_rate = fields.Float(
        help=(
            "Rate that will be used as factor to multiply of the foreign currency for the payment "
            "and the moves created by the wizard."
        ),
        digits=(16, 15),
    )
    base_currency_is_vef = fields.Boolean(
        default=lambda self: self.env.company.currency_id == self.env.ref("base.VEF")
    )

    @api.onchange("foreign_rate")
    def _onchange_foreign_rate(self):
        """
        Onchange the foreign rate and compute the foreign inverse rate
        """
        Rate = self.env["res.currency.rate"]
        for payment in self:
            if not bool(payment.foreign_rate):
                return

            batch_results = payment.batches
            payment.foreign_inverse_rate = Rate.compute_inverse_rate(
                payment.foreign_rate
            )
            total_amount_residual_in_wizard_currency = 0
            _logger.warning( payment._get_total_amounts_to_pay(batch_results))
            payment.amount = total_amount_residual_in_wizard_currency

    @api.onchange("payment_date")
    def _onchange_invoice_date(self):
        """
        Onchange the invoice date and compute the foreign rate
        """
        Rate = self.env["res.currency.rate"]
        for payment in self:
            if not bool(payment.payment_date):
                return
            rate_values = Rate.compute_rate(
                payment.foreign_currency_id.id, payment.payment_date
            )
            payment.update(rate_values)

    def _create_payment_vals_from_wizard(self, batch_result):
        """
        This method is used to add the foreign rate and the foreign inverse rate to the payment
        values that are used to create the payment from the wizard.
        """
        payment_vals = super()._create_payment_vals_from_wizard(batch_result)
        payment_vals.update(
            {
                "foreign_rate": self.foreign_rate,
                "foreign_inverse_rate": self.foreign_inverse_rate,
            }
        )
        return payment_vals

    @api.depends("can_edit_wizard", "amount", "foreign_inverse_rate")
    def _compute_payment_difference(self):
        for wizard in self:
            if wizard.can_edit_wizard:
                batch_results = wizard.batches
                total_amount_residual_in_wizard_currency = (
                    wizard._get_total_amounts_to_pay(
                        batch_results
                    )
                )
                wizard.payment_difference = (
                    total_amount_residual_in_wizard_currency.get('full_amount', 0.0) - wizard.amount
                )
            else:
                wizard.payment_difference = 0.0

    def _get_total_amounts_to_pay(self, batch_results):
        """
        Refactor basado en el método proporcionado.
        Calcula el monto total necesario en la moneda del wizard para conciliar completamente el batch de líneas.
        """
        self.ensure_one()
        next_payment_date = self._get_next_payment_date_in_context()
        amount_per_line_common = []
        amount_per_line_by_default = []
        amount_per_line_full_amount = []
        amount_per_line_for_difference = []
        epd_applied = False
        first_installment_mode = False
        all_lines = self.env['account.move.line']
        for batch_result in batch_results:
            all_lines |= batch_result['lines']
        all_lines = all_lines.sorted(key=lambda line: (line.move_id, line.date_maturity))
        for move, lines in all_lines.grouped('move_id').items():
            installments = lines._get_installments_data(payment_currency=self.currency_id, payment_date=self.payment_date, next_payment_date=next_payment_date)
            last_installment_mode = False
            for installment in installments:
                line = installment['line']
                if installment['type'] == 'early_payment_discount':
                    epd_applied = True
                    amount_per_line_by_default.append(installment)
                    amount_per_line_for_difference.append({
                        **installment,
                        'amount_residual_currency': line.amount_residual_currency,
                        'amount_residual': line.amount_residual,
                    })
                    continue

                # Installments.
                # In case of overdue, all of them are sum as a default amount to be paid.
                # The next installment is added for the difference.
                if (
                    line.display_type == 'payment_term'
                    and installment['type'] in ('overdue', 'next', 'before_date')
                ):
                    if installment['type'] == 'overdue':
                        amount_per_line_common.append(installment)
                    elif installment['type'] == 'before_date':
                        amount_per_line_common.append(installment)
                        first_installment_mode = 'before_date'
                    elif installment['type'] == 'next':
                        if last_installment_mode in ('next', 'overdue', 'before_date'):
                            amount_per_line_full_amount.append(installment)
                        elif not last_installment_mode:
                            amount_per_line_common.append(installment)
                            # if we have several moves and one of them has as first installment, a 'next', we want
                            # the whole batches to have a mode of 'next', overriding an 'overdue' on another move
                            first_installment_mode = 'next'
                    last_installment_mode = installment['type']
                    first_installment_mode = first_installment_mode or last_installment_mode
                    continue

                amount_per_line_common.append(installment)

        common = self._convert_to_wizard_currency(amount_per_line_common)
        by_default = self._convert_to_wizard_currency(amount_per_line_by_default)
        for_difference = self._convert_to_wizard_currency(amount_per_line_for_difference)
        full_amount = self._convert_to_wizard_currency(amount_per_line_full_amount)

        lines = self.env['account.move.line']
        for value in amount_per_line_common + amount_per_line_by_default:
            lines |= value['line']

        return {
            # default amount shown in the wizard (different from full for installments)
            'amount_by_default': abs(common + by_default),
            'full_amount': abs(common + by_default + full_amount),
            # for_difference is used to compute the difference for the Early Payment Discount
            'amount_for_difference': abs(common + for_difference),
            'full_amount_for_difference': abs(common + for_difference + full_amount),
            'epd_applied': epd_applied,
            'installment_mode': first_installment_mode,
            'lines': lines,
        }
