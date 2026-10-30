"""SQL helpers shared by the data migrations that repair foreign (USD) amounts.

Each step works on a temp table of repaired line ids (`lines_table`, a column `id`):
its partial reconciliations are rebuilt, `foreign_amount` refreshed and the foreign
residuals recomputed. Locked periods (`tax_lock_date` / `fiscalyear_lock_date`) are
never touched, and a partial is only changed when BOTH of its sides are unlocked.
"""
import logging

_logger = logging.getLogger(__name__)

LOCK = "m.date > %(tax_lock)s AND m.date > %(fy_lock)s"
# Same condition for the other side of a partial, joined as `m2`.
_LOCK_OTHER_SIDE = LOCK.replace("m.", "m2.")


def lock_params(company, fc_precision):
    return {
        'company_id': company.id,
        'prec': fc_precision,
        'tax_lock': company.tax_lock_date or '1900-01-01',
        'fy_lock': company.fiscalyear_lock_date or '1900-01-01',
    }


def rebuild_partials(cr, params, side, lines_table):
    """Give each partial of the repaired lines the line's foreign balance pro rata of
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
              JOIN {lines_table} n ON n.id = p.{line_col}
              JOIN account_move_line l ON l.id = p.{line_col}
              JOIN account_move m ON m.id = l.move_id
             WHERE m.company_id = %(company_id)s
               AND m.state = 'posted'
               AND {lock}
               AND NOT EXISTS (
                   SELECT 1
                     FROM account_move_line l2
                     JOIN account_move m2 ON m2.id = l2.move_id
                    WHERE l2.id IN (p.debit_move_id, p.credit_move_id)
                      AND NOT ({lock_other}))
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
    """.format(line_col=line_col, amount_col=amount_col, lines_table=lines_table,
               lock=LOCK, lock_other=_LOCK_OTHER_SIDE), params)
    _logger.info("  %s-side partials rebuilt: %s", side, cr.rowcount)


def refresh_partial_foreign_amount(cr, params, lines_table):
    cr.execute("""
        UPDATE account_partial_reconcile p
           SET foreign_amount = LEAST(COALESCE(p.debit_foreign_amount_currency, 0),
                                      COALESCE(p.credit_foreign_amount_currency, 0))
         WHERE (p.debit_move_id IN (SELECT id FROM {lines_table})
                OR p.credit_move_id IN (SELECT id FROM {lines_table}))
           AND NOT EXISTS (
               SELECT 1
                 FROM account_move_line l
                 JOIN account_move m ON m.id = l.move_id
                WHERE l.id IN (p.debit_move_id, p.credit_move_id)
                  AND NOT ({lock}))
           AND p.foreign_amount IS DISTINCT FROM LEAST(COALESCE(p.debit_foreign_amount_currency, 0),
                                                       COALESCE(p.credit_foreign_amount_currency, 0))
    """.format(lines_table=lines_table, lock=LOCK), params)
    _logger.info("  partial foreign_amount refreshed: %s", cr.rowcount)


def recompute_residuals(cr, params, lines_table, include_null_residual=False):
    """Same formula as AccountMoveLine._compute_foreign_amount_residual, for the
    repaired lines (plus, optionally, any line still holding a NULL residual)."""
    null_clause = (
        "OR l.foreign_amount_residual IS NULL OR l.foreign_amount_residual_currency IS NULL"
        if include_null_residual else ""
    )
    cr.execute("""
        WITH lines AS (
            SELECT l.id
              FROM account_move_line l
              JOIN account_move m ON m.id = l.move_id
             WHERE m.company_id = %(company_id)s
               AND {lock}
               AND (l.id IN (SELECT id FROM {lines_table}) {null_clause})
        ),
        t AS (
            SELECT x.id,
                   COALESCE((SELECT SUM(p.credit_foreign_amount_currency) FROM account_partial_reconcile p
                              WHERE p.debit_move_id = x.id), 0.0) AS credit_foreign,
                   COALESCE((SELECT SUM(p.debit_foreign_amount_currency) FROM account_partial_reconcile p
                              WHERE p.credit_move_id = x.id), 0.0) AS debit_foreign
              FROM lines x
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
    """.format(lines_table=lines_table, null_clause=null_clause, lock=LOCK), params)
    _logger.info("  foreign_amount_residual recomputed: %s", cr.rowcount)


def rebuild_repaired_lines(cr, params, lines_table, include_null_residual=False):
    """Partials, `foreign_amount` and residuals of the lines listed in `lines_table`."""
    rebuild_partials(cr, params, 'debit', lines_table)
    rebuild_partials(cr, params, 'credit', lines_table)
    refresh_partial_foreign_amount(cr, params, lines_table)
    recompute_residuals(cr, params, lines_table, include_null_residual)
