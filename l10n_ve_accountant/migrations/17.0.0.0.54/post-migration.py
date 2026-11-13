import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info(
        "Forcing debit/credit_amount_currency = amount on account_partial_reconcile "
        "when the reconciliation currency is the company currency"
    )

    # Debit side: when debit_currency_id is the company currency, the amount in that
    # currency (debit_amount_currency) must be identical to 'amount' (already in
    # company currency). l10n_ve_rate's unrounded _convert() let these two values
    # diverge: 'amount' was stored at raw precision while 'debit_amount_currency' was
    # rounded through a different path, leaving phantom cent residuals (ticket #16187).
    cr.execute("""
        UPDATE account_partial_reconcile p
        SET debit_amount_currency = p.amount
        FROM account_move_line dml, account_move dm, res_company comp
        WHERE p.debit_move_id = dml.id
          AND dml.move_id = dm.id
          AND dm.company_id = comp.id
          AND p.debit_currency_id = comp.currency_id
          AND p.debit_amount_currency IS DISTINCT FROM p.amount
        RETURNING p.debit_move_id, p.credit_move_id
    """)
    affected_line_ids = {row[0] for row in cr.fetchall()}
    _logger.info("  account_partial_reconcile.debit_amount_currency: %s rows updated", len(affected_line_ids))

    # Credit side: same case, when credit_currency_id is the company currency.
    cr.execute("""
        UPDATE account_partial_reconcile p
        SET credit_amount_currency = p.amount
        FROM account_move_line cml, account_move cm, res_company comp
        WHERE p.credit_move_id = cml.id
          AND cml.move_id = cm.id
          AND cm.company_id = comp.id
          AND p.credit_currency_id = comp.currency_id
          AND p.credit_amount_currency IS DISTINCT FROM p.amount
        RETURNING p.debit_move_id, p.credit_move_id
    """)
    for debit_id, credit_id in cr.fetchall():
        affected_line_ids.add(debit_id)
        affected_line_ids.add(credit_id)
    _logger.info("  account_partial_reconcile.credit_amount_currency: %s lines affected in total", len(affected_line_ids))

    if not affected_line_ids:
        _logger.info("Same-currency reconciliation amount_currency fix complete (nothing to recompute)")
        return

    # amount_residual / amount_residual_currency / reconciled are stored fields on
    # account.move.line computed by summing these same account_partial_reconcile rows:
    # since we updated them via raw SQL, they don't recompute on their own. Force the
    # recompute through the ORM so the DB column itself stays consistent.
    env = api.Environment(cr, SUPERUSER_ID, {})
    lines = env["account.move.line"].browse(list(affected_line_ids)).exists()
    lines._compute_amount_residual()
    lines.flush_recordset(["amount_residual", "amount_residual_currency", "reconciled"])
    _logger.info("  account_move_line: %s lines recomputed (amount_residual/reconciled)", len(lines))

    moves = lines.move_id
    moves._compute_payment_state()
    moves.flush_recordset(["payment_state"])
    _logger.info("  account_move: %s invoices recomputed (payment_state)", len(moves))

    _logger.info("Same-currency reconciliation amount_currency fix complete")
