import base64
from odoo import http, fields, _
from odoo.http import request

# Importa la clase del controlador original.
# Ajusta 'binaural_memberships' al nombre real del módulo base.
from odoo.addons.binaural_memberships.controllers.portal import (
    BinauralCustomerPortal,
)
import logging

_logger = logging.getLogger(__name__)


class CadipaMembershipsController(BinauralCustomerPortal):

    @http.route(
        "/my/memberships/add_guest/<int:membership_id>",
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
    )
    def add_membership_guest(self, membership_id, **post):
        response = super(CadipaMembershipsController, self).add_membership_guest(
            membership_id, **post
        )

        if response.location and "error=" in response.location:
            return response

        profile_image = post.get("profile_image")

        if profile_image and hasattr(profile_image, "read"):
            try:
                file_content = profile_image.read()
                if file_content:
                    encoded_image = base64.b64encode(file_content)

                    Partner = request.env["res.partner"].sudo()
                    partner_to_update = False

                    prefix = post.get("vat_prefix")
                    identification = post.get("identification")

                    if prefix and identification:
                        partner_to_update = Partner.search(
                            [("prefix_vat", "=", prefix), ("vat", "=", identification)],
                            limit=1,
                        )
                    else:
                        owner_partner = request.env.user.partner_id
                        partner_to_update = Partner.search(
                            [
                                ("parent_id", "=", owner_partner.id),
                                ("name", "=", post.get("name")),
                                ("type_relation", "=", post.get("type_relation")),
                            ],
                            order="create_date desc",
                            limit=1,
                        )

                    if partner_to_update:
                        partner_to_update.write({"image_1920": encoded_image})
                        _logger.info(
                            f"Image updated for affiliate: {partner_to_update.name}"
                        )

            except Exception as e:
                _logger.error(
                    f"Error uploading photo for affiliate in membership {membership_id}: {str(e)}"
                )

        return response
