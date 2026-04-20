from odoo import models, fields, api, _, Command
from odoo.exceptions import UserError, ValidationError

class AccountMove(models.Model):
    _inherit = "account.move"

    is_donation = fields.Boolean(string="Is Donation", tracking=True)

    can_reverse_donation_move = fields.Boolean(compute="_compute_can_reverse_donation_move")

    def _compute_can_reverse_donation_move(self):
        for move in self:
            move.can_reverse_donation_move = (
                self.env.user.has_group("l10n_ve_donation.group_donation_manager")
            )

    @api.constrains("is_donation", "line_ids","line_ids.partner_id")
    def _check_partner_donation(self):
        """Validate that all journal items of a donation move use the company partner."""
        for move in self:
            if not move.is_donation:
                continue
            company_partner = move.company_id.partner_id or self.env.company.partner_id
            if move.partner_id and move.partner_id != company_partner:
                raise ValidationError(
                    _(
                        "The contact on move '%(line)s' must be the company partner "
                        "('%(expected)s') when the entry is a donation. "
                        "Found: '%(found)s'.",
                        line=move.name or move.display_name,
                        expected=company_partner.name,
                        found=move.partner_id.name,
                    )
                )
            for line in move.line_ids.filtered(lambda l: l.partner_id):
                if line.partner_id != company_partner:
                    raise ValidationError(
                        _(
                            "The contact on journal item '%(line)s' must be the company partner "
                            "('%(expected)s') when the entry is a donation. "
                            "Found: '%(found)s'.",
                            line=line.name or line.display_name,
                            expected=company_partner.name,
                            found=line.partner_id.name,
                        )
                    )

    def print_donation_certificate(self):
        self.ensure_one()
        return self.env.ref("l10n_ve_donation.action_donation_certificate_account_move").report_action(self)

    def action_post(self):
        res = super().action_post()
        donation_moves = self.filtered(lambda m: m.is_donation and m.move_type == "out_invoice")
        donation_entries = self.filtered(lambda m: m.is_donation and m.move_type == "entry")
        for move in donation_moves:
            # ! FIXME: Buscar la manera de no ejecutar _post acá
            move._post(soft=True)
            wizard = self.env["account.move.reversal"].with_context(
                active_ids=self.ids,
                active_model="account.move"
            ).create({"date": fields.Date.today(), "journal_id": self.journal_id.id})
            wizard.reverse_moves()
            credit_note = wizard.new_move_ids
            credit_note.action_post()
            return res
        for move in donation_entries:
            company_partner = move.company_id.partner_id or self.env.company.partner_id
            for line in move.line_ids:
                line.write({"partner_id": company_partner.id})
        return res

    def _reverse_moves(self, default_values_list=None, cancel=False):
        """Reverse a recordset of account.move.
        If cancel parameter is true, the reconcilable or liquidity lines
        of each original move will be reconciled with its reverse's.
        :param default_values_list: A list of default values to consider per move.
        ('type' & 'reversed_entry_id' are computed in the method).
        :return: An account.move recordset, reverse of the current self.
        """
        donation_moves = self.filtered(lambda move: move.is_donation and move.move_type != "entry")
        if donation_moves:
            reverse_moves = self.env['account.move']
            default_values_list = default_values_list or [{} for _move in self]
            for move, default_values in zip(self, default_values_list):
                if not (move.is_donation and move.move_type != "entry"):
                    continue
                invoice_line_vals = move.product_line_donation()
                move_vals = {
                    "move_type": "out_refund",
                    "journal_id": move.journal_id.id,
                    "date": default_values.get("date", fields.Date.today()),
                    "ref": default_values.get("ref", move.ref),
                    "reversed_entry_id": move.id,
                    "partner_id": move.partner_id.id,
                    "is_donation": True,
                    "invoice_line_ids": invoice_line_vals,
                }
                reverse_move = self.env['account.move'].with_context(
                    check_move_validity=False,
                    skip_invoice_sync=True,
                ).create(move_vals)
                reverse_moves += reverse_move
            return reverse_moves

        return super()._reverse_moves(default_values_list, cancel)

    def _get_tax_grouped_lines(self):
        """
        Agrupa las líneas de factura por el conjunto de impuestos que tienen aplicados.
        Retorna un diccionario: { tuple(ids_impuestos): {'base': suma_base, 'taxes': recordset_impuestos} }
        """
        self.ensure_one()
        tax_groups = {}
        for line in self.invoice_line_ids:
            tax_ids = line.tax_ids.ids
            tax_key = tuple(sorted(tax_ids))

            if tax_key not in tax_groups:
                tax_groups[tax_key] = {
                    'base_amount': 0.0,
                    'taxes': line.tax_ids,
                }
            tax_groups[tax_key]['base_amount'] += line.price_subtotal
        return tax_groups

    def product_line_donation(self):
        """Adds the donation product lines to invoice_line_ids grouped by tax.
        Uses skip_invoice_sync=True to maintain consistency with manually 
        constructed tax lines in _reverse_moves.
        """
        product = self.env["product.template"].with_company(self.company_id).search(
            [("is_donation_product", "=", True)], limit=1
        )
        if not product:
            raise UserError(_("Please configure a donation product in the company settings. The product is type to service."))

        company = self.company_id or self.env.company
        donation_account_id = company.donation_account_id.id if company else False
        if not donation_account_id:
            raise UserError(_("Please configure a donation account in the company settings."))

        tax_data = self._get_tax_grouped_lines()

        invoice_line_vals = []
        for tax_key, data in tax_data.items():
            invoice_line_vals.append(
                Command.create(
                        {
                            "product_id": product.product_variant_ids[:1].id,
                            "account_id": donation_account_id,
                            "name": self.ref or product.name,
                            "quantity": 1,
                            "price_unit": data["base_amount"],
                            "tax_ids": [Command.set(data["taxes"].ids)],
                        }
                    )
                )
        return invoice_line_vals
 