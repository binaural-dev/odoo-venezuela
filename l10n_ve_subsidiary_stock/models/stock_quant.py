import logging

from odoo import _, api, models
from odoo.exceptions import UserError
from odoo.osv import expression
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class StockQuant(models.Model):
    _inherit = "stock.quant"

    def _domain_location_id(self):
        domain = super()._domain_location_id()
        if not domain:
            return
        _logger.warning("DOMAIN: %s", domain)
        list_domain = [*self.env.user.subsidiary_ids.ids, False]
        domain = expression.AND(
            [
                safe_eval(domain, {"context": self.env.context}),
                [("warehouse_id.subsidiary_id", "in", list_domain)],
            ]
        )
        return domain

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        if self.env.user.is_required_subsidiary and self.env.user.has_group('binaural_subsidiary_stock.permission_show_available_products'):
            domain.append(
                [
                    "location_id.warehouse_id.subsidiary_id",
                    "in",
                    [*self.env.user.subsidiary_ids.ids, False],
                ]
            )

        return super().search_read(
            domain=domain, fields=fields, offset=offset, limit=limit, order=order
        )

    @api.model
    def read_group(
        self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True
    ):
        if self.env.user.is_required_subsidiary and self.env.user.has_group('binaural_subsidiary_stock.permission_show_available_products'):
            domain.append(
                [
                    "location_id.warehouse_id.subsidiary_id",
                    "in",
                    [*self.env.user.subsidiary_ids.ids, False],
                ]
            )

        return super().read_group(domain, fields, groupby, offset, limit, orderby, lazy)

    @api.constrains("location_id")
    def _check_location_id(self):
        for record in self:
            if not (
                self.env.user.is_required_subsidiary and self.env.company.subsidiary
            ):
                continue

            if record.location_id.usage != "internal":
                continue

            if not record.location_id.warehouse_id.subsidiary_id and not self.env.user.can_transfer_to_warehouses_without_branch:
                raise UserError(
                    _("Assign a subsidiary to the location-related warehouse.")
                )

            if (
                record.location_id.warehouse_id.subsidiary_id.id
                not in self.env.user.subsidiary_ids.ids
            ) and not self.env.user.can_transfer_to_warehouses_without_branch:
                raise UserError(
                    _(
                        "You are trying to modify a record that does not belong to the subsidiaries related to your user."
                    )
                )

    def write(self, vals):
        if "inventory_quantity" in vals:
            for quant in self:
                if (
                    quant.company_id.subsidiary
                    and quant.location_id.warehouse_id.subsidiary_id.id
                    not in self.env.user.subsidiary_ids.ids
                ):
                    raise UserError(
                        _("You are not allowed to edit quantities in this subsidiary.")
                    )
        return super().write(vals)
