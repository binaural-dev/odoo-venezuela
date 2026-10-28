"""Pre-migration for l10n_ve_contact: v17 -> v19.

res_partner.identity_document (Char) has no v19 field. Lower risk than
it first looks: v17's own _onchange_vat_() already auto-fills
identity_document from vat whenever identity_document is empty, so for
most partners the two values already coincide -- dropping
identity_document loses nothing there, `vat` already has the same text.

The only real risk is partners where identity_document DIFFERS from
vat (set before vat existed, or edited independently afterward). Only
those get backed up -- no point backing up rows where the value is a
redundant copy of a field that survives anyway.
"""

import logging

_logger = logging.getLogger(__name__)

BACKUP_TABLE = "l10n_ve_contact_migration_v17_backup"


def migrate(cr, version):
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'res_partner' AND column_name = 'identity_document'"
    )
    if not cr.fetchone():
        _logger.info("l10n_ve_contact pre-migrate: identity_document does not exist, skipping")
        return

    cr.execute(
        """
        SELECT id, identity_document, vat FROM res_partner
        WHERE identity_document IS NOT NULL
          AND btrim(identity_document) != ''
          AND COALESCE(btrim(vat), '') != btrim(identity_document)
        """
    )
    divergent = cr.fetchall()
    if not divergent:
        _logger.info(
            "l10n_ve_contact pre-migrate: every non-empty identity_document already "
            "matches vat (or vat is empty) -- nothing distinctive to back up"
        )
        return

    cr.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {BACKUP_TABLE} (
            id SERIAL PRIMARY KEY,
            source_table VARCHAR NOT NULL,
            source_column VARCHAR NOT NULL,
            record_id INTEGER NOT NULL,
            value_text TEXT,
            backed_up_at TIMESTAMP DEFAULT now()
        )
        """
    )
    cr.executemany(
        f"""
        INSERT INTO {BACKUP_TABLE} (source_table, source_column, record_id, value_text)
        VALUES ('res_partner', 'identity_document', %s, %s)
        """,
        [(rec_id, f"identity_document={doc!r}, vat={vat!r}") for rec_id, doc, vat in divergent],
    )
    _logger.warning(
        "l10n_ve_contact pre-migrate: %s partner(s) have identity_document "
        "genuinely different from vat -- backed up before the column is "
        "dropped, since v19 has no field to hold this distinct value: %s",
        len(divergent), [row[0] for row in divergent],
    )
