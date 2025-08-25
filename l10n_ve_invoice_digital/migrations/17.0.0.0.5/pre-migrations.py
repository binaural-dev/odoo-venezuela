# migrations/17.0.2.0.0/pre-migration.py
from odoo import tools


def migrate(cr, version):
    tools.sql.drop_view_if_exists(
        cr, "dummy"
    )
    cr.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'account_journal' AND column_name = 'payment_method_code'
    """
    )
    row = cr.fetchone()
    if row:
        cr.execute(
            """
            ALTER TABLE account_journal
            RENAME COLUMN payment_method_code TO payment_method_code_legacy
        """
        )
