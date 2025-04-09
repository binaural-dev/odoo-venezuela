from odoo import fields, models
import logging

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    username_tfhka = fields.Char(related="company_id.username_tfhka", string="Username", readonly=False)
    password_tfhka = fields.Char(related="company_id.password_tfhka", string="Password", readonly=False)
    url_tfhka = fields.Char(related="company_id.url_tfhka", string="URL", readonly=False)
 