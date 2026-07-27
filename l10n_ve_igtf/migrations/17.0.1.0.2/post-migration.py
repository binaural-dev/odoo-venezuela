import logging

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
        for col in columns:
            cr.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = %s AND column_name = %s",
                (table, col),
            )
            if cr.fetchone():
                # Drop FK constraint if present (e.g., payment_igtf_id references account_payment)
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
                        cr.execute('ALTER TABLE "%s" DROP CONSTRAINT "%s"' % (table, fk_name))
                        _logger.info("    Dropped FK %s on %s.%s", fk_name, table, col)

                cr.execute('ALTER TABLE "%s" DROP COLUMN "%s"' % (table, col))
                _logger.info("    Dropped column %s.%s", table, col)
            else:
                _logger.info("    Column %s.%s does not exist, skipping", table, col)

    _logger.info("Orphaned column cleanup complete")
