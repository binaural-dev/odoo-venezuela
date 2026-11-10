from datetime import datetime

from odoo import models, fields, api, _, Command
from odoo.tools import float_is_zero, float_compare
from odoo.osv.expression import AND, OR
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

    def load_data(self, models_to_load):
        """Odoo 19 replacement for ``load_pos_data``.

        IMPORTANT: Odoo 19 load_data response must contain only model keys.
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
        return super(PosSession, session).load_data(models_to_load)

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
            pricelist_fields = pricelist_model._load_pos_data_fields(pos_config)
            res["product.pricelist"] += extra_pricelists.read(
                pricelist_fields, load=False
            )

        return res

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
          session with up to two legs: the incoming payments (``amount > 0``)
          netted together and the outgoing ones (``amount < 0``) netted
          together, each with its own pair of lines (see
          ``_create_combined_cross_move``). Netting sales and refunds into a
          single pair broke when they were valued at different rates: the net
          in the session currency and the net in the foreign/tender currency
          could end up with opposite signs (a line rejected by
          ``account_move_line_check_amount_currency_balance_sign``), or the
          first one at zero with the others not (nothing crossed). Only when
          the three nets are zero is nothing created.

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

        Every move is posted when created, and a cross that lands on the real
        journal's transitory account gets its statement line in that journal
        (see ``_create_cross_move``).

        Cash methods go through ``use_suspense=True`` (see
        ``_cross_move_uses_suspense``), which is what makes their move run
        between the two journals' suspense accounts.

        A method whose cash in/out is already crossed movement by movement
        does not cross its sales (``_crosses_sales``): the cash out takes that
        money to the real journal.
        """
        for session in self:
            # Per method, not per payment: an ineligible method logs why once.
            eligible_methods = session.order_ids.payment_ids.payment_method_id.filtered(
                lambda pm: session._crosses_sales(pm)
                and session._is_cross_move_eligible(
                    pm, use_suspense=session._cross_move_uses_suspense(pm)
                )
            )
            payments = session.order_ids.payment_ids.filtered(
                lambda p: p.payment_method_id in eligible_methods
            )
            for payment_method in payments.payment_method_id:
                method_payments = payments.filtered(
                    lambda p: p.payment_method_id == payment_method
                )
                use_suspense = session._cross_move_uses_suspense(payment_method)
                sign = session._get_sales_cross_sign(payment_method)
                if payment_method.split_transactions:
                    for payment in method_payments:
                        session._create_cross_move_for(
                            payment_method,
                            amount=sign * payment.amount,
                            foreign_amount=sign * payment.foreign_amount,
                            foreign_rate=payment.foreign_rate,
                            partner=payment.partner_id,
                            date=payment.create_date,
                            ref=session._cross_move_ref(payment),
                            use_suspense=use_suspense,
                            **session._sign_cross_amounts(
                                sign,
                                session._get_cross_currency_amount_kwargs(payment_method, payment),
                            ),
                        )
                    continue

                session._create_combined_cross_move(
                    payment_method,
                    [
                        session._sign_cross_amounts(sign, leg)
                        for leg in session._get_combined_cross_legs(payment_method, method_payments)
                    ],
                    # Rate of the move header. Read it off a payment rather
                    # than off ``config_id.foreign_rate``: the config value can
                    # be edited after the session opened, while the payments
                    # carry the rate actually applied. Each leg's lines carry
                    # the rate of their own payments (a refund keeps the one of
                    # its original sale), see ``_get_combined_cross_legs``.
                    foreign_rate=method_payments[0].foreign_rate,
                    date=session.stop_at or fields.Datetime.now(),
                    ref=session._cross_move_ref(payment_method=payment_method),
                    use_suspense=use_suspense,
                )

    def _get_combined_cross_legs(self, payment_method, payments, amount_of=None,
                                 foreign_amount_of=None, transitory_amount_of=None):
        """Legs of the combined cross move of ``payment_method``: the incoming
        payments (``amount > 0``) netted together and the outgoing ones
        (``amount < 0``) netted together, each one only if it has payments.

        Every payment of a leg has the same sign in every currency
        (``pos.order._align_foreign_signs``), so each leg is coherent on its
        own, whatever rate each payment was valued at.

        ``amount_of`` / ``foreign_amount_of`` read a payment's amount in the
        currency of the move lines and in the foreign currency (by default
        ``amount`` and ``foreign_amount``); ``binaural_pos_multicurrency``
        passes its conversions for a PoS in another currency.

        Each leg carries the rate of its first payment (``foreign_rate``):
        the refunds of a session are valued at the rate of their original
        sales (``pos.order._get_payment_foreign_rate``), not at the one of the
        sales of the day. The lines are not recomputed from it
        (``not_foreign_recalculate``): it is informative.

        ``transitory_amount_of`` reads a payment's amount in the currency of
        the method's journal, for a journal that is not in the company currency
        (``binaural_pos_multicurrency``, PoS in another currency): see
        ``_get_cross_transitory_currency_amount``.

        :return: list of ``{"amount", "foreign_amount", "foreign_rate"[,
            "currency_amount"][, "transitory_amount_currency"]}``
            (``currency_amount`` only for a method with a tender currency, see
            ``_get_cross_currency_amount_kwargs``; ``transitory_amount_currency``
            only with ``transitory_amount_of``).
        """
        amount_of = amount_of or (lambda payment: payment.amount)
        foreign_amount_of = foreign_amount_of or (lambda payment: payment.foreign_amount)
        legs = []
        for sign in (1, -1):
            leg_payments = payments.filtered(lambda p: sign * amount_of(p) > 0)
            if not leg_payments:
                continue
            leg = {
                "amount": sum(amount_of(p) for p in leg_payments),
                "foreign_amount": sum(foreign_amount_of(p) for p in leg_payments),
                "foreign_rate": leg_payments[0].foreign_rate,
                **self._get_cross_currency_amount_kwargs(payment_method, leg_payments),
            }
            if transitory_amount_of:
                leg["transitory_amount_currency"] = sum(
                    transitory_amount_of(p) for p in leg_payments
                )
            legs.append(leg)
        return legs

    def _create_combined_cross_move(self, payment_method, legs, foreign_rate, date, ref,
                                    use_suspense=False):
        """One cross move for every payment of ``payment_method`` in the
        session (combine granularity), with one pair of lines per leg of
        ``_get_combined_cross_legs`` (incoming / outgoing), each built exactly
        like the move of a single payment (``_get_cross_move_line_vals``,
        ``use_suspense`` inversion included) with the rate of its leg (or
        ``foreign_rate``, the one of the header, if the leg has none).

        Nothing is created when the nets of the legs are all zero in the
        currency of the move lines, the foreign currency and the tender
        currency: there is nothing to cross. A zero net in the first one with
        euros or dollars left still crosses them to the real journal.

        No partner on the move or its lines, matching the native combined
        ``account.payment``.
        """
        self.ensure_one()
        if not legs or self._cross_legs_net_is_zero(payment_method, legs):
            return self.env["account.move"]
        partner = self.env["res.partner"]
        line_vals = []
        for leg in legs:
            line_vals += self._get_cross_move_line_vals(
                payment_method, leg["amount"], leg["foreign_amount"],
                leg.get("foreign_rate") or foreign_rate, partner,
                use_suspense=use_suspense, currency_amount=leg.get("currency_amount"),
                transitory_amount_currency=leg.get("transitory_amount_currency"),
            )
        self._check_cross_move_line_accounts(payment_method, line_vals)
        return self._create_cross_move(payment_method, line_vals, foreign_rate, date, ref, partner)

    def _cross_legs_net_is_zero(self, payment_method, legs):
        """Whether the legs net to zero in the currency of the move lines
        (the company's), the foreign currency, the tender currency and, if the
        legs carry it, the currency of the method's journal."""
        nets = [
            (sum(leg["amount"] for leg in legs), self.company_id.currency_id),
            (sum(leg["foreign_amount"] for leg in legs), self.foreign_currency_id),
        ]
        if payment_method.tender_currency_id:
            nets.append((
                sum(leg.get("currency_amount") or 0.0 for leg in legs),
                payment_method.tender_currency_id,
            ))
        if any("transitory_amount_currency" in leg for leg in legs):
            nets.append((
                sum(leg.get("transitory_amount_currency") or 0.0 for leg in legs),
                payment_method.journal_id.currency_id,
            ))
        return all(
            float_is_zero(amount, precision_rounding=currency.rounding if currency else 0.01)
            for amount, currency in nets
        )

    def _get_cross_currency_amount_kwargs(self, payment_method, payments):
        """``{"currency_amount": ...}`` para un método con moneda de cobro, ``{}``
        para los demás. Solo se pasa cuando hace falta: un módulo que aún
        sobrescribe ``_create_cross_move_for`` con la firma anterior sigue
        funcionando con los métodos de siempre."""
        currency_amount = self._get_cross_currency_amount(payment_method, payments)
        return {} if currency_amount is None else {"currency_amount": currency_amount}

    def _get_cross_currency_amount(self, payment_method, payments):
        """Monto en la moneda de cobro (``tender_currency_id``) de ``payments``
        de ``payment_method``, o ``None`` si el método no tiene moneda de cobro.

        Es lo que entró al cajón en esa moneda (``tender_amount``, lo tecleado),
        y el cruce lo lleva como ``amount_currency`` de la línea del diario real
        (``cross_journal``, en esa moneda). Un pago en otra moneda de cobro (no
        debería haberlo: la moneda es la del método) no cuenta.
        """
        currency = payment_method.tender_currency_id
        if not currency:
            return None
        return currency.round(
            sum(
                payments.filtered(lambda p: p.tender_currency_id == currency).mapped(
                    "tender_amount"
                )
            )
        )

    def _get_sales_cross_sign(self, payment_method):
        """Sign the sales of ``payment_method`` are crossed with: ``-1`` for a
        cash method (between the suspense accounts, see
        ``_cross_move_uses_suspense``), ``1`` otherwise.

        The cash of a sale reaches the real journal through the cash out that
        empties the drawer, and native ``try_cash_in_out`` leaves that cash out
        as a DEBIT on the method journal's suspense account. So the cross of a
        cash sale is the one of a cash out of the same amount: credit that
        suspense account, debit the ``cross_journal``'s. ``_create_cross_move_for``
        (``use_suspense=True``, the convention of the cash in/out) reads a
        negative amount as a cash out. Crossed with its own sign, the sale
        debited the method's suspense account a second time and took the money
        out of the real journal (ticket 15219, fixed in task 86801).
        """
        return -1 if self._cross_move_uses_suspense(payment_method) else 1

    def _sign_cross_amounts(self, sign, values):
        """``values`` (a leg of ``_get_combined_cross_legs`` or the kwargs of
        ``_get_cross_currency_amount_kwargs``) with its amounts multiplied by
        ``sign``; the rate and anything else stay as they are."""
        keys = ("amount", "foreign_amount", "currency_amount", "transitory_amount_currency")
        return {
            key: sign * value if key in keys and value is not None else value
            for key, value in values.items()
        }

    def _crosses_sales(self, payment_method):
        """Whether the sales of ``payment_method`` take part in the cross of
        ``_validate_cross_move``.

        Always here. A module that crosses each cash in/out of a drawer
        (``binaural_pos_close``) answers ``False`` for the method of that
        drawer: the cash out that empties it already takes the money of the
        sales to the real journal, so crossing the sales as well moves it
        twice.
        """
        return True

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
        instead credits the method journal's suspense account, where the cash
        out parked the money as a debit, and debits the ``cross_journal``'s
        (with the sign of ``_get_sales_cross_sign``).

        Bank methods keep the previous behaviour (``outstanding_account_id``
        → the ``cross_journal``'s real liquidity account): no cash out takes
        their balance out of the outstanding account.

        This only covers the sale path. Callers outside ``_validate_cross_move``
        pass their own flag: cash in/out (``binaural_pos_close``) already used
        ``use_suspense=True``, and opening/closing differences no longer cross
        (``binaural_pos_close``, task 86801).
        """
        return payment_method.type == "cash"

    def _is_cross_move_eligible(self, payment_method, use_suspense=False):
        """Whether ``payment_method`` takes part in the automatic cross move.

        ``is_foreign_currency`` is the business marker that drives the whole
        flow: every foreign-currency method clears its transitory account,
        with no second opt-in. A method in a third currency
        (``tender_currency_id``) crosses the same way: its journal is the
        transitory one in the PoS currency and ``cross_journal`` the real one
        in that currency. (A redundant ``apply_one_cross_move`` boolean
        used to gate this on top of ``is_foreign_currency``; it was removed,
        since it only served to leave the flow silently inactive on methods
        that plainly needed it.)

        A method missing either cross journal is skipped in silence — that
        configuration is incomplete, not wrong. ``use_suspense`` must match
        whatever will be passed to ``_create_cross_move_for`` — see
        ``_get_cross_transitory_account``.

        Under ``use_suspense=True`` BOTH legs come from a journal's
        ``suspense_account_id``, and either can be empty. An empty destination
        is not a harmless skip: ``_get_cross_real_account`` returns an empty
        recordset, the line is built with ``account_id = False`` and the
        insert violates ``account_move_line_check_accountable_required_fields``
        — inside ``action_pos_session_close``, so it would take the session
        close down with it. Hence the explicit check on the destination too;
        the skip is logged, since the session can no longer be opened with
        those accounts missing (``pos.config._check_cross_move_accounts``)
        and only a session opened before they were cleared gets here.

        The ``use_suspense=False`` branch does not skip on a missing
        ``cross_journal`` payment method line account: opening the session
        requires it from every module that crosses that way (the bank sales
        here, by method type — see ``_get_cross_move_missing_accounts`` —, the
        foreign cash drawer difference in ``binaural_pos_close``), and
        ``_create_cross_move_for`` raises a readable error for a session
        created before it was cleared.
        """
        if not (
            (payment_method.is_foreign_currency or payment_method.tender_currency_id)
            and payment_method.type != "pay_later"
            and payment_method.cross_account_journal
            and payment_method.cross_journal
        ):
            return False
        if not use_suspense:
            return bool(self._get_cross_transitory_account(payment_method))
        return self._cross_move_suspense_accounts_ready(payment_method)

    def _cross_move_suspense_accounts_ready(self, payment_method):
        """Whether both suspense accounts of a ``use_suspense=True`` cross move
        of ``payment_method`` are set; if not, logs the skip and returns False.
        """
        if self._get_cross_transitory_account(
            payment_method, use_suspense=True
        ) and self._get_cross_real_account(payment_method, outbound=False, use_suspense=True):
            return True
        _logger.warning(
            "Cross move of payment method %s skipped in session %s: %s",
            payment_method.name,
            self.name,
            ", ".join(self._get_cross_move_missing_accounts(payment_method)),
        )
        return False

    def _get_cross_move_missing_accounts(self, payment_method):
        """Describe each account the cross move of ``payment_method`` needs
        and is not set, one string per account (empty list: nothing missing).

        Only what this module's own cross move uses, by method type (see
        ``_cross_move_uses_suspense``): a bank sale lands on the
        ``cross_journal``'s payment method line accounts, a cash sale crosses
        between the two journals' suspense accounts. Other ``use_suspense=False``
        callers on a cash method (``binaural_pos_close``'s opening/closing
        differences) add the payment method line accounts themselves.
        """
        if self._cross_move_uses_suspense(payment_method):
            return self._get_cross_move_missing_suspense_accounts(payment_method)
        return self._get_cross_move_missing_payment_accounts(payment_method)

    def _get_cross_move_missing_payment_accounts(self, payment_method):
        """The ``cross_journal``'s incoming/outgoing payment method line
        accounts that are not set (``_get_cross_real_account`` with
        ``use_suspense=False``). ``l10n_ve_accountant`` only requires them on
        bank journals, and Odoo creates cash journals without them."""
        journal = payment_method.cross_journal.display_name
        return [
            f"{journal}: {label}"
            for outbound, label in (
                (False, _("incoming payments account")),
                (True, _("outgoing payments account")),
            )
            if not self._get_cross_real_account(payment_method, outbound=outbound)
        ]

    def _get_cross_move_missing_suspense_accounts(self, payment_method):
        """The ``suspense_account_id`` of the method's journal and of the
        ``cross_journal`` that is not set (``use_suspense=True``)."""
        return [
            _("%(journal)s: suspense account", journal=journal.display_name)
            for journal in payment_method.journal_id | payment_method.cross_journal
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

    def _get_cross_real_account(self, payment_method, outbound, use_suspense=False):
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
        account_method = payment_method.cross_journal
        if use_suspense:
            return account_method.suspense_account_id
        line_ids = (
            account_method.outbound_payment_method_line_ids
            if outbound
            else account_method.inbound_payment_method_line_ids
        )
        return line_ids.payment_account_id

    def _get_cross_real_amount_currency(
        self, payment_method, line_currency, amount, foreign_amount, currency_amount=None
    ):
        """``amount_currency`` de la línea del diario real (``cross_journal``),
        en ``line_currency`` (la moneda de ese diario) y con el signo de
        ``amount``:

        - diario en la alterna: ``foreign_amount``;
        - diario en la moneda de cobro del método (``tender_currency_id``): lo
          cobrado en esa moneda, ``currency_amount``. Sin esto, la línea de la
          caja en EUR llevaba los Bs como si fueran euros. Un llamador que no
          lo pasa (un módulo con la firma anterior) recibe la conversión de
          ``amount``, que está en la moneda de la compañía, a la tasa del día
          de la caja (``pos.config._convert``);
        - si no (diario en la moneda de la compañía): ``amount``.
        """
        if line_currency == self.foreign_currency_id:
            return foreign_amount
        if line_currency == payment_method.tender_currency_id:
            if currency_amount is None:
                return self.config_id._convert(
                    amount, self.company_id.currency_id, line_currency
                )
            return currency_amount
        return amount

    def _get_cross_transitory_currency_amount(
        self, payment_method, amount, foreign_amount, transitory_amount_currency=None
    ):
        """``(moneda, amount_currency)`` de la línea transitoria del cruce, con
        el signo de ``amount``.

        Por defecto, la moneda de la compañía con ``amount`` (o ``foreign_amount``
        si la compañía está en la alterna). Un diario del método en otra moneda
        (el transitorio de una caja en otra moneda, ``binaural_pos_multicurrency``)
        recibe las ventas en esa moneda (extracto o pago del cierre, con su
        ``amount_currency``): con la línea del cruce en la moneda de la
        compañía, la transitoria quedaría en cero en Bs pero con saldo en la
        moneda del diario. Para esos métodos el llamador pasa
        ``transitory_amount_currency``, el monto en la moneda del diario, y la
        línea va en esa moneda: la transitoria queda en cero en las dos.
        """
        journal_currency = payment_method.journal_id.currency_id
        if transitory_amount_currency is not None and journal_currency:
            return journal_currency, transitory_amount_currency
        company_currency = self.company_id.currency_id
        if company_currency == self.foreign_currency_id:
            return company_currency, foreign_amount
        return company_currency, amount

    def _line_vals_move_cross_incoming(
        self, payment_method, amount, foreign_amount, foreign_rate, partner, use_suspense=False,
        currency_amount=None, transitory_amount_currency=None,
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
        account_method = payment_method.cross_journal
        real_account = self._get_cross_real_account(
            payment_method, outbound=False, use_suspense=use_suspense
        ).id
        line_currency = account_method.currency_id or self.env.company.currency_id
        real_amount_currency = self._get_cross_real_amount_currency(
            payment_method, line_currency, amount, foreign_amount, currency_amount
        )
        transitory_currency, transitory_amount = self._get_cross_transitory_currency_amount(
            payment_method, amount, foreign_amount, transitory_amount_currency
        )

        return [
            Command.create(
                {
                    "account_id": real_account,
                    "partner_id": partner.id,
                    "amount_currency": real_amount_currency,
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
                    "account_id": transitory_account,
                    "partner_id": partner.id,
                    "amount_currency": -transitory_amount,
                    "debit": 0.0,
                    "foreign_debit": 0.0,
                    "credit": amount,
                    "foreign_credit": foreign_amount,
                    "not_foreign_recalculate": True,
                    "foreign_rate": foreign_rate,
                    "currency_id": transitory_currency.id,
                }
            ),
        ]

    def _line_vals_move_cross_outgoing(
        self, payment_method, amount, foreign_amount, foreign_rate, partner, use_suspense=False,
        currency_amount=None, transitory_amount_currency=None,
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
        account_method = payment_method.cross_journal
        real_account = self._get_cross_real_account(
            payment_method, outbound=True, use_suspense=use_suspense
        ).id
        line_currency = account_method.currency_id or self.env.company.currency_id
        real_amount_currency = self._get_cross_real_amount_currency(
            payment_method, line_currency, amount, foreign_amount, currency_amount
        )
        transitory_currency, transitory_amount = self._get_cross_transitory_currency_amount(
            payment_method, amount, foreign_amount, transitory_amount_currency
        )

        return [
            Command.create(
                {
                    "account_id": transitory_account,
                    "partner_id": partner.id,
                    "amount_currency": abs(transitory_amount),
                    "credit": 0.0,
                    "foreign_credit": 0.0,
                    "debit": abs(amount),
                    "foreign_debit": abs(foreign_amount),
                    "not_foreign_recalculate": True,
                    "foreign_rate": foreign_rate,
                    "currency_id": transitory_currency.id,
                }
            ),
            Command.create(
                {
                    "account_id": real_account,
                    "partner_id": partner.id,
                    "amount_currency": real_amount_currency,
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

    def _cross_move_ref(self, payment=None, payment_method=None):
        """Human-readable reference identifying what a cross move clears,
        starting with the session (``Caja 1/00050 · Sales · Efectivo USD``).

        ``name`` cannot carry this text — it is the move's sequential
        "Number", assigned by the journal on posting (see
        ``_create_cross_move``) — so ``ref`` is the only field the accountant
        sees in the journal entries list to tell one move from another. It is
        also the label of every line of the move, which is what the real
        journal's reconciliation dashboard shows: with the session in it, a
        line cannot be matched against the cross of another session.

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
        method in the session, so the session and the method (``payment_method``)
        are the right granularity.
        """
        if payment:
            parts = [self.name, payment.pos_order_id.name, payment.name or f"#{payment.id}"]
        else:
            parts = [self.name, _("Sales"), payment_method.name if payment_method else ""]
        return " · ".join(part for part in parts if part)

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
        self, payment_method, amount, foreign_amount, foreign_rate, partner, date, ref,
        use_suspense=False, currency_amount=None, transitory_amount_currency=None,
    ):
        """Create one clearing move for ``payment_method``.

        ``currency_amount`` is the amount in the method's tender currency
        (``tender_currency_id``, with the sign of ``amount``), or ``None`` for
        methods without one; it becomes the ``amount_currency`` of the
        ``cross_journal`` line (see ``_get_cross_real_amount_currency``).
        ``transitory_amount_currency`` is the amount in the currency of the
        method's journal when it is not the company's, or ``None``; it becomes
        the ``amount_currency`` of the transitory line (see
        ``_get_cross_transitory_currency_amount``).

        The sign of ``amount`` picks the direction: incoming for sales,
        outgoing for change/refunds. The combine granularity does not come
        through here: ``_create_combined_cross_move`` builds one move with an
        incoming and an outgoing leg (``_get_cross_move_line_vals`` for each).

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
        line_vals = self._get_cross_move_line_vals(
            payment_method, amount, foreign_amount, foreign_rate, partner,
            use_suspense=use_suspense, currency_amount=currency_amount,
            transitory_amount_currency=transitory_amount_currency,
        )
        self._check_cross_move_line_accounts(payment_method, line_vals)
        return self._create_cross_move(
            payment_method, line_vals, foreign_rate, date, ref, partner
        )

    def _get_cross_move_line_vals(
        self, payment_method, amount, foreign_amount, foreign_rate, partner,
        use_suspense=False, currency_amount=None, transitory_amount_currency=None,
    ):
        """The pair of lines that crosses ``amount`` (one payment, or one leg
        of a combined move), with the direction picked by its sign and the
        ``use_suspense`` inversion explained in ``_create_cross_move_for``."""
        is_outgoing = amount < 0
        call_amount, call_foreign_amount = amount, foreign_amount
        call_currency_amount = currency_amount
        call_transitory_amount = transitory_amount_currency
        if use_suspense:
            is_outgoing = not is_outgoing
            call_amount, call_foreign_amount = -amount, -foreign_amount
            if currency_amount is not None:
                call_currency_amount = -currency_amount
            if transitory_amount_currency is not None:
                call_transitory_amount = -transitory_amount_currency
        line_builder = (
            self._line_vals_move_cross_outgoing
            if is_outgoing
            else self._line_vals_move_cross_incoming
        )
        return line_builder(
            payment_method, call_amount, call_foreign_amount, foreign_rate, partner,
            use_suspense=use_suspense, currency_amount=call_currency_amount,
            transitory_amount_currency=call_transitory_amount,
        )

    def _check_cross_move_line_accounts(self, payment_method, line_vals):
        """Readable error instead of a NULL ``account_id`` violation when an
        account of the cross move of ``payment_method`` is not set."""
        if all(command[2]["account_id"] for command in line_vals):
            return
        raise UserError(
            _(
                "The cross move of the payment method %(method)s cannot be created "
                "because these accounts are not set:\n%(accounts)s\n"
                "Set them in the journal configuration and try again.",
                method=payment_method.name,
                accounts="\n".join(
                    f"- {account}"
                    for account in self._get_cross_move_missing_accounts(payment_method)
                    or [_("an account of the move lines")]
                ),
            )
        )

    def _create_cross_move(
        self, payment_method, line_vals, foreign_rate, date, ref, partner
    ):
        """Create the move that clears the transitory account to zero.

        Args:
            payment_method (pos.payment.method): method being cleared.
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
            account.move: the posted cross move.

        Every line takes ``ref`` as its label (see ``_cross_move_ref``).

        The move is posted right away: a draft cannot be reconciled from the
        real journal's dashboard, and every session close used to leave its
        crosses in draft for accounting to post one by one. A line on the
        real journal's transitory account then gets its statement line in
        that journal (``_create_cross_real_statement_lines``), the one to
        reconcile it against from the dashboard.

        ``name`` (the move's sequential "Number") is intentionally left
        unset so that on posting Odoo's native ``_compute_name`` assigns the
        next sequence from ``cross_account_journal`` — setting it explicitly
        here would permanently block that assignment (``_compute_name`` only
        calls ``_set_next_sequence()`` when ``name`` is empty/``'/'``). The
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
        # sudo: the cross is part of closing the session or registering a cash
        # move, which the cashier (point_of_sale.group_pos_user) does without
        # accounting rights; the core books the session the same way
        # (``_validate_session``: ``record.sudo()``).
        move = self.env["account.move"].sudo().with_company(self.company_id).create(
            {
                "ref": ref,
                "partner_id": self._cross_move_header_partner(partner).id,
                "date": date,
                "journal_id": payment_method.cross_account_journal.id,
                "line_ids": [
                    Command.create({**command[2], "name": ref}) for command in line_vals
                ],
                "foreign_currency_id": self.foreign_currency_id.id,
                "foreign_rate": foreign_rate,
                "company_id": self.company_id.id,
            }
        )
        move.action_post()
        self._create_cross_real_statement_lines(payment_method, move)
        return move.with_env(self.env)

    def _create_cross_real_statement_lines(self, payment_method, move):
        """One statement line in the real journal (``cross_journal``) for each
        line of the cross ``move`` on that journal's transitory account
        (``suspense_account_id``), with the same amount, alternate amount,
        partner and label.

        That is where a cash cross leaves the money (``use_suspense=True``:
        cash sales, cash in/out, see ``_get_cross_real_account``), and no
        other movement takes it on to the real journal's own account: its
        dashboard had nothing to reconcile and the statement lines had to be
        entered by hand. Each statement line is left to reconcile against its
        own cross line, one to one: Odoo does not reconcile a statement line
        against several lines of its own transitory account ("the journal
        entry must always have only one suspense line").

        The statement line moves the real journal's account by the same
        amount, in that journal's currency (the ``amount_currency`` of the
        cross line, which is in that currency). Its counterpart lands on the
        same transitory account with the opposite sign: reconciling both
        clears it.

        Nothing is created if that transitory account is also the one of the
        method's journal: both lines of the cross are then on it and there is
        no way to tell the real one (the configuration needs a transitory
        account per journal).
        """
        self.ensure_one()
        journal = payment_method.cross_journal
        suspense_account = journal.suspense_account_id
        statement_lines = self.env["account.bank.statement.line"]
        if not suspense_account or suspense_account == payment_method.journal_id.suspense_account_id:
            return statement_lines
        vals_list = [
            {
                "journal_id": journal.id,
                "date": move.date,
                "payment_ref": line.name,
                # ``partner_id`` of a statement line is ``check_company``, like the
                # move header's: a customer of another company would block the close.
                "partner_id": self._cross_move_header_partner(line.partner_id).id,
                "amount": line.amount_currency,
                "foreign_amount": line.foreign_debit - line.foreign_credit,
            }
            for line in move.line_ids.filtered(lambda l: l.account_id == suspense_account)
        ]
        if not vals_list:
            return statement_lines
        return statement_lines.sudo().with_context(no_retrieve_partner=True).create(vals_list)

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
        see the same fix already applied in ``_create_split_account_payments``).

        Native Odoo 19 ``_create_combine_account_payment`` returns the
        receivable ``account.move.line`` on the ``account.payment``'s own
        move (see ``/home/binaural19/odoo/addons/point_of_sale/models/pos_session.py:1094``),
        the same contract as the core ``_create_split_account_payment``.
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

    def _create_split_account_payments(self, payment_amounts_list):
        """Venezuelan rate and alternate amounts on the ``account.payment``
        of each split bank payment.

        Odoo 19 creates the split payments in batch: ``_create_bank_payment_moves``
        calls this method directly and the core ``_create_split_account_payment``
        only delegates to it, so an override of the singular method never runs
        when a session is closed (tarea 83148, H15).

        Each payment move gets the rate the register charged with
        (``pos.payment.foreign_rate``, same convention as the other POS
        payment moves) and, on every line, the alternate amount the register
        charged (``foreign_amount``). Otherwise ``l10n_ve_accountant`` values
        the liquidity line at the rate of the move date: when the rate changed
        between the sale and the closing, the move no longer balances in the
        alternate currency (receivable 12.45 against liquidity 11.76).
        """
        payment_to_line = super(
            PosSession, self.with_context(from_pos=True)
        )._create_split_account_payments(payment_amounts_list)

        for payment, receivable_lines in payment_to_line.items():
            payment_move = receivable_lines.move_id
            if not payment_move:
                continue
            rate_vals = payment.pos_order_id.config_id._get_move_foreign_rate_vals(
                payment.foreign_rate
            )
            account_payment = payment_move.origin_payment_id
            if account_payment and rate_vals:
                account_payment.write(
                    {
                        "foreign_rate": rate_vals["foreign_rate"],
                        "foreign_inverse_rate": rate_vals["foreign_inverse_rate"],
                    }
                )
            if rate_vals:
                payment_move.write(rate_vals)

            foreign_amount = abs(payment.foreign_amount)
            for line in payment_move.line_ids:
                line.write(
                    {
                        "not_foreign_recalculate": True,
                        "foreign_debit": foreign_amount if line.debit > 0 else 0.0,
                        "foreign_credit": foreign_amount if line.credit > 0 else 0.0,
                    }
                )
        return payment_to_line

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
          ``_create_split_account_payments``).

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
        """Write ``foreign_debit``/``foreign_credit`` on ``line`` when its
        debit or credit matches ``amount``, mirroring the write onto the
        line's non-``asset_receivable`` counterpart in the same move, if any.

        The counterpart lookup used to gate the write to ``line`` itself
        too: when a payment method's ``combine_cash_receivable_lines`` sits
        on the session's own closing move — which only ever holds
        ``asset_receivable`` lines, since the real cash/bank account leg is
        booked on a separate bank-statement move — ``other_lines`` came back
        empty and the whole method silently did nothing. ``not_foreign_recalculate``
        was then never set, so the line fell back to the base compute, which
        ran once at creation time (before the move's ``foreign_inverse_rate``
        had been assigned) and got stuck at 0.

        The counterpart is only mirrored and locked (``not_foreign_recalculate``)
        on a bank-statement move — the cash statement the closing books per
        cash method, whose only non-receivable line is the cash/liquidity
        leg. Mirroring without locking let ``l10n_ve_accountant`` recompute
        that leg at the rate of the move date (the closing day), while the
        receivable leg kept the sale-time ``foreign_amount``: when the BCV
        rate changed between the sale and the closing, the statement ended
        up with foreign debit != foreign credit (ticket #15169). On any other
        move (the session's own closing move) the first non-receivable line
        is a sales or tax line of non-invoiced orders, not a counterpart:
        it is left alone so the base compute keeps valuing it.
        """
        rounding = self.currency_id.rounding
        matched_credit = abs(line.credit) > 0 and float_compare(
            line.credit, abs(amount), precision_rounding=rounding
        ) == 0
        matched_debit = abs(line.debit) > 0 and float_compare(
            line.debit, abs(amount), precision_rounding=rounding
        ) == 0
        if not (matched_credit or matched_debit):
            return

        line.not_foreign_recalculate = True
        if matched_credit:
            line.foreign_credit = abs(foreign_amount)
        if matched_debit:
            line.foreign_debit = abs(foreign_amount)

        if not line.move_id.statement_line_id:
            return
        other_lines = line.move_id.line_ids.filtered(
            lambda x: x != line and x.account_id.account_type != "asset_receivable"
        )
        if not other_lines:
            return
        other_line = other_lines[0]
        other_line.not_foreign_recalculate = True
        if matched_credit:
            other_line.foreign_debit = abs(line.foreign_credit)
        if matched_debit:
            other_line.foreign_credit = abs(line.foreign_debit)
