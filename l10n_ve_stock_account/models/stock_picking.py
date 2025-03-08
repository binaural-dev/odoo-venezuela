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
    
    def create_invoice(self):
        self._validate_one_invoice_posted()
        return super().create_invoice()
    
    def create_bill(self):
        self._validate_one_invoice_posted()
        return super().create_bill()
    
    def create_customer_credit(self):
        self._validate_one_invoice_posted()
        return super().create_customer_credit()
    
    def create_vendor_credit(self):
        self._validate_one_invoice_posted()
        return super().create_vendor_credit()
    
    def _validate_one_invoice_posted(self,):
        for picking in self:
            invoice_ids = self.env['account.move'].search(
                [
                    ('picking_id', '=', picking.id),
                    ("state", "=", "posted")
                ]
            )            
            if invoice_ids:
                raise UserError(
                    _(
                        "This guide has at least one posted invoice, please check your invoice."
                    )
                )