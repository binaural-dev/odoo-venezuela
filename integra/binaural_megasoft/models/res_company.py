from odoo import api, fields, models, _


class ResCompany(models.Model):
    _inherit = "res.company"

    change_p2c = fields.Boolean(default=False, string="Change c2p method")
    verificate_p2c = fields.Boolean(default=False, string="Verificate c2p payment")
    pdv_option = fields.Boolean(default=False, string="pdv options")
    url_megasoft = fields.Char("URL Megasoft")
    port_megasoft = fields.Char("Port of Megasoft")
