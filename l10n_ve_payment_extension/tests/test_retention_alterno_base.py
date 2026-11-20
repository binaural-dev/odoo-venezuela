from odoo import Command, fields
from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_retention_alterno_base")
class TestRetentionAlternoBase(TransactionCase):
    """Editing the alterno (Bs) taxable income of a supplier retention line recomputes its
    company currency (USD) amounts and the payment of the retention (ticket 15769).

    Country Club case: supplier invoice of 204,00 USD with 16 % VAT and 65,00 USD exempt at
    860,1753. The ISLR is computed on the subtotal (269,00 USD); the user sets the Bs base to
    55.911,44 Bs (the exempt service line), so the retention is 1,30 USD / 1.118,23 Bs at 2 %.
    """

    RATE = 860.1753
    BASE_BS = 55911.44

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        if cls.company.currency_id == cls.env.ref("base.VEF"):
            cls.skipTest(cls, "The case needs a company currency other than VEF.")
        cls.vef = cls.company.currency_foreign_id
        cls.date = fields.Date.context_today(cls.env["res.partner"])
        Rate = cls.env["res.currency.rate"]
        Rate.search(
            [
                ("currency_id", "=", cls.vef.id),
                ("company_id", "=", cls.company.id),
                ("name", "=", cls.date),
            ]
        ).unlink()
        Rate.create(
            {
                "name": cls.date,
                "rate": cls.RATE,
                "currency_id": cls.vef.id,
                "company_id": cls.company.id,
            }
        )
        if not cls.company.islr_supplier_retention_journal_id:
            cls.skipTest(cls, "The company needs a journal for ISLR supplier retentions.")
        if not cls.company.municipal_supplier_retention_journal_id:
            cls.company.municipal_supplier_retention_journal_id = (
                cls.company.islr_supplier_retention_journal_id
            )
        Tax = cls.env["account.tax"]
        tax_domain = [("type_tax_use", "=", "purchase"), ("company_id", "=", cls.company.id)]
        cls.tax_16 = Tax.search(
            tax_domain + [("amount", "=", 16), ("price_include", "=", False)], limit=1
        )
        cls.tax_0 = Tax.search(tax_domain + [("amount", "=", 0)], limit=1)
        cls.person_type = cls.env["type.person"].create({"name": "PJ Domiciliada 15769"})
        tax_unit = cls.env["tax.unit"].search([("status", "=", True)], limit=1) or cls.env[
            "tax.unit"
        ].create({"name": "UT 15769", "value": 9.0, "status": True})
        tariff = cls.env["fees.retention"].create(
            {"name": "Tarifa 2 % 15769", "percentage": 2.0, "tax_unit_ids": tax_unit.id}
        )
        cls.concept = cls.env["payment.concept"].create(
            {
                "name": "(Contratista) Servicios 15769",
                "line_payment_concept_ids": [
                    Command.create(
                        {
                            "code": "15769",
                            "type_person_id": cls.person_type.id,
                            "percentage_tax_base": 100.0,
                            "tariff_id": tariff.id,
                        }
                    )
                ],
            }
        )
        branch = cls.env["economic.branch"].create({"name": "Rama 15769", "status": "active"})
        municipality = cls.env["res.country.municipality"].search([], limit=1)
        cls.activity = cls.env["economic.activity"].create(
            {
                "name": "15769",
                "aliquot": 3.0,
                "branch_id": branch.id,
                "municipality_id": municipality.id,
                "description": "Servicios 15769",
                "minimum_monthly": 0,
                "minimum_annual": 0,
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Proveedor 15769",
                "vat": "J157690001",
                "type_person_id": cls.person_type.id,
                "economic_activity_id": cls.activity.id,
            }
        )
        cls.product = cls.env["product.product"].create(
            {"name": "Servicio 15769", "type": "service"}
        )

    def _invoice(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "invoice_date": self.date,
                "date": self.date,
                "ref": f"15769-{self.env['account.move'].search_count([])}",
                "currency_id": self.company.currency_id.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "price_unit": 204.0,
                            "tax_ids": [Command.set(self.tax_16.ids)],
                        }
                    ),
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "price_unit": 65.0,
                            "tax_ids": [Command.set(self.tax_0.ids)],
                        }
                    ),
                ],
            }
        )
        invoice.action_post()
        self.assertEqual(invoice.foreign_rate, self.RATE)
        return invoice

    def _retention(self, invoice, type_retention, base_bs, edit_after_save=False):
        view = self.env.ref(
            f"l10n_ve_payment_extension.view_retention_{type_retention}"
            "_form_l10n_ve_payment_extension"
        )
        form = Form(
            self.env["account.retention"].with_context(
                default_type="in_invoice", default_type_retention=type_retention
            ),
            view=view,
        )
        form.partner_id = self.partner
        with form.retention_line_ids.new() as line:
            line.move_id = invoice
            if type_retention == "islr":
                line.payment_concept_id = self.concept
            else:
                line.economic_activity_id = self.activity
            if not edit_after_save:
                line.foreign_invoice_amount = base_bs
        retention = form.save()
        if edit_after_save:
            self._edit_base(retention, base_bs)
        return retention

    def _edit_base(self, retention, base_bs):
        view = self.env.ref(
            f"l10n_ve_payment_extension.view_retention_{retention.type_retention}"
            "_form_l10n_ve_payment_extension"
        )
        form = Form(retention, view=view)
        with form.retention_line_ids.edit(0) as line:
            line.foreign_invoice_amount = base_bs
        form.save()

    def _assert_amounts(self, retention, base_bs, percentage):
        usd = self.company.currency_id
        line = retention.retention_line_ids
        self.assertAlmostEqual(line.foreign_invoice_amount, base_bs, places=2)
        self.assertEqual(usd.round(line.invoice_amount), usd.round(base_bs / self.RATE))
        self.assertEqual(
            usd.round(line.retention_amount), usd.round(base_bs / self.RATE * percentage)
        )
        self.assertAlmostEqual(line.foreign_retention_amount, base_bs * percentage, places=2)

    def _assert_payment(self, retention):
        usd = self.company.currency_id
        line = retention.retention_line_ids
        payment = retention.payment_ids
        self.assertEqual(payment.amount, usd.round(line.retention_amount))
        foreign = self.vef.round(line.foreign_retention_amount)
        self.assertEqual(payment.retention_foreign_amount, foreign)
        payable = payment.move_id.line_ids.filtered("debit")
        self.assertEqual(payable.debit, payment.amount)
        self.assertEqual(self.vef.round(payable.foreign_debit), foreign)

    def test_islr_edit_base_before_save(self):
        invoice = self._invoice()
        retention = self._retention(invoice, "islr", self.BASE_BS)
        self._assert_amounts(retention, self.BASE_BS, 0.02)

        retention.action_post()

        self._assert_payment(retention)
        self.assertEqual(retention.payment_ids.amount, 1.30)
        self.assertEqual(self.vef.round(retention.payment_ids.retention_foreign_amount), 1118.23)

    def test_islr_edit_base_after_save(self):
        invoice = self._invoice()
        retention = self._retention(invoice, "islr", self.BASE_BS, edit_after_save=True)

        self._assert_amounts(retention, self.BASE_BS, 0.02)
        retention.action_post()
        self._assert_payment(retention)

    def test_islr_without_edit_keeps_invoice_subtotal(self):
        invoice = self._invoice()
        form = Form(
            self.env["account.retention"].with_context(
                default_type="in_invoice", default_type_retention="islr"
            ),
            view=self.env.ref(
                "l10n_ve_payment_extension.view_retention_islr_form_l10n_ve_payment_extension"
            ),
        )
        form.partner_id = self.partner
        with form.retention_line_ids.new() as line:
            line.move_id = invoice
            line.payment_concept_id = self.concept
        retention = form.save()

        line = retention.retention_line_ids
        self.assertEqual(line.invoice_amount, 269.0)
        retention.action_post()
        self.assertEqual(retention.payment_ids.amount, self.company.currency_id.round(269.0 * 0.02))

    def test_islr_post_again_takes_new_base(self):
        """Posting again from draft reuses the payment with the new amounts of the line."""
        invoice = self._invoice()
        retention = self._retention(invoice, "islr", self.BASE_BS)
        retention.action_post()
        payment = retention.payment_ids

        retention.action_draft()
        self._edit_base(retention, 50000.0)
        retention.action_post()

        self.assertEqual(retention.payment_ids, payment)
        self._assert_amounts(retention, 50000.0, 0.02)
        self._assert_payment(retention)

    def test_municipal_edit_base(self):
        invoice = self._invoice()
        retention = self._retention(invoice, "municipal", self.BASE_BS)
        self._assert_amounts(retention, self.BASE_BS, 0.03)

        retention.action_post()

        self._assert_payment(retention)
