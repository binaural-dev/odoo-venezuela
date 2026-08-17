from odoo import fields, models


class LogisticVehicle(models.Model):
    _name = "logistic.vehicle"
    _description = "Logistic Transport Vehicle"

    name = fields.Char(
        string="Identifier",
        required=True,
        help="Internal transport number or quick identifier.",
    )
    license_plate = fields.Char(string="License Plate", required=True)
    transport_number = fields.Char(string="Transport Number / Serial")
    vehicle_type = fields.Selection(
        selection=[
            ("light", "Light"),
            ("heavy", "Heavy / Cargo"),
            ("other", "Other"),
        ],
        string="Vehicle Type",
    )
