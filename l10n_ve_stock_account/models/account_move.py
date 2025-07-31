from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    guide_number = fields.Char(compute='_compute_guide_number', string="Guide Number", store=True)
    transfer_ids = fields.Many2many("stock.picking", string="Transfers")
    picking_ids = fields.Many2many("stock.picking", column1='account_move_id', column2= 'stock_picking_id', relation='pickings_invoice_rel')
    from_picking = fields.Boolean(string="From Picking", default=False)

    # 0: not printed yet, 1: first print (original), 2 or more: copies
    free_form_copy_number = fields.Integer(default=0, copy=False)

    def print_invoice_free_form(self):

        report = self.env.ref(
            "l10n_ve_invoice.action_invoice_free_form_l10n_ve_invoice"
        )

        self.free_form_copy_number = self.free_form_copy_number + 1

        return report.report_action(self)

    @api.depends("picking_ids")
    def _compute_guide_number(self):
        for record in self:
            list_guide_number = [picking.guide_number for picking in record.picking_ids]
            record.guide_number = "/".join(list_guide_number)