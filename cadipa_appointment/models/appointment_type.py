from odoo import models, api, Command, _
# Asegúrate de importar Command

class CustomAppointmentType(models.Model):
    _inherit = 'appointment.type'

    def _prepare_calendar_event_values(
        self, asked_capacity, booking_line_values, description, duration,
        appointment_invite, guests, name, customer, staff_user, start, stop,
        resource_id=None
    ):
        """
        Override the method to add the resource_id when the appointment
        is scheduled based on resources.
        """
        
        vals = super(CustomAppointmentType, self)._prepare_calendar_event_values(
            asked_capacity, booking_line_values, description, duration,
            appointment_invite, guests, name, customer, staff_user, start, stop
        )

        if resource_id and self.schedule_based_on == 'resources':            
            vals['resource_ids'] = [Command.set([resource_id])]
            
        return vals