from datetime import datetime
import json
import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import format_date

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    invoice_reception_date = fields.Date(
        "Reception Date",
        help="Indicates when the invoice was received by the client/company",
        tracking=True,
    )
    correlative = fields.Char("Control Number", copy=False, help="Sequence control number")
    is_contingency = fields.Boolean(related="journal_id.is_contingency")

    @api.constrains("correlative", "journal_id.is_contingency")
    def _check_correlative(self):
        AccountMove = self.env["account.move"]
        is_series_invoicing_enabled = self.company_id.group_sales_invoicing_series
        for move in self:
            if not move.is_contingency:
                continue
            if not is_series_invoicing_enabled and not move.correlative:
                raise ValidationError(
                    _(
                        "Contingency journal's invoices should always have a correlative if series "
                        "invoicing is not enabled"
                    )
                )
            repeated_moves = AccountMove.search(
                [
                    ("is_contingency", "=", True),
                    ("id", "!=", move.id),
                    ("correlative", "!=", False),
                    ("correlative", "=", move.correlative),
                    ("journal_id", "=", move.journal_id.id),
                ],
                limit=1,
            )
            if repeated_moves:
                raise UserError(_("The correlative must be unique per journal when using a contingency journal"))

    def _post(self, soft=True):
        res = super()._post(soft)
        for move in res:
            if move.is_valid_to_sequence():
                move.correlative = move.get_sequence()
        return res

    @api.model
    def is_valid_to_sequence(self) -> bool:
        """
        Check if the invoice satisfies the conditions to associate a new sequence number to its
        correlative.

        Returns:
            True or False whether the invoice already has a sequence number or not.
        """
        journal_type = self.journal_id.type == "sale"
        is_contingency = self.journal_id.is_contingency
        is_series_invoicing_enabled = self.company_id.group_sales_invoicing_series
        is_valid = not self.correlative and journal_type and (not is_contingency or is_series_invoicing_enabled)

        return is_valid

    @api.model
    def get_sequence(self):
        """
        Allows the invoice to have both a generic sequence
        number or a specific one given certain conditions.

        Returns
        -------
            The next number from the sequence to be assigned.
        """

        self.ensure_one()
        is_series_invoicing_enabled = self.company_id.group_sales_invoicing_series
        sequence = self.env["ir.sequence"].sudo()
        correlative = None

        if is_series_invoicing_enabled:
            correlative = self.journal_id.series_correlative_sequence_id

            if not correlative:
                raise UserError(_("The sale's series sequence must be in the selected journal."))
            return correlative.next_by_id(correlative.id)

        correlative = sequence.search([("code", "=", "invoice.correlative"), ("company_id", "=", self.env.company.id)])
        if not correlative:
            correlative = sequence.create(
                {
                    "name": "Número de control",
                    "code": "invoice.correlative",
                    "padding": 5,
                }
            )
        return correlative.next_by_id(correlative.id)
