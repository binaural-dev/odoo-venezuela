from odoo.tools.sql import column_exists


def migrate(cr, version):
    """Rescue the donation pickings created with the previous design.

    Before this version the operation type made the donation: any picking
    without a sale order whose type has `is_donation_picking_type` was a
    donation. Now a picking is a donation only when its stored
    `is_donation` field is set, so mark those existing pickings. Pickings
    of donation sale orders are already handled by the migration of
    `l10n_ve_stock_account`. Idempotent.

    If the column does not exist (a customer module redefines `is_donation`
    as a related field) there is nothing to migrate.
    """
    if not column_exists(cr, "stock_picking", "is_donation"):
        return
    cr.execute(
        """
        UPDATE stock_picking sp
           SET is_donation = TRUE
          FROM stock_picking_type spt
         WHERE sp.picking_type_id = spt.id
           AND spt.is_donation_picking_type
           AND sp.sale_id IS NULL
           AND sp.is_donation IS NOT TRUE
        """
    )
