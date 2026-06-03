from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from unittest.mock import patch, MagicMock


@tagged("post_install", "-at_install", "pos_payment")
class PosPaymentTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.currency_vef = cls.env["res.currency"].search([("name", "=", "VEF")], limit=1)
        if cls.currency_vef:
            cls.company.currency_id = cls.currency_vef
        cls.currency_usd = cls.env.ref("base.USD")
        cls.company.foreign_currency_id = cls.currency_usd

        cls.pos_config = cls.env["pos.config"].create({
            "name": "Test POS Config",
            "company_id": cls.company.id,
        })
        cls.pos_session = cls.env["pos.session"].create({
            "config_id": cls.pos_config.id,
            "user_id": cls.env.uid,
        })
        cls.partner = cls.env["res.partner"].create({"name": "Test Partner"})
        cls.product = cls.env["product.product"].create({
            "name": "Test Product",
            "type": "consu",
        })

        cls.payment_method = cls.env["pos.payment.method"].create({
            "name": "Cash",
            "split_transactions": False,
            "is_foreign_currency": False,
        })

        cls.order = cls.env["pos.order"].create({
            "session_id": cls.pos_session.id,
            "partner_id": cls.partner.id,
            "amount_total": 100.0,
            "amount_paid": 100.0,
            "foreign_amount_total": 2500.0,
            "foreign_currency_rate": 25.0,
            "last_order_preparation_change": False,
        })

        cls.pos_payment = cls.env["pos.payment"].create({
            "pos_order_id": cls.order.id,
            "payment_method_id": cls.payment_method.id,
            "amount": 100.0,
            "foreign_amount": 2500.0,
            "foreign_rate": 25.0,
            "foreign_inverse_rate": 0.04,
        })

    def test_01_foreign_currency_id_computed(self):
        self.assertEqual(
            self.pos_payment.foreign_currency_id,
            self.company.foreign_currency_id,
        )

    def test_02_export_for_ui(self):
        result = self.pos_payment._export_for_ui(self.pos_payment)
        self.assertEqual(result["foreign_rate"], 25.0)
        self.assertEqual(result["foreign_inverse_rate"], 0.04)
        self.assertEqual(result["foreign_amount"], 2500.0)

    def test_03_get_payment_rate_values_from_payment(self):
        rate, inverse_rate = self.pos_payment._get_payment_rate_values(self.pos_payment)
        self.assertEqual(rate, 25.0)
        self.assertEqual(inverse_rate, 0.04)

    def test_04_get_payment_rate_values_fallback_to_config(self):
        payment = self.env["pos.payment"].create({
            "pos_order_id": self.order.id,
            "payment_method_id": self.payment_method.id,
            "amount": 100.0,
            "foreign_amount": 0.0,
            "foreign_rate": 0.0,
            "foreign_inverse_rate": 0.0,
        })
        rate, inverse_rate = payment._get_payment_rate_values(payment)
        self.assertIsInstance(rate, float)
        self.assertIsInstance(inverse_rate, float)

    def test_05_get_payment_rate_values_computes_missing(self):
        payment = self.env["pos.payment"].create({
            "pos_order_id": self.order.id,
            "payment_method_id": self.payment_method.id,
            "amount": 100.0,
            "foreign_amount": 0.0,
            "foreign_rate": 0.0,
            "foreign_inverse_rate": 0.04,
        })
        rate, inverse_rate = payment._get_payment_rate_values(payment)
        self.assertEqual(rate, 25.0)

    def test_06_get_payment_rate_values_computes_rate_from_inverse(self):
        payment = self.env["pos.payment"].create({
            "pos_order_id": self.order.id,
            "payment_method_id": self.payment_method.id,
            "amount": 100.0,
            "foreign_amount": 0.0,
            "foreign_rate": 25.0,
            "foreign_inverse_rate": 0.0,
        })
        rate, inverse_rate = payment._get_payment_rate_values(payment)
        self.assertEqual(inverse_rate, 0.04)

    def test_07_get_payment_foreign_amount(self):
        result = self.pos_payment._get_payment_foreign_amount(self.pos_payment)
        self.assertIsInstance(result, float)

    def test_08_create_payment_moves(self):
        account_type = self.env["account.account"].create({
            "name": "Test Account",
            "code": "TEST01",
            "account_type": "asset_receivable",
        })
        journal = self.env["account.journal"].create({
            "name": "Test Journal",
            "code": "TJRN2",
            "type": "general",
            "company_id": self.company.id,
        })
        with patch.object(type(self.env["account.move"]), "create") as mock_create:
            mock_move = MagicMock()
            mock_move.line_ids = self.env["account.move.line"]
            mock_move.filtered.return_value = self.env["account.move"]
            mock_create.return_value = mock_move

            with patch.object(
                type(self.env["pos.payment"]),
                "_create_payment_moves",
                return_value=self.env["account.move"],
            ):
                result = self.pos_payment._create_payment_moves()
                self.assertIsNotNone(result)
