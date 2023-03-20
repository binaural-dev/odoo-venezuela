from odoo import api, fields, models, _
import logging
from lxml import etree

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    correlative = fields.Char("Control Number", copy=False, help="Sequence control number")
    invoice_reception_date = fields.Date(
        "Reception Date", help="Indicates when the invoice was received by the client/company"
    )

    def _post(self, soft=True):
        res = super()._post(soft)
        for move in res:
            if move.is_valid_to_sequence():
                move.correlative = move.get_sequence()

    @api.model
    def is_valid_to_sequence(self) -> bool:
        """ Check if the invoice satisfy the conditions to 
        associate a new sequence number.

        Returns
        -------
            True or False whether the invoice already has a 
            sequence number or not.
        """

        return self.move_type in ["out_invoice", "out_refund"] and not self.correlative

    @api.model
    def get_sequence(self):
        """ Allow the invoice to have both a generic sequence
        number or a specific one given certain conditions.

        Returns
        -------
            The next number from the sequence to be assigned.
        """

        self.ensure_one()
        sequence = self.env["ir.sequence"].sudo()
        correlative = sequence.search([("code", "=", "invoice.correlative")])

        return correlative.next_by_id(correlative.id)
