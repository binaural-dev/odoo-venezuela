from odoo import fields, models

from odoo.addons.l10n_ve_stock_account.models.stock_picking import DRIVER_LICENSE_TYPES


class ResPartner(models.Model):
    _inherit = "res.partner"

    driver_license_type = fields.Selection(
        DRIVER_LICENSE_TYPES,
        string="Driver License Type",
        help="Copied to the dispatch guide when this contact is the driver of the "
        "vehicle selected from Fleet.",
    )
