import logging

from odoo import _, fields, models, api

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    transfer_reason_id = fields.Many2one(
        "transfer.reason",
        string="Reason for Transfer",
        domain="[('id', 'in', allowed_reason_ids)]",
        tracking=True,
    )

    allowed_reason_ids = fields.Many2many(
        "transfer.reason",
        string="Allowed Reasons",
        store=True,
        compute="_compute_allowed_reason_ids",
    )

    is_donation = fields.Boolean(related="sale_id.is_donation")

    operation_code = fields.Selection(related="picking_type_id.code")

    @api.depends("is_donation", "operation_code")
    def _compute_allowed_reason_ids(self):
        for picking in self:
            allowed_reason_ids = []

            reason_refs = {
                "donation": "l10n_ve_inventory_book.transfer_reason_donation",
                "sale": "l10n_ve_inventory_book.transfer_reason_sale",
                "transfer_between_warehouses": "l10n_ve_inventory_book.transfer_reason_transfer_between_warehouses",
                "export": "l10n_ve_inventory_book.transfer_reason_export",
                "self_consumption": "l10n_ve_inventory_book.transfer_reason_self_consumption",
                "consignment": "l10n_ve_inventory_book.transfer_reason_consignment",
            }

            reasons = {
                key: self.env.ref(ref, raise_if_not_found=False) for key, ref in reason_refs.items()
            }

            is_outgoing = picking.operation_code == "outgoing"
            is_return = picking.return_id
            has_sale = bool(picking.sale_id)

            _logger.info(
                "is_outgoing: %s, has_sale: %s, reasons: %s",
                is_outgoing,
                has_sale,
                reason_refs,
            )

            # Outgoing with sale
            if is_outgoing and has_sale:
                donation_reason = reasons.get("donation")
                sale_reason = reasons.get("sale")
                export_reason = reasons.get("export")

                _logger.info("entryyy")

                _logger.info(f"donation_reason: {donation_reason}")
                _logger.info(f"picking.is_donation: {picking.is_donation}")

                ## Donations
                if picking.is_donation and donation_reason:
                    allowed_reason_ids.append(donation_reason.id)

                    _logger.debug("Transfer reason set to donation")
                    picking.transfer_reason_id = donation_reason.id

                ## Without Donations
                else:
                    if sale_reason:
                        allowed_reason_ids.append(sale_reason.id)
                        if not picking.transfer_reason_id:
                            picking.transfer_reason_id = sale_reason.id
                    if export_reason:
                        allowed_reason_ids.append(export_reason.id)

            # Outgoing without sale
            elif is_outgoing and not has_sale and not is_return:
                self_consumption_reason = reasons.get("self_consumption")
                if self_consumption_reason:
                    allowed_reason_ids.append(self_consumption_reason.id)

            # Force update of transfer_reason_id field to avoid inconsistencies
            if allowed_reason_ids:
                if picking.transfer_reason_id.id not in allowed_reason_ids:
                    picking.transfer_reason_id = allowed_reason_ids[0]

            # if not allowed_reason_ids, then return all options
            picking.allowed_reason_ids = (
                self.env["transfer.reason"].search([])
                if not allowed_reason_ids
                else self.env["transfer.reason"].search([("id", "in", allowed_reason_ids)])
            )
