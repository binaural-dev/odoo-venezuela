from . import models
from . import report
from . import wizard

from odoo import api, SUPERUSER_ID


def activate_series_invoicing(cr, registry):
    """
    Ensure that the group_sales_invoicing_series configuration is activated when this module is
    installed.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    ResConfigSettings = env["res.config.settings"]
    classified_fields = ResConfigSettings._get_classified_fields(["group_sales_invoicing_series"])

    with env.norecompute():
        for _, groups, implied_group in sorted(classified_fields["group"]):
            groups.sudo()._apply_group(implied_group)