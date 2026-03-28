from datetime import datetime, time
import logging
from datetime import timedelta
from odoo.exceptions import ValidationError
from odoo import api, fields, models, Command, _

_logger = logging.getLogger(__name__)

class CalendarEventCrm(models.Model):
    _inherit = 'calendar.event'

    guest_ids = fields.Many2many(
        "appointment.guests",
        string="Guests"
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._ensure_appointment_portal_fields()
        return records

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('skip_ensure_portal_fields') and any(
            f in vals for f in (
                'appointment_type_id', 'partner_ids',
                'appointment_booker_id', 'categ_ids',
            )
        ):
            self._ensure_appointment_portal_fields()
        return res

    def _ensure_appointment_portal_fields(self):
        """Asegura que los eventos con appointment_type_id tengan los campos
        necesarios para ser visibles en el portal y calendario web.

        - categ_ids: categoría 'Online Appointment' para el calendario público
        - appointment_booker_id: para el listado 'Mis Citas' del portal
        - partner_ids: para que el filtro de partner_ids del portal funcione
        """
        online_categ = self.env.ref(
            'appointment.calendar_event_type_data_online_appointment',
            raise_if_not_found=False,
        )
        for event in self.filtered('appointment_type_id'):
            vals = {}
            if online_categ and online_categ not in event.categ_ids:
                vals['categ_ids'] = [Command.link(online_categ.id)]
            if not event.appointment_booker_id and event.partner_ids:
                potential_booker = event.partner_ids - event.user_id.partner_id
                if potential_booker:
                    vals['appointment_booker_id'] = potential_booker[0].id
                elif event.partner_ids:
                    vals['appointment_booker_id'] = event.partner_ids[0].id
            booker = event.appointment_booker_id
            if booker and booker not in event.partner_ids:
                vals.setdefault('partner_ids', [])
                vals['partner_ids'].append(Command.link(booker.id))
            if vals:
                event.with_context(
                    skip_ensure_portal_fields=True
                ).sudo().write(vals)

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