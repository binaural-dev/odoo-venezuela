from . import models
from . import wizard

from odoo.tools import column_exists, create_column


def pre_init_hook(env):
    if not column_exists(env.cr, "account_payment", "is_igtf"):
        create_column(env.cr, "account_payment", "is_igtf", "boolean")
        env.cr.execute("""
            UPDATE account_payment
            SET is_igtf = false
        """)
    if not column_exists(env.cr, "account_payment", "is_igtf_on_foreign_exchange"):
        create_column(env.cr, "account_payment", "is_igtf_on_foreign_exchange", "boolean")
        env.cr.execute("""
            UPDATE account_payment
            SET is_igtf_on_foreign_exchange = false
        """)
    if not column_exists(env.cr, "account_payment", "igtf_percentage"):
        create_column(env.cr, "account_payment", "igtf_percentage", "float")
        env.cr.execute("""
            UPDATE account_payment
            SET igtf_percentage = 0.0
        """)
    if not column_exists(env.cr, "account_payment", "igtf_amount"):
        create_column(env.cr, "account_payment", "igtf_amount", "float")
        env.cr.execute("""
            UPDATE account_payment
            SET igtf_amount = 0.0
        """)
    if not column_exists(env.cr, "account_payment", "amount_with_igtf"):
        create_column(env.cr, "account_payment", "amount_with_igtf", "float")
        env.cr.execute("""
            UPDATE account_payment
            SET amount_with_igtf = 0.0
        """)
    if not column_exists(env.cr, "account_journal", "default_is_igtf_config"):
        create_column(env.cr, "account_journal", "default_is_igtf_config", "boolean")
        env.cr.execute("""
            UPDATE account_journal
            SET default_is_igtf_config = false
        """)
