from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_invoice_digital", "res_partner")
class TestResPartnerEmailDuplicate(TransactionCase):
    def test_duplicate_email_allowed_with_digital_invoice(self):
        # Create first partner with email
        partner_1 = self.env["res.partner"].create({
            "name": "Partner 1",
            "email": "test_duplicate@example.com",
        })
        self.assertTrue(partner_1.id)

        # Create second partner with the exact same email
        # This should not raise ValidationError because l10n_ve_invoice_digital is installed
        partner_2 = self.env["res.partner"].create({
            "name": "Partner 2",
            "email": "test_duplicate@example.com",
        })
        self.assertTrue(partner_2.id)
