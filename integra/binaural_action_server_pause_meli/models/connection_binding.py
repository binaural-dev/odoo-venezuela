from odoo import models
import logging

_logger = logging.getLogger(__name__)


class MercadoLibreConnectionBinding(models.Model):
    _inherit = "mercadolibre.product"

    def product_meli_status_put(self, context=None, status=None, meli=False):
        company = self.env.user.company_id
        account = self.connection_account
        config = (account and account.configuration) or company
        company = ("company_id" in config._fields and config.company_id) or company

        if not meli:
            meli = self.env["meli.util"].get_new_instance(company, account)

            if meli.need_login():
                return meli.redirect_login()

        if status and (status in ["paused", "closed", "active"]):
            for record in self:
                meli_id = record.conn_id
                response = meli.put(
                    "/items/" + str(meli_id),
                    {"status": status},
                    {"access_token": meli.access_token},
                )
                if response:
                    _logger.info(response.json())
        else:
            _logger.error("Undefined status set")
        return {}
