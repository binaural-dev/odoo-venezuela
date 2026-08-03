import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

MOVE_TYPES = (
    'out_invoice', 'out_refund',
    'in_invoice', 'in_refund',
    'out_receipt', 'in_receipt',
    'entry',
)


def _is_period_unlocked(move, company):
    """A move is touchable when it is strictly after the company lock dates."""
    if company.tax_lock_date and move.date <= company.tax_lock_date:
        return False
    if company.fiscalyear_lock_date and move.date <= company.fiscalyear_lock_date:
        return False
    return True


def _reconciled_move_ids(cr, company, state_filter=('posted',)):
    """IDs of moves whose reconcilable lines have any settlement.

    Single SQL pass: any line with ``reconciled``/``full_reconcile_id`` marks
    the whole move. Avoids ORM iteration over tens of thousands of posted
    moves during the migration.
    """
    cr.execute("""
        SELECT DISTINCT m.id
        FROM account_move m
        JOIN account_move_line l ON l.move_id = m.id
        WHERE m.company_id = %(company_id)s
          AND m.state IN %(states)s
          AND (l.reconciled OR l.full_reconcile_id IS NOT NULL)
    """, {
        'company_id': company.id,
        'states': state_filter,
    })
    return [row[0] for row in cr.fetchall()]


def _do_sql_rounding(cr, company, fc_id, precision, state_filter, excluded_move_ids=()):
    """Round foreign monetary fields via SQL, scoped to one company.

    - ``company_id`` filter keeps every company's lines from being rounded with
      the precision of another company in multi-company databases.
    - Locked/closed periods (``tax_lock_date`` / ``fiscalyear_lock_date``) are
      never touched.
    - ``excluded_move_ids`` (reconciled moves) are skipped so residuals and
      ``account_partial_reconcile`` stay consistent.
    """
    params = {
        'prec': precision,
        'prec_fc': precision,
        'fc_id': fc_id,
        'company_id': company.id,
        'states': state_filter,
        'excluded': list(excluded_move_ids),
        'move_types': MOVE_TYPES,
        'tax_lock': company.tax_lock_date or '1900-01-01',
        'fy_lock': company.fiscalyear_lock_date or '1900-01-01',
    }
    lock_filter = "m.date > %(tax_lock)s AND m.date > %(fy_lock)s"
    not_excluded = "NOT (m.id = ANY(%(excluded)s::bigint[]))"

    # account_move_line foreign_* fields
    cr.execute("""
        UPDATE account_move_line l
        SET foreign_price = ROUND(l.foreign_price, %(prec)s),
            foreign_subtotal = ROUND(l.foreign_subtotal, %(prec)s),
            foreign_price_total = ROUND(l.foreign_price_total, %(prec)s),
            foreign_debit = ROUND(l.foreign_debit, %(prec)s),
            foreign_credit = ROUND(l.foreign_credit, %(prec)s),
            foreign_balance = ROUND(l.foreign_debit, %(prec)s)
                            - ROUND(l.foreign_credit, %(prec)s),
            foreign_debit_adjustment = ROUND(l.foreign_debit_adjustment, %(prec)s),
            foreign_credit_adjustment = ROUND(l.foreign_credit_adjustment, %(prec)s),
            foreign_amount_residual = ROUND(l.foreign_amount_residual, %(prec)s),
            foreign_amount_residual_currency = ROUND(l.foreign_amount_residual_currency, %(prec)s)
        FROM account_move m
        WHERE l.move_id = m.id
          AND m.state IN %(states)s
          AND m.company_id = %(company_id)s
          AND """ + lock_filter + """
          AND """ + not_excluded + """
          AND (l.foreign_price IS NOT NULL OR l.foreign_debit IS NOT NULL
               OR l.foreign_credit IS NOT NULL)
          AND m.move_type IN %(move_types)s
    """, params)
    _logger.info("    SQL foreign_* lines: %s rows updated (state=%s)",
                 cr.rowcount, state_filter)

    # account_move foreign_total_billed
    cr.execute("""
        UPDATE account_move m
        SET foreign_total_billed = ROUND(foreign_total_billed, %(prec)s)
        WHERE m.company_id = %(company_id)s
          AND m.state IN %(states)s
          AND m.foreign_total_billed IS NOT NULL
          AND """ + lock_filter + """
          AND """ + not_excluded + """
          AND m.move_type IN %(move_types)s
    """, params)
    _logger.info("    SQL foreign_total_billed: %s rows updated", cr.rowcount)

    # amount_currency (uses move's own currency precision, not foreign)
    cr.execute("""
        UPDATE account_move_line l
        SET amount_currency = ROUND(l.amount_currency, c.decimal_places)
        FROM res_currency c, account_move m
        WHERE l.move_id = m.id
          AND m.currency_id = c.id
          AND l.amount_currency IS NOT NULL
          AND ROUND(l.amount_currency, c.decimal_places) != l.amount_currency
          AND m.state IN %(states)s
          AND m.company_id = %(company_id)s
          AND """ + lock_filter + """
          AND """ + not_excluded + """
          AND m.move_type IN %(move_types)s
    """, params)
    _logger.info("    SQL amount_currency: %s rows updated", cr.rowcount)

    # account_partial_reconcile
    cr.execute("""
        UPDATE account_partial_reconcile p
        SET foreign_amount = ROUND(p.foreign_amount, %(prec)s),
            debit_foreign_amount_currency = ROUND(p.debit_foreign_amount_currency, %(prec_fc)s),
            credit_foreign_amount_currency = ROUND(p.credit_foreign_amount_currency, %(prec_fc)s)
        FROM account_move_line dml, account_move dm
        WHERE p.debit_move_id = dml.id
          AND dml.move_id = dm.id
          AND dm.company_id = %(company_id)s
          AND dm.state IN %(states)s
          AND """ + lock_filter.replace('m.', 'dm.') + """
          AND """ + not_excluded.replace('m.', 'dm.') + """
          AND p.foreign_amount IS NOT NULL
    """, params)
    _logger.info("    SQL partial_reconcile: %s rows updated", cr.rowcount)


def _check_and_fix_balance(cr, company, state_filter, excluded_move_ids=(), tolerance=0.01):
    """Detect foreign debit/credit drift introduced by independent rounding and
    repair it by adjusting the line with the largest debit (or credit)."""
    cr.execute("""
        SELECT m.id, m.name,
               ROUND(SUM(l.foreign_debit) - SUM(l.foreign_credit), 2) AS delta
        FROM account_move_line l
        JOIN account_move m ON l.move_id = m.id
        WHERE m.state IN %(states)s
          AND m.company_id = %(company_id)s
          AND NOT (m.id = ANY(%(excluded)s::bigint[]))
        GROUP BY m.id, m.name
        HAVING ABS(SUM(l.foreign_debit) - SUM(l.foreign_credit)) > %(tolerance)s
    """, {
        'company_id': company.id,
        'states': state_filter,
        'excluded': list(excluded_move_ids),
        'tolerance': tolerance,
    })
    rows = cr.fetchall()
    for move_id, name, delta in rows:
        _logger.warning(
            "    Move %s (id=%s) drifted %.2f after rounding; repairing",
            name, move_id, delta,
        )
        if delta > 0:
            cr.execute("""
                UPDATE account_move_line l
                SET foreign_debit = ROUND(l.foreign_debit - %(delta)s, 2)
                WHERE l.id = (
                    SELECT ll.id FROM account_move_line ll
                    WHERE ll.move_id = %(move_id)s
                      AND ll.foreign_debit IS NOT NULL
                    ORDER BY ll.foreign_debit DESC NULLS LAST, ll.id
                    LIMIT 1
                )
            """, {'move_id': move_id, 'delta': delta})
        else:
            cr.execute("""
                UPDATE account_move_line l
                SET foreign_credit = ROUND(l.foreign_credit + %(delta)s, 2)
                WHERE l.id = (
                    SELECT ll.id FROM account_move_line ll
                    WHERE ll.move_id = %(move_id)s
                      AND ll.foreign_credit IS NOT NULL
                    ORDER BY ll.foreign_credit DESC NULLS LAST, ll.id
                    LIMIT 1
                )
            """, {'move_id': move_id, 'delta': delta})
        # keep foreign_balance consistent with the adjusted debit/credit
        cr.execute("""
            UPDATE account_move_line l
            SET foreign_balance = ROUND(l.foreign_debit - l.foreign_credit, 2)
            WHERE l.move_id = %(move_id)s
        """, {'move_id': move_id})
        _logger.info("    Repaired move %s (delta=%.2f)", name, delta)


def _lock_expr(alias='m'):
    """WHERE expression keeping only moves strictly after the lock dates."""
    return ("%(alias)s.date > %(tax_lock)s AND %(alias)s.date > %(fy_lock)s"
            .replace('%(alias)s', alias))


def _round_reconciled_lines(cr, company, fc_precision, move_ids):
    """Round foreign monetary fields of reconciled posted lines.

    The rework of 17.0.0.0.56 rounds only non-reconciled posted moves; the
    lines of reconciled moves keep balances with many decimals (e.g.
    -900.2536850000001) while their settlements hold rounded amounts. This
    rounds those lines too, so their balances agree with the rebuilt
    reconciliations at the foreign currency precision. Locked periods are
    never touched.
    """
    if not move_ids:
        _logger.info("    No reconciled lines to round")
        return

    params = {
        'prec': fc_precision,
        'move_ids': tuple(move_ids),
        'tax_lock': company.tax_lock_date or '1900-01-01',
        'fy_lock': company.fiscalyear_lock_date or '1900-01-01',
    }
    lock = _lock_expr('m')

    cr.execute("""
        UPDATE account_move_line l
        SET foreign_price = ROUND(l.foreign_price, %(prec)s),
            foreign_subtotal = ROUND(l.foreign_subtotal, %(prec)s),
            foreign_price_total = ROUND(l.foreign_price_total, %(prec)s),
            foreign_debit = ROUND(l.foreign_debit, %(prec)s),
            foreign_credit = ROUND(l.foreign_credit, %(prec)s),
            foreign_balance = ROUND(l.foreign_debit, %(prec)s)
                            - ROUND(l.foreign_credit, %(prec)s),
            foreign_debit_adjustment = ROUND(l.foreign_debit_adjustment, %(prec)s),
            foreign_credit_adjustment = ROUND(l.foreign_credit_adjustment, %(prec)s)
        FROM account_move m
        WHERE l.move_id = m.id
          AND m.id IN %(move_ids)s
          AND """ + lock + """
          AND (l.foreign_price IS NOT NULL OR l.foreign_debit IS NOT NULL
               OR l.foreign_credit IS NOT NULL)
    """, params)
    _logger.info("    SQL reconciled lines: %s rows updated", cr.rowcount)

    # amount_currency is rounded to the move's own currency precision
    cr.execute("""
        UPDATE account_move_line l
        SET amount_currency = ROUND(l.amount_currency, c.decimal_places)
        FROM res_currency c, account_move m
        WHERE l.move_id = m.id
          AND m.id IN %(move_ids)s
          AND m.currency_id = c.id
          AND l.amount_currency IS NOT NULL
          AND ROUND(l.amount_currency, c.decimal_places) != l.amount_currency
          AND """ + lock + """
    """, params)
    _logger.info("    SQL reconciled amount_currency: %s rows updated", cr.rowcount)


def _rebuild_reconciled_partials(cr, company, fc_precision):
    """Recompute the foreign amounts of the company's partial reconciliations.

    The residual formula (AccountMoveLine._compute_foreign_amount_residual) is:

        residual = foreign_balance
                   - SUM(credit_foreign_amount_currency)   # partials where the
                                                           # line is the debit side
                   + SUM(debit_foreign_amount_currency)    # partials where the
                                                           # line is the credit side

    so for a fully reconciled line the reconciliations must satisfy, per line:

        debit  side: SUM(credit_foreign_amount_currency) ==  foreign_balance(D)
        credit side: SUM(debit_foreign_amount_currency)  == -foreign_balance(C)

    i.e. credit_foreign_amount_currency is allocated by debit line and
    debit_foreign_amount_currency by credit line. Existing per-partial amounts
    are kept and rounded; missing ones (reconciliations created before the
    override existed) are derived from the line's foreign_balance proportionally
    to the native `amount` of each partial. The last partial of each side
    absorbs the rounding remainder so the invariant holds exactly. Locked
    periods are never rebuilt.
    """
    params = {
        'prec': fc_precision,
        'company_id': company.id,
        'tax_lock': company.tax_lock_date or '1900-01-01',
        'fy_lock': company.fiscalyear_lock_date or '1900-01-01',
    }
    lock = _lock_expr('m')

    # ---- debit side: credit_foreign_amount_currency allocated by debit_move_id ----
    cr.execute("""
        WITH debit_totals AS (
            SELECT p.debit_move_id AS line_id,
                   SUM(p.amount) AS total_amount,
                   ABS(l.foreign_balance) AS fb_abs
            FROM account_partial_reconcile p
            JOIN account_move_line l ON l.id = p.debit_move_id
            JOIN account_move m ON m.id = l.move_id
            WHERE m.company_id = %(company_id)s
              AND m.state = 'posted'
              AND """ + lock + """
              AND l.foreign_balance IS NOT NULL
            GROUP BY p.debit_move_id, ABS(l.foreign_balance)
        ),
        ranked AS (
            SELECT p.id,
                   dt.line_id,
                   dt.total_amount,
                   dt.fb_abs,
                   COALESCE(p.credit_foreign_amount_currency,
                            ROUND(dt.fb_abs * p.amount / NULLIF(dt.total_amount, 0), %(prec)s)) AS raw_share,
                   ROW_NUMBER() OVER (PARTITION BY p.debit_move_id
                                      ORDER BY p.credit_foreign_amount_currency DESC NULLS LAST,
                                               p.amount DESC, p.id) AS rn,
                   COUNT(*) OVER (PARTITION BY p.debit_move_id) AS cnt
            FROM account_partial_reconcile p
            JOIN debit_totals dt ON dt.line_id = p.debit_move_id
        ),
        target AS (
            SELECT r.*,
                   ROUND(r.fb_abs, %(prec)s) AS target_total
            FROM ranked r
        ),
        normalized AS (
            SELECT t.*,
                   COALESCE(SUM(t.raw_share) OVER (PARTITION BY t.line_id
                       ORDER BY t.rn ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS prev_sum
            FROM target t
        )
        UPDATE account_partial_reconcile p
        SET credit_foreign_amount_currency = CASE
                WHEN n.rn < n.cnt THEN ROUND(n.raw_share, %(prec)s)
                ELSE n.target_total - n.prev_sum
            END
        FROM normalized n
        WHERE p.id = n.id
          AND CASE
                WHEN n.rn < n.cnt THEN ROUND(n.raw_share, %(prec)s)
                ELSE n.target_total - n.prev_sum
              END IS DISTINCT FROM p.credit_foreign_amount_currency
    """, params)
    _logger.info("    SQL debit-side partials: %s rows updated", cr.rowcount)

    # ---- credit side: debit_foreign_amount_currency allocated by credit_move_id ----
    cr.execute("""
        WITH credit_totals AS (
            SELECT p.credit_move_id AS line_id,
                   SUM(p.amount) AS total_amount,
                   ABS(l.foreign_balance) AS fb_abs
            FROM account_partial_reconcile p
            JOIN account_move_line l ON l.id = p.credit_move_id
            JOIN account_move m ON m.id = l.move_id
            WHERE m.company_id = %(company_id)s
              AND m.state = 'posted'
              AND """ + lock + """
              AND l.foreign_balance IS NOT NULL
            GROUP BY p.credit_move_id, ABS(l.foreign_balance)
        ),
        ranked AS (
            SELECT p.id,
                   dt.line_id,
                   dt.total_amount,
                   dt.fb_abs,
                   COALESCE(p.debit_foreign_amount_currency,
                            ROUND(dt.fb_abs * p.amount / NULLIF(dt.total_amount, 0), %(prec)s)) AS raw_share,
                   ROW_NUMBER() OVER (PARTITION BY p.credit_move_id
                                      ORDER BY p.debit_foreign_amount_currency DESC NULLS LAST,
                                               p.amount DESC, p.id) AS rn,
                   COUNT(*) OVER (PARTITION BY p.credit_move_id) AS cnt
            FROM account_partial_reconcile p
            JOIN credit_totals dt ON dt.line_id = p.credit_move_id
        ),
        target AS (
            SELECT r.*,
                   ROUND(r.fb_abs, %(prec)s) AS target_total
            FROM ranked r
        ),
        normalized AS (
            SELECT t.*,
                   COALESCE(SUM(t.raw_share) OVER (PARTITION BY t.line_id
                       ORDER BY t.rn ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS prev_sum
            FROM target t
        )
        UPDATE account_partial_reconcile p
        SET debit_foreign_amount_currency = CASE
                WHEN n.rn < n.cnt THEN ROUND(n.raw_share, %(prec)s)
                ELSE n.target_total - n.prev_sum
            END
        FROM normalized n
        WHERE p.id = n.id
          AND CASE
                WHEN n.rn < n.cnt THEN ROUND(n.raw_share, %(prec)s)
                ELSE n.target_total - n.prev_sum
              END IS DISTINCT FROM p.debit_foreign_amount_currency
    """, params)
    _logger.info("    SQL credit-side partials: %s rows updated", cr.rowcount)

    # ---- foreign_amount = smallest reconciled amount of both sides ----
    # Only touch settlements where BOTH lines are in unlocked periods so a
    # settlement reaching into a locked period keeps its original value.
    cr.execute("""
        UPDATE account_partial_reconcile p
        SET foreign_amount = LEAST(
                COALESCE(p.debit_foreign_amount_currency, 0),
                COALESCE(p.credit_foreign_amount_currency, 0)
            )
        WHERE p.company_id = %(company_id)s
          AND NOT EXISTS (
              SELECT 1 FROM account_move_line dl
              JOIN account_move dm ON dm.id = dl.move_id
              WHERE dl.id = p.debit_move_id
                AND NOT (dm.date > %(tax_lock)s AND dm.date > %(fy_lock)s)
          )
          AND NOT EXISTS (
              SELECT 1 FROM account_move_line cl
              JOIN account_move cm ON cm.id = cl.move_id
              WHERE cl.id = p.credit_move_id
                AND NOT (cm.date > %(tax_lock)s AND cm.date > %(fy_lock)s)
          )
    """, params)
    _logger.info("    SQL foreign_amount: %s rows updated", cr.rowcount)


def _recompute_residuals(cr, company):
    """Recompute foreign_amount_residual with the same formula used by
    AccountMoveLine._compute_foreign_amount_residual, but in pure SQL.

    Recomputing through the ORM would call _synchronize_business_models /
    _synchronize_from_moves on every payment move, which can raise on legacy
    data (e.g. payment move lines with different partners). SQL avoids that.
    Lines in locked periods are never recomputed (their balance was not
    rounded either, so their original residual is kept).

    Formula (foreign currency):
        residual = foreign_balance
                  - SUM(credit_foreign_amount_currency) over partials
                      where this line is debit_move_id
                  + SUM(debit_foreign_amount_currency) over partials
                      where this line is credit_move_id
    """
    lock = _lock_expr('m')
    params = {
        'company_id': company.id,
        'tax_lock': company.tax_lock_date or '1900-01-01',
        'fy_lock': company.fiscalyear_lock_date or '1900-01-01',
    }
    cr.execute("""
        WITH matched AS (
            SELECT p.debit_move_id AS line_id,
                   SUM(p.credit_foreign_amount_currency) AS credit_foreign,
                   NULL::numeric AS debit_foreign
            FROM account_partial_reconcile p
            JOIN account_move_line l ON l.id = p.debit_move_id
            JOIN account_move m ON m.id = l.move_id
            WHERE m.company_id = %(company_id)s
              AND """ + lock + """
              AND p.credit_foreign_amount_currency IS NOT NULL
            GROUP BY p.debit_move_id
            UNION ALL
            SELECT p.credit_move_id AS line_id,
                   NULL::numeric AS credit_foreign,
                   SUM(p.debit_foreign_amount_currency) AS debit_foreign
            FROM account_partial_reconcile p
            JOIN account_move_line l ON l.id = p.credit_move_id
            JOIN account_move m ON m.id = l.move_id
            WHERE m.company_id = %(company_id)s
              AND """ + lock + """
              AND p.debit_foreign_amount_currency IS NOT NULL
            GROUP BY p.credit_move_id
        ),
        totals AS (
            SELECT line_id,
                   SUM(credit_foreign) AS credit_foreign,
                   SUM(debit_foreign) AS debit_foreign
            FROM matched
            GROUP BY line_id
        )
        UPDATE account_move_line l
        SET foreign_amount_residual = l.foreign_balance
                                    - COALESCE(t.credit_foreign, 0.0)
                                    + COALESCE(t.debit_foreign, 0.0),
            foreign_amount_residual_currency = l.foreign_balance
                                             - COALESCE(t.credit_foreign, 0.0)
                                             + COALESCE(t.debit_foreign, 0.0)
        FROM totals t, account_move m
        WHERE l.id = t.line_id
          AND m.id = l.move_id
          AND m.company_id = %(company_id)s
          AND """ + lock + """
          AND (
              l.foreign_amount_residual IS DISTINCT FROM
                  (l.foreign_balance - COALESCE(t.credit_foreign, 0.0)
                                    + COALESCE(t.debit_foreign, 0.0))
              OR l.foreign_amount_residual_currency IS DISTINCT FROM
                  (l.foreign_balance - COALESCE(t.credit_foreign, 0.0)
                                    + COALESCE(t.debit_foreign, 0.0))
          )
    """, params)
    _logger.info("    SQL residual recompute: %s rows updated", cr.rowcount)

    # Lines with no partials in foreign currency: mirror the ORM behaviour.
    # Reconcilable accounts keep their foreign_balance as residual; others are
    # set to 0 by the ORM and must stay 0.
    cr.execute("""
        UPDATE account_move_line l
        SET foreign_amount_residual = CASE
                WHEN a.reconcile OR a.account_type IN ('asset_cash', 'liability_credit_card')
                THEN l.foreign_balance ELSE 0.0 END,
            foreign_amount_residual_currency = CASE
                WHEN a.reconcile OR a.account_type IN ('asset_cash', 'liability_credit_card')
                THEN l.foreign_balance ELSE 0.0 END
        FROM account_move m, account_account a
        WHERE l.move_id = m.id
          AND l.account_id = a.id
          AND m.company_id = %(company_id)s
          AND """ + lock + """
          AND NOT EXISTS (
              SELECT 1 FROM account_partial_reconcile p
              WHERE p.debit_move_id = l.id OR p.credit_move_id = l.id
          )
          AND (
              l.foreign_amount_residual IS DISTINCT FROM
                  CASE WHEN a.reconcile OR a.account_type IN ('asset_cash', 'liability_credit_card')
                  THEN l.foreign_balance ELSE 0.0 END
              OR l.foreign_amount_residual_currency IS DISTINCT FROM
                  CASE WHEN a.reconcile OR a.account_type IN ('asset_cash', 'liability_credit_card')
                  THEN l.foreign_balance ELSE 0.0 END
          )
    """, params)
    _logger.info("    SQL residual no-partials: %s rows updated", cr.rowcount)


def _fix_draft_real_portion(move):
    """Trigger real_portion ORM chain for draft invoices only.

    Writes ``manually_set_rate`` so the real_portion distribution is recomputed
    on the (already rounded) foreign_* values without the rates being
    overwritten. Uses a savepoint so that if any ORM operation fails (e.g.
    missing columns from other modules), the transaction is not aborted and SQL
    can continue.
    """
    with move.env.cr.savepoint():
        move.write({
            'manually_set_rate': True,
            'foreign_inverse_rate': move.foreign_inverse_rate,
        })

        move._distribute_final_real_portion(move)
        move._compute_foreign_tax_balance(move)
        move._distribute_foreign_pt_residual(move)
        move._compute_foreign_total_billed()
        move.env.flush_all()


def migrate(cr, version):
    """Round foreign monetary values via SQL + ORM real_portion chain.

    For every foreign-currency company:
      - draft moves: the real_portion ORM chain plus a company/lock/exclusion
        aware SQL rounding, repairing any debit/credit drift introduced by
        independent rounding;
      - posted moves: same SQL rounding for the non-reconciled moves, then the
        reconciled lines are rounded and their partial reconciliations rebuilt
        and residuals recomputed, all respecting the company lock dates.
    """
    _logger.info("Rounding Monetary values via SQL + ORM real_portion chain")

    env = api.Environment(cr, SUPERUSER_ID, {})
    all_errors = []

    companies = env['res.company'].search([
        ('currency_foreign_id', '!=', False),
    ])
    _logger.info("Companies with foreign currency: %s", len(companies))

    USD_NAME = 'USD'
    VEF_NAMES = ('VEF', 'VES', 'VED')

    for company in companies:
        fc = company.currency_foreign_id
        if not fc:
            continue
        if not company.currency_id or company.currency_id == fc:
            continue

        fc_name = fc.name.upper()
        fc_precision = fc.decimal_places

        if fc_name == USD_NAME:
            log_tag = 'base=VEF (full: draft+posted)'
            process_posted = True
        elif fc_name in VEF_NAMES:
            log_tag = 'base=USD (draft only)'
            process_posted = False
        else:
            _logger.info(
                "  %s: foreign=%s no es USD ni VEF, se omite",
                company.name, fc_name,
            )
            continue

        _logger.info("  %s (base=%s, foreign=%s): %s",
                     company.name, company.currency_id.name, fc_name, log_tag)

        # ---- DRAFT real_portion chain (ORM, only for invoices) ----
        draft_domain = [
            ('company_id', '=', company.id),
            ('state', '=', 'draft'),
            ('move_type', 'in', MOVE_TYPES),
            '|',
            ('currency_id', '!=', company.currency_id.id),
            ('foreign_inverse_rate', '>', 0),
        ]
        draft_moves = env['account.move'].search(draft_domain)
        errors = []
        for move in draft_moves:
            if not _is_period_unlocked(move, company):
                continue
            try:
                _fix_draft_real_portion(move)
            except Exception as e:
                errors.append((move.name, str(e)))
                _logger.error("    Draft %s: ORM ERROR: %s", move.name, e)
        if draft_moves:
            _logger.info(
                "    Drafts processed: %s (marked manually_set_rate for the "
                "real_portion chain)", len(draft_moves),
            )
        all_errors.extend(errors)

        # ---- SQL rounding for draft (reliable) ----
        _logger.info("    Draft SQL rounding...")
        _do_sql_rounding(cr, company, fc.id, fc_precision, ('draft',))
        _check_and_fix_balance(cr, company, ('draft',))

        # ---- POSTED SQL rounding (only VEF base) ----
        reconciled_ids = _reconciled_move_ids(cr, company, ('posted',))
        if process_posted:
            posted_moves = env['account.move'].search([
                ('company_id', '=', company.id),
                ('state', '=', 'posted'),
                ('move_type', 'in', MOVE_TYPES),
            ])
            _logger.info(
                "    Posted moves (skipping %s reconciled)",
                len(reconciled_ids),
            )
            _do_sql_rounding(
                cr, company, fc.id, fc_precision, ('posted',),
                excluded_move_ids=reconciled_ids,
            )
            _check_and_fix_balance(
                cr, company, ('posted',), excluded_move_ids=reconciled_ids,
            )

        # ---- Reconciled lines + settlements (respecting lock dates) ----
        _logger.info("    Reconciled rounding pass (%s reconciled moves)...",
                     len(reconciled_ids))
        _round_reconciled_lines(cr, company, fc_precision, reconciled_ids)
        _rebuild_reconciled_partials(cr, company, fc_precision)
        _recompute_residuals(cr, company)

    if all_errors:
        raise RuntimeError(
            "Migration 17.0.0.0.56: %d draft move(s) failed the ORM "
            "real_portion chain: %s" % (len(all_errors), all_errors),
        )

    _logger.info("Monetary rounding migration complete")