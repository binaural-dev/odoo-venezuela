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

    is_donation = fields.Boolean(string="Is Donation", tracking=True)

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

    def print_donation_certificate(self):
        self.ensure_one()
        return self.env.ref("l10n_ve_stock_account.action_donation_certificate_account_move").report_action(self)

    def action_post(self):
        res = super().action_post()
        donation_moves = self.filtered(lambda m: m.is_donation and m.move_type == "out_invoice")
        for move in donation_moves:
            # ! FIXME: Buscar la manera de no ejecutar _post acá
            move._post(soft=True)
            wizard = self.env["account.move.reversal"].with_context(
                active_ids=self.ids,
                active_model="account.move"
            ).create({"date": fields.Date.today(), "journal_id": self.journal_id.id})
            wizard.reverse_moves()
            credit_note = wizard.new_move_ids
            credit_note.action_post()
            return res
        return res

    def write(self, vals):
        
        for record in self:
            is_donation = vals.get('is_donation', record.is_donation)
            move_type = vals.get('move_type', record.move_type)
            ref = vals.get('ref', record.ref)

            if is_donation and move_type == "entry":
                if 'is_donation' in vals or 'ref' in vals or 'line_ids' in vals:
                    if not ref:
                        raise UserError(_("The reference is required for a donation"))
                
                if "line_ids" in vals:
                    for command in vals["line_ids"]:
                        is_valid_command = isinstance(command, (list, tuple)) and len(command) == 3 and isinstance(command[2], dict)
                        if not is_valid_command:
                            continue

                        line_vals = command[2]
                        line_vals['name'] = ref

        return super().write(vals)
