import json
import logging

from odoo import api, fields, models, _
from odoo.osv import expression
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _name = "account.move"
    _inherit = ["account.move", "filter.partner.mixin"]

    correlative = fields.Char("Control Number", copy=False, help="Sequence control number")
    invoice_reception_date = fields.Date(
        "Reception Date", help="Indicates when the invoice was received by the client/company"
    )

    @api.onchange("invoice_line_ids")
    def _onchange_invoice_line_ids(self):
        """
        Limit the number of products that can be added to the invoice
        """
        if self.invoice_line_ids and self.move_type in ["out_invoice","out_refund"]:
            max_product_invoice = self.company_id.max_product_invoice
            if len(self.invoice_line_ids) > max_product_invoice:
                raise ValidationError(
                    _(
                        "You can not add more than %s products to the invoice."
                        % max_product_invoice
                    )
                )

    @api.depends("filter_partner")
    def _compute_partner_id_domain(self):
        for move in self:
            company_id = move.company_id.id
            extend_domain = [("type", "!=", "private"), ("company_id", "in", (False, company_id))]
            domain = move.get_partner_domain(extend=extend_domain)

            move.update({"partner_id_domain": json.dumps(domain)})

    def _post(self, soft=True):
        res = super()._post(soft)
        for move in res:
            if move.is_valid_to_sequence():
                move.correlative = move.get_sequence()

    @api.model
    def is_valid_to_sequence(self) -> bool:
        """Check if the invoice satisfy the conditions to
        associate a new sequence number.

        Returns
        -------
            True or False whether the invoice already has a
            sequence number or not.
        """

        return self.move_type in ["out_invoice", "out_refund"] and not self.correlative

    @api.model
    def get_sequence(self):
        """Allow the invoice to have both a generic sequence
        number or a specific one given certain conditions.

        Returns
        -------
            The next number from the sequence to be assigned.
        """

        self.ensure_one()
        sequence = self.env["ir.sequence"].sudo()
        correlative = sequence.search([("code", "=", "invoice.correlative")])

        return correlative.next_by_id(correlative.id)
