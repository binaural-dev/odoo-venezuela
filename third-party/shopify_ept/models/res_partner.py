# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

import logging
from odoo import models, fields, api

_logger = logging.getLogger("Shopify Partner")


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_shopify_customer = fields.Boolean(string="Is Shopify Customer?", default=False,
                                         help="Used for identified that the customer is imported from Shopify store.")

    @api.model
    def create_shopify_pos_customer(self, order_response, instance):
        """
        Creates customer from POS Order.
        @author: Maulik Barad on Date 27-Feb-2020.
        """
        address = {}
        shopify_partner_obj = self.env["shopify.res.partner.ept"]
        partner_obj = self.env["res.partner"]
        customer_data = partner_obj.remove_special_chars_from_partner_vals(order_response.get("customer"))

        if customer_data.get("default_address"):
            address = customer_data.get("default_address")

        customer_id = customer_data.get("id")
        first_name = customer_data.get("first_name") if customer_data.get("first_name") else ''
        last_name = customer_data.get("last_name") if customer_data.get("last_name") else ''
        phone = customer_data.get("phone")
        email = customer_data.get("email")

        shopify_partner = shopify_partner_obj.search([("shopify_customer_id", "=", customer_id),
                                                      ("shopify_instance_id", "=", instance.id)],
                                                     limit=1)

        partner_vals = shopify_partner_obj.shopify_prepare_partner_vals(address, instance)
        partner_vals = self.update_name_in_partner_vals(partner_vals, first_name, last_name, email, phone)
        if shopify_partner:
            parent_id = shopify_partner.partner_id.id
            partner_vals.update(parent_id=parent_id)
            key_list = list(partner_vals.keys())
            res_partner = self._find_partner_ept(partner_vals, key_list, [])
            if not res_partner:
                del partner_vals["parent_id"]
                key_list = list(partner_vals.keys())
                res_partner = self._find_partner_ept(partner_vals, key_list, [])
                if not res_partner:
                    partner_vals.update(
                        {'is_company': False, 'type': 'invoice', 'customer_rank': 0, 'is_shopify_customer': True})
                    res_partner = self.create(partner_vals)
            return res_partner

        res_partner = self

        res_partner = self.search_partner_by_email_phone(res_partner, email, phone)

        if res_partner:
            partner_vals.update({"is_shopify_customer": True, "type": "invoice", "parent_id": res_partner.id})
            res_partner = self.create(partner_vals)
        else:
            key_list = list(partner_vals.keys())
            res_partner = self._find_partner_ept(partner_vals, key_list, [])
            if res_partner:
                res_partner.write({"is_shopify_customer": True})
            else:
                partner_vals.update({"is_shopify_customer": True, "type": "contact"})
                res_partner = self.create(partner_vals)

        shopify_partner_obj.create({"shopify_instance_id": instance.id,
                                    "shopify_customer_id": customer_id,
                                    "partner_id": res_partner.id})
        return res_partner

    def update_name_in_partner_vals(self, partner_vals, first_name, last_name, email, phone):
        """ This method is used to update the name of the pos customer if the first name and last name
            do not exist in response.
            @return: partner_vals
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 2 November 2020 .
            Task_id: 167537
        """
        name = ("%s %s" % (first_name, last_name)).strip()
        if name == "":
            if email:
                name = email
            elif phone:
                name = phone

        partner_vals.update({"name": name})

        return partner_vals

    def search_partner_by_email_phone(self, res_partner, email, phone):
        """ This method is used to search res partner record base on email and phone.
            @return:res_partner
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 2 November 2020 .
            Task_id:167537
        """

        if email:
            res_partner = self.search([("email", "=", email)], limit=1)
        if not res_partner and phone:
            res_partner = self.search([("phone", "=", phone)], limit=1)
        if res_partner and res_partner.parent_id:
            res_partner = res_partner.parent_id

        return res_partner

    def create_or_search_tag(self, tag):
        """
        :param tag:
        :return:
        """
        res_partner_category_obj = self.env['res.partner.category']

        exists_tag = res_partner_category_obj.search([('name', '=ilike', tag)], limit=1)

        if not exists_tag:
            exists_tag = res_partner_category_obj.sudo().create({'name': tag})
        return exists_tag.id
