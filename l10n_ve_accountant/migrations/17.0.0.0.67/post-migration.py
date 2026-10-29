import logging
import os

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

LOCK = "m.date > %(tax_lock)s AND m.date > %(fy_lock)s"
# Net USD (foreign_balance) the payment term line of a vendor document must hold: the
# opposite of everything else on the entry.
EXPECTED = """
    SELECT pt.id AS pt_id, pt.move_id,
           ROUND(-SUM(o.foreign_balance), %(prec)s) AS expected
      FROM account_move_line pt
      JOIN account_move m ON m.id = pt.move_id
      JOIN account_move_line o ON o.move_id = pt.move_id AND o.display_type IS DISTINCT FROM 'payment_term'
     WHERE pt.display_type = 'payment_term'
       AND m.company_id = %(company_id)s
       AND m.state = 'posted'
       AND m.move_type IN ('in_invoice', 'in_refund')
       AND """ + LOCK + """
       AND (SELECT COUNT(*) FROM account_move_line x
             WHERE x.move_id = m.id AND x.display_type = 'payment_term') = 1
     GROUP BY pt.id, pt.move_id
"""


def _lock_params(company, fc_precision):
    return {
        'company_id': company.id,
        'prec': fc_precision,
        'tax_lock': company.tax_lock_date or '1900-01-01',
        'fy_lock': company.fiscalyear_lock_date or '1900-01-01',
    }


def _report_manual_review(cr, params):
    """Moves this step cannot fix on its own: several payment term lines or a payment
    term line with the wrong sign. They are only listed."""
    cr.execute("""
        SELECT m.id, m.name,
               (SELECT COUNT(*) FROM account_move_line x
                 WHERE x.move_id = m.id AND x.display_type = 'payment_term') AS pt_count
          FROM account_move m
         WHERE m.company_id = %(company_id)s
           AND m.state = 'posted'
           AND m.move_type IN ('in_invoice', 'in_refund')
           AND """ + LOCK + """
           AND (SELECT COUNT(*) FROM account_move_line x
                 WHERE x.move_id = m.id AND x.display_type = 'payment_term') > 1
           AND ABS((SELECT COALESCE(SUM(x.foreign_balance), 0) FROM account_move_line x
                     WHERE x.move_id = m.id)) >= 10 ^ -%(prec)s
    """, params)
    for move_id, name, count in cr.fetchall():
        _logger.warning("  REVIEW by hand: %s (id %s) has %s payment term lines and is unbalanced in USD",
                        name, move_id, count)
    cr.execute("""
        WITH e AS (""" + EXPECTED + """)
        SELECT m.id, m.name, e.expected, pt.foreign_balance
          FROM e
          JOIN account_move_line pt ON pt.id = e.pt_id
          JOIN account_move m ON m.id = e.move_id
         WHERE ROUND(COALESCE(pt.foreign_balance, 0) - e.expected, %(prec)s) <> 0
           AND e.expected <> 0
           AND SIGN(e.expected) <> CASE WHEN m.move_type = 'in_invoice' THEN -1 ELSE 1 END
    """, params)
    for move_id, name, expected, current in cr.fetchall():
        _logger.warning("  REVIEW by hand: %s (id %s) unexpected sign (expected %s, CxP %s)",
                        name, move_id, expected, current)


def _find_affected(cr, params):
    """Payment term lines whose USD amount is not the opposite of the rest of the entry.

    Their ids are kept in `l10n_ve_vb_lines` for the next steps.
    """
    cr.execute("""
        CREATE TEMP TABLE IF NOT EXISTS l10n_ve_vb_lines (
            id integer PRIMARY KEY, expected numeric
        ) ON COMMIT DROP
    """)
    cr.execute("""
        INSERT INTO l10n_ve_vb_lines (id, expected)
        SELECT e.pt_id, e.expected
          FROM (""" + EXPECTED + """) e
          JOIN account_move_line pt ON pt.id = e.pt_id
          JOIN account_move m ON m.id = e.move_id
         WHERE ROUND(COALESCE(pt.foreign_balance, 0) - e.expected, %(prec)s) <> 0
           AND e.expected <> 0
           AND SIGN(e.expected) = CASE WHEN m.move_type = 'in_invoice' THEN -1 ELSE 1 END
        ON CONFLICT DO NOTHING
    """, params)
    cr.execute("SELECT COUNT(*) FROM l10n_ve_vb_lines")
    count = cr.fetchone()[0]
    _logger.info("  vendor documents with a wrong payment term USD amount: %s", count)
    return count


def _fix_payment_terms(cr, params):
    cr.execute("""
        UPDATE account_move_line l
           SET foreign_debit = GREATEST(t.expected, 0),
               foreign_credit = GREATEST(-t.expected, 0),
               foreign_balance = t.expected
          FROM l10n_ve_vb_lines t
         WHERE l.id = t.id
    """, params)
    _logger.info("  payment term lines fixed: %s", cr.rowcount)


def _rebuild_partials(cr, params, side):
    """Give each partial of the fixed lines the line's foreign balance pro rata of
    its native `amount`; the last one absorbs the rounding when the line is settled.

    side='debit': credit_foreign_amount_currency allocated by debit_move_id.
    side='credit': debit_foreign_amount_currency allocated by credit_move_id.
    """
    line_col = 'debit_move_id' if side == 'debit' else 'credit_move_id'
    amount_col = 'credit_foreign_amount_currency' if side == 'debit' else 'debit_foreign_amount_currency'
    cr.execute("""
        WITH totals AS (
            SELECT p.{line_col} AS line_id,
                   SUM(p.amount) AS total_amount,
                   ABS(l.foreign_balance) AS fb_abs,
                   ABS(l.balance) AS balance_abs,
                   l.amount_residual = 0 AS settled
              FROM account_partial_reconcile p
              JOIN l10n_ve_vb_lines n ON n.id = p.{line_col}
              JOIN account_move_line l ON l.id = p.{line_col}
              JOIN account_move m ON m.id = l.move_id
             WHERE m.company_id = %(company_id)s
               AND m.state = 'posted'
               AND """.format(line_col=line_col) + LOCK + """
             GROUP BY p.{line_col}, ABS(l.foreign_balance), ABS(l.balance), l.amount_residual
        ),
        ranked AS (
            SELECT p.id, t.line_id, t.fb_abs, t.settled, t.total_amount, t.balance_abs,
                   ROUND(t.fb_abs * p.amount / NULLIF(t.balance_abs, 0), %(prec)s) AS raw_share,
                   ROW_NUMBER() OVER (PARTITION BY p.{line_col} ORDER BY p.amount, p.id) AS rn,
                   COUNT(*) OVER (PARTITION BY p.{line_col}) AS cnt
              FROM account_partial_reconcile p
              JOIN totals t ON t.line_id = p.{line_col}
             WHERE t.balance_abs > 0
        ),
        normalized AS (
            SELECT r.*,
                   CASE WHEN r.settled THEN ROUND(r.fb_abs, %(prec)s)
                        ELSE ROUND(r.fb_abs * r.total_amount / r.balance_abs, %(prec)s) END AS target_total,
                   COALESCE(SUM(r.raw_share) OVER (PARTITION BY r.line_id ORDER BY r.rn
                            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS prev_sum
              FROM ranked r
        )
        UPDATE account_partial_reconcile p
           SET {amount_col} = CASE WHEN n.rn < n.cnt THEN ROUND(n.raw_share, %(prec)s)
                                   ELSE n.target_total - n.prev_sum END
          FROM normalized n
         WHERE p.id = n.id
           AND (CASE WHEN n.rn < n.cnt THEN ROUND(n.raw_share, %(prec)s)
                     ELSE n.target_total - n.prev_sum END) IS DISTINCT FROM p.{amount_col}
    """.format(line_col=line_col, amount_col=amount_col), params)
    _logger.info("  %s-side partials rebuilt: %s", side, cr.rowcount)


def _refresh_partial_foreign_amount(cr, params):
    cr.execute("""
        UPDATE account_partial_reconcile p
           SET foreign_amount = LEAST(COALESCE(p.debit_foreign_amount_currency, 0),
                                      COALESCE(p.credit_foreign_amount_currency, 0))
         WHERE (p.debit_move_id IN (SELECT id FROM l10n_ve_vb_lines)
                OR p.credit_move_id IN (SELECT id FROM l10n_ve_vb_lines))
           AND NOT EXISTS (
               SELECT 1
                 FROM account_move_line l
                 JOIN account_move m ON m.id = l.move_id
                WHERE l.id IN (p.debit_move_id, p.credit_move_id)
                  AND NOT (""" + LOCK + """))
           AND p.foreign_amount IS DISTINCT FROM LEAST(COALESCE(p.debit_foreign_amount_currency, 0),
                                                       COALESCE(p.credit_foreign_amount_currency, 0))
    """, params)
    _logger.info("  partial foreign_amount refreshed: %s", cr.rowcount)


def _recompute_residuals(cr, params):
    """Same formula as AccountMoveLine._compute_foreign_amount_residual, for the fixed lines."""
    cr.execute("""
        WITH t AS (
            SELECT x.id,
                   COALESCE((SELECT SUM(p.credit_foreign_amount_currency) FROM account_partial_reconcile p
                              WHERE p.debit_move_id = x.id), 0.0) AS credit_foreign,
                   COALESCE((SELECT SUM(p.debit_foreign_amount_currency) FROM account_partial_reconcile p
                              WHERE p.credit_move_id = x.id), 0.0) AS debit_foreign
              FROM l10n_ve_vb_lines x
        )
        UPDATE account_move_line l
           SET foreign_amount_residual = CASE
                   WHEN a.reconcile OR a.account_type IN ('asset_cash', 'liability_credit_card')
                   THEN ROUND(l.foreign_balance - t.credit_foreign + t.debit_foreign, %(prec)s) ELSE 0.0 END,
               foreign_amount_residual_currency = CASE
                   WHEN a.reconcile OR a.account_type IN ('asset_cash', 'liability_credit_card')
                   THEN ROUND(l.foreign_balance - t.credit_foreign + t.debit_foreign, %(prec)s) ELSE 0.0 END
          FROM t, account_account a
         WHERE t.id = l.id
           AND a.id = l.account_id
    """, params)
    _logger.info("  foreign_amount_residual recomputed: %s", cr.rowcount)


def migrate(cr, version):
    """Equalise the payment term (CxP) USD amount of posted vendor bills (ticket 15694).

    Bills created before `_distribute_foreign_pt_residual` spread the rounding could
    have the CxP line at 0 USD, at a stale amount, or off by the per-line rounding gap
    against the product + tax lines. Each such CxP is set to the opposite of the rest
    of the entry and its reconciliations are rebuilt. Locked periods are never
    touched; bills with several payment term lines or an unexpected sign are only
    logged for manual review. Set the env var DRY_RUN=1 to log the affected bills
    without changing anything (run it first in staging).
    """
    dry_run = bool(os.environ.get('DRY_RUN'))
    env = api.Environment(cr, SUPERUSER_ID, {})
    companies = env['res.company'].search([('currency_foreign_id', '!=', False)])
    for company in companies:
        fc = company.currency_foreign_id
        if not company.currency_id or company.currency_id == fc:
            continue
        params = _lock_params(company, fc.decimal_places)
        _logger.info("Vendor bill USD amounts for %s%s", company.name, " (DRY_RUN)" if dry_run else "")
        _report_manual_review(cr, params)
        if not _find_affected(cr, params) or dry_run:
            cr.execute("TRUNCATE l10n_ve_vb_lines")
            continue
        _fix_payment_terms(cr, params)
        _rebuild_partials(cr, params, 'debit')
        _rebuild_partials(cr, params, 'credit')
        _refresh_partial_foreign_amount(cr, params)
        _recompute_residuals(cr, params)
        cr.execute("TRUNCATE l10n_ve_vb_lines")
