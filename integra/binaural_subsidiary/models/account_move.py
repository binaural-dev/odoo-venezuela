from odoo import _, api, fields, models
from odoo.osv import expression


class AccountMove(models.Model):
    _inherit = "account.move"

    account_analytic_id = fields.Many2one(
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
        related='company_id.subsidiary', store=True, string="Company Subsidiary",
    )

    @api.depends('company_id', 'invoice_filter_type_domain')
    def _compute_suitable_journal_ids(self):
        for m in self:
            journal_type = m.invoice_filter_type_domain or 'general'
            company_id = m.company_id.id or self.env.company.id
            domain = [('company_id', '=', company_id), ('type', '=', journal_type)]

            domain = expression.AND([domain, ['|', ('subsidiary_id', 'in', self.env.user.subsidiary_ids.ids), ('subsidiary_id', '=', False)]])

            m.suitable_journal_ids = self.env['account.journal'].search(domain)

    # It's needed to inherit the create and write methods to update the analytic distribution of the
    # lines when the analytic account is changed. The compute method isn't used because it is
    # called before the write method and we need the old analytic account to update the analytic
    # distribution.
    @api.depends('company_subsidiary')
    def _compute_account_analytic_id(self):
        for record in self:
            if record.account_analytic_id:
                continue
            record.account_analytic_id = self.env.user.subsidiary_id  if record.company_subsidiary else None

    @api.model_create_multi
    def create(self, vals_list):
        """
        Inherits the create method to set the analytic distribution of the lines when the analytic
        account (subsidiary) is set.
        """
        moves = super().create(vals_list)
        if self.env.context.get("skip_subsidiaries_setting", False):
            return moves
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
        Inherits the write method to update the analytic distribution of the lines when the analytic
        account (subsidiary) is changed.

        We need to extend the write method because the compute method is called before the write
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
        Inherits the action_register_payment method to send the default analytic account
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

    def correccion_subsidiary(self):
        for move in self:
            if move.invoice_line_ids:
                subsidiary_id = move.invoice_line_ids[0].analytic_distribution
                if subsidiary_id:
                    subsidiary_id = subsidiary_id.keys()
                    for subsidiary in subsidiary_id:
                        subsidiary_id = subsidiary
                    move.account_analytic_id = self.env['account.analytic.account'].search([('id', '=', subsidiary_id)])