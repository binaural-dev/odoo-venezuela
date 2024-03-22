# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api
from datetime import timedelta


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _action_done(self):
        """
        Create and paid invoice on the basis of auto invoice work flow
        when invoicing policy is 'delivery'.
        """
        result = super(StockPicking, self)._action_done()
        for picking in self:
            if picking.sale_id.invoice_status == 'invoiced':
                continue

            order = picking.sale_id
            work_flow_process_record = order and order.auto_workflow_process_id
            delivery_lines = picking.move_line_ids.filtered(lambda l: l.product_id.invoice_policy == 'delivery')

            if work_flow_process_record and delivery_lines and work_flow_process_record.create_invoice and \
                    picking.location_dest_id.usage == 'customer':
                order.validate_and_paid_invoices_ept(work_flow_process_record)
        return result

    @api.depends('move_ids.state', 'move_ids.date', 'move_type')
    def _compute_scheduled_date(self):
        for picking in self:
            carrier_id = picking.carrier_id
            if carrier_id and carrier_id.on_time_shipping:
                order = picking.sale_id
                order_date = fields.Datetime.from_string(order.date_order)
                picking.scheduled_date = order_date + timedelta(days=carrier_id.on_time_shipping or 0.0)
            else:
                moves_dates = picking.move_ids.filtered(lambda move: move.state not in ('done', 'cancel')).mapped(
                    'date')
                if picking.move_type == 'direct':
                    picking.scheduled_date = min(moves_dates, default=picking.scheduled_date or fields.Datetime.now())
                else:
                    picking.scheduled_date = max(moves_dates, default=picking.scheduled_date or fields.Datetime.now())
