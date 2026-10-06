"""Carry the line currency of the v17 multi-currency invoices to its v19 field.

What: account.move.line_currency was a Selection (VES / USD, default VES) in v17; v19 uses
    line_currency_id, a Many2one to res.currency. For the multi-currency invoices this script creates
    the new column ahead of the ORM and fills it: VES -> the company currency when it is VES/VEF,
    otherwise the active VES/VEF currency; USD -> the USD currency. The original values are backed up
    in l10n_ve_invoice_digital_migration_v17_backup.

Why: v19 fills line_currency_id only when an invoice is created or edited
    (_apply_payment_driven_multi_currency, the pricelist onchange). A migrated multi-currency invoice
    would keep it empty, and its digitalization would not know whether the line prices go in
    bolivars or in dollars. Non multi-currency invoices are left empty, as v19 does: v17 sent them in
    VES regardless of the field.

If it does not run: the multi-currency invoices still to be digitalized lose the line currency
    chosen in v17.

How to revert: empty line_currency_id on the invoices of the backup table.

Task: https://binaural.odoo.com/odoo/action-1963/4199/action-345/82849
"""

from odoo.upgrade import util

BACKUP = "l10n_ve_invoice_digital_migration_v17_backup"


def migrate(cr, version):
    if not version or not version.startswith("17."):
        return
    if not util.column_exists(cr, "account_move", "line_currency"):
        return
    if not util.column_exists(cr, "account_move", "multi_currency_invoice"):
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
             SELECT 'account.move', id, 'line_currency', line_currency, %s
               FROM account_move
              WHERE multi_currency_invoice IS TRUE
                AND line_currency IS NOT NULL
        ON CONFLICT (model, res_id, field) DO NOTHING
        """,
        [version],
    )

    util.create_column(cr, "account_move", "line_currency_id", "int4")
    cr.execute(
        """
        WITH bolivar AS (
            SELECT id FROM res_currency WHERE name IN ('VES', 'VEF') ORDER BY active DESC, name = 'VES' DESC, id LIMIT 1
        ), dollar AS (
            SELECT id FROM res_currency WHERE name = 'USD'
        )
        UPDATE account_move am
           SET line_currency_id = CASE
                   WHEN am.line_currency = 'USD' THEN (SELECT id FROM dollar)
                   WHEN cur.name IN ('VES', 'VEF') THEN rc.currency_id
                   ELSE (SELECT id FROM bolivar)
               END
          FROM res_company rc
          JOIN res_currency cur ON cur.id = rc.currency_id
         WHERE rc.id = am.company_id
           AND am.multi_currency_invoice IS TRUE
           AND am.line_currency IN ('VES', 'USD')
           AND am.line_currency_id IS NULL
        """
    )
    if cr.rowcount:
        util.add_to_migration_reports(
            f"TFHKA: the line currency of {cr.rowcount} multi-currency invoices moved from the v17 "
            f"VES/USD selection to the v19 currency field. Original values in {BACKUP}.",
            category="Binaural · Digital Invoicing",
        )
