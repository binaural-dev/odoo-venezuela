import logging

from werkzeug import urls
from odoo import _, fields, models, api
from odoo.exceptions import UserError, ValidationError
from odoo.addons.payment import utils as payment_utils


_logger = logging.getLogger(__name__)

class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _get_specific_rendering_values(self, processing_values):
        """ Override of payment to return Paypal-specific rendering values.

        Note: self.ensure_one() from `_get_processing_values`

        :param dict processing_values: The generic and specific processing values of the transaction
        :return: The dict of provider-specific processing values
        :rtype: dict
        """

        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'megasoft':
            return res

        base_url = self.provider_id.get_base_url()
        partner_first_name, partner_last_name = payment_utils.split_partner_name(self.partner_name)
        return {
            'address1': self.partner_address,
            'amount': self.amount,
            'business': self.provider_id.paypal_email_account,
            'city': self.partner_city,
            'country': self.partner_country_id.code,
            'currency_code': self.currency_id.name,
            'email': self.partner_email,
            'first_name': partner_first_name,
            'handling': self.fees,
            'item_name': f"{self.company_id.name}: {self.reference}",
            'item_number': self.reference,
            'last_name': partner_last_name,
            'lc': self.partner_lang,
            'notify_url': None,
            'return_url': urls.url_join(base_url),
            'state': self.partner_state_id.name,
            'zip_code': self.partner_zip,
            'api_url': self.provider_id.megasoft_url(),
        }

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """ Override of payment to find the transaction based on Paypal data.

        :param str provider_code: The code of the provider that handled the transaction
        :param dict notification_data: The notification data sent by the provider
        :return: The transaction if found
        :rtype: recordset of `payment.transaction`
        :raise: ValidationError if the data match no transaction
        """

        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'megasoft' or len(tx) == 1:
            return tx

        reference = notification_data['response']['factura']
        _logger.warning("")
        tx = self.search([('reference', '=', reference), ('provider_code', '=', 'megasoft')])
        return tx

            
    def _process_notification_data(self, notification_data):
        """ Override of `payment` to process the transaction based on Mercado Pago data.

        Note: self.ensure_one() from `_process_notification_data`

        :param dict notification_data: The notification data sent by the provider.
        :return: None
        :raise ValidationError: If inconsistent data were received.
        """
        super()._process_notification_data(notification_data)


        if self.provider_code != 'megasoft':
            return

        payment_id = notification_data['response']['control']

        if not payment_id:
            return
        if notification_data['response']['estado'] == "A":
            self.provider_reference = payment_id
            self._set_pending()
            self._set_done()
            self._finalize_post_processing()
            self._reconcile_after_done()
