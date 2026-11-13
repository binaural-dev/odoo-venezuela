import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def _lock_expr(alias='m'):
    """WHERE expression keeping only moves strictly after the lock dates."""
    return ("%(alias)s.date > %(tax_lock)s AND %(alias)s.date > %(fy_lock)s"
            .replace('%(alias)s', alias))


def migrate(cr, version):
    """Force debit/credit_amount_currency = amount on account_partial_reconcile
    when the reconciliation currency is the company currency (ticket #16187).

    Before 17.0.0.0.65 (odoo-venezuela@adfc269d0), l10n_ve_rate's _convert()
    defaulted to round=False and its own round() override rarely delegated to
    the core rounding either, so 'amount' (company currency) was stored at raw
    precision while 'debit_amount_currency'/'credit_amount_currency' (the
    line's own currency) were rounded through a different path. When the line
    currency IS the company currency these two values must be identical by
    definition; the divergence is what left phantom cent residuals on
    otherwise fully paid invoices (amount_residual == 0 but
    amount_residual_currency != 0, so `reconciled` never flips to True).

    This only repairs same-currency reconciliations in unlocked periods; it
    does not touch the 'foreign' (alterno currency) fields already handled by
    17.0.0.0.56.
    """
    _logger.info(
        "Forcing debit/credit_amount_currency = amount on account_partial_reconcile "
        "when the reconciliation currency is the company currency"
    )

    env = api.Environment(cr, SUPERUSER_ID, {})
    companies = env['res.company'].search([])
    debit_lock = _lock_expr('dm')
    credit_lock = _lock_expr('cm')
    affected_line_ids = set()

    for company in companies:
        params = {
            'company_id': company.id,
            'currency_id': company.currency_id.id,
            'tax_lock': company.tax_lock_date or '1900-01-01',
            'fy_lock': company.fiscalyear_lock_date or '1900-01-01',
        }

        cr.execute("""
            UPDATE account_partial_reconcile p
            SET debit_amount_currency = p.amount
            FROM account_move_line dml, account_move dm
            WHERE p.debit_move_id = dml.id
              AND dml.move_id = dm.id
              AND dm.company_id = %(company_id)s
              AND p.debit_currency_id = %(currency_id)s
              AND p.debit_amount_currency IS DISTINCT FROM p.amount
              AND """ + debit_lock + """
            RETURNING p.debit_move_id, p.credit_move_id
        """, params)
        for debit_id, credit_id in cr.fetchall():
            affected_line_ids.add(debit_id)
            affected_line_ids.add(credit_id)

        cr.execute("""
            UPDATE account_partial_reconcile p
            SET credit_amount_currency = p.amount
            FROM account_move_line cml, account_move cm
            WHERE p.credit_move_id = cml.id
              AND cml.move_id = cm.id
              AND cm.company_id = %(company_id)s
              AND p.credit_currency_id = %(currency_id)s
              AND p.credit_amount_currency IS DISTINCT FROM p.amount
              AND """ + credit_lock + """
            RETURNING p.debit_move_id, p.credit_move_id
        """, params)
        for debit_id, credit_id in cr.fetchall():
            affected_line_ids.add(debit_id)
            affected_line_ids.add(credit_id)

    _logger.info("  account_partial_reconcile: %s lines affected in total", len(affected_line_ids))

    if not affected_line_ids:
        _logger.info("Same-currency reconciliation amount_currency fix complete (nothing to recompute)")
        return

    # amount_residual / amount_residual_currency / reconciled are stored fields on
    # account.move.line computed by summing these same account_partial_reconcile rows:
    # since we updated them via raw SQL, they don't recompute on their own. Force the
    # recompute through the ORM so the DB column itself stays consistent.
    lines = env["account.move.line"].browse(list(affected_line_ids)).exists()
    lines._compute_amount_residual()
    lines.flush_recordset(["amount_residual", "amount_residual_currency", "reconciled"])
    _logger.info("  account_move_line: %s lines recomputed (amount_residual/reconciled)", len(lines))

    moves = lines.move_id
    moves._compute_payment_state()
    moves.flush_recordset(["payment_state"])
    _logger.info("  account_move: %s invoices recomputed (payment_state)", len(moves))

    _logger.info("Same-currency reconciliation amount_currency fix complete")
