import logging
from psycopg2 import sql

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info("Dropping orphaned columns from l10n_ve_igtf")

    orphan_columns = {
        "account_move": [
            "payment_igtf_id",
            "amount_to_pay_igtf",
            "amount_residual_igtf",
        ],
        "account_payment": [
            "amount_with_igtf",
            "amount_residual_from_payment",
        ],
    }

    for table, columns in orphan_columns.items():
        _logger.info("  Processing table: %s", table)
        tbl = sql.Identifier(table)
        for col in columns:
            cr.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = %s AND column_name = %s",
                (table, col),
            )
            if cr.fetchone():
                col_id = sql.Identifier(col)
                cr.execute(
                    "SELECT constraint_name FROM information_schema.table_constraints "
                    "WHERE table_name = %s AND constraint_type = 'FOREIGN KEY'",
                    (table,),
                )
                for fk in cr.fetchall():
                    fk_name = fk[0]
                    cr.execute(
                        "SELECT 1 FROM information_schema.constraint_column_usage "
                        "WHERE constraint_name = %s AND column_name = %s",
                        (fk_name, col),
                    )
                    if cr.fetchone():
                        fk_id = sql.Identifier(fk_name)
                        cr.execute(sql.SQL("ALTER TABLE {} DROP CONSTRAINT {}").format(tbl, fk_id))
                        _logger.info("    Dropped FK %s on %s.%s", fk_name, table, col)

                cr.execute(sql.SQL("ALTER TABLE {} DROP COLUMN {}").format(tbl, col_id))
                _logger.info("    Dropped column %s.%s", table, col)
            else:
                _logger.info("    Column %s.%s does not exist, skipping", table, col)

    _logger.info("Orphaned column cleanup complete")
