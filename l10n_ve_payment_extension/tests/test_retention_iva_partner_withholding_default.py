from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from .test_withholding_common_VEF import RetentionTestCommon


@tagged("post_install", "-at_install", "retention_iva_partner_default")
class TestRetentionIvaPartnerWithholdingDefault(RetentionTestCommon):
    """Ticket 86944: the withholding type a partner gets by default from its
    person type and taxpayer type is the one its vendor bill needs to generate
    the IVA retention (a partner without it makes the bill fail to post)."""

    def _post_bill_with_iva_retention(self, type_person_xmlid, taxpayer_type):
        partner = self.env["res.partner"].create({
            "name": "Proveedor %s %s" % (type_person_xmlid, taxpayer_type),
            "vat": "J%09d" % self.env["res.partner"].search_count([]),
            "property_account_receivable_id": self.acc_receivable.id,
            "property_account_payable_id": self.acc_payable.id,
            "type_person_id": self.env.ref(
                "l10n_ve_payment_extension." + type_person_xmlid
            ).id,
            "taxpayer_type": taxpayer_type,
        })
        partner._apply_default_withholding_type()
        bill = self._create_invoice_reten_iva(
            amount=200, partner=partner, out_invoice="in_invoice",
            journal=self.purchase_journal,
        )
        bill.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        bill.generate_iva_retention = True
        bill.action_post()
        return partner, bill

    def test_vendor_bill_posts_with_the_default_withholding_type(self):
        for xmlid, taxpayer_type, expected in (
            ("type_person_three_l10n_ve_payment_extension", "ordinary", "75"),
            ("type_person_two_l10n_ve_payment_extension", "ordinary", "100"),
            ("type_person_four_l10n_ve_payment_extension", "ordinary", "100"),
        ):
            with self.subTest(xmlid=xmlid):
                partner, bill = self._post_bill_with_iva_retention(
                    xmlid, taxpayer_type
                )
                self.assertEqual(
                    partner.withholding_type_id,
                    self.env.ref(
                        "l10n_ve_payment_extension.account_withholding_type_" + expected
                    ),
                )
                self.assertEqual(bill.state, "posted")
                self.assertTrue(bill.retention_iva_line_ids)

    def test_vendor_bill_of_a_contact_uses_the_withholding_of_its_company(self):
        # The withholding type is a commercial datum: the contact of a company
        # reads the one of the company it belongs to.
        parent, _bill = self._post_bill_with_iva_retention(
            "type_person_three_l10n_ve_payment_extension", "special"
        )
        parent.write({"is_company": True, "prefix_vat": "J"})
        child = self.env["res.partner"].create({
            "name": "Contacto de %s" % parent.name,
            "parent_id": parent.id,
            "property_account_receivable_id": self.acc_receivable.id,
            "property_account_payable_id": self.acc_payable.id,
        })
        self.assertFalse(child.withholding_type_id)
        self.assertEqual(child._get_retention_partner(), parent)
        bill = self._create_invoice_reten_iva(
            amount=200, partner=child, out_invoice="in_invoice",
            journal=self.purchase_journal,
        )
        bill.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        bill.generate_iva_retention = True
        bill.action_post()
        self.assertEqual(bill.state, "posted")
        self.assertTrue(bill.retention_iva_line_ids)

    def test_sale_iva_percentage_comes_from_the_company_not_the_customer(self):
        # When the company is withheld the percentage is the one of the company
        # (condition_withholding_id), whatever the customer has in its file.
        w75 = self.env.ref("l10n_ve_payment_extension.account_withholding_type_75")
        w100 = self.env.ref("l10n_ve_payment_extension.account_withholding_type_100")
        customer = self.env["res.partner"].create({
            "name": "Cliente con 75",
            "property_account_receivable_id": self.acc_receivable.id,
            "property_account_payable_id": self.acc_payable.id,
            "withholding_type_id": w75.id,
        })
        self.env.company.partner_id.withholding_type_id = w100
        invoice = self._create_invoice_reten_iva(
            amount=200, partner=customer, out_invoice="out_invoice",
            journal=self.sale_journal,
        )
        self.assertEqual(
            invoice._get_iva_withholding_partner(), self.env.company.partner_id
        )
        lines = self.env["account.retention"].compute_retention_lines_data(invoice)
        self.assertTrue(lines)
        self.env.company.auto_fill_retention_amount_iva = True
        lines = self.env["account.retention"].compute_retention_lines_data(invoice)
        for line in lines:
            self.assertAlmostEqual(line["retention_amount"], line["iva_amount"])
        self.env.company.partner_id.withholding_type_id = w75
        lines = self.env["account.retention"].compute_retention_lines_data(invoice)
        for line in lines:
            self.assertAlmostEqual(line["retention_amount"], line["iva_amount"] * 0.75)

    def test_purchase_iva_percentage_keeps_coming_from_the_vendor(self):
        w100 = self.env.ref("l10n_ve_payment_extension.account_withholding_type_100")
        vendor, bill = self._post_bill_with_iva_retention(
            "type_person_three_l10n_ve_payment_extension", "special"
        )
        self.env.company.partner_id.withholding_type_id = w100
        self.assertEqual(bill._get_iva_withholding_partner(), vendor)

    def test_islr_of_a_contact_uses_the_person_type_of_its_company(self):
        # The ISLR person type is a fiscal datum of the company: its contact
        # has none of its own and must not be asked for one.
        parent, _bill = self._post_bill_with_iva_retention(
            "type_person_three_l10n_ve_payment_extension", "special"
        )
        parent.write({"is_company": True, "prefix_vat": "J"})
        child = self.env["res.partner"].create({
            "name": "Contacto ISLR de %s" % parent.name,
            "parent_id": parent.id,
            "property_account_receivable_id": self.acc_receivable.id,
            "property_account_payable_id": self.acc_payable.id,
        })
        self.assertFalse(child.type_person_id)
        bill = self._create_invoice_reten_iva(
            amount=200, partner=child, out_invoice="in_invoice",
            journal=self.purchase_journal,
        )
        retention = self.env["account.retention"].create({
            "type_retention": "islr", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": child.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
            "retention_line_ids": [Command.create({
                "move_id": bill.id, "name": "Linea ISLR",
                "invoice_total": 232.0, "invoice_amount": 200.0,
                "retention_amount": 0.0,
            })],
        })
        # It no longer fails for the missing person type, only for the concept.
        with self.assertRaisesRegex(UserError, "payment concept"):
            retention._validate_islr_retention_fields()
        self.assertEqual(
            retention.retention_line_ids._get_islr_type_person_id(),
            parent.type_person_id,
        )
