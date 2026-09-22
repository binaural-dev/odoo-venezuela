"""Tests del contrato de read del partner para el Kiosko.

``res.partner._load_pos_self_data_read`` inyecta ``vat``/``prefix_vat`` sobre lo
que devuelve el core, para que las integraciones de pago que la necesitan —hoy
Megasoft (``binaural_megasoft_self_order``)— lean la cédula/RIF del partner de la
orden sin volver a pedirla. Estos tests fijan ese contrato.
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_pos_self_order")
class TestResPartnerPosSelfData(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        usd = cls.env.ref("base.USD")
        cls.company = cls.env["res.company"].create(
            {
                "name": "Partner SelfData Co",
                "currency_id": usd.id,
                "country_id": cls.env.ref("base.ve").id,
            }
        )
        sale_journal = cls.env["account.journal"].create(
            {
                "name": "Partner SelfData Sale Journal",
                "type": "sale",
                "code": "PSDSJ",
                "company_id": cls.company.id,
            }
        )
        cls.config = cls.env["pos.config"].create(
            {
                "name": "Partner SelfData Config",
                "company_id": cls.company.id,
                "journal_id": sale_journal.id,
                "invoice_journal_id": sale_journal.id,
                "payment_method_ids": [(6, 0, [])],
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {"name": "Cliente Kiosko", "prefix_vat": "V", "vat": "12345678"}
        )

    def test_read_includes_vat_and_prefix_vat(self):
        result = self.env["res.partner"]._load_pos_self_data_read(
            self.partner, self.config
        )
        self.assertTrue(result)
        record = result[0]
        self.assertEqual(record["id"], self.partner.id)
        self.assertEqual(record["vat"], "12345678")
        self.assertEqual(record["prefix_vat"], "V")

    def test_read_empty_recordset_returns_empty(self):
        result = self.env["res.partner"]._load_pos_self_data_read(
            self.env["res.partner"], self.config
        )
        self.assertEqual(result, [])

    def test_read_preserves_core_fields(self):
        """No se rompe el contrato del core: id/name siguen presentes."""
        record = self.env["res.partner"]._load_pos_self_data_read(
            self.partner, self.config
        )[0]
        self.assertIn("id", record)
        self.assertIn("name", record)
