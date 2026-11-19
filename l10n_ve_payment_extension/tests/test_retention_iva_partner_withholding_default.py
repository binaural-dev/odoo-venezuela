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
