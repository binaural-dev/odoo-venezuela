"""Carry the line currency of the v17 multi-currency invoices to its v19 field.

What: account.move.line_currency was a Selection (VES / USD, default VES) in v17; v19 uses
    line_currency_id, a Many2one to res.currency. For the multi-currency invoices this script creates
    the new column ahead of the ORM and fills it: VES -> the company currency when it is VES/VEF,
    otherwise the company foreign currency when it is VES/VEF, otherwise the active VES/VEF currency;
    USD -> the USD currency. The original values are backed up in
    l10n_ve_invoice_digital_migration_v17_backup.

    It then reports the multi-currency invoices v19 would reject (_check_multi_currency_consistency)
    when someone edits their flag, line currency or pricelist: v17 let the flag be set freely, v19
    needs the pricelist currency (or, without a pricelist, the company foreign currency) to differ
    from the company currency, and the line currency to be one of the two. The ORM may fill the
    pricelist of the migrated invoices from the customer's when account_invoice_pricelist is
    installed during the update. Those invoices are left as they were issued in v17, not changed.

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
REPORT_IDS_LIMIT = 50


def _foreign_currency_column(cr):
    """l10n_ve_rate renames currency_foreign_id to foreign_currency_id earlier in the update."""
    for column in ("foreign_currency_id", "currency_foreign_id"):
        if util.column_exists(cr, "res_company", column):
            return column
    return None


def _report_rejected_by_v19(cr, foreign_col):
    """Multi-currency invoices whose flag or line currency v19's consistency check rejects."""
    pricelist_currency = "rc.%s" % foreign_col if foreign_col else "NULL::int4"
    pricelist_join = ""
    if util.column_exists(cr, "account_move", "pricelist_id"):
        pricelist_join = "LEFT JOIN product_pricelist pl ON pl.id = am.pricelist_id"
        pricelist_currency = "COALESCE(pl.currency_id, %s)" % pricelist_currency
    cr.execute(
        f"""
        SELECT am.id
          FROM account_move am
          JOIN res_company rc ON rc.id = am.company_id
          {pricelist_join}
         WHERE am.multi_currency_invoice IS TRUE
           AND am.move_type IN ('out_invoice', 'out_refund')
           AND (
                {pricelist_currency} IS NULL
                OR {pricelist_currency} = rc.currency_id
                OR (am.line_currency_id IS NOT NULL
                    AND am.line_currency_id NOT IN (rc.currency_id, {pricelist_currency}))
           )
      ORDER BY am.id
        """
    )
    ids = [row[0] for row in cr.fetchall()]
    if ids:
        shown = ids[:REPORT_IDS_LIMIT]
        more = " (and %s more)" % (len(ids) - len(shown)) if len(ids) > len(shown) else ""
        util.add_to_migration_reports(
            f"TFHKA: {len(ids)} migrated multi-currency invoices do not meet v19's rule: the "
            "pricelist currency (or the company foreign currency) must differ from the company "
            "currency, and the line currency must be one of the two. Editing their "
            "'Multi-Currency Invoice', line currency or pricelist will fail unless they have a "
            f"reconciled USD payment. They were left as issued in v17. account.move ids: {shown}{more}",
            category="Binaural · Digital Invoicing",
        )


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

    foreign_col = _foreign_currency_column(cr)
    # The company foreign currency when it is the bolivar, so the line currency stays within what v19
    # allows when a database has both VES and VEF.
    foreign_bolivar = (
        f"WHEN fcur.name IN ('VES', 'VEF') THEN rc.{foreign_col}" if foreign_col else ""
    )
    foreign_join = (
        f"LEFT JOIN res_currency fcur ON fcur.id = rc.{foreign_col}" if foreign_col else ""
    )
    util.create_column(cr, "account_move", "line_currency_id", "int4")
    cr.execute(
        f"""
        WITH bolivar AS (
            SELECT id FROM res_currency WHERE name IN ('VES', 'VEF') ORDER BY active DESC, name = 'VES' DESC, id LIMIT 1
        ), dollar AS (
            SELECT id FROM res_currency WHERE name = 'USD'
        )
        UPDATE account_move am
           SET line_currency_id = CASE
                   WHEN am.line_currency = 'USD' THEN (SELECT id FROM dollar)
                   WHEN cur.name IN ('VES', 'VEF') THEN rc.currency_id
                   {foreign_bolivar}
                   ELSE (SELECT id FROM bolivar)
               END
          FROM res_company rc
          JOIN res_currency cur ON cur.id = rc.currency_id
          {foreign_join}
         WHERE rc.id = am.company_id
           AND am.multi_currency_invoice IS TRUE
           AND am.line_currency IN ('VES', 'USD')
           AND am.line_currency_id IS NULL
        """
    )
    migrated = cr.rowcount
    _report_rejected_by_v19(cr, foreign_col)
    if migrated:
        util.add_to_migration_reports(
            f"TFHKA: the line currency of {migrated} multi-currency invoices moved from the v17 "
            f"VES/USD selection to the v19 currency field. Original values in {BACKUP}.",
            category="Binaural · Digital Invoicing",
        )
