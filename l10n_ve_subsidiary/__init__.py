from . import models
from . import report
from . import wizard

from odoo.tools import column_exists, create_column

def pre_init_hook(env):
    if not column_exists(env.cr, "account_move", "account_analytic_id"):
        create_column(env.cr, "account_move", "account_analytic_id", "int4")
    if not column_exists(env.cr, "sale_order", "company_subsidiary"):
        create_column(env.cr, "sale_order", "subsidiary_id", "int4")
    if not column_exists(env.cr, "sale_order", "subsidiary_id"):
        create_column(env.cr, "sale_order", "subsidiary_id", "int4")


def post_init_hook(env):
    activate_series_invoicing(env)
    set_res_users_default_subsidiaries(env)


def set_res_users_default_subsidiaries(env):
    """
    Assigns the default subsidiary to the users that already exists.
    """
    ResUsers = env["res.users"]
    all_users = ResUsers.search([])
    for user in all_users:
        user._assign_default_required_subsidiary_to_user()


def activate_series_invoicing(env):
    """
    Ensure that the group_sales_invoicing_series configuration is activated when this
    module is installed.
    """
    ResConfigSettings = env["res.config.settings"]
    classified_fields = ResConfigSettings._get_classified_fields(
        ["group_sales_invoicing_series"]
    )

    with env.norecompute():
        for _, groups, implied_group in sorted(classified_fields["group"]):
            groups.sudo()._apply_group(implied_group)
