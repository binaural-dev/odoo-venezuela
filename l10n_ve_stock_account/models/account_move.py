from odoo import models, fields, api, _, Command
from odoo.exceptions import UserError, ValidationError

import logging

_logger = logging.getLogger(__name__)

TYPE_REVERSE_MAP = {
    'entry': 'entry',
    'out_invoice': 'out_refund',
    'out_refund': 'out_invoice',
    'in_invoice': 'in_refund',
    'in_refund': 'in_invoice',
    'out_receipt': 'out_refund',
    'in_receipt': 'in_refund',
}

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

    def _reverse_moves(self, default_values_list=None, cancel=False):
        """Reverse a recordset of account.move.
        If cancel parameter is true, the reconcilable or liquidity lines
        of each original move will be reconciled with its reverse's.
        :param default_values_list: A list of default values to consider per move.
        ('type' & 'reversed_entry_id' are computed in the method).
        :return: An account.move recordset, reverse of the current self.
        """
        for move in self:
            if move.is_donation:
                reverse_moves = self.env['account.move']
                for move, default_values in zip(self, default_values_list):
                    line_vals_list = []
                    for line in move.line_ids:
                        is_tax = bool(line.tax_line_id or line.display_type == 'tax')
                        is_receivable = line.account_id.account_type == 'asset_receivable'
                        if not (is_receivable or is_tax):
                            continue
                        lv = {
                            "account_id": line.account_id.id,
                            "name": line.name,
                            "balance": -line.balance,
                            "amount_currency": -line.amount_currency,
                            "currency_id": line.currency_id.id,
                            "partner_id": line.partner_id.id,
                            "display_type": line.display_type,
                        }
                        if is_tax and line.tax_line_id:
                            lv['tax_line_id'] = line.tax_line_id.id
                        line_vals_list.append((0, 0, lv))
                        move_vals = {
                            "move_type": "out_refund",
                            "journal_id": move.journal_id.id,
                            "date": default_values.get("date", fields.Date.today()),
                            "ref": default_values.get("ref", move.ref),
                            "reversed_entry_id": move.id,
                            "partner_id": move.partner_id.id,
                            "is_donation": True,
                            "line_ids": line_vals_list,
                        }
                        reverse_move = self.env['account.move'].with_context(
                            check_move_validity=False,
                            skip_invoice_sync=True,
                        ).create(move_vals)
                        reverse_moves += reverse_move
                for rm in reverse_moves:
                    rm.product_line_donation()
                    # rm.update({'invoice_line_ids': line_vals_list})
                return reverse_moves

        return super()._reverse_moves(default_values_list, cancel)
    def product_line_donation(self):
        """Adds the donation product line to invoice_line_ids using
        skip_invoice_sync=True to prevent Odoo from executing _synchronize_business_models
        and overwriting manually constructed receivable/tax lines.

        Explicitly sets account_id=donation_account_id so the journal entry
        uses the configured donation account instead of the product's default
        income account.
        """
        product = self.env["product.template"].search(
            [("is_donation_product", "=", True)], limit=1
        )
        if not product:
            raise UserError(_("Please configure a donation product in the company settings."))

        company = self.company_id or self.env.company
        donation_account_id = company.donation_account_id.id if company else False
        if not donation_account_id:
            raise UserError(_("Please configure a donation account in the company settings."))

        price_unit = abs(self.reversed_entry_id.amount_total_in_currency_signed) if self.reversed_entry_id else 0.0

        self.with_context(
            check_move_validity=False,
            skip_invoice_sync=True,
        ).write({
            'invoice_line_ids': [
                Command.create({
                    'product_id': product.product_variant_ids[:1].id,
                    'account_id': donation_account_id,
                    'name': self.ref or product.name,
                    'quantity': 1,
                    'price_unit': price_unit,
                })
            ]
        })
