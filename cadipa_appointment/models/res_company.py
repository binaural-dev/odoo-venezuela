# Copyright 2020 Tecnativa - Ernesto Tejeda
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models

hours = [
    ('1', '1'),
    ('2', '2'),
    ('3', '3'),
    ('4', '4'),
    ('5', '5'),
    ('6', '6'),
    ('7', '7'),
    ('8', '8'),
    ('9', '9'),
    ('10', '10'),
    ('11', '11'),
    ('12', '12'),
    ('13', '13'),
    ('14', '14'),
    ('15', '15'),
    ('16', '16'),
    ('17', '17'),
    ('18', '18'),
    ('19', '19'),
    ('20', '20'),
    ('21', '21'),
    ('22', '22'),
    ('23', '23'),
]


class ResCompany(models.Model):
    _inherit = "res.company"

    appointment_open_hour = fields.Selection(
        string="Appointment Open Hour",
        selection=hours
    )

    appointment_close_hour = fields.Selection(
        string="Appointment Close Hour",
        selection=hours,
    )

    minimum_child_age = fields.Integer(
        string="Minimum age (years)",
        help="Minimum age in years that a minor must have to be included in a membership.",
    )

    maximum_child_age = fields.Integer(
        string="Maximum age (years)",
        help="Maximum age in years that a minor can have to be included in a membership.",
    )

    membership_auto_suspend = fields.Boolean(
        string="Enable automatic suspension of memberships",
        default=False
    )
    membership_suspension_delay_days = fields.Integer(
        string="Days of delay before suspension",
        default=30
    )

    restrict_appointment_to_members = fields.Boolean(
        string="Restrict appointments to members only",
        default=False
    )

    appointment_lead_time_days = fields.Integer(
        string="Appointment Lead Time (days)",
        default=1,
        help="Minimum number of days in advance to book an appointment."
    )

    def toggle_sync_cron(self):
        """
        Toggle the synchronization cron job for the company.
        """
        for record in self:
            cron_job = record.env.ref('cadipa_appointment.ir_cron_member_club_auto_suspend', raise_if_not_found=False)
            if not cron_job:
                continue
            
            cron_job.write({'active': record.membership_auto_suspend})

    def write(self, vals):
        res = super(ResCompany, self).write(vals)
        if 'membership_auto_suspend' in vals:
            self.toggle_sync_cron()
        return res
