##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) Sitaram Solutions (<https://sitaramsolutions.in/>).
#
#    For Module Support : info@sitaramsolutions.in  or Skype : contact.hiren1188
#
##############################################################################

from odoo import fields, models


class srResUsers(models.Model):
    _inherit = 'res.users'
    
    discount_limit = fields.Float(string="Asignar limite de descuento", default=0.00, help="Asignar limite de descuento para este usuario")

