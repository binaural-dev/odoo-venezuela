"""Post-migration for l10n_ve_contact 19.0.1.5: drop res_partner.identity_document,
already backed up (where it diverged from vat) by pre-migrate.py.
"""

import logging

from psycopg2 import sql

_logger = logging.getLogger(__name__)


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
        "WHERE table_name = 'res_partner' AND column_name = 'identity_document'"
    )
    if not cr.fetchone():
        _logger.info("l10n_ve_contact post-migrate: identity_document does not exist, skipping")
        return

    views = _views_referencing_field(cr, "identity_document")
    if views:
        _logger.warning(
            "l10n_ve_contact post-migrate: SKIPPING drop of "
            "res_partner.identity_document -- %s view(s) still reference it "
            "in their arch (this field was commonly shown on the v17 partner "
            "form, so this is a likely hit) and would break. Views: %s. "
            "Fix/retire those views first; safe to re-run this migration "
            "afterward.", len(views), views,
        )
        return

    cr.execute(
        sql.SQL("ALTER TABLE res_partner DROP COLUMN {}").format(
            sql.Identifier("identity_document")
        )
    )
    _logger.info(
        "l10n_ve_contact post-migrate: dropped res_partner.identity_document "
        "(divergent values preserved in l10n_ve_contact_migration_v17_backup)"
    )
