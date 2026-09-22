from odoo.exceptions import UserError
from odoo import api, models, _, fields


class AccountJournal(models.Model):
    _inherit = "account.journal"

    # ESTA HERENCIA NO SE IMPORTARÁ PORQUE ESTÁ GENERANDO ERROR, AL SOLUCIONAR, VOLVER A AGREGAR EN EN IMPORT

    is_purchase_international = fields.Boolean(string="International purchase",default=False)

    @api.depends('default_account_id')
    def _compute_inbound_payment_method_line_ids(self):
        super()._compute_inbound_payment_method_line_ids()
        self._fill_payment_account_id_from_default()

    @api.depends('default_account_id')
    def _compute_outbound_payment_method_line_ids(self):
        super()._compute_outbound_payment_method_line_ids()
        self._fill_payment_account_id_from_default()

    def _fill_payment_account_id_from_default(self):
        for journal in self:
            if journal.type != 'bank' or not journal.default_account_id:
                continue
            all_lines = journal.inbound_payment_method_line_ids | journal.outbound_payment_method_line_ids
            for line in all_lines:
                if not line.payment_account_id:
                    line.payment_account_id = journal.default_account_id

    @api.model
    def _create_default_account(self, company, journal_type, vals):
        if self.env.context.get('skip_default_account_autofill'):
            return False
        return super()._create_default_account(company, journal_type, vals)

    @api.constrains('default_account_id', 'type')
    def _check_default_account_id_required_for_bank(self):
        for journal in self:
            if journal.type == 'bank' and not journal.default_account_id:
                raise UserError(
                    _("Bank journals require a default account (Bank Account).")
                )

    @api.model_create_multi
    def create(self, vals_list):

        for vals in vals_list:
            self._validate_support_user_group(vals)

        return super().create(vals_list)

    @api.constrains('inbound_payment_method_line_ids', 'outbound_payment_method_line_ids')
    def _check_payment_method_line_accounts(self):

        if self.env.context.get('chart_template_load') or self.env.context.get('install_mode'):
            return

        for journal in self:

            if journal.type == 'bank':
                if not journal.inbound_payment_method_line_ids:
                    raise UserError(_(
                        "Journal \"%(journal)s\" must have at least one inbound payment method.",
                        journal=journal.display_name,
                    ))

                if not journal.outbound_payment_method_line_ids:
                    raise UserError(_(
                        "Journal \"%(journal)s\" must have at least one outbound payment method.",
                        journal=journal.display_name,
                    ))

                all_lines = journal.inbound_payment_method_line_ids | journal.outbound_payment_method_line_ids
                if not all_lines.mapped('payment_account_id'):
                    raise UserError(_("All payment methods must have an assigned account."))

    @api.constrains('is_purchase_international')
    def _check_single_international_purchase_journal(self):
        for record in self:
            if record.is_purchase_international:
                domain = [
                    ('is_purchase_international', '=', True),
                    ('id', '!=', record.id),
                ]

                if self.search_count(domain) > 0:
                    raise UserError(
                        _("An International Purchase Journal is already enabled. Only one is allowed.")
                    )


    def write(self, vals):
        for record in self:
            if "type" in vals:
                record._validate_support_user_group(vals)
        return super().write(vals)

    def _validate_support_user_group(self, vals):
        user = self.env.user
        is_support_user = user.has_group("l10n_ve_accountant.group_support_user")

        if not is_support_user:
            if vals["type"] not in ["bank", "general", "cash"]:

                raise UserError(
                    _(
                        "You do not have permissions to create/update a journal with this type."
                    )
                )

        return
