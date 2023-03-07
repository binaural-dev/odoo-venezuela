from odoo import api, models, fields, _


class AccumulatedFees(models.Model):
    _name = "accumulated.fees"
    _description = "Accumulated Fees"

    name = fields.Char(string="Description", required=True)
    start = fields.Float(required=True)
    stop = fields.Float(help='Leave blank to compare only with the value "start"')
    percentage = fields.Float(string="Porcentaje de tarifa", required=True)
    subtract_ut = fields.Float(string="Restar UT")
    fees_id = fields.Many2one("fees.retention", string="Tarifa acumulada")
