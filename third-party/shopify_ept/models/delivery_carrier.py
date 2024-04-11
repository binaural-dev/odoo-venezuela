# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class DeliveryCarrier(models.Model):
    """Inherit the model to handle the delivery carrier in the connector"""
    _inherit = "delivery.carrier"

    shopify_code = fields.Char("Shopify Delivery Code")
    shopify_source = fields.Char("Shopify Delivery Source")
    shopify_tracking_company = fields.Selection([
        ('4PX', '4PX'),
        ('APC', 'APC'),
        ('Amazon Logistics UK', 'Amazon Logistics UK'),
        ('Amazon Logistics US', 'Amazon Logistics US'),
        ('Anjun Logistics', 'Anjun Logistics'),
        ('Australia Post', 'Australia Post'),
        ('Bluedart', 'Bluedart'),
        ('Canada Post', 'Canada Post'),
        ('Canpar', 'Canpar'),
        ('China Post', 'China Post'),
        ('Chukou1', 'Chukou1'),
        ('Correios', 'Correios'),
        ('Couriers Please', 'Couriers Please'),
        ('DHL Express', 'DHL Express'),
        ('DHL eCommerce', 'DHL eCommerce'),
        ('DHL eCommerce Asia', 'DHL eCommerce Asia'),
        ('DPD', 'DPD'),
        ('DPD Local', 'DPD Local'),
        ('DPD UK', 'DPD UK'),
        ('Delhivery', 'Delhivery'),
        ('Eagle', 'Eagle'),
        ('FSC', 'FSC'),
        ('Fastway Australia', 'Fastway Australia'),
        ('FedEx', 'FedEx'),
        ('GLS', 'GLS'),
        ('GLS (US)', 'GLS (US)'),
        ('Globegistics', 'Globegistics'),
        ('Japan Post (EN)', 'Japan Post (EN)'),
        ('Japan Post (JA)', 'Japan Post (JA)'),
        ('La Poste', 'La Poste'),
        ('New Zealand Post', 'New Zealand Post'),
        ('Newgistics', 'Newgistics'),
        ('PostNL', 'PostNL'),
        ('PostNord', 'PostNord'),
        ('Purolator', 'Purolator'),
        ('Royal Mail', 'Royal Mail'),
        ('SF Express', 'SF Express'),
        ('SFC Fulfillment', 'SFC Fulfillment'),
        ('Sagawa (EN)', 'Sagawa (EN)'),
        ('Sagawa (JA)', 'Sagawa (JA)'),
        ('Sendle', 'Sendle'),
        ('Singapore Post', 'Singapore Post'),
        ('StarTrack', 'StarTrack'),
        ('TNT', 'TNT'),
        ('Toll IPEC', 'Toll IPEC'),
        ('UPS', 'UPS'),
        ('USPS', 'USPS'),
        ('Whistl', 'Whistl'),
        ('Yamato (EN)', 'Yamato (EN)'),
        ('Yamato (JA)', 'Yamato (JA)'),
        ('YunExpress', 'YunExpress')
    ], help="shopify_tracking_company selection help:When creating a fulfillment for a supported carrier, send the"
            "tracking_company exactly as written in the list above. If the tracking company doesn't match one of the"
            "supported entries, then the shipping status might not be updated properly during the fulfillment process.")

    def shopify_search_create_delivery_carrier(self, line, instance):
        """
        This method use to search and create delivery carrier base on received response in order line.
        :param line: Response of order line as received from Shopify store.
        :param instance: Response of instance.
        :return: carrier
        """
        delivery_source = line.get('source')
        delivery_code = line.get('code')
        delivery_title = line.get('title')
        carrier = self.env['delivery.carrier']
        if delivery_source and delivery_code:
            carrier = self.search([('shopify_source', '=', delivery_source), '|', ('shopify_code', '=', delivery_code),
                                   ('shopify_tracking_company', '=', delivery_code)], limit=1)

            if not carrier:
                carrier = self.search([('name', '=', delivery_title)], limit=1)
                if carrier:
                    carrier.write({'shopify_source': delivery_source, 'shopify_code': delivery_code})

            if not carrier:
                carrier = self.create(
                    {'name': delivery_title, 'shopify_code': delivery_code, 'shopify_source': delivery_source,
                     'product_id': instance.shipping_product_id.id})
        return carrier

    def search_carrier_for_webhook_fulfillment(self, instance, fulfillment_data):
        """
        This method is use to search the carrier for webhook fulfillment
        """
        carrier_name = fulfillment_data.get('service')
        carrier = False
        if carrier_name:
            carrier = self.search([('name', '=', carrier_name)], limit=1)
            if not carrier:
                carrier = self.create(
                    {'name': carrier_name, 'shopify_code': carrier_name, 'shopify_source': carrier_name,'product_id': instance.shipping_product_id.id})
        return carrier
