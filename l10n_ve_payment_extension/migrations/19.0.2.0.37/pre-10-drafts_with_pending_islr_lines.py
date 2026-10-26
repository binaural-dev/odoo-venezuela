"""Set generate_islr_retention on the drafts that in v17 were going to create an ISLR retention.

What: creates account_move.generate_islr_retention and sets it to True on draft invoices without an
    ISLR voucher that already have ISLR retention lines (with a payment concept or from an islr
    retention, the same domain as retention_islr_line_ids in v17).

Why: in v17, action_post created the ISLR retention when the invoice had those lines and no voucher.
    In v19 it only creates it if generate_islr_retention is set, a new field that starts as False.
    Posted invoices are not affected, since they already have their voucher. But a draft that in v17
    already had its ISLR lines would be posted in v19 without a retention. Among the v17 databases
    we have there is one case, in idv.

If it does not run: those drafts, when posted after the migration, do not create the ISLR retention
    and it has to be done by hand.

How to revert: untick the field on the invoice before posting it.

Task: https://binaural.odoo.com/odoo/action-1963/4199/action-345/82849
"""

from odoo.upgrade import util


def migrate(cr, version):
    if not version or not version.startswith("17."):
        return
    if not util.create_column(cr, "account_move", "generate_islr_retention", "boolean"):
        return
    if not util.table_exists(cr, "account_retention_line"):
        return

    cr.execute(
        """
        UPDATE account_move m
           SET generate_islr_retention = TRUE
         WHERE m.state = 'draft'
           AND m.islr_voucher_number IS NULL
           AND EXISTS (
                SELECT 1
                  FROM account_retention_line l
             LEFT JOIN account_retention r ON r.id = l.retention_id
                 WHERE l.move_id = m.id
                   AND (l.payment_concept_id IS NOT NULL OR r.type_retention = 'islr')
           )
        """
    )
    if cr.rowcount:
        util.add_to_migration_reports(
            f"Retentions: {cr.rowcount} draft invoices with v17 ISLR lines keep \"Generate ISLR "
            "retention\" set, so that posting them creates the retention as in v17.",
            category="Binaural · Accounting",
        )
