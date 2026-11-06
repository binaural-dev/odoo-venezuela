from odoo import api, models, fields, _


class AccumulatedFees(models.Model):
    _name = "accumulated.fees"
    _description = "Accumulated Fees"

    name = fields.Char(string="Description", required=True, store=True)
    start = fields.Float(required=True, store=True)
    stop = fields.Float(help='Leave blank to compare only with the value "start"', store=True)
    percentage = fields.Float(string="Porcentaje de tarifa", required=True, store=True)
    subtract_ut = fields.Float(string="Subsctrat TU", store=True)
    fees_id = fields.Many2one("fees.retention", string="Tarifa acumulada", store=True)

    @api.constrains("start", "stop", "fees_id")
    def _check_tiers_continuity(self):
        # Editing a tier does not trigger the constraint declared on the one2many.
        self.fees_id._check_accumulated_tiers_continuity()
