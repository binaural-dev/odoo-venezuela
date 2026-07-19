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
        """Create the transitory-account clearing move for split payments.

        Migration contract (spec ``pos-cross-account-move/spec.md``):

        - Odoo 17 legacy had the condition inverted
          (``if not apply_one_cross_move:``), so the cross move fired when
          the flag was OFF (the default). Fixed here: the cross move fires
          only when ``apply_one_cross_move`` is True.
        - The resulting ``account.move`` is always created in ``state="draft"``
          (see ``_create_cross_move``) — accounting reviews and posts it
          manually, it is never posted automatically.
        - The transitory leg of the cross move uses
          ``_get_cross_transitory_account`` (see there) instead of reading
          ``outstanding_account_id`` directly, so cash payment methods (which
          never expose that field in the native UI) still resolve a valid
          account via the same fallback native Odoo uses for
          ``_get_receivable_account``.
        """
        for session in self:
            for order_payment in session.order_ids.payment_ids:
                payment_method = order_payment.payment_method_id
                if payment_method.type == "pay_later":
                    continue
                if not payment_method.apply_one_cross_move:
                    continue
                if not (
                    payment_method.cross_account_journal
                    and payment_method.cross_journal
                    and session._get_cross_transitory_account(payment_method)
                ):
                    continue

                if order_payment.amount < 0:
                    line_vals = session._line_vals_move_cross_outgoing(order_payment)
                else:
                    line_vals = session._line_vals_move_cross_incoming(order_payment)

                session._create_cross_move(order_payment, line_vals)

    def _get_cross_transitory_account(self, payment_method):
        """Return the transitory account for the cross move's OTHER leg.

        Mirrors the native Odoo 19 fallback pattern for the analogous
        ``_get_receivable_account`` (``pos_session.py:1660``):
        ``payment_method.receivable_account_id or
        company.account_default_pos_receivable_account_id``.

        ``outstanding_account_id`` is bank-only in the native UI
        (``invisible="type != 'bank'"`` in
        ``point_of_sale/views/pos_payment_method_views.xml:24``) — cash
        payment methods never expose it, because native Odoo routes cash
        straight to the cash journal's own account, with no separate
        transitory/outstanding account. When it's empty (always the case for
        cash), fall back to the company's default PoS receivable account —
        the same account native Odoo already uses as the session-side
        transitory account for that payment.
        """
        return (
            payment_method.outstanding_account_id
            or self.company_id.account_default_pos_receivable_account_id
        )

    def _line_vals_move_cross_incoming(self, payment):
        """Build the cross-move lines for an incoming (amount >= 0) payment.

        Debits the ``cross_journal``'s real bank account and credits the
        transitory account resolved by ``_get_cross_transitory_account``,
        clearing it.

        NOTE: the Odoo 17 legacy compared against a hardcoded currency id
        (``== 3``, VEF in the original dev database). Fixed to compare
        against ``self.foreign_currency_id`` (the session's configured
        foreign currency), which does not assume a fixed id.
        """
        payment_method = payment.payment_method_id
        debit_account = self._get_cross_transitory_account(payment_method).id
        account_method = payment_method.cross_journal
        credit_account = account_method.inbound_payment_method_line_ids.payment_account_id.id
        line_currency = account_method.currency_id or self.env.company.currency_id
        is_foreign_line_currency = line_currency == self.foreign_currency_id

        return [
            Command.create(
                {
                    "name": _("PoS Payment Method Adjustment"),
                    "account_id": credit_account,
                    "partner_id": payment.partner_id.id,
                    "amount_currency": payment.foreign_amount
                    if is_foreign_line_currency
                    else payment.amount,
                    "credit": 0.0,
                    "foreign_credit": 0.0,
                    "debit": payment.amount,
                    "foreign_debit": payment.foreign_amount,
                    "not_foreign_recalculate": True,
                    "foreign_rate": payment.foreign_rate,
                    "currency_id": line_currency.id,
                }
            ),
            Command.create(
                {
                    "name": _("PoS Payment Method Adjustment"),
                    "account_id": debit_account,
                    "partner_id": payment.partner_id.id,
                    "amount_currency": -payment.foreign_amount
                    if self.env.company.currency_id == self.foreign_currency_id
                    else -payment.amount,
                    "debit": 0.0,
                    "foreign_debit": 0.0,
                    "credit": payment.amount,
                    "foreign_credit": payment.foreign_amount,
                    "not_foreign_recalculate": True,
                    "foreign_rate": payment.foreign_rate,
                    "currency_id": self.env.company.currency_id.id,
                }
            ),
        ]

    def _line_vals_move_cross_outgoing(self, payment):
        """Build the cross-move lines for an outgoing (amount < 0) payment.

        Mirror of ``_line_vals_move_cross_incoming`` for change/refunds:
        debits the transitory account (see ``_get_cross_transitory_account``)
        and credits the ``cross_journal``'s real bank account, using
        absolute magnitudes.
        """
        payment_method = payment.payment_method_id
        debit_account = self._get_cross_transitory_account(payment_method).id
        account_method = payment_method.cross_journal
        credit_account = account_method.outbound_payment_method_line_ids.payment_account_id.id
        line_currency = account_method.currency_id or self.env.company.currency_id
        is_foreign_line_currency = line_currency == self.foreign_currency_id

        return [
            Command.create(
                {
                    "name": _("PoS Payment Method Adjustment"),
                    "account_id": debit_account,
                    "partner_id": payment.partner_id.id,
                    "amount_currency": abs(payment.foreign_amount)
                    if self.env.company.currency_id == self.foreign_currency_id
                    else abs(payment.amount),
                    "credit": 0.0,
                    "foreign_credit": 0.0,
                    "debit": abs(payment.amount),
                    "foreign_debit": abs(payment.foreign_amount),
                    "not_foreign_recalculate": True,
                    "foreign_rate": payment.foreign_rate,
                    "currency_id": self.env.company.currency_id.id,
                }
            ),
            Command.create(
                {
                    "name": _("PoS Payment Method Adjustment"),
                    "account_id": credit_account,
                    "partner_id": payment.partner_id.id,
                    "amount_currency": payment.foreign_amount
                    if is_foreign_line_currency
                    else payment.amount,
                    "debit": 0.0,
                    "foreign_debit": 0.0,
                    "credit": abs(payment.amount),
                    "foreign_credit": abs(payment.foreign_amount),
                    "not_foreign_recalculate": True,
                    "foreign_rate": payment.foreign_rate,
                    "currency_id": line_currency.id,
                }
            ),
        ]

    def _create_cross_move(self, payment, line_vals):
        """Create the move that clears the transitory account to zero.

        Args:
            payment (pos.payment): payment from PoS
            line_vals (account.move.line): move line to move cross

        Returns:
            account.move: Pos payment method adjustment move.

        The move is always created in ``state="draft"`` — it is not posted
        automatically; accounting reviews and validates it manually.
        """
        move = self.env["account.move"].create(
            {
                "name": _("PoS Payment Method Adjustment"),
                "date": payment.create_date,
                "journal_id": payment.payment_method_id.cross_account_journal.id,
                "state": "draft",
                "line_ids": line_vals,
                "foreign_currency_id": payment.foreign_currency_id.id,
                "foreign_rate": payment.foreign_rate,
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
        cross_method = account_payment.pos_payment_method_id if account_payment else self.env["pos.payment.method"]
        if (
            cross_method.apply_one_cross_move
            and cross_method.cross_account_journal
            and cross_method.cross_journal
            and self._get_cross_transitory_account(cross_method)
        ):
            self._create_cross_move_payment(res)
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

    def _create_cross_move_payment(self, receivable_line):
        """Create the cross move for a combine (non-split) bank payment.

        ``receivable_line`` is the ``account.move.line`` returned by
        ``_create_combine_account_payment`` (the receivable line on the
        ``account.payment``'s own move), not an ``account.move``.
        """
        move = self.env["account.move"].create(
            {
                "name": _("PoS Payment Method Adjustment"),
                "date": receivable_line.move_id.create_date,
                "journal_id": receivable_line.move_id.origin_payment_id.pos_payment_method_id.cross_account_journal.id,
                "state": "draft",
                "line_ids": self._line_vals_move_cross_payment_incoming(receivable_line),
                "foreign_currency_id": receivable_line.move_id.foreign_currency_id.id,
                "foreign_rate": receivable_line.move_id.foreign_rate,
                "company_id": self.company_id.id,
            }
        )
        return move

    def _line_vals_move_cross_payment_incoming(self, receivable_line):
        """Build the cross-move lines for a combine (non-split) bank payment.

        Args:
            receivable_line (account.move.line): the receivable line
                returned by ``_create_combine_account_payment``.

        Returns:
            list[Command]: move lines to create the cross move.

        Same fixes as the split path: ``payment_id`` → ``origin_payment_id``
        (Odoo 19 rename) and the hardcoded currency id (``== 3``) replaced by
        a comparison against ``self.foreign_currency_id``.
        """
        origin_payment = receivable_line.move_id.origin_payment_id
        payment_method = origin_payment.pos_payment_method_id
        debit_account = self._get_cross_transitory_account(payment_method).id
        account_method = payment_method.cross_journal
        credit_account = account_method.inbound_payment_method_line_ids.payment_account_id.id
        line_currency = account_method.currency_id or self.env.company.currency_id
        is_foreign_line_currency = line_currency == self.foreign_currency_id

        return [
            Command.create(
                {
                    "name": _("PoS Payment Method Adjustment"),
                    "account_id": credit_account,
                    "amount_currency": abs(receivable_line.foreign_credit)
                    if is_foreign_line_currency
                    else abs(receivable_line.credit),
                    "credit": 0.0,
                    "foreign_credit": 0.0,
                    "debit": abs(receivable_line.credit),
                    "foreign_debit": abs(receivable_line.foreign_credit),
                    "not_foreign_recalculate": True,
                    "foreign_rate": origin_payment.foreign_rate,
                    "currency_id": line_currency.id,
                }
            ),
            Command.create(
                {
                    "name": _("PoS Payment Method Adjustment"),
                    "account_id": debit_account,
                    "amount_currency": -receivable_line.foreign_credit
                    if self.env.company.currency_id == self.foreign_currency_id
                    else -receivable_line.credit,
                    "debit": 0.0,
                    "foreign_debit": 0.0,
                    "credit": abs(receivable_line.credit),
                    "foreign_credit": abs(receivable_line.foreign_credit),
                    "not_foreign_recalculate": True,
                    "foreign_rate": origin_payment.foreign_rate,
                    "currency_id": self.env.company.currency_id.id,
                }
            ),
        ]

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
