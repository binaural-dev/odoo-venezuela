# -*- coding: utf-8 -*-

from odoo import models, fields


class Digest(models.Model):
    _inherit = 'digest.digest'

    shopify_instance_id = fields.Many2one('shopify.instance.ept')

    def _prepare_domain_shopify_digest(self):
        """
        Prepared shopify instance domain for shopify connector Digest.
        @author: Meera Sidapara on Date 13-07-2022
        @Task_id : 194458
        """
        domain = []
        domain += [('shopify_instance_id', '=', self.shopify_instance_id.id)]
        if self.kpi_orders:
            self.get_total_orders_count(domain)
        if self.kpi_refund_orders:
            self.get_refund_orders_count(domain)
        if self.kpi_avg_order_value:
            self.get_orders_average(domain)
        if self.kpi_cancel_orders:
            self.get_cancel_orders_count(domain)
        if self.kpi_account_total_revenue:
            self.get_account_total_revenue(domain)
        if self.kpi_late_deliveries:
            self.get_late_delivery_orders_count(domain)
        if self.kpi_on_shipping_orders:
            self.get_on_time_shipping_ratio(domain)
        if self.kpi_shipped_orders:
            domain.append(('updated_in_shopify', '=', True))
            self.get_shipped_orders_count(domain)
        if self.kpi_pending_shipment_on_date:
            domain.pop(1)
            domain.append(('updated_in_shopify', '=', False))
            self.get_pending_shipment_on_date_count(domain)
        return True

    def _prepare_domain_based_on_connector(self):
        if self.shopify_instance_id:
            self._prepare_domain_shopify_digest()
        return super(Digest, self)._prepare_domain_based_on_connector()
