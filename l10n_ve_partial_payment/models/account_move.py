"""Route the payment widget's "Add" popover through a validated partial amount.

``l10n_ve_igtf.js_assign_outstanding_line`` always reconciles the full
``amount_residual`` of an outstanding line and, for advances, never calls
``super()``. This module reads a single validated context key
(``CONTEXT_KEY``) and, when present and strictly smaller than the invoice's
residual, routes the call so only that amount gets applied -- without
reimplementing the advance-move builder, the IGTF calculation, or the core
reconciliation engine.

Known limitation (documented, not fixed in this base cut): ``force_balance``
is unconditionally neutralized for partial advances (see
``prepare_advance_payment_vals`` below) rather than recomputed proportionally
for multi-currency cases. This keeps a single advance application consistent
regardless of how many partials it took, but successive partials in a
different-currency scenario (invoice/advance in USD, company in VEF) can
leave the exchange-difference entries distributed differently than a single
full application would. Left as follow-up refactor.
"""
from odoo import api, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare
from odoo.tools.misc import formatLang

CONTEXT_KEY = "l10n_ve_partial_paid_amount"
GROUP_XML_ID = "l10n_ve_partial_payment.group_partial_payment_apply"


class AccountMove(models.Model):
    """Extend ``account.move`` to support partial outstanding-line reconciliation."""

    _inherit = "account.move"

    def _can_apply_partial_payment(self):
        """Return whether the current user/company may use a partial amount.

        Both gates are enforced server-side, not just in the JS popover
        (which is cosmetic and bypassable via a direct RPC call): the
        company flag defaults to ``False`` (section 6.1, flags don't affect
        integrity but the feature must actually stay off by default), and
        users outside ``group_partial_payment_apply`` get the unmodified
        ``l10n_ve_igtf`` behavior instead of an error (section 6.13).
        """
        self.ensure_one()
        return bool(
            self.company_id.partial_pay_from_outstanding
            and self.env.user.has_group(GROUP_XML_ID)
        )

    def can_apply_partial_payment(self):
        """Public accessor for ``_can_apply_partial_payment``, callable from JS.

        The "Add" popover calls this before deciding whether to open at all.
        Without it, a click with the feature disabled (missing group, or the
        company flag off) would still show the amount input and silently
        apply the *full* amount on submit -- technically correct (the server
        gate in ``js_assign_outstanding_line`` still holds), but confusing,
        since nothing would tell the user their typed amount was ignored.
        """
        self.ensure_one()
        return self._can_apply_partial_payment()

    def _is_advance_outstanding_line(self, line):
        """Return whether ``line``'s originating move is an advance payment.

        Mirrors the predicate used by ``l10n_ve_igtf.js_assign_outstanding_line``
        (``is_advance_move`` / ``origin_payment_advanced_payment_id`` /
        ``origin_payment_id.is_advance_payment``) so both modules agree on
        what counts as an advance.

        Parameters
        ----------
        line : account.move.line
            The outstanding credit/debit line selected from the payment
            widget's "Add" popover.

        Returns
        -------
        bool
            ``True`` when ``line``'s move is flagged as an advance payment.
        """
        payment_move = line.move_id
        return bool(
            payment_move.is_advance_move
            or payment_move.origin_payment_advanced_payment_id
            or (payment_move.origin_payment_id and payment_move.origin_payment_id.is_advance_payment)
        )

    @api.readonly
    def preview_advance_igtf_shortfall(self, line_id, paid_amount):
        """RPC-callable, read-only preview of an advance's IGTF shortfall.

        Computes (without creating/writing anything) whether applying
        ``paid_amount`` to the advance outstanding line ``line_id`` would
        leave that advance without enough headroom to also cover its own
        IGTF -- in which case ``l10n_ve_igtf`` carves the IGTF out of the
        invoice's receivable/payable line instead, applying LESS than
        ``paid_amount`` to the invoice. This is intentional, confirmed
        behavior on the accounting side (not a bug); this method only
        exists to warn the user about it *before* they apply.

        Replicates, without calling or modifying it, the exact formula of
        ``l10n_ve_igtf.account_move._create_advance_payment_move`` (lines
        326-477 at the time of writing, in particular the
        ``base_amount_applied``/``igtf_in_invoice_curr`` comparison at
        lines 372-439) and of ``prepare_igtf_payment_vals`` (lines
        524-577, the sign-aware adjustment of the counterpart line that
        decides what actually reconciles against the invoice). Only
        public methods/fields of ``l10n_ve_igtf`` are used:
        ``account.payment.calculate_igtf_for_payment`` and
        ``invoice_outstanding_credits_debits_widget_advance_payment``. If
        that module's formula changes, this preview can drift out of sync
        -- the parity test in this module's test suite
        (``test_advance_igtf_shortfall_preview.py``) pins the two against
        each other so such a drift fails loudly instead of silently.

        Parameters
        ----------
        line_id : int
            ID of the outstanding ``account.move.line`` selected from the
            popover (same id ``js_assign_outstanding_line`` would receive).
        paid_amount : float
            Amount the user is about to apply, in the invoice's currency
            (may be a genuine partial, or an amount greater than or equal
            to the invoice's residual -- the "apply in full" case, which
            this preview also covers by clamping to the residual the same
            way the full-apply path does downstream).

        Returns
        -------
        dict
            ``{'shortfall': False}`` when there is nothing to warn about
            (not an advance line, not an IGTF journal, enough headroom in
            the advance, or any input that can't be resolved -- e.g. a
            line belonging to a different company/partner's advance, which
            simply won't be found in the widget content). Otherwise
            ``{'shortfall': True, 'requested': <float>, 'real_applied':
            <float>, 'igtf': <float>, 'currency_id': <int>}``, all amounts
            in the invoice's currency.
        """
        self.ensure_one()
        no_shortfall = {"shortfall": False}

        widget = self.invoice_outstanding_credits_debits_widget_advance_payment or {}
        widget_content = widget.get("content", []) if isinstance(widget, dict) else []

        outstanding_line = self.env["account.move.line"].browse(line_id)
        target_move_id = outstanding_line.move_id.id
        matched_content = next(
            (c for c in widget_content if c.get("move_id") == target_move_id), None
        )
        if not matched_content or not self._is_advance_outstanding_line(outstanding_line):
            return no_shortfall

        payment = (
            outstanding_line.move_id.origin_payment_advanced_payment_id
            or outstanding_line.move_id.origin_payment_id
        )
        if not payment:
            return no_shortfall

        is_igtf_journal = bool(
            payment.journal_id.is_igtf
            if (
                self.partner_id._check_igtf_apply_improved(self.move_type)
                and not self.journal_id.is_purchase_international
            )
            else False
        )
        if not is_igtf_journal:
            return no_shortfall

        currency = self.currency_id
        advance_amount = matched_content.get("amount", 0.0) or 0.0
        advance_amount_payment_curr = matched_content.get("amount_residual_currency", 0.0) or 0.0
        conversion_date = matched_content.get("date_to_convert")

        if currency.is_zero(advance_amount):
            # Mirrors `_create_advance_payment_move`'s own `UserError` guard
            # ("advance amount not found"): nothing meaningful to preview.
            return no_shortfall

        try:
            requested = float(paid_amount)
        except (TypeError, ValueError):
            return no_shortfall
        if float_compare(requested, 0.0, precision_rounding=currency.rounding) <= 0:
            return no_shortfall

        # The "apply in full" path (paid_amount >= residual, or no
        # CONTEXT_KEY at all) always routes through `js_assign_outstanding_line`
        # with the invoice's own full residual as `amount_residual`, never
        # the literal typed amount -- clamp the same way here so the preview
        # matches what would actually be sent downstream.
        invoice_residual = abs(self.amount_residual)
        effective_requested = (
            min(requested, invoice_residual) if not currency.is_zero(invoice_residual) else requested
        )

        base_amount_applied = min(effective_requested, advance_amount)
        applied_payment_curr = advance_amount_payment_curr
        if advance_amount > 0:
            applied_payment_curr = payment.currency_id.round(
                advance_amount_payment_curr * (base_amount_applied / advance_amount)
            )

        igtf_amount = abs(
            payment.calculate_igtf_for_payment(
                self, applied_payment_curr, payment.currency_id, conversion_date
            )
        )
        if currency.is_zero(igtf_amount):
            return no_shortfall

        igtf_in_invoice_curr = payment.currency_id._convert(
            igtf_amount, currency, self.company_id, conversion_date
        )

        if currency.compare_amounts(base_amount_applied + igtf_in_invoice_curr, advance_amount) <= 0:
            # Escenario A: the advance absorbs its own IGTF -- the full
            # (clamped) requested amount still lands on the invoice.
            return no_shortfall

        # Escenario B: replicate `prepare_igtf_payment_vals`'s sign-aware
        # adjustment of the counterpart (receivable/payable) line instead of
        # a naive subtraction. Regardless of inbound/outbound sign, that
        # adjustment always shrinks the counterpart line's magnitude by
        # `igtf_amount` (in the payment's own currency) -- see the method's
        # docstring for the line-by-line trace.
        amount_advance_payment_curr = (
            base_amount_applied if payment.currency_id == currency else applied_payment_curr
        )
        real_applied_payment_curr = amount_advance_payment_curr - igtf_amount
        if payment.currency_id != currency:
            real_applied = payment.currency_id._convert(
                real_applied_payment_curr, currency, self.company_id, conversion_date
            )
        else:
            real_applied = real_applied_payment_curr
        real_applied = max(0.0, currency.round(real_applied))

        return {
            "shortfall": True,
            "requested": requested,
            "real_applied": real_applied,
            "igtf": currency.round(igtf_in_invoice_curr),
            "currency_id": currency.id,
        }

    def js_assign_outstanding_line(self, line_id):
        """Reconcile ``line_id`` against ``self``, honoring a partial amount.

        Without ``context[CONTEXT_KEY]`` this call is byte-for-byte identical
        to ``l10n_ve_igtf``'s behavior (full-residual reconciliation), via a
        plain ``super()`` call. A requested amount that is negative or zero
        is rejected; one that is greater than or equal to the invoice's
        residual is treated as a full application (same plain ``super()``
        path, since there is nothing left to prorate).

        For a genuine partial amount:

        - On an advance outstanding line, the amount is routed through the
          existing ``_create_advance_payment_move`` /
          ``_reconcile_move_with_payment_difference`` pair (which apply the
          advance's own available-amount clamp internally via
          ``base_amount_applied = min(advance_amount_residual, advance_amount)``).
          The call runs under ``self.with_company(self.company_id)`` so
          accounts/journals resolve against the invoice's company, not the
          active one.
        - Otherwise, ``super()`` is called with ``move_id``/``line_id`` added
          to the context so the core reconciliation engine can prorate via
          ``account.move.line._prepare_reconciliation_amls``. Those two keys
          scope that override to this exact (invoice, outstanding line) pair
          so it never touches unrelated reconciliations (exchange-difference
          or cash-basis moves) that might run under the same context later
          in the same request.

        Parameters
        ----------
        line_id : int
            ID of the outstanding ``account.move.line`` to reconcile.

        Returns
        -------
        None
            Matches the return type of ``l10n_ve_igtf``'s advance branch,
            or whatever the core/``l10n_ve_igtf`` ``super()`` call returns.
        """
        self.ensure_one()
        raw_amount = self.env.context.get(CONTEXT_KEY)

        if raw_amount is None or not self._can_apply_partial_payment():
            return super().js_assign_outstanding_line(line_id)

        currency = self.currency_id
        paid_amount = float(raw_amount)

        if float_compare(paid_amount, 0.0, precision_rounding=currency.rounding) <= 0:
            raise UserError(_("The amount to apply must be greater than zero."))

        invoice_residual = abs(self.amount_residual)

        if float_compare(paid_amount, invoice_residual, precision_rounding=currency.rounding) >= 0:
            # Requesting the full residual (or more, clamped downstream): no
            # partial to prorate, behave exactly like the unmodified module.
            return super().js_assign_outstanding_line(line_id)

        outstanding_line = self.env["account.move.line"].browse(line_id)
        residual_before = invoice_residual

        if not self._is_advance_outstanding_line(outstanding_line):
            result = super(
                AccountMove, self.with_context(move_id=self.id, line_id=line_id)
            ).js_assign_outstanding_line(line_id)
        else:
            company = self.company_id
            move_to_reconcile = self.with_context(
                **{CONTEXT_KEY: paid_amount}
            ).with_company(company)._create_advance_payment_move(paid_amount, outstanding_line)

            result = self.with_company(company)._reconcile_move_with_payment_difference(
                outstanding_line.move_id, move_to_reconcile
            )

        self._post_partial_payment_audit_message(outstanding_line, residual_before)
        return result

    def _post_partial_payment_audit_message(self, outstanding_line, residual_before):
        """Log who applied how much of which payment, in the invoice's chatter.

        Reads the actually-applied amount back from ``self.amount_residual``
        (before/after) rather than trusting the requested ``paid_amount``,
        since the advance branch can apply less than requested when the
        advance itself holds less than what was asked (see module
        docstring: that clamp lives in ``l10n_ve_igtf``, not here).

        Parameters
        ----------
        outstanding_line : account.move.line
            The outstanding line the user applied from the popover.
        residual_before : float
            ``abs(self.amount_residual)`` captured before reconciling.
        """
        self.ensure_one()
        self.invalidate_recordset(["amount_residual"])
        applied = residual_before - abs(self.amount_residual)
        payment = (
            outstanding_line.move_id.origin_payment_advanced_payment_id
            or outstanding_line.move_id.origin_payment_id
        )
        self.message_post(
            body=_(
                "Partial payment applied: %(applied)s from %(payment)s. "
                "Remaining balance: %(remaining)s.",
                applied=formatLang(self.env, applied, currency_obj=self.currency_id),
                payment=payment.name or payment.id if payment else _("Unknown"),
                remaining=formatLang(self.env, abs(self.amount_residual), currency_obj=self.currency_id),
            )
        )

    def prepare_advance_payment_vals(
        self,
        payment,
        amount,
        advance_values,
        counter_part_values,
        date,
        common_vals,
        amount_payment_curr=None,
        force_balance=None,
    ):
        """Prevent ``force_balance`` from overriding a genuinely partial amount.

        ``l10n_ve_igtf._create_advance_payment_move`` sets ``force_balance``
        to the invoice's full residual whenever the amount it is about to
        apply equals (within rounding) the amount it was asked to apply --
        which is trivially true even for a partial request, because the
        caller already passed the partial amount as ``amount_residual``.
        Left uncorrected, this would force the cross-entry to settle the
        invoice in full regardless of the smaller amount requested (see
        module docstring).

        This override unconditionally neutralizes ``force_balance`` to
        ``None`` whenever ``context[CONTEXT_KEY]`` is set (i.e. the call was
        routed through the partial-advance branch above), so the cross-entry
        reflects the applied amount instead of the full residual. This is
        the simple variant (option A): it does not attempt to reproduce the
        proportional "balance at invoice rate" behavior ``force_balance``
        gives full applications in multi-currency scenarios -- see the
        module docstring's "Known limitation". Every other case (no partial
        context) delegates unchanged to ``super()``.

        Parameters
        ----------
        payment : account.payment
            The payment originating the advance.
        amount : float
            Base amount, in the invoice's currency, being applied.
        advance_values : dict
            ``name``/``account_id`` for the advance account line.
        counter_part_values : dict
            ``name``/``account_id`` for the receivable/payable line.
        date : date
            Conversion date for currency conversions.
        common_vals : dict
            Values shared by both generated lines.
        amount_payment_curr : float, optional
            ``amount`` expressed in the payment's currency.
        force_balance : float, optional
            Balance to force on the advance line, or ``None``.

        Returns
        -------
        list of odoo.fields.Command
            Same shape as the core/``l10n_ve_igtf`` implementation.
        """
        self.ensure_one()

        if self.env.context.get(CONTEXT_KEY) is not None and force_balance is not None:
            force_balance = None

        return super().prepare_advance_payment_vals(
            payment,
            amount,
            advance_values,
            counter_part_values,
            date,
            common_vals,
            amount_payment_curr=amount_payment_curr,
            force_balance=force_balance,
        )
