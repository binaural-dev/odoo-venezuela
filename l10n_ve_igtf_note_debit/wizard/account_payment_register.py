from odoo import api, fields, models


class AccountPaymentRegisterIgtfNoteDebit(models.TransientModel):
    _inherit = "account.payment.register"

   
    igtf_note_debit_include_in_payment = fields.Boolean(
        string="Include IGTF in Amount",
        default=lambda self: self.env.company.igtf_note_debit_include_in_payment_default,
    )

    igtf_note_debit_mode = fields.Selection(related="company_id.igtf_note_debit_mode")

    total_amount_with_igtf_note_debit = fields.Monetary(
        string="Total to Pay (payment + IGTF Debit Note)",
        compute="_compute_total_amount_with_igtf_note_debit",
        currency_field="currency_id",
    )

    @api.depends("igtf_note_debit_include_in_payment")
    def _compute_amount(self):

        super()._compute_amount()
        for wizard in self:
            if (
                wizard.igtf_note_debit_mode == "debit_note"
                and wizard.is_igtf
                and not wizard.igtf_note_debit_include_in_payment
                and not wizard.custom_user_amount
            ):
                wizard.amount = wizard.amount_without_difference
                wizard.last_computed_amount = wizard.amount

    @api.depends("amount", "igtf_to_show", "igtf_note_debit_include_in_payment", "is_igtf", "igtf_note_debit_mode")
    def _compute_total_amount_with_igtf_note_debit(self):
        for wizard in self:
            if (
                wizard.igtf_note_debit_mode == "debit_note"
                and wizard.is_igtf
                and not wizard.igtf_note_debit_include_in_payment
            ):
                wizard.total_amount_with_igtf_note_debit = wizard.amount + wizard.igtf_to_show
            else:
                wizard.total_amount_with_igtf_note_debit = wizard.amount

    @api.depends("igtf_note_debit_include_in_payment")
    def _compute_payment_difference(self):
        
        super()._compute_payment_difference()
        for wizard in self:
            if not (
                wizard.igtf_note_debit_mode == "debit_note"
                and wizard.is_igtf
                and not wizard.igtf_note_debit_include_in_payment
                and wizard.payment_date
            ):
                continue
            total_amount_values = wizard._get_total_amounts_to_pay(wizard.batches)
            efective_amount = abs(wizard.amount)
            if wizard.installments_mode == "full":
                wizard.payment_difference = total_amount_values["full_amount_for_difference"] - efective_amount
            else:
                wizard.payment_difference = total_amount_values["amount_for_difference"] - efective_amount

    def _create_payments(self):
        
        payments = super()._create_payments()

        if self.company_id.igtf_note_debit_mode != "debit_note":
            return payments

     
        invoices = self.get_moves()

        if isinstance(invoices, set):
            invoices = sum(invoices, self.env["account.move"])
        if not invoices:
            return payments

        for payment in payments:
            if not payment.igtf_amount or payment.igtf_amount <= 0.0:
                continue

            # Cada `payment` puede corresponder a una factura distinta
            # (pago sin agrupar de varias facturas a la vez) -- se usa la
            # factura realmente conciliada por ESTE pago cuando hay más de
            # una factura en el batch; con una sola, se conserva el mismo
            # comportamiento de siempre (evita depender de que
            # `reconciled_invoice_ids` ya esté actualizado en este punto).
            invoice = invoices[:1]
            if len(invoices) > 1:
                invoice = payment.reconciled_invoice_ids[:1] or invoice

            company_currency = payment.company_id.currency_id
            reconcilable_lines = payment.move_id.line_ids.filtered(
                lambda l: l.account_type in ("asset_receivable", "liability_payable")
            )
            
            payment_total_base = payment.move_id.amount_total_signed
            payment_residual_base = reconcilable_lines.amount_residual

            igtf_amount_company_curr = payment.currency_id._convert(
                payment.igtf_amount, company_currency, payment.company_id, payment.date,
            )
         
            if abs(payment_residual_base) > 0:
                supposed_invoice_amount = payment.currency_id.round(
                    abs(payment_total_base) - abs(igtf_amount_company_curr)
                )
                if abs(supposed_invoice_amount) - abs(invoice.amount_total_signed) <= 0.1:
                    igtf_amount_company_curr = abs(payment_residual_base)

            debit_note = invoice.prepare_igtf_payment_debit_note(
                igtf_amount_company_curr, invoice, payment,
            )

            outstanding_line = reconcilable_lines.filtered(
                lambda l: not l.reconciled and abs(l.amount_residual) > 0.01
            )[:1]
            invoice.settle_igtf_debit_note(
                debit_note, payment,
                include_in_payment=self.igtf_note_debit_include_in_payment,
                outstanding_line=outstanding_line,
            )

        return payments
