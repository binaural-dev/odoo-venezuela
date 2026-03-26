from odoo import models, fields, api, _, Command
from odoo.exceptions import UserError, ValidationError

import logging

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = "account.move"

    guide_number = fields.Char(compute='_compute_guide_number', string="Guide Number", store=True)
    transfer_ids = fields.Many2many("stock.picking", string="Transfers")
    picking_ids = fields.Many2many("stock.picking", column1='account_move_id', column2= 'stock_picking_id', relation='pickings_invoice_rel')
    from_picking = fields.Boolean(string="From Picking", default=False)

    # 0: not printed yet, 1: first print (original), 2 or more: copies
    free_form_copy_number = fields.Integer(default=0, copy=False)

    is_donation = fields.Boolean(string="Is Donation", tracking=True)

    def print_invoice_free_form(self):

        report = self.env.ref(
            "l10n_ve_invoice.action_invoice_free_form_l10n_ve_invoice"
        )

        self.free_form_copy_number = self.free_form_copy_number + 1

        return report.report_action(self)

    @api.depends("picking_ids")
    def _compute_guide_number(self):
        for record in self:
            list_guide_number = [picking.guide_number for picking in record.picking_ids]
            record.guide_number = "/".join(list_guide_number)

    def print_donation_certificate(self):
        self.ensure_one()
        return self.env.ref("l10n_ve_stock_account.action_donation_certificate_account_move").report_action(self)

    def action_post(self):
        res = super().action_post()
        donation_moves = self.filtered(lambda m: m.is_donation and m.move_type == "out_invoice")
        for move in donation_moves:
            # ! FIXME: Buscar la manera de no ejecutar _post acá
            move._post(soft=True)
            wizard = self.env["account.move.reversal"].with_context(
        # Normalizar default_values_list para evitar errores al hacer zip
        if default_values_list is None:
            default_values_list = [{} for _ in self]

        # Si no hay moves de donación, delegar completamente al super
        if not self.filtered('is_donation'):
            return super()._reverse_moves(default_values_list, cancel)

        # Separar moves de donación y no donación junto con sus defaults
        donation_moves_with_defaults = []
        other_moves_with_defaults = []
        for move, default_values in zip(self, default_values_list):
            if move.is_donation:
                donation_moves_with_defaults.append((move, default_values or {}))
            else:
                other_moves_with_defaults.append((move, default_values or {}))

        reverse_moves = self.env['account.move']

        # Procesar moves que no son donación mediante la lógica estándar
        if other_moves_with_defaults:
            other_moves = self.env['account.move'].browse([m.id for m, _d in other_moves_with_defaults])
            other_defaults = [d for _m, d in other_moves_with_defaults]
            reverse_moves |= super(AccountMove, other_moves)._reverse_moves(other_defaults, cancel)

        # Procesar moves de donación con lógica específica
        for move, default_values in donation_moves_with_defaults:
            line_vals_list = []
            for line in move.line_ids:
                is_tax = bool(line.tax_line_id or line.display_type == 'tax')
                is_receivable = line.account_id.account_type == 'asset_receivable'
                if not (is_receivable or is_tax):
                    continue
                lv = {
                    "account_id": line.account_id.id,
                    "name": line.name,
                    "balance": -line.balance,
                    "amount_currency": -line.amount_currency,
                    "currency_id": line.currency_id.id,
                    "partner_id": line.partner_id.id,
                    "display_type": line.display_type,
                }
                if is_tax and line.tax_line_id:
                    lv['tax_line_id'] = line.tax_line_id.id
                line_vals_list.append((0, 0, lv))

            move_vals = {
                "move_type": "out_refund",
                "journal_id": move.journal_id.id,
                "date": default_values.get("date", fields.Date.today()),
                "ref": default_values.get("ref", move.ref),
                "reversed_entry_id": move.id,
                "partner_id": move.partner_id.id,
                "is_donation": True,
                "line_ids": line_vals_list,
            }
            reverse_move = self.env['account.move'].with_context(
                check_move_validity=False,
                skip_invoice_sync=True,
            ).create(move_vals)
            # Añadir línea de producto de donación a invoice_line_ids
            reverse_move.product_line_donation()
            reverse_moves |= reverse_move

        return reverse_moves
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
        product = self.env["product.template"].search(
            [("is_donation_product", "=", True)], limit=1
        )
        if not product:
            raise UserError(_("Please configure a donation product in the company settings."))

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
