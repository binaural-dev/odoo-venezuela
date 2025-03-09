import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression

_logger = logging.getLogger(__name__)

from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"
    
    guide_number = fields.Char(
        tracking=True, 
        copy=False,
    )

    state_guide_dispatch = fields.Selection(
        [
            ("to_invoice", "To Invoice"), 
            ("invoiced", "Invoiced"), 
        ], 
        default="to_invoice",
    )

    show_create_invoice = fields.Boolean(compute='_compute_button_visibility')
    show_create_bill = fields.Boolean(compute='_compute_button_visibility')
    show_create_customer_credit = fields.Boolean(compute='_compute_button_visibility')
    show_create_vendor_credit = fields.Boolean(compute='_compute_button_visibility')

    has_document = fields.Boolean(
        string="Has Document",
        compute="_compute_has_document",
        help="Technical field to check if the related sale order has a document.",
    )

    def _compute_button_visibility(self):
        for record in self:
            record.show_create_invoice = all([
                record.invoice_count == 0,
                record.state == 'done',
                record.operation_code != 'incoming',
                not record.is_return
            ])
            
            record.show_create_bill = all([
                record.invoice_count == 0,
                record.state == 'done',
                record.operation_code != 'outgoing',
                not record.is_return
            ])
            
            record.show_create_customer_credit = all([
                record.invoice_count == 0,
                record.state == 'done',
                record.operation_code != 'outgoing',
                record.is_return
            ])
            
            record.show_create_vendor_credit = all([
                record.invoice_count == 0,
                record.state == 'done',
                record.operation_code != 'incoming',
                record.is_return
            ])

    def create_invoice_lots(self):
        valid_picking = self.filtered(
            lambda picking: picking.state_guide_dispatch == "invoiced"
        )
        
        if valid_picking:
            raise UserError(_("You cannot create an invoice from this picking for this state."))
            
        for picking in self:
            if picking.show_create_invoice:
                picking.create_invoice()
            elif picking.show_create_bill:
                picking.create_bill()
            elif picking.show_create_customer_credit:
                picking.create_customer_credit()
            elif picking.show_create_vendor_credit:
                picking.create_vendor_credit()

    def button_validate(self,):
        res = super().button_validate()
        # Picking_type 
        self.guide_number = self.get_sequence_guide_num()
        return res
    
    @api.model
    def get_sequence_guide_num(self):
        self.ensure_one()
        sequence = self.env["ir.sequence"].sudo()
        guide_number = None

        guide_number = sequence.search(
            [("code", "=", "guide.number"), ("company_id", "=", self.company_id.id)]
        )
        if not guide_number:
            guide_number = sequence.create(
                {
                    "name": "Guide Number",
                    "code": "guide.number",
                    "company_id": self.company_id.id,
                    "prefix": "GUIDE",
                    "padding": 5,
                }
            )
        return guide_number.next_by_id(guide_number.id)


    def print_dispatch_guide(self):
        return self.env.ref("l10n_ve_stock_account.action_dispatch_guide").read()[0]


    def get_foreign_currency_is_vef(self):
        return self.company_id.currency_foreign_id == self.env.ref("base.VEF")

    def get_digits(self):
        return self.env.ref("base.VEF").decimal_places


    @api.depends('sale_id.document')
    def _compute_has_document(self):
        for picking in self:
            picking.has_document = bool(picking.sale_id.document)

    def get_totals(self, use_foreign_currency=False):
        """
        """
        self.ensure_one()
        totals = {
            'subtotal': 0.0,
            'tax': 0.0,
            'total': 0.0,
        }

        for line in self.move_ids_without_package:
            line_values = line._get_line_values(use_foreign_currency=use_foreign_currency)
            totals['subtotal'] += line_values['subtotal_after_discount']
            totals['tax'] += line_values['tax_amount']
            totals['total'] += line_values['total']

        return totals
