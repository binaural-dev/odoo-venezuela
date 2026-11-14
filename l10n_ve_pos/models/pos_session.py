from datetime import datetime

from odoo import models, fields, api, _, Command
from odoo.tools import float_is_zero, float_compare
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class PosSession(models.Model):
    _inherit = "pos.session"

    foreign_currency_id = fields.Many2one(
        "res.currency",
        related="config_id.foreign_currency_id",
        string="Foreign Currency",
    )

    @api.model
    def _load_pos_data_models(self, config):
        return super()._load_pos_data_models(config) + ["pos.payment.method.currency"]

    def load_data(self, local_data={}):
        """Odoo 20 ``load_data`` (replaces ``load_pos_data``).

        IMPORTANT: the ``load_data`` response must contain only model keys.
        Adding ad-hoc top-level keys (e.g. ``prefix_vats``) breaks RecordStore
        parsing with "Index 'id' not defined for model ..." in POS bootstrap.

        With ``pos_show_just_products_with_available_qty`` the products come
        back whole on every load (new session, opening from the backend), not
        only the ones modified since the browser cache, so the PoS gets the
        current stock. Costs like the first load. See ``pos.load.mixin``.
        """
        session = self
        if self.config_id.pos_show_just_products_with_available_qty:
            session = self.with_context(pos_reload_stock_dependent_data=True)
        return super(PosSession, session).load_data(local_data)

    def get_pos_ui_product_pricelist_item_by_product(
        self, product_tmpl_ids, product_ids, config_id
    ):
        """Agrega los items de las listas BASE de la cadena.

        El core restringe el dominio a ``config._get_available_pricelists()``
        (ver ``point_of_sale/models/pos_session.py``). Las listas base de la
        cadena no están entre las disponibles — no pueden estarlo, porque
        ``pos.config`` exige que toda lista disponible tenga la moneda del PdV
        (constraint en ``pos_config.py``) y las listas base están justamente en
        otra moneda. Resultado: los productos que entran por búsqueda
        on-demand llegan sin los items donde viven los precios fijos, y
        ``getPrice()`` cae a ``list_price``.

        Se llama al core y se le suman los items faltantes, en vez de
        reimplementar el método, para no heredar su mantenimiento.

        KEEP IN SYNC WITH:
          ``models/product_pricelist.py`` :: ``_load_pos_data_domain``
          (la carga inicial debe cubrir las mismas listas que esta).
        """
        res = super().get_pos_ui_product_pricelist_item_by_product(
            product_tmpl_ids, product_ids, config_id
        )

        pos_config = self.env["pos.config"].browse(config_id)
        available_ids = set(pos_config._get_available_pricelists().ids)
        chain_ids = self.env["product.pricelist"]._pos_expand_base_pricelists(
            available_ids
        )
        missing_ids = chain_ids - available_ids
        if not missing_ids:
            return res

        item_model = self.env["product.pricelist.item"]
        today = fields.Date.today()
        # Espejo del dominio del core, cambiando solo el conjunto de listas.
        item_domain = [
            "&",
            ("pricelist_id", "in", list(missing_ids)),
            *item_model._check_company_domain(self.company_id),
            "|",
            "&",
            ("product_id", "=", False),
            ("product_tmpl_id", "in", product_tmpl_ids),
            ("product_id", "in", product_ids),
            "|",
            ("date_start", "=", False),
            ("date_start", "<=", today),
            "|",
            ("date_end", "=", False),
            ("date_end", ">=", today),
        ]
        extra_items = item_model.search(item_domain)
        if not extra_items:
            return res

        # Dedup por id: si el core alguna vez amplía su propio conjunto de
        # listas, no queremos entregar el mismo item dos veces.
        known_item_ids = {item["id"] for item in res.get("product.pricelist.item", [])}
        extra_items = extra_items.filtered(lambda item: item.id not in known_item_ids)
        if not extra_items:
            return res

        item_fields = item_model._load_pos_data_fields(pos_config)
        res["product.pricelist.item"] += extra_items.read(item_fields, load=False)

        # Las listas base también tienen que viajar: sin el registro de la
        # lista, el many2one ``base_pricelist_id`` del item no resuelve en el
        # navegador y volvemos al mismo fallback silencioso.
        pricelist_model = self.env["product.pricelist"]
        known_pricelist_ids = {p["id"] for p in res.get("product.pricelist", [])}
        extra_pricelists = extra_items.pricelist_id.filtered(
            lambda pricelist: pricelist.id not in known_pricelist_ids
        )
        if extra_pricelists:
            res["product.pricelist"] += pricelist_model._load_pos_data_read(
                extra_pricelists, pos_config
            )

        return res

    def _validate_cross_move(self):
        """Create the moves that clear each foreign-currency payment's
        transitory account into the ``cross_journal`` of its currency.

        A payment is crossed when it was made in a currency other than the
        order's (``pos.payment.is_foreign_currency``). Its cross journals come
        from the settings of its payment method for that currency
        (``pos.payment.method.currency``): the cash method of a register takes
        Bs, USD and EUR, so what Odoo 19 kept on three methods is keyed by
        method and currency.

        Granularity follows the method's ``split_transactions`` ("Identify
        Customer") flag, mirroring how native Odoo groups its own receivable
        lines in ``_accumulate_amounts``:

        - ``split_transactions=True``  -> one move per ``pos.payment``.
        - ``split_transactions=False`` -> one move per payment method,
          currency and session, netting every payment of that pair. A zero net
          creates nothing.

        Reading ``pos.payment`` directly, rather than the ``account.payment``
        the native bank pipeline produces, is what lets cash and bank methods
        share this code path.

        Every move is created in ``state="draft"`` (see ``_create_cross_move``)
        - accounting reviews and posts it manually.

        Cash methods go through ``use_suspense=True`` (see
        ``_cross_move_uses_suspense``), which is what makes their move run
        between the two journals' suspense accounts.
        """
        for session in self:
            foreign_payments = session.order_ids.payment_ids.filtered(
                lambda p: p.is_foreign_currency
                and p.payment_method_id.type != "pay_later"
            )
            pairs = {
                (p.payment_method_id, p.foreign_currency_id) for p in foreign_payments
            }
            for payment_method, currency in sorted(
                pairs, key=lambda pair: (pair[0].id, pair[1].id)
            ):
                use_suspense = session._cross_move_uses_suspense(payment_method)
                if not session._is_cross_move_eligible(
                    payment_method, currency, use_suspense=use_suspense
                ):
                    continue
                method_payments = foreign_payments.filtered(
                    lambda p: p.payment_method_id == payment_method
                    and p.foreign_currency_id == currency
                )
                if payment_method.split_transactions:
                    for payment in method_payments:
                        session._create_cross_move_for(
                            payment_method,
                            currency,
                            amount=payment.amount,
                            foreign_amount=payment.foreign_amount,
                            currency_amount=payment.amount_currency,
                            foreign_rate=payment.foreign_rate,
                            partner=payment.partner_id,
                            date=payment.create_date,
                            ref=session._cross_move_ref(payment),
                            use_suspense=use_suspense,
                        )
                    continue

                amount = sum(method_payments.mapped("amount"))
                if float_is_zero(amount, precision_rounding=session.currency_id.rounding):
                    continue
                session._create_cross_move_for(
                    payment_method,
                    currency,
                    amount=amount,
                    foreign_amount=sum(method_payments.mapped("foreign_amount")),
                    currency_amount=sum(method_payments.mapped("amount_currency")),
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
                    use_suspense=use_suspense,
                )

    def _cross_move_uses_suspense(self, payment_method):
        """Whether the SALE cross move of ``payment_method`` runs between the
        two journals' suspense accounts ("Cuenta transitoria").

        Cash methods do. The cash a session takes in leaves the POS journal's
        own account through the **cash out the cashier registers when closing**
        — native ``try_cash_in_out`` credits ``journal_id.default_account_id``
        and parks the amount in ``journal_id.suspense_account_id``. So that
        account is already balanced without the cross move; draining it here
        as well credited it twice and left both suspense accounts loaded with
        nothing to offset them. Routing the sale through ``use_suspense=True``
        instead debits the method journal's suspense account and credits the
        ``cross_journal``'s, which is what nets the sale against what the cash
        out parked there.

        Bank methods keep the previous behaviour (``outstanding_account_id``
        → the ``cross_journal``'s real liquidity account): no cash out takes
        their balance out of the outstanding account.

        This only covers the sale path. Callers outside ``_validate_cross_move``
        pass their own flag: cash in/out (``binaural_pos_close``) already used
        ``use_suspense=True``, and opening/closing differences
        (``_post_foreign_statement_difference``) still land on the real
        liquidity account.
        """
        return payment_method.type == "cash"

    def _is_cross_move_eligible(self, payment_method, currency, use_suspense=False):
        """Whether the payments of ``payment_method`` made in ``currency``
        take part in the automatic cross move.

        The method must have settings for the currency
        (``pos.payment.method.currency``) with both cross journals: a foreign
        currency without them is skipped in silence - that configuration is
        incomplete, not wrong. ``use_suspense`` must match whatever will be
        passed to ``_create_cross_move_for`` - see
        ``_get_cross_transitory_account``.

        Under ``use_suspense=True`` BOTH legs come from a journal's
        ``suspense_account_id``, and either can be empty. An empty destination
        is not a harmless skip: ``_get_cross_real_account`` returns an empty
        recordset, the line is built with ``account_id = False`` and the
        insert violates ``account_move_line_check_accountable_required_fields``
        - inside ``close_session_from_ui``, so it would take the session
        close down with it. Hence the explicit check on the destination too;
        the skip is logged, since the session can no longer be opened with
        those accounts missing (``pos.config._check_cross_move_accounts``)
        and only a session opened before they were cleared gets here.

        The ``use_suspense=False`` branch does not skip on a missing
        ``cross_journal`` payment method line account: opening the session
        requires it from every module that crosses that way (the bank sales
        here, by method type - see ``_get_cross_move_missing_accounts`` -, the
        foreign cash drawer difference in ``binaural_pos_close``), and
        ``_create_cross_move_for`` raises a readable error for a session
        created before it was cleared.
        """
        settings = payment_method._get_currency_settings(currency)
        if not (
            payment_method.type != "pay_later"
            and settings.cross_account_journal
            and settings.cross_journal
        ):
            return False
        if not use_suspense:
            return bool(self._get_cross_transitory_account(payment_method))
        return self._cross_move_suspense_accounts_ready(payment_method, currency)

    def _cross_move_suspense_accounts_ready(self, payment_method, currency):
        """Whether both suspense accounts of a ``use_suspense=True`` cross move
        of ``payment_method`` in ``currency`` are set; if not, logs the skip
        and returns False.
        """
        settings = payment_method._get_currency_settings(currency)
        if self._get_cross_transitory_account(
            payment_method, use_suspense=True
        ) and self._get_cross_real_account(
            payment_method, currency, outbound=False, use_suspense=True
        ):
            return True
        _logger.warning(
            "Cross move of payment method %s (%s) skipped in session %s: %s",
            payment_method.name,
            settings.currency_id.name,
            self.name,
            ", ".join(self._get_cross_move_missing_accounts(payment_method, currency)),
        )
        return False

    def _get_cross_move_missing_accounts(self, payment_method, currency):
        """Describe each account the cross move of ``payment_method`` in
        ``currency`` needs and is not set, one string per account (empty list:
        nothing missing).

        Only what this module's own cross move uses, by method type (see
        ``_cross_move_uses_suspense``): a bank sale lands on the
        ``cross_journal``'s payment method line accounts, a cash sale crosses
        between the two journals' suspense accounts. Other ``use_suspense=False``
        callers on a cash method (``binaural_pos_close``'s opening/closing
        differences) add the payment method line accounts themselves.
        """
        if self._cross_move_uses_suspense(payment_method):
            return self._get_cross_move_missing_suspense_accounts(payment_method, currency)
        return self._get_cross_move_missing_payment_accounts(payment_method, currency)

    def _get_cross_move_missing_payment_accounts(self, payment_method, currency):
        """The ``cross_journal``'s incoming/outgoing payment method line
        accounts that are not set (``_get_cross_real_account`` with
        ``use_suspense=False``). ``l10n_ve_accountant`` only requires them on
        bank journals, and Odoo creates cash journals without them."""
        journal = payment_method._get_currency_settings(currency).cross_journal.display_name
        return [
            f"{journal}: {label}"
            for outbound, label in (
                (False, _("incoming payments account")),
                (True, _("outgoing payments account")),
            )
            if not self._get_cross_real_account(payment_method, currency, outbound=outbound)
        ]

    def _get_cross_move_missing_suspense_accounts(self, payment_method, currency):
        """The ``suspense_account_id`` of the method's journal and of the
        ``cross_journal`` of the currency that is not set (``use_suspense=True``)."""
        settings = payment_method._get_currency_settings(currency)
        return [
            _("%(journal)s: suspense account", journal=journal.display_name)
            for journal in payment_method.journal_id | settings.cross_journal
            if not journal.suspense_account_id
        ]

    def _get_cross_transitory_account(self, payment_method, use_suspense=False):
        """Return the account the cross move drains.

        Which account that is depends on *what created the balance being
        cleared*, not just the payment method type:

        - ``use_suspense=False`` (bank sales, opening/closing differences): the
          account where native Odoo parked the money once the session
          closed / the difference was posted.

          - ``bank``: ``_create_combine_account_payment`` posts an
            ``account.payment`` with ``force_outstanding_account_id =
            payment_method.outstanding_account_id`` (native
            ``pos_session.py:1104``), so the balance sits in the outstanding
            account.
          - ``cash``: there is no outstanding account at all —
            ``outstanding_account_id`` is ``invisible="type != 'bank'"`` in
            the native view
            (``point_of_sale/views/pos_payment_method_views.xml:24``),
            because Odoo routes cash straight to the journal. The statement
            line debits the journal's own default account and credits the
            POS receivable (``_get_combine_statement_line_vals``, native
            line 1452) or, for differences, the configured loss/profit
            account (``_post_foreign_statement_difference``) — either way
            the leftover balance sits in ``journal_id.default_account_id``.

          The company's default POS receivable account stays on as a
          last-resort fallback so that an incomplete journal setup degrades
          into a skipped cross move (see ``_is_cross_move_eligible``) rather
          than an ``account_move_line_check_accountable_required_fields``
          violation from a NULL ``account_id``.

        - ``use_suspense=True`` (cash sales — see
          ``_cross_move_uses_suspense`` — and plain cash in/out,
          ``binaural_pos_close``'s ``try_cash_in_out``): that flow never sets an explicit
          ``counterpart_account_id``, so native
          ``_prepare_move_line_default_vals`` falls back to
          ``journal_id.suspense_account_id`` — Odoo's own "Cuenta
          transitoria" field
          (``account/i18n/es.po``: ``Suspense Account`` → ``Cuenta
          transitoria``). That is the account actually left unexplained by
          that flow, not ``default_account_id`` (which already got
          reconciled by the other cross move, see
          ``_line_vals_move_cross_incoming``/``_outgoing``'s ``use_suspense``
          branch for why draining it requires inverting debit/credit too).
        """
        if use_suspense:
            return payment_method.journal_id.suspense_account_id
        if payment_method.type == "cash":
            account = payment_method.journal_id.default_account_id
        else:
            account = (
                payment_method.outstanding_account_id
                or payment_method.journal_id.default_account_id
            )
        return account or self.company_id.account_default_pos_receivable_account_id

    def _get_cross_real_account(self, payment_method, currency, outbound, use_suspense=False):
        """Return the ``cross_journal`` account that receives/gives the value.

        ``use_suspense=False`` (bank sales, opening/closing differences): the
        journal's own inbound/outbound payment method line account — the
        confirmed liquidity account, same as the native ``account.payment``/
        bank pipeline would use.

        ``use_suspense=True`` (cash sales and cash in/out): lands in
        ``cross_journal.suspense_account_id`` instead — pending an actual
        bank statement to reconcile it, the same "not yet confirmed"
        treatment already applied to the origin leg (see
        ``_get_cross_transitory_account``). A journal has a single suspense
        account regardless of direction, so ``outbound`` is unused here.
        """
        account_method = payment_method._get_currency_settings(currency).cross_journal
        if use_suspense:
            return account_method.suspense_account_id
        line_ids = (
            account_method.outbound_payment_method_line_ids
            if outbound
            else account_method.inbound_payment_method_line_ids
        )
        return line_ids.payment_account_id

    def _cross_line_amount_currency(
        self, line_currency, currency, amount, foreign_amount, currency_amount
    ):
        """``amount_currency`` of the cross line that sits on the
        ``cross_journal`` (``line_currency``): the alternate amount when that
        journal is in the session's foreign currency, what the customer handed
        over when it is in the payment's currency (EUR), the local amount
        otherwise."""
        if line_currency == self.foreign_currency_id:
            return foreign_amount
        if line_currency == currency and line_currency != self.company_id.currency_id:
            return currency_amount
        return amount

    def _line_vals_move_cross_incoming(
        self, payment_method, currency, amount, foreign_amount, foreign_rate, partner,
        use_suspense=False, currency_amount=0.0,
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

        ``use_suspense`` only changes *which* account
        ``_get_cross_transitory_account`` resolves — ``_create_cross_move_for``
        is what inverts debit/credit for that case, by swapping which of
        ``_line_vals_move_cross_incoming``/``_outgoing`` gets called (see
        there for why).
        """
        transitory_account = self._get_cross_transitory_account(
            payment_method, use_suspense=use_suspense
        ).id
        account_method = payment_method._get_currency_settings(currency).cross_journal
        real_account = self._get_cross_real_account(
            payment_method, currency, outbound=False, use_suspense=use_suspense
        ).id
        line_currency = account_method.currency_id or self.env.company.currency_id
        line_amount_currency = self._cross_line_amount_currency(
            line_currency, currency, amount, foreign_amount, currency_amount
        )

        return [
            Command.create(
                {
                    "name": _("PoS Payment Method Adjustment"),
                    "account_id": real_account,
                    "partner_id": partner.id,
                    "amount_currency": line_amount_currency,
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
                    if self.company_id.currency_id == self.foreign_currency_id
                    else -amount,
                    "debit": 0.0,
                    "foreign_debit": 0.0,
                    "credit": amount,
                    "foreign_credit": foreign_amount,
                    "not_foreign_recalculate": True,
                    "foreign_rate": foreign_rate,
                    "currency_id": self.company_id.currency_id.id,
                }
            ),
        ]

    def _line_vals_move_cross_outgoing(
        self, payment_method, currency, amount, foreign_amount, foreign_rate, partner,
        use_suspense=False, currency_amount=0.0,
    ):
        """Build the cross-move lines for an outgoing (amount < 0) movement.

        Mirror of ``_line_vals_move_cross_incoming`` for change/refunds:
        debits the transitory account (see ``_get_cross_transitory_account``)
        and credits the ``cross_journal``'s real bank account, using
        absolute magnitudes.
        """
        transitory_account = self._get_cross_transitory_account(
            payment_method, use_suspense=use_suspense
        ).id
        account_method = payment_method._get_currency_settings(currency).cross_journal
        real_account = self._get_cross_real_account(
            payment_method, currency, outbound=True, use_suspense=use_suspense
        ).id
        line_currency = account_method.currency_id or self.env.company.currency_id
        line_amount_currency = self._cross_line_amount_currency(
            line_currency, currency, amount, foreign_amount, currency_amount
        )

        return [
            Command.create(
                {
                    "name": _("PoS Payment Method Adjustment"),
                    "account_id": transitory_account,
                    "partner_id": partner.id,
                    "amount_currency": abs(foreign_amount)
                    if self.company_id.currency_id == self.foreign_currency_id
                    else abs(amount),
                    "credit": 0.0,
                    "foreign_credit": 0.0,
                    "debit": abs(amount),
                    "foreign_debit": abs(foreign_amount),
                    "not_foreign_recalculate": True,
                    "foreign_rate": foreign_rate,
                    "currency_id": self.company_id.currency_id.id,
                }
            ),
            Command.create(
                {
                    "name": _("PoS Payment Method Adjustment"),
                    "account_id": real_account,
                    "partner_id": partner.id,
                    "amount_currency": line_amount_currency,
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
        self, payment_method, currency, amount, foreign_amount, foreign_rate, partner,
        date, ref, use_suspense=False, currency_amount=0.0,
    ):
        """Create one clearing move for ``payment_method`` and ``currency``.

        The sign of ``amount`` picks the direction: incoming for sales,
        outgoing for change/refunds. Under combine granularity ``amount`` is
        already the net of the method's payments, so a session whose refunds
        outweigh its sales yields a single outgoing move — the branch the
        legacy combine path never had.

        ``use_suspense=True`` (cash sales and ``binaural_pos_close``'s plain
        cash in/out) clears ``journal_id.suspense_account_id`` instead of
        ``default_account_id`` — see ``_get_cross_transitory_account``. That
        account carries the OPPOSITE native polarity from
        ``default_account_id`` for the same movement (a balanced 2-line
        entry always splits debit/credit between its two accounts), so
        clearing it needs the mirror-image entry: same magnitude, opposite
        role. Rather than duplicating ``_line_vals_move_cross_incoming``/
        ``_outgoing`` with the roles hand-swapped (and every sign/currency
        field re-derived), this reuses them as-is by swapping *which one*
        gets called and negating the amounts fed to it — the already-correct
        abs()/sign logic in the builder then produces exactly the mirrored
        entry. Confirmed line-by-line against a manual T-account trace
        (see ``proposal.md``): for an entrada, calling the *outgoing*
        builder with ``-amount`` debits the suspense account and credits
        ``cross_journal`` (draining the placeholder, moving Banco Real
        opposite to the sales-like direction); for a salida, the mirrored
        call to the *incoming* builder credits suspense and debits
        ``cross_journal``.
        """
        is_outgoing = amount < 0
        call_amount, call_foreign_amount = amount, foreign_amount
        call_currency_amount = currency_amount
        if use_suspense:
            is_outgoing = not is_outgoing
            call_amount, call_foreign_amount = -amount, -foreign_amount
            call_currency_amount = -currency_amount
        line_builder = (
            self._line_vals_move_cross_outgoing
            if is_outgoing
            else self._line_vals_move_cross_incoming
        )
        line_vals = line_builder(
            payment_method, currency, call_amount, call_foreign_amount, foreign_rate,
            partner, use_suspense=use_suspense, currency_amount=call_currency_amount,
        )
        if not all(command[2]["account_id"] for command in line_vals):
            raise UserError(
                _(
                    "The cross move of the payment method %(method)s cannot be created "
                    "because these accounts are not set:\n%(accounts)s\n"
                    "Set them in the journal configuration and try again.",
                    method=payment_method.name,
                    accounts="\n".join(
                        f"- {account}"
                        for account in self._get_cross_move_missing_accounts(
                            payment_method, currency
                        )
                        or [_("an account of the move lines")]
                    ),
                )
            )
        return self._create_cross_move(
            payment_method, currency, line_vals, foreign_rate, date, ref, partner
        )

    def _create_cross_move(
        self, payment_method, currency, line_vals, foreign_rate, date, ref, partner
    ):
        """Create the move that clears the transitory account to zero.

        Args:
            payment_method (pos.payment.method): method being cleared.
            currency (res.currency): foreign currency of the payments cleared.
            line_vals (list): ``Command`` list of move lines to create.
            foreign_rate (float): operative rate stamped on the move.
            date (date | datetime): accounting date of the move. A Datetime
                (``stop_at``, a payment's ``create_date``) is in UTC and is
                turned into the user's day, see below.
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

        ``account.move.date`` is a Date: a Datetime would be cut with
        ``.date()`` to the UTC day, which from 8 pm in Caracas is already the
        next one. ``l10n_ve_accountant`` then asks for that day's rate, which
        does not exist yet, and the session cannot be closed (ticket 16145).
        The core dates its own payment moves the same way
        (``fields.Date.context_today(self, timestamp=payment.payment_date)``).
        """
        if isinstance(date, datetime):
            date = fields.Date.context_today(self, date)
        move = self.env["account.move"].create(
            {
                "ref": ref,
                "partner_id": self._cross_move_header_partner(partner).id,
                "date": date,
                "journal_id": payment_method._get_currency_settings(
                    currency
                ).cross_account_journal.id,
                "state": "draft",
                "line_ids": line_vals,
                "foreign_currency_id": self.foreign_currency_id.id,
                "foreign_rate": foreign_rate,
                "company_id": self.company_id.id,
            }
        )
        return move

    def close_session_from_ui(self, payment_method_closing={}):
        """Create the cross moves and round the orders once the session is
        closed. Odoo 20 closes from the UI and from the backend button through
        this single entry point (Odoo 19 went through ``action_pos_session_close``).
        """
        res = super().close_session_from_ui(payment_method_closing)
        if not res.get("status"):
            return res

        self._validate_cross_move()

        orders = self.env["pos.order"].search([("session_id", "=", self.id)])
        for order in orders:
            order.amount_total = self._apply_rounding(order.amount_total)
            for line in order.lines:
                line.price_subtotal = self._apply_rounding(line.price_subtotal)
        return res

    def _apply_rounding(self, amount):
        return round(amount, 2)

    def _create_session_account_move(self, orders):
        """Stamp the operative rate on the closing entry and hand
        ``pos.payment.method._create_payment_line`` the payments the entry
        groups, so it stamps their alternate amount on the entries it creates
        before core reconciles them with the ``payment_term`` lines.

        Odoo 20 builds one closing entry per kind of order (sales, refunds),
        with one ``payment_term`` line per payment method, and then creates and
        reconciles, per line, the cash statement line or the ``account.payment``
        that settles it.
        """
        if not orders:
            return super()._create_session_account_move(orders)
        payments_data = orders._prepare_account_move_line_data_for_payments()
        move = super()._create_session_account_move(
            orders.with_context(
                l10n_ve_pos_payments_data={
                    "session_closing": True,
                    "entries": payments_data,
                }
            )
        )
        if move:
            self._restore_closing_foreign_amounts(move, payments_data)
            move.write(
                {
                    "foreign_rate": self.config_id.foreign_rate,
                    "foreign_inverse_rate": self.config_id.foreign_inverse_rate,
                }
            )
        return move

    def _restore_closing_foreign_amounts(self, move, payments_data):
        """Give the closing entry the alternate amounts of the sales, as Odoo 19
        stamped them: each ``payment_term`` line carries the sum of the
        alternate amounts the register charged on the payments it groups, and
        the other lines are scaled to them so the entry stays balanced.

        Odoo 20 builds the closing entry as an invoice, and
        ``l10n_ve_accountant`` values an invoice at the rate of its date: with
        the rate moved between the sale and the closing, the term lines would
        carry a different alternate amount than the payments that settle them.
        The payments keep the rate of the sale (``_create_payment_line``), and
        no exchange difference entry is left behind at the reconciliation.
        """
        foreign_currency = self.foreign_currency_id
        term_lines = move.line_ids.filtered(
            lambda line: line.display_type == "payment_term"
        ).sorted("id")
        if not foreign_currency or len(term_lines) != len(payments_data):
            return
        term_balance = 0.0
        for line, entry in zip(term_lines, payments_data):
            foreign_amount = abs(entry["metadata"]["foreign_amount"])
            sign = 1 if line.balance > 0 else -1
            line.write(
                {
                    "foreign_debit": foreign_amount if sign > 0 else 0.0,
                    "foreign_credit": foreign_amount if sign < 0 else 0.0,
                    "not_foreign_recalculate": True,
                }
            )
            term_balance += sign * foreign_amount
        other_lines = (move.line_ids - term_lines).filtered(
            lambda line: not foreign_currency.is_zero(line.foreign_balance)
        )
        other_balance = sum(other_lines.mapped("foreign_balance"))
        target_balance = -term_balance
        if foreign_currency.is_zero(other_balance) or foreign_currency.is_zero(
            other_balance - target_balance
        ):
            return
        remaining = target_balance
        ordered = other_lines.sorted(lambda line: abs(line.foreign_balance))
        for line in ordered[:-1]:
            share = foreign_currency.round(
                line.foreign_balance * target_balance / other_balance
            )
            self._write_closing_foreign_balance(line, share)
            remaining -= share
        self._write_closing_foreign_balance(ordered[-1], foreign_currency.round(remaining))

    def _write_closing_foreign_balance(self, line, balance):
        line.write(
            {
                "foreign_debit": balance if balance > 0 else 0.0,
                "foreign_credit": -balance if balance < 0 else 0.0,
                "not_foreign_recalculate": True,
            }
        )
