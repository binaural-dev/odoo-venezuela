from odoo import _, api, fields, models
import logging
_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = "payment.provider"

    code = fields.Selection(
        selection_add=[("megasoft", "Megasoft")], ondelete={"megasoft": "set default"}
    )
    megasoft_url = fields.Char(string="Megasoft Url", required_if_provider="megasoft")

    megasoft_user = fields.Char(string="User", required_if_provider="megasoft")

    megasoft_password = fields.Char(string="Password", required_if_provider="megasoft")

    megasoft_cod_afiliation = fields.Char(string="Afiliation code", required_if_provider="megasoft")


    @api.model
    def _get_compatible_providers(self, *args, currency_id=None, **kwargs):
        """ Override of `payment` to filter out megasoft providers for unsupported currencies. """
        providers = super()._get_compatible_providers(*args, currency_id=currency_id, **kwargs)
        return providers