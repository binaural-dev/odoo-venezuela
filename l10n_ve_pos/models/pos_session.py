from odoo import models, fields, api, _, Command
from odoo.tools import float_is_zero, float_compare
from odoo.osv.expression import AND, OR
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class PosSession(models.Model):
    _inherit = "pos.session"

    foreign_currency_id = fields.Many2one(
        "res.currency",
        related="config_id.foreign_currency_id",
        string="Foreign Currency",
    )

    def load_data(self, models_to_load):
        """Odoo 19 replacement for ``load_pos_data``.

        IMPORTANT: Odoo 19 load_data response must contain only model keys.
        Adding ad-hoc top-level keys (e.g. ``prefix_vats``) breaks RecordStore
        parsing with "Index 'id' not defined for model ..." in POS bootstrap.
        """
        return super().load_data(models_to_load)

    def is_user_authorized(self):
        is_group = self.env.user.has_group("l10_ve_pos.group_authorized_discount_pos")
        return is_group

    def _validate_cross_move(self):
        """Create the moves that clear each foreign-currency payment method's
        transitory account into its real ``cross_journal`` account.

        Granularity follows the method's native ``split_transactions``
        ("Identify Customer") flag, mirroring how native Odoo groups its own
        receivable lines in ``_accumulate_amounts``
        (``point_of_sale/models/pos_session.py:892``, keyed by ``pos.payment``
        when split and by payment method when not):

        - ``split_transactions=True``  → one move per ``pos.payment``.
        - ``split_transactions=False`` → one move per payment method and
          session, netting every payment of that method. A zero net creates
          nothing.

        This is the single entry point for both granularities. It replaces a
        two-trigger design where the combine path fired from inside
        ``_create_combine_account_payment`` while this method fired for
        *every* payment regardless of ``split_transactions``: combined bank
        methods ended up with one aggregated move **plus** one move per
        payment, and combined cash methods — which never reach
        ``_create_combine_account_payment`` at all, since
        ``_create_bank_payment_moves`` only walks bank methods (native line
        1057) — got one move per payment and nothing aggregated. Either way
        the "Identify Customer" flag had no visible effect.

        Reading ``pos.payment`` directly, rather than the ``account.payment``
        the native bank pipeline produces, is what lets cash and bank methods
        share this code path.

        Every move is created in ``state="draft"`` (see ``_create_cross_move``)
        — accounting reviews and posts it manually.
        """
        for session in self:
            payments = session.order_ids.payment_ids.filtered(
                lambda p: session._is_cross_move_eligible(p.payment_method_id)
            )
            for payment_method in payments.payment_method_id:
                method_payments = payments.filtered(
                    lambda p: p.payment_method_id == payment_method
                )
                if payment_method.split_transactions:
                    for payment in method_payments:
                        session._create_cross_move_for(
                            payment_method,
                            amount=payment.amount,
                            foreign_amount=payment.foreign_amount,
                            foreign_rate=payment.foreign_rate,
                            partner=payment.partner_id,
                            date=payment.create_date,
                            ref=session._cross_move_ref(payment),
                        )
                    continue

                amount = sum(method_payments.mapped("amount"))
                if float_is_zero(amount, precision_rounding=session.currency_id.rounding):
                    continue
                session._create_cross_move_for(
                    payment_method,
                    amount=amount,
                    foreign_amount=sum(method_payments.mapped("foreign_amount")),
                    # The operative rate is a session-level setting, so every
                    # payment being netted here already shares it. Read it off
                    # a payment rather than off ``config_id.foreign_rate``:
                    # the config value can be edited after the session opened,
                    # while the payments carry the rate actually applied.
                    foreign_rate=method_payments[0].foreign_rate,
                    # No partner, matching the native combined account.payment.
                    partner=session.env["res.partner"],
                    date=session.stop_at or fields.Datetime.now(),
                    ref=session._cross_move_ref(),
                )

    def _is_cross_move_eligible(self, payment_method):
        """Whether ``payment_method`` takes part in the automatic cross move.

        ``is_foreign_currency`` is the business marker that drives the whole
        flow: every foreign-currency method clears its transitory account,
        with no second opt-in. (A redundant ``apply_one_cross_move`` boolean
        used to gate this on top of ``is_foreign_currency``; it was removed,
        since it only served to leave the flow silently inactive on methods
        that plainly needed it.)

        A method missing either cross journal is skipped in silence — that
        configuration is incomplete, not wrong.
        """
        return bool(
            payment_method.is_foreign_currency
            and payment_method.type != "pay_later"
            and payment_method.cross_account_journal
            and payment_method.cross_journal
            and self._get_cross_transitory_account(payment_method)
        )

    def _get_cross_transitory_account(self, payment_method):
        """Return the account the cross move drains — the one where native
        Odoo parked the money once the session closed.

        Which account that is depends on the payment method type, because the
        native pipelines differ:

        - ``bank``: ``_create_combine_account_payment`` posts an
          ``account.payment`` with ``force_outstanding_account_id =
          payment_method.outstanding_account_id`` (native
          ``pos_session.py:1104``), so the balance sits in the outstanding
          account.
        - ``cash``: there is no outstanding account at all —
          ``outstanding_account_id`` is ``invisible="type != 'bank'"`` in the
          native view (``point_of_sale/views/pos_payment_method_views.xml:24``),
          because Odoo routes cash straight to the journal. The statement line
          debits the journal's own default account and credits the POS
          receivable (``_get_combine_statement_line_vals``, native line 1452),
          which leaves the POS receivable squared at zero and the balance in
          ``journal_id.default_account_id``.

        Draining the POS receivable for a cash method would therefore unbalance
        an account already at zero while never touching the cash it was meant
        to move.

        The company's default POS receivable account stays on as a last-resort
        fallback so that an incomplete journal setup degrades into a skipped
        cross move (see ``_is_cross_move_eligible``) rather than an
        ``account_move_line_check_accountable_required_fields`` violation from
        a NULL ``account_id``.
        """
        if payment_method.type == "cash":
            account = payment_method.journal_id.default_account_id
        else:
            account = (
                payment_method.outstanding_account_id
                or payment_method.journal_id.default_account_id
            )
        return account or self.company_id.account_default_pos_receivable_account_id

    def _line_vals_move_cross_incoming(
        self, payment_method, amount, foreign_amount, foreign_rate, partner
    ):
        """Build the cross-move lines for an incoming (amount >= 0) movement.

        Debits the ``cross_journal``'s real bank account and credits the
        transitory account resolved by ``_get_cross_transitory_account``,
        clearing it.

        Takes plain amounts instead of a ``pos.payment`` so the same lines
        serve both granularities of ``_validate_cross_move``: one payment
        (split) or the net of every payment of the method (combine).

        NOTE: the Odoo 17 legacy compared against a hardcoded currency id
        (``== 3``, VEF in the original dev database). Fixed to compare
        against ``self.foreign_currency_id`` (the session's configured
        foreign currency), which does not assume a fixed id.
        """
        transitory_account = self._get_cross_transitory_account(payment_method).id
        account_method = payment_method.cross_journal
        real_account = account_method.inbound_payment_method_line_ids.payment_account_id.id
        line_currency = account_method.currency_id or self.env.company.currency_id
        is_foreign_line_currency = line_currency == self.foreign_currency_id

        return [
            Command.create(
                {
                    "name": _("PoS Payment Method Adjustment"),
                    "account_id": real_account,
                    "partner_id": partner.id,
                    "amount_currency": foreign_amount
                    if is_foreign_line_currency
                    else amount,
                    "credit": 0.0,
                    "foreign_credit": 0.0,
                    "debit": amount,
                    "foreign_debit": foreign_amount,
                    "not_foreign_recalculate": True,
                    "foreign_rate": foreign_rate,
                    "currency_id": line_currency.id,
                }
            ),
            Command.create(
                {
                    "name": _("PoS Payment Method Adjustment"),
                    "account_id": transitory_account,
                    "partner_id": partner.id,
                    "amount_currency": -foreign_amount
                    if self.env.company.currency_id == self.foreign_currency_id
                    else -amount,
                    "debit": 0.0,
                    "foreign_debit": 0.0,
                    "credit": amount,
                    "foreign_credit": foreign_amount,
                    "not_foreign_recalculate": True,
                    "foreign_rate": foreign_rate,
                    "currency_id": self.env.company.currency_id.id,
                }
            ),
        ]

    def _line_vals_move_cross_outgoing(
        self, payment_method, amount, foreign_amount, foreign_rate, partner
    ):
        """Build the cross-move lines for an outgoing (amount < 0) movement.

        Mirror of ``_line_vals_move_cross_incoming`` for change/refunds:
        debits the transitory account (see ``_get_cross_transitory_account``)
        and credits the ``cross_journal``'s real bank account, using
        absolute magnitudes.
        """
        transitory_account = self._get_cross_transitory_account(payment_method).id
        account_method = payment_method.cross_journal
        real_account = account_method.outbound_payment_method_line_ids.payment_account_id.id
        line_currency = account_method.currency_id or self.env.company.currency_id
        is_foreign_line_currency = line_currency == self.foreign_currency_id

        return [
            Command.create(
                {
                    "name": _("PoS Payment Method Adjustment"),
                    "account_id": transitory_account,
                    "partner_id": partner.id,
                    "amount_currency": abs(foreign_amount)
                    if self.env.company.currency_id == self.foreign_currency_id
                    else abs(amount),
                    "credit": 0.0,
                    "foreign_credit": 0.0,
                    "debit": abs(amount),
                    "foreign_debit": abs(foreign_amount),
                    "not_foreign_recalculate": True,
                    "foreign_rate": foreign_rate,
                    "currency_id": self.env.company.currency_id.id,
                }
            ),
            Command.create(
                {
                    "name": _("PoS Payment Method Adjustment"),
                    "account_id": real_account,
                    "partner_id": partner.id,
                    "amount_currency": foreign_amount
                    if is_foreign_line_currency
                    else amount,
                    "debit": 0.0,
                    "foreign_debit": 0.0,
                    "credit": abs(amount),
                    "foreign_credit": abs(foreign_amount),
                    "not_foreign_recalculate": True,
                    "foreign_rate": foreign_rate,
                    "currency_id": line_currency.id,
                }
            ),
        ]

    def _cross_move_ref(self, payment=None):
        """Human-readable reference identifying what a cross move clears.

        ``name`` cannot carry this text — it is the move's sequential
        "Number", assigned by the journal on posting (see
        ``_create_cross_move``) — so ``ref`` is the only field the accountant
        sees in the journal entries list to tell one draft from another.

        Under split granularity a session produces one draft per payment, all
        with the same date, amount shape and journal; without a discriminator
        they are indistinguishable in that list (the move header carries no
        partner either — the partner lives on the lines). So the reference
        goes down to the individual payment, not just the order: an order can
        hold several payments of the same method, in which case the order name
        alone would still repeat.

        ``pos.payment.name`` is a free "Label" that only payment terminals
        populate — it is empty for manual payments — and ``display_name``
        falls back to the formatted amount, which is not unique either. Hence
        the database id as the last-resort discriminator: it is the only value
        guaranteed to differ, and it lets the accountant look the payment up
        directly.

        Under combine granularity a single move covers every payment of the
        method in the session, so the session name is the right granularity.
        """
        base = _("PoS Payment Method Adjustment")
        if not payment:
            return f"{base} - {self.name}"
        return f"{base} - {payment.pos_order_id.name} - {payment.name or f'#{payment.id}'}"

    def _cross_move_header_partner(self, partner):
        """Partner that is safe to put on the cross move's header.

        ``account.move.partner_id`` is ``check_company=True``
        (``account/models/account_move.py:425``) while
        ``account.move.line.partner_id`` is not, and ``pos.order.partner_id``
        has no company check at all
        (``point_of_sale/models/pos_order.py:316``) — so Odoo happily accepts
        an order whose customer belongs to another company. Propagating that
        partner to the header would raise ``UserError`` and **block the whole
        session close**, which is far too high a price for what is only a
        readability nicety in the journal entries list.

        In that case drop it: the lines still carry the partner and ``ref``
        still identifies the payment (see ``_cross_move_ref``).
        """
        if partner.company_id and partner.company_id != self.company_id:
            return self.env["res.partner"]
        return partner

    def _create_cross_move_for(
        self, payment_method, amount, foreign_amount, foreign_rate, partner, date, ref
    ):
        """Create one clearing move for ``payment_method``.

        The sign of ``amount`` picks the direction: incoming for sales,
        outgoing for change/refunds. Under combine granularity ``amount`` is
        already the net of the method's payments, so a session whose refunds
        outweigh its sales yields a single outgoing move — the branch the
        legacy combine path never had.
        """
        line_builder = (
            self._line_vals_move_cross_outgoing
            if amount < 0
            else self._line_vals_move_cross_incoming
        )
        line_vals = line_builder(
            payment_method, amount, foreign_amount, foreign_rate, partner
        )
        return self._create_cross_move(
            payment_method, line_vals, foreign_rate, date, ref, partner
        )

    def _create_cross_move(
        self, payment_method, line_vals, foreign_rate, date, ref, partner
    ):
        """Create the move that clears the transitory account to zero.

        Args:
            payment_method (pos.payment.method): method being cleared.
            line_vals (list): ``Command`` list of move lines to create.
            foreign_rate (float): operative rate stamped on the move.
            date (datetime): accounting date of the move.
            ref (str): reference identifying what is being cleared (see
                ``_cross_move_ref``).
            partner (res.partner): partner for the move header; empty under
                combine granularity, where one move spans several customers.

        Returns:
            account.move: PoS payment method adjustment move.

        The move is always created in ``state="draft"`` — it is not posted
        automatically; accounting reviews and validates it manually.

        ``name`` (the move's sequential "Number") is intentionally left
        unset so that when accounting posts it, Odoo's native
        ``_compute_name`` assigns the next sequence from
        ``cross_account_journal`` — setting it explicitly here would
        permanently block that assignment (``_compute_name`` only calls
        ``_set_next_sequence()`` when ``name`` is empty/``'/'``). The
        descriptive text goes in ``ref`` instead.
        """
        move = self.env["account.move"].create(
            {
                "ref": ref,
                "partner_id": self._cross_move_header_partner(partner).id,
                "date": date,
                "journal_id": payment_method.cross_account_journal.id,
                "state": "draft",
                "line_ids": line_vals,
                "foreign_currency_id": self.foreign_currency_id.id,
                "foreign_rate": foreign_rate,
                "company_id": self.company_id.id,
            }
        )
        return move

    def action_pos_session_close(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None):
        """
        When the session is closed, the cross move is created, and the rounding issue is corrected.
        """
        res = super().action_pos_session_close(balancing_account, amount_to_balance, bank_payment_method_diffs)

        self._validate_cross_move()

        # Obtener todas las órdenes de esta sesión de POS
        orders = self.env['pos.order'].search([('session_id', '=', self.id)])

        for order in orders:
            # Ajuste de redondeo en el total de la orden
            order.amount_total = self._apply_rounding(order.amount_total)

            # Recalcular los impuestos (si es necesario)
            for line in order.lines:
                line.price_subtotal = self._apply_rounding(line.price_subtotal)
                # line.price_total = self._apply_rounding(line.price_total)
            # _logger.info(f"AYUDA {order.state}")
            # # Verificamos si es un reembolso
            # states = ['invoiced','in_refund']
            # if order.state in states:
            #     self._handle_refund(order)

            # Si es necesario, actualiza los apuntes contables o crea nuevos
            self._adjust_accounting_entries(order)

        return res

    def _apply_rounding(self, amount):
        """ Aplica el redondeo a dos decimales (ajusta según la moneda) """
        return round(amount, 2)

    def _adjust_accounting_entries(self, order):
        """ Ajusta o crea los apuntes contables asociados a la orden """
        # Aquí puedes añadir la lógica de ajustes contables si es necesario
        pass

    # def _handle_refund(self, order):
    #     """ Maneja los reembolsos para asegurarse de que los impuestos no se apliquen nuevamente """
    #     for line in order.lines:
    #         # Verifica si la línea tiene un impuesto que no debería aplicarse nuevamente
    #         if line.tax_ids:
    #             for tax in line.tax_ids:
    #                 _logger.info(f"log_tax_before {tax.name}")
    #                 if tax.name == "IGTF":
    #                     _logger.info(f"log_tax_after {tax.name}")  # Ajusta al nombre de tu impuesto IGTF
    #                     # Asegúrate de que el impuesto no se aplique nuevamente en el reembolso
    #                     line.price_subtotal = self._apply_rounding(line.price_subtotal / (1 + (tax.amount / 100)))
    #                     line.price_total = self._apply_rounding(line.price_total / (1 + (tax.amount / 100)))
    #                     break


    def _create_combine_account_payment(self, payment_method, amounts, diff_amount):
        """Odoo 19-compatible override for combine (non-split) bank payments.

        Migration contract (spec ``pos-cross-account-move/spec.md``): the
        pre-C2 override accessed ``res.move_id.payment_id``, which raised
        ``AttributeError`` in Odoo 19 (renamed to ``origin_payment_id`` —
        see the same fix already applied in ``_create_split_account_payment``).

        Native Odoo 19 ``_create_combine_account_payment`` returns the
        receivable ``account.move.line`` on the ``account.payment``'s own
        move (see ``/home/binaural19/odoo/addons/point_of_sale/models/pos_session.py:1094``),
        the same contract as ``_create_split_account_payment``.
        """
        res = super(PosSession, self.with_context(from_pos=True))._create_combine_account_payment(
            payment_method, amounts, diff_amount
        )
        account_payment = res.move_id.origin_payment_id
        if account_payment:
            account_payment.write(
                {
                    "foreign_rate": self.config_id.foreign_rate,
                    "foreign_inverse_rate": self.config_id.foreign_inverse_rate,
                }
            )

        for line in res.move_id.line_ids:
            if line.credit > 0 and amounts.get("foreign_amount", False):
                line.not_foreign_recalculate = True
                line.foreign_credit = abs(amounts["foreign_amount"])

            if line.debit > 0 and amounts.get("foreign_amount", False):
                line.not_foreign_recalculate = True
                line.foreign_debit = abs(amounts["foreign_amount"])
        return res

    def _create_split_account_payment(self, payment, amounts):
        """Odoo 19-compatible override.

        Migration contract (Slice C2.1, spec
        ``pos-odoo19-session-accounting/spec.md``):

        - Odoo 19 super returns an ``account.move.line`` recordset (the
          receivable line on the ``account.payment.move_id``), NOT an
          ``account.payment`` — see
          ``/home/binaural19/odoo/addons/point_of_sale/models/pos_session.py:1170``.
        - When the payment method has no journal, super short-circuits
          and returns ``self.env['account.move.line']`` (empty recordset)
          — see native line 1147-1148. We MUST handle the empty case
          without touching non-existent records.
        - The pre-C2 override accessed ``res.move_id.payment_id`` which
          raised ``AttributeError`` in Odoo 19 (the field on
          ``account.move`` was renamed to ``origin_payment_id`` —
          ``/home/binaural19/odoo/addons/account/models/account_move.py:206``).

        The Venezuelan write contract is preserved: the originating
        ``account.payment`` receives ``foreign_rate`` and
        ``foreign_inverse_rate``, and every line of its move receives
        the matching ``foreign_debit`` / ``foreign_credit``.
        """
        receivable_lines = super(
            PosSession, self.with_context(from_pos=True)
        )._create_split_account_payment(payment, amounts)

        if not receivable_lines:
            # Odoo 19 early-return: payment method without journal.
            return receivable_lines

        payment_move = receivable_lines.move_id
        account_payment = payment_move.origin_payment_id
        if account_payment:
            account_payment.write(
                {
                    "foreign_rate": self.config_id.foreign_rate,
                    "foreign_inverse_rate": self.config_id.foreign_inverse_rate,
                }
            )

        foreign_amount = abs(payment.foreign_amount)
        for line in payment_move.line_ids:
            if line.credit > 0:
                line.not_foreign_recalculate = True
                line.foreign_credit = foreign_amount
            if line.debit > 0:
                line.not_foreign_recalculate = True
                line.foreign_debit = foreign_amount

        return receivable_lines

    def _create_account_move(
        self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None
    ):
        """
        This function was overwritten to assign the cash rate since it was previously assigned
        after creation.

        Additionally, the execution of the function: "compute_line_ids_foreign_debit_and_credit"
        is added so that it can calculate it
        """
        res = super()._create_account_move(
            balancing_account, amount_to_balance, bank_payment_method_diffs
        )
        account_move = self.move_id
        account_move.write(
            {
                "foreign_rate": self.config_id.foreign_rate,
                "foreign_inverse_rate": self.config_id.foreign_inverse_rate,
            }
        )
        return res

    def _accumulate_amounts(self, data):
        """Odoo 19 l10n_ve_pos extension of ``_accumulate_amounts``.

        Migration contract (Slice C1, spec
        ``pos-odoo19-session-accounting/spec.md``):

        - Call ``super()`` first to materialize the Odoo 19 dict shape
          (every entry has ``amount`` + ``amount_converted``).
        - Iterate the SAME source the Odoo 19 super uses
          (``self._get_closed_orders()``) — NEVER ``self.order_ids`` —
          so a ``draft`` / ``cancel`` order with a payment cannot
          create a ghost entry in the Odoo 19 defaultdict (C2 would
          then try to post a zero-amount move).
        - For each non-pay-later payment of a closed order, find the
          same bucket the super populated and add the Venezuelan
          ``foreign_amount`` via ``_update_amounts``. We pass
          ``{"amount": 0, "foreign_amount": foreign_amount}`` so the
          additive contract holds: ``amount`` / ``amount_converted``
          are preserved from super; ``foreign_amount`` is accumulated.
        - For invoiced orders, mirror the same additive update into
          ``split_invoice_receivables`` / ``combine_invoice_receivables``
          (keyed the same way as super does).
        """
        data = super()._accumulate_amounts(data)
        split_receivables_bank = data["split_receivables_bank"]
        split_receivables_cash = data["split_receivables_cash"]
        combine_receivables_bank = data["combine_receivables_bank"]
        combine_receivables_cash = data["combine_receivables_cash"]
        combine_invoice_receivables = data["combine_invoice_receivables"]
        split_invoice_receivables = data["split_invoice_receivables"]

        currency_rounding = self.currency_id.rounding
        for order in self._get_closed_orders():
            order_is_invoiced = order.is_invoiced
            for payment in order.payment_ids:
                amount = payment.amount
                foreign_amount = payment.foreign_amount
                if float_is_zero(amount, precision_rounding=currency_rounding):
                    continue
                date = payment.payment_date
                payment_method = payment.payment_method_id
                is_split_payment = payment_method.split_transactions
                payment_type = payment_method.type

                if payment_type == "pay_later":
                    continue

                if is_split_payment and payment_type == "cash":
                    split_receivables_cash[payment] = self._update_amounts(
                        split_receivables_cash[payment],
                        {"amount": 0, "foreign_amount": foreign_amount},
                        date,
                    )
                elif not is_split_payment and payment_type == "cash":
                    combine_receivables_cash[payment_method] = self._update_amounts(
                        combine_receivables_cash[payment_method],
                        {"amount": 0, "foreign_amount": foreign_amount},
                        date,
                    )
                elif is_split_payment and payment_type == "bank":
                    split_receivables_bank[payment] = self._update_amounts(
                        split_receivables_bank[payment],
                        {"amount": 0, "foreign_amount": foreign_amount},
                        date,
                    )
                elif not is_split_payment and payment_type == "bank":
                    combine_receivables_bank[payment_method] = self._update_amounts(
                        combine_receivables_bank[payment_method],
                        {"amount": 0, "foreign_amount": foreign_amount},
                        date,
                    )

                # Create the vals to create the pos receivables that will
                # balance the pos receivables from invoice payment moves.
                if order_is_invoiced:
                    if is_split_payment:
                        split_invoice_receivables[payment] = self._update_amounts(
                            split_invoice_receivables[payment],
                            {"amount": 0, "foreign_amount": foreign_amount},
                            order.date_order,
                        )
                    else:
                        combine_invoice_receivables[payment_method] = self._update_amounts(
                            combine_invoice_receivables[payment_method],
                            {"amount": 0, "foreign_amount": foreign_amount},
                            order.date_order,
                        )

        return data

    def _update_amounts(
        self, old_amounts, amounts_to_add, date, round=True, force_company_currency=False
    ):
        new_amounts = super()._update_amounts(
            old_amounts, amounts_to_add, date, round, force_company_currency
        )
        foreign_amount = amounts_to_add.get("foreign_amount", 0)
        new_amounts.update(
            {"foreign_amount": old_amounts.get("foreign_amount", 0) + foreign_amount}
        )
        return new_amounts

    def _create_invoice_receivable_lines(self, data):
        res = super()._create_invoice_receivable_lines(data)
        combine_invoice_receivable_lines = res.get("combine_invoice_receivable_lines")
        split_invoice_receivable_lines = res.get("split_invoice_receivable_lines")
        combine_invoice_receivables = res.get("combine_invoice_receivables")

        for payment_method, amounts in combine_invoice_receivables.items():
            line = combine_invoice_receivable_lines[payment_method]
            if line.credit > 0:
                line.not_foreign_recalculate = True
                line.foreign_credit = abs(amounts["foreign_amount"])
            if line.debit > 0:
                line.not_foreign_recalculate = True
                line.foreign_debit = abs(amounts["foreign_amount"])

        for payment in split_invoice_receivable_lines.keys():
            line = split_invoice_receivable_lines[payment]
            if line.credit > 0:
                line.not_foreign_recalculate = True
                line.foreign_credit = abs(payment["foreign_amount"])
            if line.debit > 0:
                line.not_foreign_recalculate = True
                line.foreign_debit = abs(payment["foreign_amount"])

        return res

    def _create_bank_payment_moves(self, data):
        """Odoo 19 l10n_ve_pos extension of ``_create_bank_payment_moves``.

        Migration contract (Slice C2.2, spec
        ``pos-odoo19-session-accounting/spec.md``):

        - Odoo 19 super MUTATES ``data`` in-place and returns the same
          dict — see
          ``/home/binaural19/odoo/addons/point_of_sale/models/pos_session.py:1050-1072``.
        - ``payment_method_to_receivable_lines`` is keyed by
          ``pos.payment.method`` (combined bank bucket).
        - ``payment_to_receivable_lines`` is keyed by ``pos.payment``
          records (split bank bucket).
        - Each value is a UNION of two ``account.move.line`` records:
          the session-side receivable line (created here) plus the
          receivable line on the ``account.payment.move_id`` (created
          by ``_create_combine_account_payment`` /
          ``_create_split_account_payment``).

        For every receivable line in both buckets we set the matching
        Venezuelan ``foreign_debit`` / ``foreign_credit`` and mark it
        ``not_foreign_recalculate=True`` so the base compute in
        ``l10n_ve_accountant`` does not overwrite it.
        """
        data = super()._create_bank_payment_moves(data)
        combine_receivables_bank = data["combine_receivables_bank"]
        payment_method_to_receivable_lines = data["payment_method_to_receivable_lines"]
        payment_to_receivable_lines = data["payment_to_receivable_lines"]

        for payment_method, amounts in combine_receivables_bank.items():
            self._set_foreign_amount_on_receivable_lines(
                payment_method_to_receivable_lines[payment_method],
                amounts["foreign_amount"],
            )

        for payment, lines in payment_to_receivable_lines.items():
            # Split bucket keys are ``pos.payment`` records; read the
            # foreign amount directly from the payment to keep the
            # Venezuelan write aligned with the accumulator source.
            self._set_foreign_amount_on_receivable_lines(
                lines, payment.foreign_amount
            )
        return data

    def _set_foreign_amount_on_receivable_lines(self, lines, foreign_amount):
        """Write the Venezuelan ``foreign_debit`` / ``foreign_credit`` on
        every receivable ``account.move.line`` in ``lines``.

        This helper is the single place where the Venezuelan write
        contract for bank payment moves is materialized. It centralizes
        the two loops that used to duplicate the credit/debit branching
        for the combine and split buckets.
        """
        abs_foreign = abs(foreign_amount)
        for line in lines:
            if line.credit > 0:
                line.not_foreign_recalculate = True
                line.foreign_credit = abs_foreign
            if line.debit > 0:
                line.not_foreign_recalculate = True
                line.foreign_debit = abs_foreign

    def _create_cash_statement_lines_and_cash_move_lines(self, data):
        res = super()._create_cash_statement_lines_and_cash_move_lines(data)
        split_receivables_cash = res.get("split_receivables_cash")
        combine_receivables_cash = res.get("combine_receivables_cash")
        split_cash_statement_lines = res.get("split_cash_statement_lines")
        combine_cash_statement_lines = res.get("combine_cash_statement_lines")
        split_cash_receivable_lines = res.get("split_cash_receivable_lines")
        combine_cash_receivable_lines = res.get("combine_cash_receivable_lines")

        for payment, amounts in split_receivables_cash.items():
            lines = split_cash_receivable_lines + split_cash_statement_lines
            for line in lines:
                self.set_foreign_amount_in_line(line, amounts["foreign_amount"], amounts["amount"])

        for payment_method, amounts in combine_receivables_cash.items():
            lines = combine_cash_receivable_lines + combine_cash_statement_lines
            for line in lines:
                self.set_foreign_amount_in_line(line, amounts["foreign_amount"], amounts["amount"])
        return data

    def set_foreign_amount_in_line(self, line, foreign_amount, amount=0.0):
        other_lines = line.move_id.line_ids.filtered(
            lambda x: x != line and x.account_id.account_type != "asset_receivable"
        )
        if other_lines:
            other_line = other_lines[0]
            if (
                abs(line.credit) > 0
                and float_compare(
                    line.credit, abs(amount), precision_rounding=self.currency_id.rounding
                ) == 0
            ):
                line.not_foreign_recalculate = True
                line.foreign_credit = abs(foreign_amount)
                if other_line.foreign_debit != line.foreign_credit:
                    other_line.foreign_debit = abs(line.foreign_credit)
            if (
                abs(line.debit) > 0
                and float_compare(line.debit, abs(amount), precision_rounding=self.currency_id.rounding) == 0
            ):
                line.not_foreign_recalculate = True
                line.foreign_debit = abs(foreign_amount)
                if other_line.foreign_credit != line.foreign_debit:
                    other_line.foreign_credit = abs(line.foreign_debit)
