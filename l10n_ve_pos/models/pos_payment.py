from odoo import api, fields, models


class PosPayment(models.Model):
    _inherit = "pos.payment"

    # Odoo 19 frontend `PosPayment` expects these base fields when creating/
    # mutating payment lines (e.g. setAmount -> pos_order_id.assertEditable()).
    _POS_PAYMENT_CORE_FIELDS = (
        "id",
        "name",
        "uuid",
        "amount",
        "payment_date",
        "payment_method_id",
        "payment_status",
        "ticket",
        "is_change",
        "pos_order_id",
        "currency_id",
        # Required by core's DevicesSynchronisation.constructOrdersDomain,
        # which calls record.write_date.plus(...) on every dynamic model.
        "write_date",
    )

    foreign_rate = fields.Float(
        help="The rate that is gonna be always shown to the user.",
        default=0.0,
        readonly=False,
    )
    foreign_amount = fields.Float(readonly=True, digits=(16, 2))
    foreign_currency_id = fields.Many2one("res.currency", compute="_compute_foreign_currency_id")

    @api.depends()
    def _compute_foreign_currency_id(self):
        for record in self:
            record.foreign_currency_id = record.env.company.foreign_currency_id

    @api.model
    def _load_pos_data_fields(self, config):
        """Keep Odoo 19 core payment contract and extend it with Venezuelan
        foreign-currency fields.

        Important: `pos.load.mixin._load_pos_data_fields` returns `[]` for
        pos.payment in core, which is a special value meaning "load every
        field" (see `_load_pos_data_read`: `records.read(fields, ...)` with
        an empty list reads all fields). Turning that `[]` into an explicit
        whitelist — even one padded with our own required fields — silently
        breaks every OTHER module's pos.payment field (e.g. an analytic
        account added by a subsidiary/cost-center module): anything not in
        this hardcoded list stops reaching the frontend, and the client's
        `related_models` engine rejects it with "field does not exist" the
        moment something tries to set it. Only build the whitelist if some
        ancestor already narrowed it; otherwise, keep passing "all fields"
        through untouched.
        """
        res = super()._load_pos_data_fields(config)
        if not res:
            return res
        required = list(self._POS_PAYMENT_CORE_FIELDS) + [
            "foreign_rate",
            "foreign_amount",
            "foreign_currency_id",
        ]
        for name in required:
            if name not in res:
                res.append(name)
        return res

    def _create_payment_moves(self, is_reverse=False):
        """The function that creates the payment entry was overwritten so that it has the same
        rate as the invoice/order/payment. Each move is matched to its payments through
        ``pos_payment_ids``, not by amount: a move merging a payment and its change carries
        their net.
        """
        # Core sets the move's date with fields.Date.context_today(order,
        # order.date_order), which reads self._context.get("tz") or
        # self.env.user.tz, falling back to UTC when neither is set --
        # common for a POS/cashier account. In Venezuela (UTC-4), from the
        # evening onward the UTC day is already "tomorrow", which then
        # makes l10n_ve_rate's compute_rate() look for a rate that doesn't
        # exist yet. Supplying a Venezuela fallback via context (instead of
        # writing .date() after the fact) keeps the move's date right from
        # creation -- a posted move's date can't be rewritten afterwards.
        #
        # IMPORTANT: the fallback chain below reads the tz from the
        # ORDER's cashier field (order.user_id.tz), never from
        # self.env.context.get("tz"). Odoo freezes a logged-in user's
        # context -- tz included -- into the session cookie once, at LOGIN
        # time (odoo/http.py's finalize(), via res.users.context_get()),
        # and never refreshes it for that session afterwards. A cashier
        # whose tz was blank/wrong at the moment they logged in keeps that
        # stale value in self.env.context for the rest of the shift, even
        # after someone later fixes their user profile to "America/
        # Caracas" -- so reading self.env.context.get("tz") here would
        # silently reproduce the exact bug this fix closes, just moved
        # from the invoice date to the payment move's date. order.user_id
        # .tz is a plain field read straight from the DB on every call, so
        # it always reflects the CURRENT profile value regardless of how
        # stale the request's session context is.
        #
        # Every payment in self belongs to the same order: the only
        # caller, point_of_sale's _generate_pos_order_invoice, invokes
        # this with one order's payment_ids, never a mix -- so reading it
        # once from the first payment is safe.
        # "America/Caracas": same fallback as
        # res.currency.rate._local_date_from_datetime (l10n_ve_rate).
        order = self.mapped("pos_order_id")[:1]
        tz_name = (order.user_id.tz if order else False) or self.env.user.tz or "America/Caracas"
        moves = self.with_context(tz=tz_name)._create_payment_moves_by_method(is_reverse)
        for payment_move in moves:
            payments = payment_move.pos_payment_ids
            payment = payments.filtered(lambda p: not p.is_change)[:1] or payments[:1]
            rate_vals = payment.pos_order_id.config_id._get_move_foreign_rate_vals(
                payment.foreign_rate
            )
            if rate_vals:
                payment_move.write(rate_vals)
            # A move merging a payment and its change carries their net, so its
            # alternate amount is the sum of their signed foreign amounts.
            # Fallback: a change (vuelto) line created server-side may reach
            # here with foreign_amount == 0 (see pos.order._process_payment_lines).
            # Derive it from the order rate so the alternate-currency columns are
            # never silently zeroed (ticket #15090).
            foreign_amount = sum(
                p.foreign_amount
                or (p.amount and p.pos_order_id._amount_to_foreign(p.amount))
                or 0.0
                for p in payments
            )

            for line in payment_move.line_ids:
                line.write(
                    {
                        "not_foreign_recalculate": True,
                        "foreign_debit": abs(foreign_amount) if line.debit > 0 else 0,
                        "foreign_credit": abs(foreign_amount) if line.credit > 0 else 0,
                    }
                )
        return moves

    def _create_payment_moves_by_method(self, is_reverse=False):
        """Keep the change in the payment move of its own payment method.

        Core merges the cash change into the move of the first cash payment of
        the order, whatever its method (the change always goes to the first
        cash method of the POS). The session closing reconciles the POS
        receivable account per payment method, so a move holding payments of
        two methods left two lines that net to zero unreconciled (task 83148,
        H12). Merge the change with a cash payment of its method, or give it
        its own move when there is none. A split-transactions method is
        reconciled per payment, so its change always gets its own move.
        """
        change = self.filtered(lambda p: p.is_change and p.payment_method_id.type == "cash")
        cash_payments = self.filtered(
            lambda p: not p.is_change and p.payment_method_id.type == "cash"
        )
        if not change or not cash_payments:
            return super()._create_payment_moves(is_reverse=is_reverse)
        change_method = change.payment_method_id
        same_method = cash_payments.filtered(
            lambda p: p.payment_method_id == change_method
        )[:1]
        if same_method and len(change_method) == 1 and not change_method.split_transactions:
            # Core merges the change into the first cash payment of the recordset.
            return super(PosPayment, same_method | self)._create_payment_moves(
                is_reverse=is_reverse
            )
        # Alone in the recordset, core gives each change its own move.
        return super(PosPayment, self - change)._create_payment_moves(
            is_reverse=is_reverse
        ) | super(PosPayment, change)._create_payment_moves(is_reverse=is_reverse)
