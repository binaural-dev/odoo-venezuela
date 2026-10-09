"""Prorate a non-advance reconciliation candidate to a requested partial amount.

Advances are routed elsewhere (``account.move.js_assign_outstanding_line``);
this hook only handles the non-advance branch of the payment widget's "Add"
popover, where the core reconciliation engine (``account.move.line.reconcile``,
via ``_reconcile_plan_with_sync`` / ``_prepare_reconciliation_plan``) ends up
calling ``_prepare_reconciliation_amls``.

The cap is applied to ``values_list`` *before* delegating to ``super()``, not
to its result afterwards: capping the result would leave the core's own
exchange-difference computation (``exchange_values``, built from the
uncapped amount) and its bookkeeping of which lines got fully reconciled
untouched, producing a wrong exchange-difference entry whenever the invoice
and the outstanding line are in different currencies from the company
currency. Capping the input lets the core compute both consistently for the
smaller amount.
"""
from odoo import models
from odoo.tools import float_is_zero

CONTEXT_KEY = "l10n_ve_partial_paid_amount"


class AccountMoveLine(models.Model):
    """Extend ``account.move.line`` to prorate a partial reconciliation candidate."""

    _inherit = "account.move.line"

    def _prepare_reconciliation_amls(self, values_list, shadowed_aml_values=None):
        """Cap the invoice's candidate lines in ``values_list`` to a SHARED
        budget of the requested amount, instead of capping each one
        independently.

        Only active when both ``context[CONTEXT_KEY]`` and ``context['move_id']``/
        ``context['line_id']`` are present -- these are set together by
        ``account.move.js_assign_outstanding_line`` for the exact (invoice,
        outstanding line) pair being reconciled from the widget, so this
        never touches an unrelated reconciliation (e.g. cash-basis or
        exchange-difference moves) that happens to run under the same
        ambient context later in the same request.

        Capping each candidate line independently is wrong whenever the
        invoice's payment term has more than one installment line: e.g. two
        50 installments with a requested amount of 60 would let each one
        independently claim ``min(60, 50) = 50``, over-applying 100 instead
        of 60. Here a single ``remaining_amount`` budget (initialized to
        ``abs(paid_amount)``) is shared and consumed across ALL of the
        move's candidate lines, oldest due date first, so the total applied
        never exceeds the requested amount.

        ``remaining_amount`` is reset on every call to this hook. That is
        correct in this flow because ``js_assign_outstanding_line`` always
        reconciles against a SINGLE invoice per call (one currency node with
        pending lines); if the core ever allowed splitting one payment
        across several invoices within the same call, this accumulator
        would need to be reconsidered (it must not be assumed to hold
        across nodes).

        Parameters
        ----------
        values_list : list of dict
            Reconciliation candidates as built by the core engine, each with
            at least ``aml``, ``amount_residual`` and
            ``amount_residual_currency`` keys.
        shadowed_aml_values : dict, optional
            Shadow values forwarded unchanged to ``super()``.

        Returns
        -------
        tuple
            ``(all_results, fully_reconciled_aml_ids)``, identical in shape
            to the core's return value.
        """
        paid_amount = self.env.context.get(CONTEXT_KEY)
        move_id = self.env.context.get("move_id")
        line_id = self.env.context.get("line_id")

        if paid_amount is None or not move_id or not line_id:
            return super()._prepare_reconciliation_amls(
                values_list, shadowed_aml_values=shadowed_aml_values
            )

        target_indexes = sorted(
            (
                i
                for i, v in enumerate(values_list)
                if v["aml"].move_id.id == move_id and v["aml"].id != line_id
            ),
            key=lambda i: (
                values_list[i]["aml"].date_maturity or values_list[i]["aml"].date,
                values_list[i]["aml"].id,
            ),
        )

        remaining_amount = abs(paid_amount)
        capped_values_list = list(values_list)
        for i in target_indexes:
            values = dict(values_list[i])
            aml = values["aml"]
            currency = aml.currency_id
            original_currency_residual = values["amount_residual_currency"]
            sign = -1.0 if original_currency_residual < 0 else 1.0

            if float_is_zero(remaining_amount, precision_rounding=currency.rounding):
                capped_currency_residual = 0.0
            else:
                capped_currency_residual = currency.round(
                    sign * min(remaining_amount, abs(original_currency_residual))
                )
            remaining_amount -= abs(capped_currency_residual)

            if float_is_zero(original_currency_residual, precision_rounding=currency.rounding):
                ratio = 0.0
            else:
                ratio = capped_currency_residual / original_currency_residual

            values["amount_residual_currency"] = capped_currency_residual
            values["amount_residual"] = aml.company_currency_id.round(
                values["amount_residual"] * ratio
            )
            capped_values_list[i] = values

        return super()._prepare_reconciliation_amls(
            capped_values_list, shadowed_aml_values=shadowed_aml_values
        )
