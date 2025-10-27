from datetime import datetime, time
import logging
from datetime import timedelta
from pickle import NONE
from odoo.exceptions import ValidationError
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

class CalendarEventCrm(models.Model):
    _inherit = 'calendar.event'

    guest_ids = fields.Many2many(
        "appointment.guests",
        string="Guests"
    )

    # @api.constrains('guest_ids', 'start')
    # def _check_guest_daily_reservation(self):
    #     """
    #     Prevent a guest (appointment.guests) from being added to more than one
    #     calendar event (calendar.event) on the same day.
    #     """
    #     for event in self:
    #         if not event.guest_ids or not event.start:
    #             continue
    #         reservation_date = event.start.date()
    #         day_start_utc_str = fields.Datetime.to_string(datetime.combine(reservation_date, time.min))
    #         day_end_utc_str = fields.Datetime.to_string(datetime.combine(reservation_date, time.max))

    #         for guest in event.guest_ids:                
    #             domain = [
    #                 ('id', '!=', event.id),
    #                 ('guest_ids', '=', guest.id),
    #                 ('start', '>=', day_start_utc_str),
    #                 ('start', '<=', day_end_utc_str),
    #             ]
                
    #             if self.env['calendar.event'].search(domain, limit=1):                    
    #                 guest_vat = f"{guest.prefix_vat}-{guest.vat}" if guest.prefix_vat and guest.vat else (guest.vat or 'N/A')
                    
    #                 raise ValidationError(
    #                     _("Validación fallida: El invitado '%s' (CI: %s) ya tiene otra reserva asignada para el día %s.") %
    #                     (guest.name, guest_vat, reservation_date.strftime('%d-%m-%Y'))
    #                 )

    def create_invoices(self, data):
        if self.env.context.get('skip_core_invoice'):
            return self.env['account.move']

        invoice_lines = []
        duration = False
        for event in self:
            duration = event.duration
            invoice_create = event.appointment_type_id.invoice_create
            if not invoice_create:
                continue
            

            partner = event.partner_ids - event.user_id.partner_id
            partner = partner[:1]

            product_id_id = data.get("product_id", event.appointment_type_id.product_id.id)
            product_id = self.env["product.product"].browse([int(product_id_id)])

            amount_unit = product_id.lst_price

            invoice_lines.append(
                (0, 0, {
                    'product_id': product_id.id,
                    'price_unit': amount_unit,
                    'quantity': duration
                })
            )

        if invoice_lines:
            invoice_data = {
                'move_type': 'out_invoice',
                'partner_id': partner.id if partner else False,
                'invoice_date': fields.Date.today(),
                'calendar_event_id': self.ids[0] if self else False,
                'invoice_line_ids': invoice_lines,
            }
            invoice = self.env["account.move"].create(invoice_data)
            return invoice
        return self.env["account.move"]