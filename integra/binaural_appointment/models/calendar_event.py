import logging
from datetime import timedelta
from pickle import NONE

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

class CalendarEventCrm(models.Model):
    _inherit = 'calendar.event'

    invoice_ids = fields.One2many('account.move', 'calendar_event_id', string='Invoices')

    def create_invoices(self, data):
        invoice_ids = self.env["account.move"]
        duration = data.get("duration", 0)

        for event in self:
            invoice_create = event.appointment_type_id.invoice_create

            if not invoice_create:
                continue

            partner = event.partner_ids - event.user_id.partner_id
            partner = partner[:1]

            product_id_id = data.get("product_id", event.appointment_type_id.product_id.id)
            product_id = self.env["product.product"].browse([int(product_id_id)])

            unit = product_id.uom_id
            amount_unit = product_id.lst_price

            invoice_data = {
                'move_type': 'out_invoice',
                'partner_id': partner.id,
                'invoice_date': fields.Date.today(),
                'calendar_event_id': event.id,
                'invoice_line_ids': [
                    (0, 0, {
                        'product_id': product_id.id,
                        'price_unit': amount_unit,
                        'quantity': duration
                    }),
                ],
            }

            self.env["account.move"].create(invoice_data)

        return invoice_ids