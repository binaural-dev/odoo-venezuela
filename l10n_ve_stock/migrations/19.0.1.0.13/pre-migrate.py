import logging

from odoo.tools.sql import table_exists

_logger = logging.getLogger(__name__)

LINE_TABLE = "stock_picking_alter_location_line"
# Session table read by post-migrate to leave the merge in each record's chatter.
MERGE_LOG_TABLE = "l10n_ve_stock_merged_alter_location_lines"


def merge_duplicated_alter_location_lines(cr):
    """Merge the lines that repeat a location within the same record.

    Runs before the UNIQUE(stock_alter_location_id, location_id) constraint
    is created. Keeps the line with the lowest id, gives it the sum of the
    group and deletes the rest. Summing keeps every total of the record as
    it was, because pick_quantity, total_alter_quantity and total_quantity
    already added the repeated lines up.

    Returns the merged groups.
    """
    cr.execute(
        f"""
        SELECT stock_alter_location_id,
               location_id,
               MIN(id) AS kept_id,
               ARRAY_AGG(id ORDER BY id) AS line_ids,
               ARRAY_AGG(available_qty ORDER BY id) AS quantities,
               SUM(COALESCE(available_qty, 0.0)) AS total_qty
          FROM {LINE_TABLE}
         WHERE stock_alter_location_id IS NOT NULL
           AND location_id IS NOT NULL
      GROUP BY stock_alter_location_id, location_id
        HAVING COUNT(*) > 1
        """
    )
    groups = cr.dictfetchall()
    if not groups:
        return groups

    cr.execute(
        f"""
        CREATE TEMP TABLE IF NOT EXISTS {MERGE_LOG_TABLE} (
            stock_alter_location_id INTEGER,
            location_id INTEGER,
            quantities NUMERIC[],
            total_qty NUMERIC
        )
        """
    )
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
            f"""
            UPDATE {LINE_TABLE}
               SET available_qty = %s,
                   write_date = NOW() AT TIME ZONE 'UTC'
             WHERE id = %s
            """,
            (group["total_qty"], group["kept_id"]),
        )
        removed_ids = [line_id for line_id in group["line_ids"] if line_id != group["kept_id"]]
        cr.execute(f"DELETE FROM {LINE_TABLE} WHERE id = ANY(%s)", (removed_ids,))
        # Deleting by SQL skips the ORM, which would drop the external ids.
        cr.execute(
            "DELETE FROM ir_model_data WHERE model = %s AND res_id = ANY(%s)",
            ("stock.picking.alter.location.line", removed_ids),
        )
        cr.execute(
            f"INSERT INTO {MERGE_LOG_TABLE} VALUES (%s, %s, %s, %s)",
            (
                group["stock_alter_location_id"],
                group["location_id"],
                group["quantities"],
                group["total_qty"],
            ),
        )

    _logger.info("Merged %s groups of duplicated alternate location lines", len(groups))
    return groups


def migrate(cr, version):
    if not version:
        return
    # The model arrived in 19.0.1.0.6, and pre-migrate runs before the ORM
    # creates its table.
    if not table_exists(cr, LINE_TABLE):
        return
    merge_duplicated_alter_location_lines(cr)
