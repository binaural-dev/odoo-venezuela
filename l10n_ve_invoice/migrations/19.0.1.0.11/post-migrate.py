"""Post-migration for l10n_ve_invoice 19.0.1.0.11.

Drops res_company.mandatory_contact_in_payable_or_receivable_accounting_accounts,
already backed up by pre-migrate.py, now that v19 declares no field for it.
"""

import logging

from psycopg2 import sql

_logger = logging.getLogger(__name__)

COLUMN = "mandatory_contact_in_payable_or_receivable_accounting_accounts"


def _views_referencing_field(cr, column):
    cr.execute(
        """
        SELECT id, name, model FROM ir_ui_view
        WHERE arch_db::text LIKE %s OR arch_db::text LIKE %s
        """,
        (f'%name="{column}"%', f"%name='{column}'%"),
    )
    return cr.fetchall()


def migrate(cr, version):
    cr.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'res_company' AND column_name = %s",
        (COLUMN,),
    )
    if not cr.fetchone():
        _logger.info("l10n_ve_invoice post-migrate: %s does not exist, skipping", COLUMN)
        return

    views = _views_referencing_field(cr, COLUMN)
    if views:
        _logger.warning(
            "l10n_ve_invoice post-migrate: SKIPPING drop of res_company.%s -- "
            "%s view(s) still reference it in their arch and would break. "
            "Views: %s. Fix/retire those views first; safe to re-run this "
            "migration afterward.", COLUMN, len(views), views,
        )
        return

    cr.execute(
        sql.SQL("ALTER TABLE res_company DROP COLUMN {}").format(sql.Identifier(COLUMN))
    )
    _logger.info(
        "l10n_ve_invoice post-migrate: dropped res_company.%s "
        "(values preserved in l10n_ve_invoice_migration_v17_backup)", COLUMN,
    )
