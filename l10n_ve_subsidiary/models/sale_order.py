from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _default_subsidiary_id(self):
        subsidiary = self.env.user.subsidiary_id.id if self.env.company.subsidiary else False
        return subsidiary

    subsidiary_id = fields.Many2one(
        "account.analytic.account",
        string="Subsidiary",
        domain=lambda self: (
            f"[('is_subsidiary', '=', True),('id', 'in', {self.env.user.subsidiary_ids.ids})]"
        ),
        default=_default_subsidiary_id,
        store=True,
        readonly=False,
        tracking=True,
    )

    company_subsidiary = fields.Boolean(
        related='company_id.subsidiary', string="Company Subsidiary",
    )

    def _prepare_invoice(self):
        res = super(SaleOrder, self)._prepare_invoice()
        res.update(
            {
                "account_analytic_id": self.subsidiary_id.id,
            }
        )
        return res

    def correccion_subsidiary_order(self):
        for order in self:
            if order.warehouse_id:
                order.subsidiary_id = (order.warehouse_id.subsidiary_id 
                                        if order.subsidiary_id.id != order.warehouse_id.subsidiary_id.id 
                                        else order.subsidiary_id
                                    )
