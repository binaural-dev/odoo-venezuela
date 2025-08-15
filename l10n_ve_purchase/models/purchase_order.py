from odoo import api, models

class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    @api.depends(
        "order_line.taxes_id",
        "order_line.price_unit",
        "amount_total",
        "amount_untaxed",
        "currency_id",
        "foreign_rate",
    )
    def _compute_tax_totals(self):
        # Adaptar el contexto para que el método de impuestos pueda recuperar el registro de la orden
        for order in self:
            ctx = self.env.context.copy()
            ctx.update({'active_id': order.id, 'active_model': order._name})
            order.with_context(ctx)._compute_tax_totals_base()

    def _compute_tax_totals_base(self):
        return super()._compute_tax_totals()
