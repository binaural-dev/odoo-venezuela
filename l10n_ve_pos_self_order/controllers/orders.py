from odoo import http

from odoo.addons.pos_self_order.controllers.orders import PosSelfOrderController


class L10nVePosSelfOrderController(PosSelfOrderController):
    """Kiosk customer identification by cédula/RIF for the Venezuelan Self
    Order flow.

    ``l10n_ve_pos`` forces ``to_invoice=True`` on every POS order (SENIAT
    requirement), so the Kiosk must identify the customer before the order is
    built instead of billing the generic consumer. These two public routes are
    called by ``IdentificationPage`` at the very start of the order:

    * ``identify`` looks up an existing partner by ``prefix_vat`` + ``vat``.
    * ``identify_create`` creates a new partner when the cédula is unknown.

    Both reuse the core ``_verify_pos_config`` helper to validate the
    ``access_token`` and run under the pos.config's company/user context, and
    return only the fields the Kiosk needs (id, name, phone) plus the
    ``vat``/``prefix_vat`` the customer just typed to identify themselves — the
    cédula is not a leak (it is their own, already entered) and downstream
    payment integrations (e.g. Megasoft, ``binaural_megasoft_self_order``) read
    it from the order's partner instead of asking for it again.
    """

    @http.route(
        "/l10n_ve_pos_self_order/kiosk/identify",
        auth="public",
        type="jsonrpc",
        website=True,
    )
    def l10n_ve_kiosk_identify(self, access_token, prefix_vat, vat):
        pos_config = self._verify_pos_config(access_token)
        # Same match criterion as res.partner.check_duplicate_vat's domain
        # (prefix_vat + vat), without a company_id filter — res.partner is not
        # scoped by company in this codebase.
        partner = (
            pos_config.env["res.partner"]
            .sudo()
            .search([("prefix_vat", "=", prefix_vat), ("vat", "=", vat)], limit=1)
        )
        return {
            "res.partner": partner.read(
                ["id", "name", "phone", "vat", "prefix_vat"], load=False
            ),
        }

    @http.route(
        "/l10n_ve_pos_self_order/kiosk/identify/create",
        auth="public",
        type="jsonrpc",
        website=True,
    )
    def l10n_ve_kiosk_identify_create(self, access_token, prefix_vat, vat, name, phone):
        pos_config = self._verify_pos_config(access_token)
        partner_model = pos_config.env["res.partner"].sudo()

        vals = {
            "name": name,
            "phone": phone,
            "prefix_vat": prefix_vat,
            "vat": vat,
        }
        # Preload the company address defaults exactly like the reduced partner
        # form of the regular POS box does, via l10n_ve_pos's default_get gated
        # by the l10n_ve_pos_partner_defaults context flag. No new address logic.
        default_fields = list(partner_model._POS_COMPANY_DEFAULT_FIELDS)
        address_defaults = partner_model.with_context(
            l10n_ve_pos_partner_defaults=True
        ).default_get(default_fields)
        vals.update(address_defaults)

        # Create under the pos.config's company context (same env as the
        # lookup) so res.partner's default company_id resolves to the box's
        # company, mirroring how validate_partner creates with sudo().
        partner = partner_model.create(vals)
        return {
            "res.partner": partner.read(
                ["id", "name", "phone", "vat", "prefix_vat"], load=False
            ),
        }
