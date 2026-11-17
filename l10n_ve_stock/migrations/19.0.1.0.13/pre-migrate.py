import logging

_logger = logging.getLogger(__name__)


def merge_duplicated_alter_location_lines(cr):
    """Merge the lines that repeat a location within the same record.

    Runs before the UNIQUE(stock_alter_location_id, location_id) constraint
    is created. Keeps the line with the lowest id, gives it the sum of the
    group and deletes the rest. Summing keeps every total of the record as
    it was, because pick_quantity, total_alter_quantity and total_quantity
    already added the repeated lines up.
    """
    cr.execute(
        """
        SELECT stock_alter_location_id,
               location_id,
               MIN(id) AS kept_id,
               ARRAY_AGG(id ORDER BY id) AS line_ids,
               ARRAY_AGG(available_qty ORDER BY id) AS quantities,
               SUM(COALESCE(available_qty, 0.0)) AS total_qty
          FROM stock_picking_alter_location_line
         WHERE stock_alter_location_id IS NOT NULL
           AND location_id IS NOT NULL
      GROUP BY stock_alter_location_id, location_id
        HAVING COUNT(*) > 1
        """
    )
    groups = cr.dictfetchall()
    if not groups:
        return

    for group in groups:
        _logger.info(
            "Merging duplicated alternate location lines: record %s, location %s, "
            "lines %s with quantities %s -> line %s with %s",
            group["stock_alter_location_id"],
            group["location_id"],
            group["line_ids"],
            group["quantities"],
            group["kept_id"],
            group["total_qty"],
        )
        cr.execute(
            "UPDATE stock_picking_alter_location_line SET available_qty = %s WHERE id = %s",
            (group["total_qty"], group["kept_id"]),
        )
        removed_ids = [line_id for line_id in group["line_ids"] if line_id != group["kept_id"]]
        cr.execute(
            "DELETE FROM stock_picking_alter_location_line WHERE id = ANY(%s)",
            (removed_ids,),
        )

    _logger.info("Merged %s groups of duplicated alternate location lines", len(groups))


def migrate(cr, version):
    if not version:
        return
    merge_duplicated_alter_location_lines(cr)
