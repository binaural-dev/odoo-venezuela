from odoo import models, fields, api, _


class PosOrder(models.Model):
    _inherit = "pos.order"

    igtf_amount = fields.Float()
    bi_igtf = fields.Float()

    @api.model
    def _order_fields(self, ui_order):
        res = super()._order_fields(ui_order)
        res["igtf_amount"] = ui_order["igtf_amount"]
        return res

    def _payment_fields(self, order, ui_paymentline):
        res = super()._payment_fields(order, ui_paymentline)
        res["include_igtf"] = ui_paymentline["include_igtf"]
        res["igtf_amount"] = ui_paymentline.get("igtf_amount", 0)
        res["foreign_igtf_amount"] = ui_paymentline.get("foreign_igtf_amount", 0)
        
        return res

    def _create_invoice(self, move_vals):
        res = super()._create_invoice(move_vals)
        return res

    def _apply_invoice_payments(self, is_reverse=False):
        """Same as the standard Odoo implementation, but resolving
        ``receivable_account`` through ``pos.payment._get_pos_receivable_account``
        instead of reading ``property_account_receivable_id`` directly.

        Standard Odoo looks up the receivable account straight from the
        partner's property to find the invoice/payment lines to reconcile.
        When the partner has none (e.g. a contact created on the fly from
        the POS), that lookup returns an empty account, so the
        ``if receivable_account.reconcile:`` guard below is skipped and the
        invoice is never reconciled against its payment, even though
        ``_create_payment_moves`` already credited the payment to the
        invoice's own receivable account via the same fallback.
        """
        accounting_partner = self.env["res.partner"]._find_accounting_partner(
            self.partner_id
        )
        receivable_account = self.env["pos.payment"]._get_pos_receivable_account(
            accounting_partner, self
        )
        payment_moves = self.payment_ids.sudo().with_company(
            self.company_id
        )._create_payment_moves(is_reverse)
        if receivable_account.reconcile:
            invoice_receivables = self.account_move.line_ids.filtered(
                lambda line: line.account_id == receivable_account
                and not line.reconciled
            )
            if invoice_receivables:
                credit_line_ids = payment_moves._context.get("credit_line_ids", None)
                payment_receivables = payment_moves.mapped("line_ids").filtered(
                    lambda line: (
                        (credit_line_ids and line.id in credit_line_ids)
                        or (
                            not credit_line_ids
                            and line.account_id == receivable_account
                            and line.partner_id
                        )
                    )
                )
                (invoice_receivables | payment_receivables).sudo().with_company(
                    self.company_id
                ).reconcile()
        return payment_moves
