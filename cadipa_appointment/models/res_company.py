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
