from odoo import _, api, fields, models
from odoo.exceptions import ValidationError, UserError
from odoo.osv import expression

import logging

_logger = logging.getLogger(__name__)

class AccountJournal(models.Model):
    _inherit = "account.journal"

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
        related="company_id.subsidiary",
        string="Company Subsidiary",
    )

    @api.model
    def get_domain_subsidiaries_suitable_journals(self, domain, id_record_parent_subsidiary=None):

        if not id_record_parent_subsidiary:
            domain = expression.AND(
                [
                    domain,
                    [
                        "|",
                        ("subsidiary_id", "in", self.env.user.subsidiary_ids.ids),
                        ("subsidiary_id", "=", False),
                    ],
                ]
            )

            return domain

        domain = expression.AND(
            [
                domain,
                [
                    "|",
                    ("subsidiary_id", "=", id_record_parent_subsidiary),
                    ("subsidiary_id", "=", False),
                ],
            ]
        )

        return domain

    def _get_distinc_subsidiaries_where_journal_was_used_by_model(
        self, model_name, subsidiary_field_name, journal_field_name
    ):
        self.ensure_one()

        _cr = self.env.cr

        sql = """
            SELECT 
	            DISTINCT %s
            FROM 
                %s
            WHERE %s = %s and company_id = %s and %s IS NOT NULL
            ;
        """ % (
            subsidiary_field_name,
            model_name,
            journal_field_name,
            self.id,
            self.company_id.id,
            subsidiary_field_name,
        )

        _cr.execute(sql)

        # dict_record_fetched =  _cr.dictfetchall()
        dict_record_fetched = _cr.dictfetchall()

        return dict_record_fetched

    def check_journal_selected(self, id_account_analytic):
        self.ensure_one()

        if self.subsidiary_id.id in [False, id_account_analytic]:
            return

        raise UserError(
            _(
                "The subsidiary of either journal and record must be the same",
            )
        )

    def _get_distinc_subsidiaries_where_journal_was_used(self):
        self.ensure_one()

        # There is no need for account_payment, because when you create a payment record, this creates an account_move and the journal cannot be changed and when
        # you change the subsidiary the value of the payment field of the related account_move branch changes to the same
        account_move_count = self._get_distinc_subsidiaries_where_journal_was_used_by_model(
            "account_move", "account_analytic_id", "journal_id"
        )
        purchase_order_count = self._get_distinc_subsidiaries_where_journal_was_used_by_model(
            "purchase_order", "account_analytic_id", "journal_invoice_id"
        )

        subsidiaries = [
            dict_subsidiary.get("account_analytic_id", None)
            for dict_subsidiary in account_move_count + purchase_order_count
        ]

        return subsidiaries

    @api.constrains("subsidiary_id")
    def _constraint_change_subsidiary_id(self):
        for record in self:
            
            distinc_subsidiaries_where_journal_was_used = (
                record._get_distinc_subsidiaries_where_journal_was_used()
            )
            count_distinc_subsidiary = len(distinc_subsidiaries_where_journal_was_used)

            if not record.subsidiary_id.id or count_distinc_subsidiary == 0:
                continue

            if (
                count_distinc_subsidiary == 1
                and record.subsidiary_id.id in distinc_subsidiaries_where_journal_was_used
            ):
                continue
            raise ValidationError(
                _("The journal has been used in payments, account movements or purchase orders")
            )
