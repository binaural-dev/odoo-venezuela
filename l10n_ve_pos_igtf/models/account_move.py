from odoo import api, models


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.depends("amount_residual")
    def compute_bi_igtf(self):
        """Take the IGTF fields of the invoice of a POS order from the order.

        ``l10n_ve_igtf`` reads them from the payment entries of the invoice
        (an entry with a bank line, the receivable and the IGTF line). The POS
        settles the IGTF in its own entry (``pos.payment.method._create_igtf_move``),
        so the base and the amount the cashier charged are read from the order
        instead, the values the invoice had in Odoo 19: base taxable of the
        IGTF, IGTF charged, the base in the currency of the invoice and the
        maximum the IGTF could reach on it. A credit note has no IGTF base,
        as in Odoo 19 (``l10n_ve_igtf`` would add up the payment of the refund).
        """
        super().compute_bi_igtf()
        for move in self.filtered(lambda move: move.move_type in ("out_invoice", "out_refund")):
            orders = move.sudo().pos_order_ids.filtered(
                lambda order: not order.currency_id.is_zero(order.igtf_amount)
            )
            if not orders:
                continue
            if move.move_type == "out_refund":
                move.bi_igtf = move.alter_bi_igtf = move.foreign_bi_igtf = move.igtf_top_aply = 0.0
                continue
            company = move.company_id
            total = abs(move.amount_total_signed)
            base = min(sum(abs(order.bi_igtf) for order in orders), total)
            foreign_base = min(
                company.currency_id._convert(
                    base,
                    move.currency_id,
                    company,
                    move.invoice_date or move.date,
                ),
                abs(move.amount_total),
            )
            move.bi_igtf = base
            move.alter_bi_igtf = sum(abs(order.igtf_amount) for order in orders)
            move.foreign_bi_igtf = foreign_base
            move.igtf_top_aply = base * company.igtf_percentage / 100
