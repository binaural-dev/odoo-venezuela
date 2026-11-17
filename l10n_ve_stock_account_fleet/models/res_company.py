from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    # Al desinstalar este módulo, las compañías en 'fleet' vuelven a 'manual'.
    transport_data_source = fields.Selection(
        selection_add=[("fleet", "Fleet")],
        ondelete={"fleet": "set default"},
    )
