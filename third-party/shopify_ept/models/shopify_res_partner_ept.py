# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api


class ShopifyResPartnerEpt(models.Model):
    _name = "shopify.res.partner.ept"
    _description = "Shopify Res Partner"

    partner_id = fields.Many2one("res.partner", ondelete="cascade")
    shopify_instance_id = fields.Many2one("shopify.instance.ept", "Instances")
    shopify_customer_id = fields.Char()

    def shopify_create_contact_partner(self, vals, instance, queue_line):
        """
        This method is used to create a contact type customer.
        @author: Maulik Barad on Date 09-Sep-2020.
        @change : pass category_id as tag on vals by Nilam Kubavat for task id : 190111 at 19/05/2022
        """
        partner_obj = self.env["res.partner"]
        common_log_line_obj = self.env["common.log.lines.ept"]

        shopify_instance_id = instance.id
        shopify_customer_id = vals.get("id", False)
        first_name = vals.get("first_name", "")
        last_name = vals.get("last_name", "")
        email = vals.get("email", "")

        if not first_name and not last_name and not email:
            message = "First name, Last name and Email are not found in customer data."
            common_log_line_obj.create_common_log_line_ept(shopify_instance_id=instance.id, module="shopify_ept",
                                                           message=message,
                                                           model_name='res.partner',
                                                           shopify_customer_data_queue_line_id=queue_line.id
                                                           if queue_line else False)
            return False

        name = ""
        if first_name:
            name = "%s" % first_name
        if last_name:
            name += " %s" % last_name if name else "%s" % last_name
        if not name and email:
            name = email

        partner = self.search_shopify_partner(shopify_customer_id, shopify_instance_id)
        tags = vals.get("tags").split(",") if vals.get("tags") != '' else vals.get("tags")
        tag_ids = []
        for tag in tags:
            tag_ids.append(partner_obj.create_or_search_tag(tag))

        if partner:
            if not partner.parent_id:
                partner = self.update_partner_with_company(instance, vals.get("default_address", {}), False, partner)
            partner.write({"category_id": tag_ids})
            return partner

        shopify_partner_values = {"shopify_customer_id": shopify_customer_id,
                                  "shopify_instance_id": shopify_instance_id}
        if email:
            partner = partner_obj.search_partner_by_email(email)

            if partner:
                partner.write({"is_shopify_customer": True, "category_id": tag_ids})
                shopify_partner_values.update({"partner_id": partner.id})
                self.create(shopify_partner_values)
                return partner

        partner_vals = self.shopify_prepare_partner_vals(vals.get("default_address", {}), instance)
        partner_vals.update({
            "name": name,
            "email": email,
            "customer_rank": 1,
            "is_shopify_customer": True,
            "type": "contact",
            "category_id": tag_ids,
            "phone": vals.get("phone", "") if not partner_vals.get("phone") else partner_vals.get("phone")
        })
        partner = partner_obj.create(partner_vals)

        shopify_partner_values.update({"partner_id": partner.id})
        self.create(shopify_partner_values)
        partner = self.update_partner_with_company(instance, vals.get("default_address", {}), False, partner)
        return partner

    def search_shopify_partner(self, shopify_customer_id, shopify_instance_id):
        """ This method is used to search the shopify partner.
            :param shopify_customer_id: Id of shopify customer which receive from customer response.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 27 October 2020 .
            Task_id: 167537
        """
        partner = False
        shopify_partner = self.search([("shopify_customer_id", "=", shopify_customer_id),
                                       ("shopify_instance_id", "=", shopify_instance_id)], limit=1)
        if shopify_partner:
            partner = shopify_partner.partner_id
            return partner

        return partner

    @api.model
    def shopify_create_or_update_address(self, instance, shopify_customer_data, parent_partner, partner_type="contact"):
        """
        Creates or updates existing partner from Shopify customer's data.
        @author: Maulik Barad on Date 09-Sep-2020.
        """
        partner_obj = self.env["res.partner"]

        first_name = shopify_customer_data.get("first_name")
        last_name = shopify_customer_data.get("last_name")

        if not first_name and not last_name:
            return False

        company_name = shopify_customer_data.get("company")
        partner_vals = self.shopify_prepare_partner_vals(shopify_customer_data)
        address_key_list = ["name", "street", "street2", "city", "zip", "phone", "state_id", "country_id"]

        if company_name and not instance.import_customer_as_company:
            address_key_list.append("company_name")
            partner_vals.update({"company_name": company_name})

        partner = partner_obj._find_partner_ept(partner_vals, address_key_list,
                                                [("parent_id", "=", parent_partner.id), ("type", "=", partner_type)])

        if not partner:
            partner = partner_obj._find_partner_ept(partner_vals, address_key_list,
                                                    [("parent_id", "=", parent_partner.id)])
        if not partner:
            partner = partner_obj._find_partner_ept(partner_vals, address_key_list)
            if partner and not partner.child_ids and partner_type == 'invoice':
                partner.write({"type": partner_type})

        if partner:
            if not partner.parent_id:
                partner = self.update_partner_with_company(instance, shopify_customer_data, parent_partner, partner)
            if parent_partner.email:
                partner.write({'email': parent_partner.email})
            return partner

        partner_vals.update({"type": partner_type, "parent_id": parent_partner.id})
        if parent_partner.email:
            partner_vals.update({'email': parent_partner.email})
        partner = partner_obj.create(partner_vals)

        company_name and partner.write({"company_name": company_name})
        partner = self.update_partner_with_company(instance, shopify_customer_data, parent_partner, partner)
        if instance.import_customer_as_company and partner.parent_id:
            partner.company_name = False

        return partner

    def shopify_prepare_partner_vals(self, vals, instance=False):
        """
        This method used to prepare a partner vals.
        @param : self,vals
        @return: partner_vals
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 29 August 2020 .
        Task_id: 165956
        @change : pass lang on vals by Nilam Kubavat for task id : 190111 at 19/05/2022
        """
        partner_obj = self.env["res.partner"]

        first_name = vals.get("first_name")
        last_name = vals.get("last_name")
        name = "%s %s" % (first_name, last_name)

        zipcode = vals.get("zip")
        state_code = vals.get("province_code")

        country_code = vals.get("country_code")
        country = partner_obj.get_country(country_code)

        state = partner_obj.create_or_update_state_ept(country_code, state_code, zipcode, country)

        partner_vals = {
            "email": vals.get("email") or False,
            "name": name,
            "phone": vals.get("phone"),
            "street": vals.get("address1"),
            "street2": vals.get("address2"),
            "city": vals.get("city"),
            "zip": zipcode,
            "state_id": state and state.id or False,
            "country_id": country and country.id or False,
            "is_company": False,
            'lang': instance.shopify_lang_id.code if instance != False else None,
        }
        update_partner_vals = partner_obj.remove_special_chars_from_partner_vals(partner_vals)
        return update_partner_vals

    def create_customer_as_company(self, vals, partner):
        """
        :param vals:
        :param partner:
        :return:
        """
        partner_obj = self.env["res.partner"]
        # company = partner_obj.search(['|', ('name', '=', vals.get('company')),
        #                               ('email', '=', vals.get('email')),
        #                               ('is_company', '=', True)])
        company = partner_obj.search([('name', '=', vals.get('company')), ('is_company', '=', True)])
        partner_id = False
        if partner and partner.parent_id:
            partner_id = partner.parent_id.id
        elif partner and not partner.parent_id:
            partner_id = partner.id
        if not company:
            partner_vals = {
                "name": vals.get('company'),
                "is_company": True,
                "customer_rank": 1,
                # 'parent_id': partner.parent_id if partner and partner.parent_id else partner
                'parent_id': partner_id
            }
            company = partner_obj.create(partner_vals)
        return company

    def update_partner_with_company(self, instance, address_details, parent_partner, partner):
        """
        :param instance:
        :param address_details:
        :param parent_partner:
        :param partner:
        :return:
        """
        if address_details.get('company') and instance.import_customer_as_company:
            company_id = self.create_customer_as_company(address_details, parent_partner)
            if not parent_partner:
                if company_id and not partner.parent_id and company_id.parent_id != partner:
                    partner.parent_id = company_id
            else:
                if company_id and company_id.parent_id != partner:
                    partner.parent_id = company_id
        return partner
