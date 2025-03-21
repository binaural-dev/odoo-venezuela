from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    guide_number = fields.Char(related="picking_id.guide_number")
    picking_id = fields.Many2one("stock.picking", string="Picking")
    transfer_ids = fields.Many2many("stock.picking", string="Transfers")
    from_picking = fields.Boolean(string="From Picking", default=False)

    free_form_copy_number = fields.Integer(default=0)  # 0: not printed yet, 1: first print (original), 2 or more: copies

    def print_invoice_free_form(self):

        report = self.env.ref("l10n_ve_invoice.action_invoice_free_form_l10n_ve_invoice")

        self.free_form_copy_number = self.free_form_copy_number + 1

        return report.report_action(self)

