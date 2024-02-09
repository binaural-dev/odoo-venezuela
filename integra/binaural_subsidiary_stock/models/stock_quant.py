import logging

from odoo import _, api, models
from odoo.exceptions import UserError
from odoo.osv import expression

_logger = logging.getLogger(__name__)

class StockQuant(models.Model):
    _inherit = "stock.quant"

    def _domain_location_id(self):
        domain = super()._domain_location_id()
        if not domain:
            return

        list_domain = [*self.env.user.subsidiary_ids.ids, False]
        domain = expression.AND(
            [
                domain,
                [("warehouse_id.subsidiary_id", "in", list_domain)],
            ]
        )
        return domain

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        if self.env.user.is_required_subsidiary:
            domain.append(['location_id.warehouse_id.subsidiary_id', 'in', [*self.env.user.subsidiary_ids.ids, False]])

        return super().search_read(
            domain=domain, fields=fields, offset=offset, limit=limit, order=order
        )

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        if self.env.user.is_required_subsidiary:
            domain.append(['location_id.warehouse_id.subsidiary_id', 'in', [*self.env.user.subsidiary_ids.ids, False]])

        return super().read_group(domain, fields, groupby, offset, limit, orderby, lazy)


    @api.constrains("location_id")
    def _check_location_id(self):
        for record in self:

            if not self.env.user.is_required_subsidiary:
                continue

            if record.location_id.usage not in ['transit', 'internal']:
                continue

            if not record.location_id.warehouse_id.subsidiary_id:
                raise UserError(_("Assign a subsidiary to the location-related warehouse."))

            if (
                record.location_id.warehouse_id.subsidiary_id.id
                not in self.env.user.subsidiary_ids.ids
            ):
                raise UserError(_("You are trying to modify a record that does not belong to the subsidiaries related to your user."))
