from odoo import api, fields, models, _


class AccountMove(models.Model):
    _inherit = "account.move"

    account_analytic_id = fields.Many2one(
        "account.analytic.account",
        string="Subsidiary",
        domain=[("is_subsidiary", "=", True)],
        default=lambda self: self.env.user.subsidiary_id,
    )

    # We need to override the create and write methods to update the analytic distribution of the
    # lines when the analytic account is changed. We don't use the compute method because it is
    # called before the write method and we need the old analytic account to update the analytic
    # distribution.

    @api.model_create_multi
    def create(self, vals_list):
        """
        Override the create method to set the analytic distribution of the lines when the analytic
        account (subsidiary) is set.
        """
        moves = super().create(vals_list)
        for move in moves:
            self.invoice_origin_purchase(moves)
            if not move.account_analytic_id or not move.line_ids:
                continue
            for line in move.line_ids:
                analytic_distribution = line.analytic_distribution or {}
                analytic_distribution[str(move.account_analytic_id.id)] = 100.0
                line.analytic_distribution = analytic_distribution
        return moves

    def write(self, vals):
        """
        Override the write method to update the analytic distribution of the lines when the analytic
        account (subsidiary) is changed.

        We need to override the write method because the compute method is called before the write
        method and we need the old subsidiary to update the analytic distribution.
        """
        if not vals.get("account_analytic_id") or not self.line_ids:
            return super().write(vals)
        old_account_analytic_id = str(self.account_analytic_id.id)
        res = super().write(vals)
        for line in self.line_ids:
            analytic_distribution = line.analytic_distribution or {}
            if old_account_analytic_id in analytic_distribution:
                del analytic_distribution[old_account_analytic_id]
            analytic_distribution[str(self.account_analytic_id.id)] = 100.0
            line.analytic_distribution = analytic_distribution
        return res

    @api.model
    def _get_new_analytic_distribution_dicts_list(self, move, vals):
        analytic_distributions = []
        if not vals.get("account_analytic_id") or not move.line_ids:
            return analytic_distributions
        old_account_analytic_id = move.account_analytic_id.id
        new_account_analytic_id = vals["account_analytic_id"]
        for line in move.line_ids:
            analytic_distribution = line.analytic_distribution or {}
            if not old_account_analytic_id in analytic_distribution:
                analytic_distribution[new_account_analytic_id] = 100.0
            else:
                del analytic_distribution[old_account_analytic_id]
                analytic_distribution[new_account_analytic_id] = 100.0
            analytic_distributions.append(analytic_distribution)
        return analytic_distributions

    def action_register_payment(self):
        """
        Override the action_register_payment method to send the default analytic account
        (sbusidiary) to the payment wizard.
        """
        res = super().action_register_payment()
        res["context"]["default_account_analytic_id"] = self.account_analytic_id.id
        return res

    def invoice_origin_purchase(self, moves):
        for invoice in moves:
            if invoice.invoice_origin and invoice.move_type in (
                "out_invoice",
                "out_refund",
                "in_invoice",
                "in_refund",
            ):
                purchase_order = self.env["purchase.order"].search(
                    [
                        ("name", "=", invoice.invoice_origin),
                        ("company_id", "=", self.env.company.id),
                    ]
                )
                if purchase_order:
                    invoice.account_analytic_id = purchase_order.account_analytic_id
