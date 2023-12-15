import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    is_change_method = fields.Boolean(related="company_id.change_p2c", default=False)
    confirm_payment_p2c = fields.Boolean(related="company_id.verificate_p2c", default=False)
    confirm_payment_pdv = fields.Boolean(related="company_id.pdv_option", default=False)

    is_change = fields.Boolean(default=False, readonly=False)
    is_payment_p2c = fields.Boolean(default=False, readonly=False)
    is_payment_pdv = fields.Boolean(default=False, readonly=False)
