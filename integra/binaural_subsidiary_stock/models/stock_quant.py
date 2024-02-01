import logging

from odoo import _, api, models
from odoo.exceptions import UserError
from odoo.osv import expression


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
        domain.append(['location_id.warehouse_id.subsidiary_id', 'in', [*self.env.user.subsidiary_ids.ids, False]])

        return super().search_read(
            domain=domain, fields=fields, offset=offset, limit=limit, order=order
        )

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        domain.append(['location_id.warehouse_id.subsidiary_id', 'in', [*self.env.user.subsidiary_ids.ids, False]])

        return super().read_group(domain, fields, groupby, offset, limit, orderby, lazy)


    @api.constrains("location_id")
    def _check_location_id(self):
        for record in self:
            if not record.location_id.warehouse_id.subsidiary_id:
                continue

            if (
                record.location_id.warehouse_id.subsidiary_id
                not in self.env.user.subsidiary_ids.ids
            ):
                raise UserError(_("Subsidiary Stock Quant Rule"))
