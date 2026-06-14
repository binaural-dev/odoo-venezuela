from odoo import models, fields, api, _

class PosConfigInherit(models.Model):
    _inherit = "pos.config"

    # Campos de configuración legacy que antes estaban en iot.device
    # Ahora son campos directos en pos.config (no related)
    serial_machine = fields.Char(string="Serial de Máquina Fiscal")
    flag_21 = fields.Selection([('1', 'Activado'), ('0', 'Desactivado')], string="Flag 21")
    traditional_line = fields.Boolean(string="Línea Tradicional")
    has_cashbox = fields.Boolean(string="Tiene Caja de Efectivo")
    
    access_button_mf = fields.Boolean()
    message_in_head = fields.Boolean()
