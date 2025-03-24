from odoo import api, models

from ..tools.utils import get_is_foreign_currency


class ResCurrency(models.Model):
    _inherit = "res.currency"

