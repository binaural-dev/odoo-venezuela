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
        """Cap the invoice line's residual in ``values_list`` to the requested amount.

        Only active when both ``context[CONTEXT_KEY]`` and ``context['move_id']``/
        ``context['line_id']`` are present -- these are set together by
        ``account.move.js_assign_outstanding_line`` for the exact (invoice,
        outstanding line) pair being reconciled from the widget, so this
        never touches an unrelated reconciliation (e.g. cash-basis or
        exchange-difference moves) that happens to run under the same
        ambient context later in the same request.

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

        capped_values_list = []
        for values in values_list:
            aml = values["aml"]
            if aml.move_id.id == move_id and aml.id != line_id:
                values = dict(values)
                original_currency_residual = values["amount_residual_currency"]
                sign = -1.0 if original_currency_residual < 0 else 1.0
                capped_currency_residual = sign * min(abs(paid_amount), abs(original_currency_residual))

                if float_is_zero(original_currency_residual, precision_rounding=aml.currency_id.rounding):
                    ratio = 0.0
                else:
                    ratio = capped_currency_residual / original_currency_residual

                values["amount_residual_currency"] = capped_currency_residual
                values["amount_residual"] = values["amount_residual"] * ratio

            capped_values_list.append(values)

        return super()._prepare_reconciliation_amls(
            capped_values_list, shadowed_aml_values=shadowed_aml_values
        )
