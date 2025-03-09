import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    default_document = fields.Selection(
        [
            ("dispatch_guide", "Dispatch Guide"),
            ("invoice", "Invoice"),
        ],
        string="Default Document",
        default="invoice",
        tracking=True,
        required=True,
        help="Default document for importing documents.",
    )

    def _get_main_partner(self):
        """
        Returns the main partner associated with this contact.

        If the current partner is a child (linked to a parent), it returns the parent partner.
        Otherwise, it returns itself as it is already the main entity.
        """
        if not self._ids:
            _logger.warning("No partner found in the recordset.")
            return self
        self.ensure_one()
        return self.parent_id if self.parent_id else self
