from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    subsidiary_id = fields.Many2one(
        "account.analytic.account",
        string="Subsidiary",
        domain=lambda self: (
            f"[('is_subsidiary', '=', True),('id', 'in', {self.env.user.subsidiary_ids.ids})]"
        ),
        compute="_compute_account_analytic_id",
        store=True,
        readonly=False,
        tracking=True,
    )

    company_subsidiary = fields.Boolean(
        related='company_id.subsidiary', store=True,
    )

    @api.depends('company_subsidiary')
    def _compute_account_analytic_id(self):
        for record in self:
            if record.subsidiary_id:
                continue
            record.subsidiary_id = self.env.user.subsidiary_id  if record.company_subsidiary else None

    def _prepare_invoice(self):
        res = super(SaleOrder, self)._prepare_invoice()
        res.update(
            {
                "account_analytic_id": self.subsidiary_id.id,
            }
        )
        return res

    def _compute_warehouse_id(self):
        for order in self:
            main_warehouse_id = self.env.company.main_warehouse_id
            user_warehouse_id = self.env.user.property_warehouse_id
            if order.state in ["draft", "sent"] or not order.ids:
                if not main_warehouse_id and not user_warehouse_id:
                    res = super()._compute_warehouse_id()
                    return
                order.warehouse_id = (
                    main_warehouse_id
                    if main_warehouse_id and not user_warehouse_id
                    else user_warehouse_id
                )
