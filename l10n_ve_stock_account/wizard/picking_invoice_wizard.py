from odoo import models


class PickingInvoiceWizard(models.TransientModel):

    _name = "picking.invoice.wizard"
    _description = "Picking Invoice Wizard"

    def picking_multi_invoice(self):
        active_ids = self._context.get("active_ids")
        picking_ids = self.env["stock.picking"].browse(active_ids)
        picking_id = picking_ids.filtered(lambda x: x.state == "done" and x.invoice_count == 0)
        for picking in picking_id:
            if picking.picking_type_id.code == "incoming" and not picking.is_return:
                picking.create_bill()
            if picking.picking_type_id.code == "outgoing" and not picking.is_return:
                picking.create_invoice()
            if picking.picking_type_id.code == "incoming" and picking.is_return:
                picking.create_vendor_credit()
            if picking.picking_type_id.code == "outgoing" and picking.is_return:
                picking.create_customer_credit()
