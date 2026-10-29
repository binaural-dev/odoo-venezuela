import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def _lock_params(company, fc_precision):
    return {
        'company_id': company.id,
        'prec': fc_precision,
        'tax_lock': company.tax_lock_date or '1900-01-01',
        'fy_lock': company.fiscalyear_lock_date or '1900-01-01',
    }


LOCK = "m.date > %(tax_lock)s AND m.date > %(fy_lock)s"


def _repair_null_lines(cr, params):
    """Set NULL foreign_debit/foreign_credit to 0 and rebuild foreign_balance.

    Affected line ids are kept in `l10n_ve_fb_null_lines` for the next steps.
    """
    cr.execute("""
        CREATE TEMP TABLE IF NOT EXISTS l10n_ve_fb_null_lines (id integer PRIMARY KEY) ON COMMIT DROP
    """)
    cr.execute("""
        WITH upd AS (
            UPDATE account_move_line l
               SET foreign_debit = COALESCE(l.foreign_debit, 0.0),
                   foreign_credit = COALESCE(l.foreign_credit, 0.0),
                   foreign_balance = ROUND(COALESCE(l.foreign_debit, 0.0)
                                           - COALESCE(l.foreign_credit, 0.0), %(prec)s)
              FROM account_move m
             WHERE m.id = l.move_id
               AND m.company_id = %(company_id)s
               AND """ + LOCK + """
               AND (l.foreign_debit IS NULL OR l.foreign_credit IS NULL OR l.foreign_balance IS NULL)
            RETURNING l.id
        )
        INSERT INTO l10n_ve_fb_null_lines (id) SELECT id FROM upd ON CONFLICT DO NOTHING
    """, params)
    _logger.info("  foreign_* NULL repaired on %s move lines", cr.rowcount)


def _rebuild_partials(cr, params, side):
    """Rebuild the foreign amounts of the partials of the repaired lines.

    17.0.0.0.56 `_rebuild_reconciled_partials` skipped every line whose
    foreign_balance was NULL, so their partials still hold stale amounts (often
    the counterpart's full balance). Keeping them, as .56 does, makes the last
    partial absorb a large negative remainder; instead each partial gets the
    line's foreign balance pro rata of its native `amount` over the line's
    native balance. When the line is fully settled in company currency the last
    partial absorbs the rounding so the foreign residual is exactly zero.

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
              JOIN l10n_ve_fb_null_lines n ON n.id = p.{line_col}
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
         WHERE (p.debit_move_id IN (SELECT id FROM l10n_ve_fb_null_lines)
                OR p.credit_move_id IN (SELECT id FROM l10n_ve_fb_null_lines))
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
    """Same formula as AccountMoveLine._compute_foreign_amount_residual, for the
    repaired lines plus any line still holding a NULL residual."""
    cr.execute("""
        WITH lines AS (
            SELECT l.id
              FROM account_move_line l
              JOIN account_move m ON m.id = l.move_id
             WHERE m.company_id = %(company_id)s
               AND """ + LOCK + """
               AND (l.id IN (SELECT id FROM l10n_ve_fb_null_lines)
                    OR l.foreign_amount_residual IS NULL
                    OR l.foreign_amount_residual_currency IS NULL)
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
    """, params)
    _logger.info("  foreign_amount_residual recomputed: %s", cr.rowcount)


def migrate(cr, version):
    """Repair foreign_* NULLs left by the 17.0.0.0.56 rounding migration (ticket 15691).

    That migration computed `foreign_balance` in SQL as
    `ROUND(foreign_debit) - ROUND(foreign_credit)`: whenever one side was NULL the
    whole balance became NULL, its `_rebuild_reconciled_partials` skipped those
    lines and `_recompute_residuals` copied the NULL into
    `foreign_amount_residual(_currency)`. Reports summing `foreign_balance`
    either crashed (aged/advance reports, ticket 15690) or under-reported USD.
    Locked periods are never touched.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    companies = env['res.company'].search([('currency_foreign_id', '!=', False)])
    for company in companies:
        params = _lock_params(company, company.currency_foreign_id.decimal_places)
        _logger.info("Repairing foreign_* NULLs for %s", company.name)
        _repair_null_lines(cr, params)
        _rebuild_partials(cr, params, 'debit')
        _rebuild_partials(cr, params, 'credit')
        _refresh_partial_foreign_amount(cr, params)
        _recompute_residuals(cr, params)
        cr.execute("TRUNCATE l10n_ve_fb_null_lines")
