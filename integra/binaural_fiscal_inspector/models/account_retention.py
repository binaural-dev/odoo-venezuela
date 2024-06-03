from odoo import api, models, fields, Command, _
from datetime import datetime
from odoo.exceptions import UserError
from collections import defaultdict
import json


class AccountRetention(models.Model):
    _inherit = "account.retention"
    
    def write(self, vals):
        if self.env.user.has_group('binaural_fiscal_inspector.group_fiscal_inspectorate'):
            raise UserError(_("No tienes permiso para sobreescribir esta retencion"))
        return super().write(vals)
