import logging
import os

from odoo import api, SUPERUSER_ID
from odoo.addons.l10n_ve_accountant.utils.foreign_partials import (
    LOCK, lock_params, rebuild_repaired_lines,
)

_logger = logging.getLogger(__name__)

LINES_TABLE = 'l10n_ve_vb_lines'
# Same scope as 17.0.0.0.56: posted data is only rebuilt for companies whose foreign
# currency is USD (base VEF); a base-USD company is "draft only" there.
FOREIGN_CURRENCY = 'USD'


def _load_candidates(cr, params):
    """One pass over the company's posted vendor documents (outside locked periods).

    Per move: how many payment term (CxP) lines it has, the net USD of everything
    else (the CxP must hold its opposite) and the USD net of the whole entry.
    """
    cr.execute("""
        CREATE TEMP TABLE IF NOT EXISTS l10n_ve_vb_candidates (
            move_id integer PRIMARY KEY, name varchar, move_type varchar,
            pt_count integer, pt_id integer, other_fb numeric, total_fb numeric
        ) ON COMMIT DROP
    """)
    cr.execute("TRUNCATE l10n_ve_vb_candidates")
    cr.execute("""
        INSERT INTO l10n_ve_vb_candidates
        SELECT m.id, m.name, m.move_type,
               COUNT(*) FILTER (WHERE l.display_type = 'payment_term'),
               MIN(l.id) FILTER (WHERE l.display_type = 'payment_term'),
               SUM(l.foreign_balance) FILTER (WHERE l.display_type IS DISTINCT FROM 'payment_term'),
               SUM(l.foreign_balance)
          FROM account_move m
          JOIN account_move_line l ON l.move_id = m.id
         WHERE m.company_id = %(company_id)s
           AND m.state = 'posted'
           AND m.move_type IN ('in_invoice', 'in_refund')
           AND """ + LOCK + """
         GROUP BY m.id
    """, params)


def _report_manual_review(cr, params):
    """Moves this step cannot fix on its own: several payment term lines or a payment
    term line with the wrong sign. They are only listed."""
    cr.execute("""
        SELECT move_id, name, pt_count FROM l10n_ve_vb_candidates
         WHERE pt_count > 1 AND ABS(COALESCE(total_fb, 0)) >= 10 ^ -%(prec)s
    """, params)
    for move_id, name, count in cr.fetchall():
        _logger.warning("  REVIEW by hand: %s (id %s) has %s payment term lines and is unbalanced in USD",
                        name, move_id, count)
    cr.execute("""
        SELECT c.move_id, c.name, ROUND(-c.other_fb, %(prec)s), pt.foreign_balance
          FROM l10n_ve_vb_candidates c
          JOIN account_move_line pt ON pt.id = c.pt_id
         WHERE c.pt_count = 1
           AND ROUND(-c.other_fb, %(prec)s) <> 0
           AND ROUND(COALESCE(pt.foreign_balance, 0) + c.other_fb, %(prec)s) <> 0
           AND SIGN(-c.other_fb) <> CASE WHEN c.move_type = 'in_invoice' THEN -1 ELSE 1 END
    """, params)
    for move_id, name, expected, current in cr.fetchall():
        _logger.warning("  REVIEW by hand: %s (id %s) unexpected sign (expected %s, CxP %s)",
                        name, move_id, expected, current)


def _find_affected(cr, params):
    """Payment term lines whose USD amount is not the opposite of the rest of the entry.

    Their ids and target amount are kept in `l10n_ve_vb_lines` for the next steps.
    """
    cr.execute("""
        CREATE TEMP TABLE IF NOT EXISTS l10n_ve_vb_lines (
            id integer PRIMARY KEY, expected numeric
        ) ON COMMIT DROP
    """)
    cr.execute("TRUNCATE l10n_ve_vb_lines")
    cr.execute("""
        INSERT INTO l10n_ve_vb_lines (id, expected)
        SELECT c.pt_id, ROUND(-c.other_fb, %(prec)s)
          FROM l10n_ve_vb_candidates c
          JOIN account_move_line pt ON pt.id = c.pt_id
         WHERE c.pt_count = 1
           AND ROUND(-c.other_fb, %(prec)s) <> 0
           AND ROUND(COALESCE(pt.foreign_balance, 0) + c.other_fb, %(prec)s) <> 0
           AND SIGN(-c.other_fb) = CASE WHEN c.move_type = 'in_invoice' THEN -1 ELSE 1 END
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


def migrate(cr, version):
    """Equalise the payment term (CxP) USD amount of posted vendor bills (ticket 15694).

    Bills created before `_distribute_foreign_pt_residual` spread the rounding could
    have the CxP line at 0 USD, at a stale amount, or off by the per-line rounding gap
    against the product + tax lines. Each such CxP is set to the opposite of the rest
    of the entry and its reconciliations are rebuilt. Like 17.0.0.0.56, only companies
    whose foreign currency is USD are processed and locked periods are never touched;
    bills with several payment term lines or an unexpected sign are only logged for
    manual review. Set the env var DRY_RUN=1 to log the affected bills without
    changing anything (run it first in staging).
    """
    dry_run = bool(os.environ.get('DRY_RUN'))
    env = api.Environment(cr, SUPERUSER_ID, {})
    companies = env['res.company'].search([('currency_foreign_id', '!=', False)])
    for company in companies:
        fc = company.currency_foreign_id
        if fc.name.upper() != FOREIGN_CURRENCY or company.currency_id == fc:
            _logger.info("  %s: foreign=%s, base=%s, se omite (solo base VEF con USD)",
                         company.name, fc.name, company.currency_id.name)
            continue
        params = lock_params(company, fc.decimal_places)
        _logger.info("Vendor bill USD amounts for %s%s", company.name, " (DRY_RUN)" if dry_run else "")
        _load_candidates(cr, params)
        _report_manual_review(cr, params)
        if _find_affected(cr, params) and not dry_run:
            _fix_payment_terms(cr, params)
            rebuild_repaired_lines(cr, params, LINES_TABLE)
        cr.execute("TRUNCATE l10n_ve_vb_lines")
        cr.execute("TRUNCATE l10n_ve_vb_candidates")
