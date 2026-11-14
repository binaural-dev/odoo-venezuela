from odoo import api, fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    foreign_currency_id = fields.Many2one(
        "res.currency", related="company_id.foreign_currency_id"
    )
    foreign_amount_total = fields.Float(
        string="Foreign Total", readonly=True, required=True
    )
    foreign_currency_rate = fields.Float(readonly=True, required=False)

    @api.model
    def _complete_values_from_session(self, session, values):
        """Guarantee ``foreign_amount_total`` (required=True) is never NULL
        at INSERT time, regardless of which channel creates the order.

        Normally the POS frontend computes it client-side
        (``static/src/overrides/models/pos_order.js::serializeForORM``), but
        that patch only loads in the cashier app's asset bundle
        (``point_of_sale._assets_pos``). Any other channel that builds a
        ``pos.order`` without going through that bundle — e.g. the native
        Kiosk/Self-Order app, which ships its own separate bundle — never
        sends the field and the NOT NULL constraint used to raise a raw SQL
        error. ``setdefault`` makes this a no-op for the normal cashier flow
        (the value is already present), so it only fills the gap for
        channels that don't have it.
        """
        values = super()._complete_values_from_session(session, values)
        config = session.config_id
        values.setdefault(
            "foreign_amount_total",
            config._convert(values.get("amount_total") or 0.0, config.currency_id, config.foreign_currency_id),
        )
        values.setdefault(
            "foreign_currency_rate",
            config._get_pos_conversion_rate(config.currency_id, config.foreign_currency_id),
        )
        return values

    @api.model
    def _load_pos_data_read(self, records, config):
        """Inject only the Venezuelan foreign-currency values on top of
        whatever core Odoo 19 already returned. We do NOT touch the
        field contract (``_load_pos_data_fields``) — core owns that.
        """
        read_records = super()._load_pos_data_read(records, config)
        if not read_records:
            return read_records
        records_by_id = {r.id: r for r in records}
        for record in read_records:
            source = records_by_id.get(record["id"])
            if not source:
                continue
            record["foreign_amount_total"] = source.foreign_amount_total
            record["foreign_currency_rate"] = source.foreign_currency_rate
        return read_records

    def _prepare_invoice_vals(self):
        self.ensure_one()
        res = super()._prepare_invoice_vals()
        res.update(self.config_id._get_move_foreign_rate_vals(self.foreign_currency_rate))
        return res

    def _amount_to_foreign(self, amount):
        """Convert a POS main-currency amount (Bs.) into the company's foreign
        currency (USD) using this order's rate, rounded to the foreign
        currency precision.

        Mirrors the frontend ``pos.order.localToForeign`` used to fill
        ``foreign_amount`` on every regular payment line, so any line created
        server-side (e.g. the change/vuelto line) gets the same value.
        """
        self.ensure_one()
        rate = self.foreign_currency_rate
        if not rate:
            return 0.0
        foreign_amount = amount * rate
        foreign_currency = self.foreign_currency_id
        if foreign_currency:
            foreign_amount = foreign_currency.round(foreign_amount)
        return foreign_amount

    def _process_payment_lines(self, pos_order, order, pos_session, draft):
        """Backfill the foreign-currency amount on the change (vuelto) line.

        Odoo core creates the change payment server-side here (``is_change``)
        without a ``foreign_amount``/``foreign_rate``. Both the invoice payment
        moves (``pos.payment._create_payment_moves``) and the session-close
        cross moves (``pos.session``) build the alternate-currency columns
        (``foreign_debit``/``foreign_credit``) from ``payment.foreign_amount``,
        so a missing value left the change move with USD 0,00 and the alternate
        currency unbalanced against the invoice (ticket #15090). Populate it at
        the source so every downstream consumer reads a correct value.
        """
        res = super()._process_payment_lines(pos_order, order, pos_session, draft)
        # Core hands the change back in the currency of the first payment of
        # the order (a $20 bill pays a $12 sale and the change is in $). Odoo 19
        # always gave it in the currency of the register, from the cash method
        # in Bs, and the cross move of the foreign cash only carried what the
        # customer handed over: keep that.
        order.payment_ids.filtered(
            lambda payment: payment.is_change and payment.foreign_currency_id
        ).write({"foreign_currency_id": False, "amount_currency": 0.0})
        change_payments = order.payment_ids.filtered(
            lambda payment: payment.is_change
            and payment.amount
            and not payment.foreign_amount
        )
        for payment in change_payments:
            payment.write(
                {
                    "foreign_amount": order._amount_to_foreign(payment.amount),
                    "foreign_rate": order.foreign_currency_rate,
                }
            )
        # The POS serializes the payments nested in the order, so a bundle
        # older than task 83148 (H7), or an order queued offline with it,
        # sends them without ``foreign_rate``. Fill those with the rate their
        # foreign amounts were valued at.
        payments_without_rate = order.payment_ids.filtered(
            lambda payment: not payment.is_change and not payment.foreign_rate
        )
        rate = order._get_payment_foreign_rate()
        if payments_without_rate and rate:
            payments_without_rate.write({"foreign_rate": rate})
        return res

    def _get_payment_foreign_rate(self):
        """Main → foreign multiplier the payments of this order are valued at:
        the order's own, or the original sale's for a refund (the POS values a
        refund's foreign amounts at the original rate, see
        ``get_effective_foreign_multiplier``)."""
        self.ensure_one()
        original = self.refunded_order_id
        if original and original.foreign_currency_rate:
            return original.foreign_currency_rate
        return self.foreign_currency_rate

    def _process_saved_order(self, draft):
        # Before super: it marks the order paid and creates the payment moves
        # and the invoice, which read the foreign amounts. Runs for the POS
        # sync and for the backend return wizard (pos.make.payment).
        self._align_foreign_signs()
        return super()._process_saved_order(draft)

    def _align_foreign_signs(self):
        """Give ``foreign_amount_total`` and every ``foreign_amount`` the sign
        of their local amount, keeping the magnitude the POS sent.

        POS clients still running a bundle from before task 83148 (H1) send
        refunds with positive foreign amounts next to a negative ``amount``.
        ``binaural_pos_close`` and the session cross moves add
        ``foreign_amount`` as stored, so the refund counted as cash coming in:
        a false shortage at close and a crash on
        ``account_move_line_check_amount_currency_balance_sign`` when the net
        of a foreign cash method was a refund.
        """
        for order in self:
            if order.amount_total * order.foreign_amount_total < 0:
                order.foreign_amount_total = -order.foreign_amount_total
            for payment in order.payment_ids:
                if payment.amount * payment.foreign_amount < 0:
                    payment.foreign_amount = -payment.foreign_amount
                if payment.amount * payment.amount_currency < 0:
                    payment.amount_currency = -payment.amount_currency

    @api.model
    def get_payments_order_refund(self, order_ids):
        if not order_ids:
            return []
        if isinstance(order_ids, int):
            order_ids = [order_ids]
        orders = self.browse(order_ids).exists()
        if not orders:
            return []
        return orders.mapped("payment_ids").read()

    @api.model
    def get_refund_foreign_rate(self, order_ids):
        """Effective local-per-foreign rate the customer actually got on the
        original order's foreign tender.

        Returns ``sum(|amount|) / sum(|foreign_amount|)`` across the original
        order(s) payments made in the company's foreign currency. A refund uses
        this to value a foreign payment line at the EXACT rate the original
        payment was recorded with (mirror the customer's tender), instead of
        re-deriving a rate from the order's rounded aggregate totals — which
        drifts by a few cents. Returns ``0`` when there is no foreign tender
        to mirror (caller falls back to its normal conversion).
        """
        if not order_ids:
            return 0.0
        if isinstance(order_ids, int):
            order_ids = [order_ids]
        orders = self.browse(order_ids).exists()
        if not orders:
            return 0.0
        payments = orders.mapped("payment_ids").filtered(
            lambda p: p.is_foreign_currency
            and p.foreign_currency_id == p.pos_order_id.foreign_currency_id
            and p.foreign_amount
        )
        total_local = sum(abs(p.amount) for p in payments)
        total_foreign = sum(abs(p.foreign_amount) for p in payments)
        return total_local / total_foreign if total_foreign else 0.0

    def _prepare_refund_values(self, current_session):
        return super()._prepare_refund_values(current_session)

    def _prepare_account_move_line_data_from_base_line(self, base_lines):
        """Inject the Venezuelan ``foreign_price`` into the product lines of
        the invoice.

        Safety net for credit notes: if the refund line arrived without a
        foreign price (lines synced before the backfill of
        ``pos.order.line.create``, or any other path), take it from the
        original line so the credit note reverses the USD of the original
        invoice 1:1 instead of recomputing with the rate of the refund day
        (ticket #15106).
        """
        to_create = super()._prepare_account_move_line_data_from_base_line(base_lines)
        for entry in to_create:
            line = entry["metadata"].get("line")
            values = entry["account.move.line"]
            if not line or values.get("display_type") != "product":
                continue
            foreign_price = line.foreign_price
            original_line = line.refunded_orderline_id
            if original_line and not foreign_price:
                foreign_price = original_line.foreign_price
            values["foreign_price"] = foreign_price
        return to_create

    def _prepare_account_move_line_data_for_payments(self, partner=None):
        """Add to the metadata of each payment line the payments it groups and
        their alternate amount, so the closing and the invoice can stamp it on
        the entries that settle them."""
        result = super()._prepare_account_move_line_data_for_payments(partner)
        for entry in result:
            metadata = entry["metadata"]
            payments = self.payment_ids.filtered(
                lambda payment: self._get_payment_group_key(payment, partner)
                == (
                    metadata["payment_method_id"],
                    metadata["foreign_currency_id"],
                    metadata["partner"],
                )
            )
            metadata["payments"] = payments
            metadata["foreign_amount"] = sum(payments.mapped("foreign_amount"))
        return result

    def _order_receipt_generate_taxe_data(self):
        """Add the total in the company's foreign currency to the prices of
        the receipt, as the PoS does (``GeneratePrinterData.generateTaxData``)."""
        prices = super()._order_receipt_generate_taxe_data()
        if self.foreign_currency_id:
            prices["foreign_total_amount"] = self._order_receipt_format_currency(
                self.foreign_amount_total, self.foreign_currency_id
            )
        return prices

    def _get_payment_group_key(self, payment, partner=None):
        """Key core groups the payments of an order with in
        ``_prepare_account_move_line_data_for_payments``."""
        payment_method = payment.payment_method_id
        foreign_currency = payment.foreign_currency_id
        if foreign_currency == payment.currency_id:
            foreign_currency = self.env["res.currency"]
        line_partner = (
            payment.pos_order_id.partner_id
            if payment_method.type == "pay_later"
            else partner
        )
        return (payment_method, foreign_currency, line_partner)

    def _generate_pos_order_invoice(self):
        """Hand ``pos.payment.method._create_payment_line`` the payments that
        settle the invoice, so it stamps their rate and alternate amount on the
        entries it creates before core reconciles them."""
        orders_in_invoice = self.filtered(lambda order: not order.is_globally_invoiced)
        payments_data = []
        for order in orders_in_invoice:
            payments_data += order._prepare_account_move_line_data_for_payments(
                order.partner_id
            )
        return super(
            PosOrder,
            self.with_context(
                l10n_ve_pos_payments_data={
                    "session_closing": False,
                    "entries": payments_data,
                }
            ),
        )._generate_pos_order_invoice()
