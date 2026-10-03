from odoo.tools.sql import column_exists


def migrate(cr, version):
    """`stock.picking.is_donation` used to be a related field to
    `sale_id.is_donation` (not stored). It is now a stored field, so flag the
    pickings of donation sale orders, which were already donations before.

    Some customers load an integration module (`l10n_ve_inventory_book`)
    that redefines `is_donation` as a related field: in that case the column
    does not exist and there is nothing to migrate.
    """
    if not column_exists(cr, "stock_picking", "is_donation"):
        return
    cr.execute(
        """
        UPDATE stock_picking sp
           SET is_donation = TRUE
          FROM sale_order so
         WHERE sp.sale_id = so.id
           AND so.is_donation
           AND sp.is_donation IS NOT TRUE
        """
    )
