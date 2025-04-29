from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)
class PickingInvoiceWizard(models.TransientModel):

    _name = "picking.invoice.wizard"
    _description = "Picking Invoice Wizard"

    invoice_type_selection = fields.Selection([('unique', 'One invoice for all stock pickings'), ('multiple', 'Unique invoice for each stock pickings')], required=True)
    pickings_ids = fields.Many2many("stock.picking", string="Pickings", required=True)
    
    def picking_selection_invoice(self):
        for record in self:
            if record.invoice_type_selection == 'unique':
                self.unique_invoice()
            else:
                self.multiple_invoice()
    
    def unique_invoice(self):
        _logger.warning("Unique invoice selected")
        active_ids = self._context.get("active_ids")
        picking_ids = self.env["stock.picking"].browse(active_ids)
        picking_id_check_state = picking_ids.filtered(lambda x: x.state != 'done')

        if picking_id_check_state: 
            raise UserError("You can only create invoices for pickings in the 'To Invoice' state.")
        partner_id = picking_ids.mapped("partner_id")
        if len(partner_id) == 1:
            pass
        else:
            raise UserError("You can only create invoices for pickings with the same partner.")
        
        status_set = set()

        for picking in picking_ids:
            if picking.show_create_bill:
                status_set.add('bill')
            elif picking.show_create_invoice:
                status_set.add('invoice')
            elif picking.show_create_vendor_credit:
                status_set.add('vendor_credit')
            elif picking.show_create_customer_credit:
                status_set.add('customer_credit')
            else: 
                raise UserError("You can only create invoices for not internal dispatch guides.")

        _logger.warning("Status set: %s", status_set) 
        if len(status_set) > 1:
            raise UserError("All selected pickings must have the same invoice type to create a single invoice.")
            
        if list(status_set)[0] == 'invoice':
            father_picking = picking_ids[0]
            father_picking.create_multi_invoice(picking_ids)
            
    def multiple_invoice(self):
        active_ids = self._context.get("active_ids")
        picking_ids = self.env["stock.picking"].browse(active_ids)
        picking_id_check_state = picking_ids.filtered(lambda x: x.state_guide_dispatch != 'to_invoice')
        if picking_id_check_state: 
            raise UserError("You can only create invoices for pickings in the 'To Invoice' state.")
        partner_id = picking_ids.mapped("partner_id")
        if len(partner_id) == 1:
            pass
        else:
            raise UserError("You can only create invoices for pickings with the same partner.")

        for picking in picking_ids:
            if picking.show_create_bill:
                picking.create_bill()
            elif picking.show_create_invoice:
                picking.create_invoice()
            elif picking.show_create_vendor_credit:
                picking.create_vendor_credit()
            elif picking.show_create_customer_credit():
                picking.create_customer_credit()
            else: 
                raise UserError("You can only create invoices for not internal dispatch guides.")

    @api.model
    def default_get(self, fields):
        res = super(PickingInvoiceWizard, self).default_get(fields)
        active_ids = self._context.get("active_ids")
        res['pickings_ids'] = [(6, 0, active_ids)]
        return res
    
    