from . import models
from . import wizard

from odoo.tools import column_exists, create_column


def pre_init_hook(cr):
    if not column_exists(cr, "account_payment", "is_igtf_on_foreign_exchange"):
        create_column(cr, "account_payment", "is_igtf_on_foreign_exchange", "boolean")
        cr.execute("""
            UPDATE account_payment
            SET is_igtf_on_foreign_exchange = false
        """)
    if not column_exists(cr, "account_payment", "igtf_percentage"):
        create_column(cr, "account_payment", "igtf_percentage", "float")
        cr.execute("""
            UPDATE account_payment
            SET igtf_percentage = 0.0
        """)
    if not column_exists(cr, "account_payment", "igtf_amount"):
        create_column(cr, "account_payment", "igtf_amount", "float")
        cr.execute("""
            UPDATE account_payment
            SET igtf_amount = 0.0
        """)
    if not column_exists(cr, "account_payment", "amount_with_igtf"):
        create_column(cr, "account_payment", "amount_with_igtf", "float")
        cr.execute("""
            UPDATE account_payment
            SET amount_with_igtf = 0.0
        """)
