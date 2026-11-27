from odoo import models


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _get_donation_vat(self):
        """Tax ID as it is printed in the donation documents: with its prefix
        (J-21232157-1), the one of the commercial partner."""
        self.ensure_one()
        partner = self.commercial_partner_id
        if not partner.vat:
            return ""
        return f"{partner.prefix_vat}-{partner.vat}" if partner.prefix_vat else partner.vat

    def _get_donation_address(self):
        """Address as it is printed in the donation documents: the street
        data, the city, the state (its name), the zip and the country, without
        the name of the contact that `contact_address` puts first."""
        self.ensure_one()
        parts = [
            self.street, self.street2, self.city, self.state_id.name, self.zip,
            self.country_id.name,
        ]
        return ", ".join(part for part in parts if part)
