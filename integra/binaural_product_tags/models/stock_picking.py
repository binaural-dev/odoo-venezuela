import logging
from odoo import _, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def print_package_qty_report(self):
        if not self.package_qty:
            raise ValidationError(
                _("To print the Package Labels, you must set the Package Quantity first.")
            )

        return self.env.ref("binaural_product_tags.package_quantity_report_action").report_action(
            self, data={"picking_id": self.id}
        )
