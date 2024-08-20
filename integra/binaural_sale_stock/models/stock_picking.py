from odoo import fields, models, api


class StockPicking(models.Model):
    _inherit = "stock.picking"

    is_invoiced = fields.Boolean(compute="_compute_is_invoiced", store=True)
    amount_invoiced = fields.Float(compute="_compute_amount_invoiced", store=True)

    @api.depends("sale_id.invoice_ids.state")
    def _compute_amount_invoiced(self):
        for record in self:
            record.amount_invoiced = sum(
                record.sale_id.invoice_ids.filtered(lambda x: x.state == "posted").mapped("amount_total")
            )

    @api.depends("move_ids.sale_line_id.invoice_status")
    def _compute_is_invoiced(self):
        for record in self:
            status = False
            for invoice in record.move_ids.sale_line_id:
                if invoice.invoice_status == "invoiced":
                    status = True
            record.is_invoiced = status
