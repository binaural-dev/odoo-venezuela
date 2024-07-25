from odoo import http
import xmltodict
import requests
import base64
from datetime import timedelta
import psycopg2
from odoo.http import request
import xml.etree.ElementTree as ET
from odoo import fields
from odoo.addons.payment.controllers.post_processing import PaymentPostProcessing

import logging

_logger = logging.getLogger(__name__)

PAYMENT_URL = "https://paytest.megasoft.com.ve/payment"


class MegasoftController(http.Controller):
    @http.route("/get_values_payment_method", cors="*", type="json", auth="public", website=True)
    def get_values_payment_method(self, values, **kwargs):
        return values

    @http.route("/get_partner_data", type="json", cors="*", auth="public", website=True)
    def get_partner_data(self, values, **kwargs):
        partner_id = values["partner_id"]
        partner = request.env["res.partner"].sudo().browse(int(partner_id))
        return partner

    @http.route("/get_config_payment", type="json", cors="*", auth="public", website=True)
    def get_config_payment(self, **kwargs):
        values = kwargs.get("values")
        partner = self.get_partner_data(values)
        if values and partner:
            provider_id = values["provider_id"]
            payment_method = request.env["payment.provider"].sudo().browse(int(provider_id))
            username = payment_method.megasoft_user
            password = payment_method.megasoft_password
            url = payment_method.megasoft_url
            cod_affiliation = payment_method.megasoft_cod_afiliation
            # Partner info
            name = partner.name
            prefix_vat = partner.prefix_vat
            vat = partner.vat
            # Amount
            amount = values["amount"]
            # Reference
            reference = values["reference"]

            pre_register_payment = self.payment_gateway(
                username, password, url, cod_affiliation, name, prefix_vat, vat, amount, reference
            )
            return pre_register_payment.response

    @http.route("/payment_gateway", cors="*", type="http", auth="user", methods=["POST"])
    def payment_gateway(
        self,
        username,
        password,
        url,
        cod_affiliation,
        name,
        prefix_vat,
        vat,
        amount,
        reference,
        **kw,
    ):
        # Credenciales para la autorización
        megasoft_username = username
        megasoft_password = password
        # Payment reference
        odoo_reference = reference.split("-")
        megasoft_reference = odoo_reference[0]

        encoded_credentials = base64.b64encode(
            f"{megasoft_username}:{megasoft_password}".encode()
        ).decode()

        # Construcción del XML
        root = ET.Element("request")
        ET.SubElement(root, "cod_afiliacion").text = cod_affiliation
        ET.SubElement(root, "factura").text = megasoft_reference
        ET.SubElement(root, "monto").text = str("{:.2f}".format(amount))
        ET.SubElement(root, "nombre").text = name
        ET.SubElement(root, "tipo").text = prefix_vat
        ET.SubElement(root, "cedula_rif").text = vat
        # Agrega más subelementos si es necesario
        xml_data = ET.tostring(root, encoding="utf-8", method="xml").decode()

        # Encabezados para la solicitud
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/xml",
        }
        # URL del servicio de pago
        megasoft_url = f"{url}/action/paymentgatewayuniversal-prereg"

        # Realiza la solicitud
        response = requests.post(megasoft_url, data=xml_data, headers=headers)

        # Maneja la respuesta
        if response.status_code == 200:
            control = response.text
            request.session['payment_control'] = control
            request.env.context = {'pan':False}
            payment_gateway_locked = (
                f"{url}/action/paymentgatewayuniversal-data_locked?control={control}"
            )
            return payment_gateway_locked
        else:
            return f"Error: {response.status_code}"

    @http.route("/redirect_megasoft_url", cors="*", type='http', auth="public", methods=['GET'])
    def redirect_megasoft_url(self, url):
        _logger.warning(url)
        return request.redirect(f"{url}")


    def _create_transaction(
        self, payment_option_id, reference_prefix, amount, currency_id, partner_id, flow,
        tokenization_requested, landing_route, is_validation=False,
        custom_create_values=None, **kwargs
    ):
        tx_sudo = super()._create_transaction(payment_option_id, reference_prefix, amount, currency_id, partner_id, flow,
        tokenization_requested, landing_route, is_validation=False,
        custom_create_values=None, **kwargs)

        return tx_sudo


    @http.route("/redirect_get_payment/<string:control>", cors="*", type='http', auth="public", methods=['GET'])
    def redirect_get_payment(self, control, **kw):
        """ Process the notification data sent by Megasoft after redirection from checkout.

        :param dict data: The notification data.
        """
        # Handle the notification data.
        # uid = 1
        if control != 'null':
            get_payment_url = f"{PAYMENT_URL}/action/paymentgatewayuniversal-querystatus?control={control}"

            response = requests.get(get_payment_url)
            response.raise_for_status()
            response_xml = response.text

            _logger.warning(response_xml)
            _logger.warning(type(response_xml))

            data_dict = xmltodict.parse(response_xml)

            _logger.warning("DATA DICT")
            _logger.warning(data_dict)

            megasoft_response = ET.fromstring(response_xml)

            state = megasoft_response.find('estado').text
            description = megasoft_response.find('descripcion').text
            voucher = megasoft_response.find('voucher').text
                        
            if state == "A":
                tx_sudo = request.env['payment.transaction'].sudo()._get_tx_from_notification_data(
                    'megasoft', data_dict
                )
                tx_sudo.provider_id.done_msg = '<div style="width:300px;">' + voucher + '</div>'

                tx_sudo._handle_notification_data('megasoft', data_dict)


            elif state == "R":
                tx_sudo = request.env['payment.transaction'].sudo()._get_tx_from_notification_data(
                    'megasoft', data_dict
                )
                if voucher is not None:
                    msg = voucher 
                else:
                    msg = 'Megasoft error: ' + description 
                tx_sudo._set_error(
                 msg
                )
                tx_sudo._finalize_post_processing()
                tx_sudo._reconcile_after_done()

        else:  # The customer cancelled the payment by clicking on the return button.
            pass  # Don't try to process this case because the payment id was not provided.

        # Redirect the user to the status page.
        return request.redirect('/payment/status')


class BinauralPaymentPostProcessing(PaymentPostProcessing):
    @http.route('/payment/status/poll', cors="*", type='json', auth='public')
    def poll_status(self, **_kwargs):
        """ Fetch the transactions to display on the status page and finalize their post-processing.
        :return: The post-processing values of the transactions
        :rtype: dict
        """
        # Retrieve recent user's transactions from the session
        limit_date = fields.Datetime.now() - timedelta(days=1)

        monitored_txs = request.env['payment.transaction'].sudo().search([
            ('id', 'in', self.get_monitored_transaction_ids()),
            ('last_state_change', '>=', limit_date)
        ])

        if not monitored_txs:  # The transaction was not correctly created
            return {
                'success': False,
                'error': 'no_tx_found',
            }

        # Build the list of display values with the display message and post-processing values
        display_values_list = []
        for tx in monitored_txs:
            display_message = None
            if tx.state == 'pending':
                display_message = tx.provider_id.pending_msg
            elif tx.state == 'done':
                display_message = tx.provider_id.done_msg
            elif tx.state == 'cancel':
                display_message = tx.provider_id.cancel_msg
            display_values_list.append({
                'display_message': display_message,
                **tx._get_post_processing_values(),
            })

        # Stop monitoring already post-processed transactions
        post_processed_txs = monitored_txs.filtered('is_post_processed')
        self.remove_transactions(post_processed_txs)

        # Finalize post-processing of transactions before displaying them to the user
        txs_to_post_process = (monitored_txs - post_processed_txs).filtered(
            lambda t: t.state == 'done'
        )
        success, error = True, None
        try:
            txs_to_post_process._finalize_post_processing()
        except psycopg2.OperationalError:  # A collision of accounting sequences occurred
            request.env.cr.rollback()  # Rollback and try later
            success = False
            error = 'tx_process_retry'
        except Exception as e:
            request.env.cr.rollback()
            success = False
            error = str(e)
            _logger.exception(
                "encountered an error while post-processing transactions with ids %s:\n%s",
                ', '.join([str(tx_id) for tx_id in txs_to_post_process.ids]), e
            )

        return {
            'success': success,
            'error': error,
            'display_values_list': display_values_list,
        }