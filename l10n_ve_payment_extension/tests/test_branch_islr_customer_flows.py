from odoo import Command, fields
from odoo.tests import Form, tagged

from .retention_flow_helpers import RetentionFlowHelpers
from .test_withholding_common_VEF import RetentionTestCommon

LINE_FIELDS = (
    "invoice_total",
    "related_percentage_tax_base",
    "related_percentage_fees",
    "retention_amount",
)


@tagged("post_install", "-at_install", "branch_fiscal_propagation")
class TestBranchIslrCustomerFlows(RetentionFlowHelpers, RetentionTestCommon):
    """Ticket #16438: la retencion ISLR de cliente con una sucursal como empresa
    activa debe calcular igual que con la casa matriz, tanto la que genera solo la
    factura al publicarse como la que el usuario crea a mano. Ambas se arman con
    `Form`.

    Las lineas ISLR de cliente toman el tipo de persona del contacto de la empresa
    activa; el de la sucursal lo hereda de la matriz. El caso de control vacia esos
    campos en la sucursal (saltandose la constraint) para comprobar que sin la
    herencia la linea queda en cero."""

    def setUp(self):
        super().setUp()
        self.accounting_date = fields.Date.today()
        self.doc_date = self.accounting_date
        type_person = self.env.ref("l10n_ve_payment_extension.type_person_l10n_ve_payment_extension")
        self.company.partner_id.write({
            "type_person_id": type_person.id,
            "withholding_type_id": self.env.ref(
                "l10n_ve_payment_extension.account_withholding_type_75"
            ).id,
            "taxpayer_type": "formal",
        })
        self.branch = self.env["res.company"].create({
            "name": "Sucursal ISLR 16438",
            "parent_id": self.company.id,
            "currency_id": self.currency_vef.id,
            "foreign_currency_id": self.currency_usd.id,
            "country_id": self.company.country_id.id,
            "account_fiscal_country_id": self.company.account_fiscal_country_id.id,
        })
        self.env.user.company_ids |= self.branch
        self.assertEqual(self.branch.partner_id.type_person_id, type_person)

        Account = self.Account.with_company(self.branch)

        def branch_account(code, account_type, name, reconcile=False):
            return Account.create({
                "code": code,
                "name": name,
                "account_type": account_type,
                "reconcile": reconcile,
                "company_ids": [Command.set(self.branch.ids)],
            })

        acc_receivable = branch_account("B16438R", "asset_receivable", "CxC Sucursal", True)
        acc_income = branch_account("B16438I", "income", "Ingresos Sucursal")
        acc_bank = branch_account("B16438B", "asset_cash", "Banco Sucursal")
        self.branch_sale_journal = self.Journal.create({
            "name": "Ventas Sucursal 16438", "type": "sale", "code": "BS16",
            "company_id": self.branch.id, "currency_id": self.currency_vef.id,
            "default_account_id": acc_income.id,
        })
        bank_journal = self.Journal.create({
            "name": "Banco Sucursal 16438", "type": "bank", "code": "BB16",
            "company_id": self.branch.id, "currency_id": self.currency_vef.id,
            "default_account_id": acc_bank.id,
        })
        self.branch.write({
            "islr_supplier_retention_journal_id": bank_journal.id,
            "islr_customer_retention_journal_id": bank_journal.id,
        })
        # Propiedades dependientes de la compania: las de la matriz no aplican a la sucursal.
        self.partner_pnr_75.with_company(self.branch).write({
            "property_account_receivable_id": acc_receivable.id,
        })
        self.product_islr_one.with_company(self.branch).write({
            "property_account_income_id": acc_income.id,
        })

    def _branch_document(self):
        return self._form_document(
            "out_invoice", "islr", self.AMOUNT,
            company=self.branch, journal=self.branch_sale_journal,
        )

    def _post(self, document):
        document.with_context(move_action_post_alert=True).action_post()
        return document

    def _clear_branch_fiscal_fields(self):
        """Branch contact without the fiscal data, as before the fix. Direct SQL because
        the constraint of the contact (rightly) forbids it."""
        self.env.flush_all()  # pending ORM writes would overwrite the raw SQL below
        self.env.cr.execute(
            "UPDATE res_partner SET type_person_id = NULL, withholding_type_id = NULL,"
            " taxpayer_type = NULL WHERE id = %s",
            (self.branch.partner_id.id,),
        )
        self.env.invalidate_all()

    def _auto_islr_line(self, document):
        with Form(document) as form:
            form.generate_islr_retention = True
        document = self._post(form.save())
        line = document.retention_islr_line_ids
        self.assertEqual(len(line), 1, "La factura debe generar una linea de retencion ISLR.")
        return line

    def _manual_islr_line(self, document, company=None):
        retention = self._retention_from_form("islr", document, company=company)
        line = retention.retention_line_ids
        self.assertEqual(len(line), 1)
        self.assertEqual(line.move_id, document)
        return line

    def _values(self, line):
        return {fname: line[fname] for fname in LINE_FIELDS}

    def _assert_computed(self, values):
        for fname in LINE_FIELDS:
            self.assertTrue(values[fname], "%s no debe quedar en 0" % fname)
        self.assertEqual(values["related_percentage_tax_base"], self.islr_concept_line.percentage_tax_base)
        self.assertEqual(values["related_percentage_fees"], self.islr_tariff.percentage)

    def _assert_zero(self, values):
        for fname in LINE_FIELDS:
            self.assertFalse(values[fname], "%s debe quedar en 0 sin la herencia fiscal" % fname)

    def test_automatic_flow_on_branch_matches_main_company(self):
        main_values = self._values(self._auto_islr_line(
            self._form_document("out_invoice", "islr", self.AMOUNT)
        ))
        branch_line = self._auto_islr_line(self._branch_document())
        self.assertEqual(branch_line.company_id, self.branch)
        self.assertEqual(branch_line.retention_id.company_id, self.branch)
        branch_values = self._values(branch_line)
        self._assert_computed(branch_values)
        self.assertEqual(branch_values, main_values)

    def test_automatic_flow_on_branch_without_inherited_fields_stays_zero(self):
        document = self._branch_document()
        with Form(document) as form:
            form.generate_islr_retention = True
        document = form.save()
        self._clear_branch_fiscal_fields()
        self._post(document)
        line = document.retention_islr_line_ids
        self.assertEqual(len(line), 1)
        self._assert_zero(self._values(line))

    def test_manual_flow_on_branch_matches_main_company(self):
        main_document = self._post(self._form_document("out_invoice", "islr", self.AMOUNT))
        main_values = self._values(self._manual_islr_line(main_document))
        branch_document = self._post(self._branch_document())
        branch_line = self._manual_islr_line(branch_document, company=self.branch)
        self.assertEqual(branch_line.company_id, self.branch)
        branch_values = self._values(branch_line)
        self._assert_computed(branch_values)
        self.assertEqual(branch_values, main_values)

    def test_manual_flow_on_branch_without_inherited_fields_stays_zero(self):
        document = self._post(self._branch_document())
        self._clear_branch_fiscal_fields()
        line = self._manual_islr_line(document, company=self.branch)
        self._assert_zero(self._values(line))
