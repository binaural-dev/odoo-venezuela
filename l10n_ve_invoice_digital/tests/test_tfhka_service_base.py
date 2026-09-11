from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_invoice_digital")
class TestTfhkaServiceBase(TransactionCase):
    def setUp(self):
        super().setUp()
        self.service = self.env["tfhka.service.base"]

    def test_get_party_address_uses_contact_address(self):
        """``contact_address`` (Odoo core) is the field that actually
        exists on res.partner; a previous change here used a
        ``contact_address_complete`` name that isn't defined anywhere,
        which broke digitalization for every invoice and retention."""
        partner = self.env["res.partner"].create(
            {
                "name": "Tercero de prueba",
                "street": "Av. Principal",
                "city": "Caracas",
            }
        )
        address = self.service._get_party_address(partner)
        self.assertTrue(address)
        self.assertEqual(address, partner.contact_address)
