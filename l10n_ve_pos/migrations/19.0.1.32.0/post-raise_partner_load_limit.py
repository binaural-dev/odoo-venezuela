"""Raise the customers the PoS loads up front to 5000 on databases that already had the module.

What:
    Calls pos.config._l10n_ve_set_default_pos_partner_load_limit once: it sets
    point_of_sale.limited_customer_count to 5000 if it is missing, not a number or lower, and
    leaves a value of 5000 or more as it is.

Why:
    Odoo leaves the parameter at 100, and the PoS only loads that many customers. New databases
    get 5000 on install (data/ir_config_parameter_data.xml), but that file is noupdate, so it does
    not run on databases that already had the module. This script covers them, once.

If it does not run: those databases keep loading 100 customers until someone raises the parameter
    in Settings > Technical > System Parameters.

How to revert: set point_of_sale.limited_customer_count back to the previous value in the System
    Parameters.

Task: https://binaural.odoo.com/odoo/project.task/85635
"""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["pos.config"]._l10n_ve_set_default_pos_partner_load_limit()
