from . import models
from . import report

from odoo.tools import column_exists, create_column


def pre_init_hook(env):
    if not column_exists(env.cr, "stock_warehouse", "subsidiary_id"):
        create_column(env.cr, "stock_warehouse", "subsidiary_id", "int4")
    if not column_exists(env.cr, "stock_valuation_layer", "subsidiary_id"):
        create_column(env.cr, "stock_valuation_layer", "subsidiary_id", "int4")
