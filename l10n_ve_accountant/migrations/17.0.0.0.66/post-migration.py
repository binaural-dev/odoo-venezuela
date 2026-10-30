import logging

from odoo import api, SUPERUSER_ID
from odoo.addons.l10n_ve_accountant.utils.foreign_partials import (
    LOCK, lock_params, rebuild_repaired_lines,
)

_logger = logging.getLogger(__name__)

LINES_TABLE = 'l10n_ve_fb_null_lines'


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
        params = lock_params(company, company.currency_foreign_id.decimal_places)
        _logger.info("Repairing foreign_* NULLs for %s", company.name)
        _repair_null_lines(cr, params)
        rebuild_repaired_lines(cr, params, LINES_TABLE, include_null_residual=True)
        cr.execute("TRUNCATE l10n_ve_fb_null_lines")
