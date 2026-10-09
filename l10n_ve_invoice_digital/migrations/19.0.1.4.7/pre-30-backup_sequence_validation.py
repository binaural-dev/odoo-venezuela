"""Back up and report the companies that had the TFHKA sequence validation turned off.

What: copies to l10n_ve_invoice_digital_migration_v17_backup the companies with
    sequence_validation_tfhka = False and adds a line to the migration report.

Why: in v17 the option (default on) compared the invoice number with the last number TFHKA had
    before digitalizing, and could be turned off. v19 removed it: the check always runs
    (account.move._tfhka_validate_sequence_before_queue) and a mismatch waits for a user to confirm
    it in a wizard. The ORM drops the column at the end of the -u all.

If it does not run: companies that skipped the check start getting sequence mismatch alerts without
    knowing why, and nothing records that they had it off.

How to revert: the backup changes nothing; the check can only be skipped again with a code change.

Task: https://binaural.odoo.com/odoo/action-1963/4199/action-345/82849
"""

from odoo.upgrade import util

BACKUP = "l10n_ve_invoice_digital_migration_v17_backup"


def migrate(cr, version):
    if not version or not version.startswith("17."):
        return
    if not util.column_exists(cr, "res_company", "sequence_validation_tfhka"):
        return

    cr.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {BACKUP} (
            id serial PRIMARY KEY,
            model varchar NOT NULL,
            res_id integer NOT NULL,
            field varchar NOT NULL,
            value text,
            source_version varchar,
            backed_up_at timestamp NOT NULL DEFAULT (now() at time zone 'UTC'),
            UNIQUE (model, res_id, field)
        )
        """
    )
    cr.execute(
        f"""
        INSERT INTO {BACKUP} (model, res_id, field, value, source_version)
             SELECT 'res.company', id, 'sequence_validation_tfhka', 'False', %s
               FROM res_company
              WHERE sequence_validation_tfhka IS FALSE
                AND invoice_digital_tfhka IS TRUE
        ON CONFLICT (model, res_id, field) DO NOTHING
        """,
        [version],
    )
    cr.execute(
        """
        SELECT name
          FROM res_company
         WHERE sequence_validation_tfhka IS FALSE
           AND invoice_digital_tfhka IS TRUE
      ORDER BY id
        """
    )
    companies = [name for (name,) in cr.fetchall()]
    if companies:
        util.add_to_migration_reports(
            "TFHKA: these companies had the sequence validation turned off in v17: %s. v19 always "
            "compares the invoice number with TFHKA's before digitalizing and asks to confirm a "
            "mismatch. The setting is backed up in %s." % (", ".join(companies), BACKUP),
            category="Binaural · Digital Invoicing",
        )
