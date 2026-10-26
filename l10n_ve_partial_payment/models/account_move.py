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
from odoo.tools import float_compare, float_round
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

    def _get_advance_widget_match(self, line_id):
        """Return ``(outstanding_line, payment, widget_content)`` for an advance line.

        Looks ``line_id`` up in THIS invoice's own
        ``invoice_outstanding_credits_debits_widget_advance_payment`` (the same
        lookup ``l10n_ve_igtf._create_advance_payment_move`` does by
        ``move_id``), so a line from another partner/company never resolves
        and no foreign data is exposed.

        Returns
        -------
        tuple or None
            ``None`` when the line is not an advance listed in this invoice's
            advance widget, or has no originating payment.
        """
        self.ensure_one()
        widget = self.invoice_outstanding_credits_debits_widget_advance_payment or {}
        widget_content = widget.get("content", []) if isinstance(widget, dict) else []

        outstanding_line = self.env["account.move.line"].browse(line_id).exists()
        if not outstanding_line:
            return None
        target_move_id = outstanding_line.move_id.id
        matched_content = next(
            (c for c in widget_content if c.get("move_id") == target_move_id), None
        )
        if not matched_content or not self._is_advance_outstanding_line(outstanding_line):
            return None

        payment = (
            outstanding_line.move_id.origin_payment_advanced_payment_id
            or outstanding_line.move_id.origin_payment_id
        )
        if not payment:
            return None
        return outstanding_line, payment, matched_content

    def _compute_advance_igtf_preview(self, line_id, paid_amount):
        """Compute, without persisting anything, how an advance + IGTF applies.

        With an advance from an IGTF journal, the IGTF is charged ON TOP of
        the applied amount and consumed from the same advance (consumption =
        applied amount + IGTF). When the advance has no headroom for it,
        ``l10n_ve_igtf`` carves the IGTF out of the invoice's
        receivable/payable line instead, applying LESS than requested. This
        is intentional, confirmed behavior on the accounting side (not a
        bug); this helper only mirrors it so the UI can show it *before*
        applying.

        Replicates, without calling or modifying it, the formula of
        ``l10n_ve_igtf.account_move._create_advance_payment_move`` (in
        particular the ``base_amount_applied``/``igtf_in_invoice_curr``
        comparison and the rounding of ``base_amount_applied + igtf``) and of
        ``prepare_igtf_payment_vals`` (the sign-aware adjustment of the
        counterpart line that decides what actually reconciles against the
        invoice). The IGTF itself comes from the public
        ``account.payment.calculate_igtf_for_payment`` (see
        ``l10n_ve_igtf/models/l10n_ve_igtf_utils.py:28-49``): it is NOT always
        amount x %, it is computed over ``min(payment, invoice residual)``,
        capped at ``igtf_top_aply - alter_bi_igtf`` and zero when the top
        equals the residual. If ``l10n_ve_igtf`` changes, this can drift --
        the parity tests of this module pin both against each other.

        Parameters
        ----------
        line_id : int
            ID of the outstanding ``account.move.line`` selected from the
            popover.
        paid_amount : float
            Amount the user is about to apply, in the invoice's currency. It
            is clamped to the invoice's residual, as the full-apply path does.

        Returns
        -------
        dict or None
            ``None`` when nothing IGTF-related applies (not an advance of
            this invoice's widget, non-IGTF journal/partner, zero IGTF,
            invalid amount, or partial payments not allowed). Otherwise a
            dict, all amounts in the invoice's currency::

                {'applies': True, 'percentage', 'requested',
                 'applied_to_invoice', 'igtf', 'total_consumed',
                 'shortfall', 'currency_id'}
        """
        self.ensure_one()
        if not self._can_apply_partial_payment():
            return None

        match = self._get_advance_widget_match(line_id)
        if not match:
            return None
        _outstanding_line, payment, matched_content = match

        is_igtf_journal = bool(
            payment.journal_id.is_igtf
            if (
                self.partner_id._check_igtf_apply_improved(self.move_type)
                and not self.journal_id.is_purchase_international
            )
            else False
        )
        if not is_igtf_journal:
            return None

        currency = self.currency_id
        advance_amount = matched_content.get("amount", 0.0) or 0.0
        advance_amount_payment_curr = matched_content.get("amount_residual_currency", 0.0) or 0.0
        conversion_date = matched_content.get("date_to_convert")

        if currency.is_zero(advance_amount):
            # Mirrors `_create_advance_payment_move`'s own `UserError` guard
            # ("advance amount not found"): nothing meaningful to preview.
            return None

        try:
            requested = float(paid_amount)
        except (TypeError, ValueError):
            return None
        if float_compare(requested, 0.0, precision_rounding=currency.rounding) <= 0:
            return None

        # The "apply in full" path (paid_amount >= residual) always routes
        # through `js_assign_outstanding_line` with the invoice's own full
        # residual, never the literal typed amount -- clamp the same way.
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
            return None

        igtf_in_invoice_curr = payment.currency_id._convert(
            igtf_amount, currency, self.company_id, conversion_date
        )
        result = {
            "applies": True,
            "percentage": self.company_id.igtf_percentage,
            "requested": requested,
            "igtf": currency.round(igtf_in_invoice_curr),
            "currency_id": currency.id,
        }

        if currency.compare_amounts(base_amount_applied + igtf_in_invoice_curr, advance_amount) <= 0:
            # Scenario A: the advance absorbs its own IGTF -- the whole
            # (clamped) amount lands on the invoice. Rounded in ONE place,
            # like l10n_ve_igtf does (`round(base + igtf)`).
            result.update(
                applied_to_invoice=base_amount_applied,
                total_consumed=currency.round(base_amount_applied + igtf_in_invoice_curr),
                shortfall=False,
            )
            return result

        # Scenario B: replicate `prepare_igtf_payment_vals`'s sign-aware
        # adjustment of the counterpart (receivable/payable) line. Regardless
        # of inbound/outbound sign, that adjustment always shrinks the
        # counterpart line's magnitude by `igtf_amount` (in the payment's own
        # currency).
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

        # The advance line is consumed by `base_amount_applied` (the IGTF is
        # carved out of it, not added on top).
        result.update(
            applied_to_invoice=real_applied,
            total_consumed=currency.round(base_amount_applied),
            shortfall=True,
        )
        return result

    @api.readonly
    def preview_advance_igtf(self, line_id, paid_amount):
        """RPC-callable, read-only preview of an advance's IGTF breakdown.

        Parameters
        ----------
        line_id : int
            ID of the outstanding line selected from the popover.
        paid_amount : float
            Amount the user is about to apply, in the invoice's currency.

        Returns
        -------
        dict
            ``{'applies': False}`` when IGTF is not involved; otherwise the
            full dict of ``_compute_advance_igtf_preview``.
        """
        self.ensure_one()
        return self._compute_advance_igtf_preview(line_id, paid_amount) or {"applies": False}

    def _get_outstanding_available(self, line_id):
        """Return the available amount (invoice currency) of ``line_id``, or ``None``.

        Resolved only from this invoice's own payment widgets, so a foreign
        line never leaks data.
        """
        self.ensure_one()
        for widget in (
            self.invoice_outstanding_credits_debits_widget,
            self.invoice_outstanding_credits_debits_widget_advance_payment,
        ):
            content = widget.get("content", []) if isinstance(widget, dict) else []
            for item in content:
                if item.get("id") == line_id:
                    return abs(item.get("amount", 0.0) or 0.0)
        return None

    @api.readonly
    def get_partial_popover_data(self, line_id):
        """Return what the "Add" popover needs, in a single RPC.

        Returns
        -------
        dict
            ``allowed``: whether partial payments can be used;
            ``igtf_applies``/``igtf_rate``: whether an IGTF is charged on top
            of the amount (advance from an IGTF journal) and its percentage;
            ``suggested_amount``: the amount to pre-fill, in the invoice's
            currency. Without IGTF it is ``min(available, residual)``. With
            IGTF it is the largest amount that fits in the advance together
            with its own IGTF (no shortfall), never above the residual.
        """
        self.ensure_one()
        currency = self.currency_id
        data = {
            "allowed": self._can_apply_partial_payment(),
            "igtf_applies": False,
            "igtf_rate": 0.0,
            "suggested_amount": 0.0,
        }
        available = self._get_outstanding_available(line_id)
        if available is None:
            return data

        cap = currency.round(min(available, abs(self.amount_residual)))
        data["suggested_amount"] = cap
        if not data["allowed"] or currency.is_zero(cap):
            return data

        probe = self._compute_advance_igtf_preview(line_id, cap)
        if not probe:
            return data
        data["igtf_applies"] = True
        data["igtf_rate"] = probe["percentage"]
        if not probe["shortfall"]:
            # The whole min(available, residual) fits with its IGTF.
            return data

        rate = probe["percentage"] / 100.0
        rounding = currency.rounding

        def down(value):
            return float_round(value, precision_rounding=rounding, rounding_method="DOWN")

        def fits(amount):
            check = self._compute_advance_igtf_preview(line_id, amount)
            return bool(check) and not check["shortfall"]

        candidates = {cap, down(available / (1.0 + rate))}
        # Once part of the invoice's IGTF was already paid, the IGTF left to
        # charge is capped (l10n_ve_igtf_utils.py:39-49), so the best amount
        # can be "available - remaining IGTF" instead.
        remaining_igtf = self.igtf_top_aply - self.alter_bi_igtf
        if remaining_igtf > 0:
            candidates.add(down(available - remaining_igtf))

        best = 0.0
        for start in sorted((min(c, cap) for c in candidates), reverse=True):
            if start <= best or float_compare(start, 0.0, precision_rounding=rounding) <= 0:
                continue
            amount = start
            for _step in range(6):  # initial try + 5 downward steps
                if float_compare(amount, 0.0, precision_rounding=rounding) <= 0:
                    break
                if fits(amount):
                    # The unrounded IGTF can let the amount be one or two
                    # cents higher than the floor candidate: step up.
                    for _up in range(2):
                        higher = currency.round(amount + rounding)
                        if float_compare(higher, cap, precision_rounding=rounding) > 0 or not fits(higher):
                            break
                        amount = higher
                    best = max(best, amount)
                    break
                amount = currency.round(amount - rounding)
        # If nothing fits (e.g. a tiny advance), keep the cap: the shortfall
        # alert still warns before applying.
        data["suggested_amount"] = best or cap
        return data

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
