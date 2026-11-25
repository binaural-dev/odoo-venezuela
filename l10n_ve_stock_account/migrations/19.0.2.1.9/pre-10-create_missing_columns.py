"""Create this module's missing store=True columns and relation table, empty.

What: for every stored computed field this module declares that does not yet have its column
    (or, for allowed_reason_ids, its relation table), creates it empty. Never touches a field
    whose column already exists.

Why: when the ORM's own _auto_init finds a column missing, it queues env.add_to_compute for
    every row of the table itself, directly, before this module's model classes (and so
    StockPicking._l10n_ve_stock_account_protect_heavy_fields) even load. Any later cr.commit()
    unconditionally flushes everything still queued, not just what a chunk explicitly added, so
    that whole-table queue gets recomputed in one shot regardless of how carefully the chunked
    recompute scopes its own calls. Creating the column here, before _auto_init sees it
    missing, is what keeps it from queueing anything in the first place.

If it does not run: on a database where one of these columns is genuinely new, the first
    commit() inside _l10n_ve_stock_account_protect_heavy_fields's loop recomputes the whole
    table at once — the original crash, one call deeper.

How to revert: drop the columns/relation table this script created, if
    _l10n_ve_stock_account_protect_heavy_fields has not run yet; once it has, there is nothing
    to revert.

Task: <TICKET>
"""

from odoo.upgrade import util

# (table, column, pg_type) for every store=True scalar field this module declares.
COLUMNS = [
    ("stock_move", "qty_return", "numeric"),
    ("sale_order", "is_consignation", "bool"),
    ("stock_picking", "match_guide_dispatch_domain", "bool"),
    ("stock_picking", "is_dispatch_guide", "bool"),
    ("stock_picking", "is_transfer_between_warehouses", "bool"),
    ("stock_picking", "partner_required", "bool"),
    ("stock_picking", "is_consignment", "bool"),
    ("stock_picking", "type_of_return", "varchar"),
    ("stock_picking", "dispatch_guide_controls", "bool"),
    ("account_move", "guide_number", "varchar"),
    ("stock_move_line", "qty_invoiced", "numeric"),
    ("stock_move_line", "date_done", "timestamp"),
    ("stock_move_line", "guide_number", "varchar"),
]

# allowed_reason_ids on stock.picking: (relation table, column1, column2)
M2M_RELATION = "stock_picking_transfer_reason_rel"
M2M_COLUMN1 = "stock_picking_id"
M2M_COLUMN2 = "transfer_reason_id"


def migrate(cr, version):
    for table, column, pg_type in COLUMNS:
        if not util.column_exists(cr, table, column):
            util.create_column(cr, table, column, pg_type)

    if not util.table_exists(cr, M2M_RELATION):
        cr.execute(
            f"""
            CREATE TABLE {M2M_RELATION} (
                {M2M_COLUMN1} INTEGER NOT NULL REFERENCES stock_picking(id) ON DELETE CASCADE,
                {M2M_COLUMN2} INTEGER NOT NULL REFERENCES transfer_reason(id) ON DELETE CASCADE,
                PRIMARY KEY ({M2M_COLUMN1}, {M2M_COLUMN2})
            )
            """
        )
