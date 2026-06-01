from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from odoo.tools import float_round
from unittest.mock import patch, MagicMock


@tagged("post_install", "-at_install", "igtf_pos_payment")
class IgtfPosPaymentTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.currency_vef = cls.env["res.currency"].search([("name", "=", "VEF")], limit=1)
        if cls.currency_vef:
            cls.company.currency_id = cls.currency_vef
        cls.currency_usd = cls.env["res.currency"].search([("name", "=", "USD")], limit=1) or cls.env["res.currency"].create({
            "name": "USD",
            "symbol": "$",
            "rounding": 0.01,
        })
        cls.company.foreign_currency_id = cls.currency_usd
        cls.company.igtf_percentage = 3.0
        cls.account_igtf = cls.env["account.account"].create({
            "name": "IGTF Account",
            "code": "IGTFACC2",
            "account_type": "asset_current",
        })
        cls.company.customer_account_igtf_id = cls.account_igtf

        cls.pos_config = cls.env["pos.config"].create({
            "name": "Test POS Config",
            "company_id": cls.company.id,
        })
        cls.pos_session = cls.env["pos.session"].create({
            "config_id": cls.pos_config.id,
            "user_id": cls.env.uid,
        })
        cls.partner = cls.env["res.partner"].create({"name": "Test Partner"})

        cls.payment_method = cls.env["pos.payment.method"].create({
            "name": "Cash IGTF",
            "split_transactions": False,
            "apply_igtf": True,
        })

        cls.account_receivable = cls.env["account.account"].create({
            "name": "Receivable",
            "code": "RECV002",
            "account_type": "asset_receivable",
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
            "include_igtf": True,
            "igtf_amount": 3.0,
            "foreign_igtf_amount": 75.0,
        })

    def test_01_export_for_ui(self):
        result = self.pos_payment._export_for_ui(self.pos_payment)
        self.assertTrue(result["include_igtf"])
        self.assertAlmostEqual(result["igtf_amount"], 3.0)
        self.assertAlmostEqual(result["foreign_igtf_amount"], 75.0)

    def test_02_convert_company_to_foreign_amount(self):
        result = self.pos_payment._convert_company_to_foreign_amount(self.pos_payment, 100.0)
        self.assertIsInstance(result, float)

    def test_03_convert_company_to_foreign_amount_with_same_currency(self):
        payment = self.env["pos.payment"].create({
            "pos_order_id": self.order.id,
            "payment_method_id": self.payment_method.id,
            "amount": 100.0,
            "foreign_amount": 100.0,
            "foreign_rate": 25.0,
            "foreign_inverse_rate": 0.04,
        })
        self.company.foreign_currency_id = self.company.currency_id
        result = payment._convert_company_to_foreign_amount(payment, 100.0)
        self.assertEqual(result, 100.0)
        self.company.foreign_currency_id = self.currency_usd

    def test_04_get_igtf_amounts_for_move_zero_amount(self):
        payment = self.env["pos.payment"].create({
            "pos_order_id": self.order.id,
            "payment_method_id": self.payment_method.id,
            "amount": 0.0,
            "foreign_amount": 0.0,
            "foreign_rate": 25.0,
            "foreign_inverse_rate": 0.04,
            "include_igtf": True,
            "igtf_amount": 0.0,
        })
        amounts = {"amount": 0.0, "amount_converted": 0.0}
        company_igtf, converted_igtf, foreign_igtf = payment._get_igtf_amounts_for_move(
            payment, amounts
        )
        self.assertEqual(company_igtf, 0.0)
        self.assertEqual(converted_igtf, 0.0)
        self.assertEqual(foreign_igtf, 0.0)

    def test_05_get_igtf_amounts_for_move_non_zero(self):
        amounts = {"amount": 100.0, "amount_converted": 100.0}
        company_igtf, converted_igtf, foreign_igtf = self.pos_payment._get_igtf_amounts_for_move(
            self.pos_payment, amounts
        )
        self.assertAlmostEqual(company_igtf, 3.0)
        self.assertIsInstance(foreign_igtf, float)

    def test_06_normalize_foreign_amount(self):
        result = self.pos_payment._normalize_foreign_amount(self.pos_payment, 2500.0)
        self.assertEqual(result, 2500.0)

    def test_07_normalize_foreign_amount_with_none(self):
        result = self.pos_payment._normalize_foreign_amount(self.pos_payment, None)
        self.assertEqual(result, 0.0)

    def test_08_align_foreign_with_line_side_debit(self):
        line_vals = {"debit": 100.0, "credit": 0.0}
        result = self.pos_payment._align_foreign_with_line_side(
            line_vals, self.pos_payment, 2500.0
        )
        self.assertEqual(result["foreign_debit"], 2500.0)
        self.assertEqual(result["foreign_credit"], 0.0)

    def test_09_align_foreign_with_line_side_credit(self):
        line_vals = {"debit": 0.0, "credit": 100.0}
        result = self.pos_payment._align_foreign_with_line_side(
            line_vals, self.pos_payment, 2500.0
        )
        self.assertEqual(result["foreign_debit"], 0.0)
        self.assertEqual(result["foreign_credit"], 2500.0)

    def test_10_align_foreign_with_line_side_zero(self):
        line_vals = {"debit": 100.0, "credit": 0.0}
        result = self.pos_payment._align_foreign_with_line_side(
            line_vals, self.pos_payment, 0.0
        )
        self.assertEqual(result["foreign_debit"], 0.0)
        self.assertEqual(result["foreign_credit"], 0.0)

    def test_11_get_foreign_debit_credit_vals_positive(self):
        result = self.pos_payment._get_foreign_debit_credit_vals(100.0)
        self.assertEqual(result["foreign_debit"], 0.0)
        self.assertEqual(result["foreign_credit"], 100.0)

    def test_12_get_foreign_debit_credit_vals_negative(self):
        result = self.pos_payment._get_foreign_debit_credit_vals(-100.0)
        self.assertEqual(result["foreign_debit"], 100.0)
        self.assertEqual(result["foreign_credit"], 0.0)

    def test_13_get_receivable_account_id(self):
        account_id = self.pos_payment._get_receivable_account_id(self.partner, self.order)
        self.assertIsInstance(account_id, int)

    def test_14_build_credit_line_without_igtf(self):
        journal = self.env["account.journal"].create({
            "name": "Test Journal",
            "code": "TJT3",
            "type": "general",
            "company_id": self.company.id,
        })
        move = self.env["account.move"].create({
            "journal_id": journal.id,
            "state": "draft",
            "line_ids": [
                (0, 0, {"account_id": self.account_receivable.id, "name": "l1", "credit": 100}),
            ],
        })
        amounts = {"amount": 100.0, "amount_converted": 100.0}
        with patch.object(type(self.pos_session), "_credit_amounts") as mock_credit:
            mock_credit.return_value = {"account_id": self.account_receivable.id, "credit": 100.0}
            result = self.pos_payment._build_credit_line_without_igtf(
                self.pos_session, move, self.account_receivable.id, self.partner.id, amounts, self.pos_payment
            )
            self.assertIn("account_id", result)

    def test_15_build_credit_line_igtf(self):
        journal = self.env["account.journal"].create({
            "name": "Test Journal 4",
            "code": "TJT4",
            "type": "general",
            "company_id": self.company.id,
        })
        move = self.env["account.move"].create({
            "journal_id": journal.id,
            "state": "draft",
            "line_ids": [
                (0, 0, {"account_id": self.account_receivable.id, "name": "l1", "credit": 3.0}),
            ],
        })
        with patch.object(type(self.pos_session), "_credit_amounts") as mock_credit:
            mock_credit.return_value = {"credit": 3.0}
            result = self.pos_payment._build_credit_line_igtf(
                self.pos_session, move, self.partner.id, self.pos_payment,
                3.0, 3.0, 75.0
            )
            self.assertIn("credit", result)

    def test_16_build_credit_line_igtf_base(self):
        journal = self.env["account.journal"].create({
            "name": "Test Journal 5",
            "code": "TJT5",
            "type": "general",
            "company_id": self.company.id,
        })
        move = self.env["account.move"].create({
            "journal_id": journal.id,
            "state": "draft",
            "line_ids": [
                (0, 0, {"account_id": self.account_receivable.id, "name": "l1", "credit": 97.0}),
            ],
        })
        amounts = {"amount": 100.0, "amount_converted": 100.0}
        with patch.object(type(self.pos_session), "_credit_amounts") as mock_credit:
            mock_credit.return_value = {"credit": 97.0}
            result = self.pos_payment._build_credit_line_igtf_base(
                self.pos_session, move, self.account_receivable.id, self.partner.id,
                amounts, 3.0, 3.0, 75.0, self.pos_payment
            )
            self.assertIn("credit", result)

    def test_17_get_reversed_move_receivable_account_id_split_reverse(self):
        account_id, is_split = self.pos_payment._get_reversed_move_receivable_account_id(
            self.pos_payment, self.partner, self.order, is_reverse=True
        )
        self.assertIsInstance(account_id, int)

    def test_18_build_debit_line(self):
        journal = self.env["account.journal"].create({
            "name": "Test Journal 6",
            "code": "TJT6",
            "type": "general",
            "company_id": self.company.id,
        })
        move = self.env["account.move"].create({
            "journal_id": journal.id,
            "state": "draft",
            "line_ids": [
                (0, 0, {"account_id": self.account_receivable.id, "name": "l1", "debit": 100}),
            ],
        })
        amounts = {"amount": 100.0, "amount_converted": 100.0}
        with patch.object(type(self.pos_session), "_debit_amounts") as mock_debit:
            mock_debit.return_value = {"debit": 100.0}
            result = self.pos_payment._build_debit_line(
                self.pos_session, move, self.account_receivable.id, self.partner,
                False, False, amounts, self.pos_payment
            )
            self.assertIn("debit", result)

    def test_19_pay_later_skipped(self):
        pay_later_method = self.env["pos.payment.method"].create({
            "name": "Pay Later",
            "type": "pay_later",
        })
        payment = self.env["pos.payment"].create({
            "pos_order_id": self.order.id,
            "payment_method_id": pay_later_method.id,
            "amount": 100.0,
            "foreign_amount": 2500.0,
        })
        result = payment._create_payment_moves()
        self.assertFalse(result)

    def test_20_zero_amount_skipped(self):
        payment = self.env["pos.payment"].create({
            "pos_order_id": self.order.id,
            "payment_method_id": self.payment_method.id,
            "amount": 0.0,
            "foreign_amount": 0.0,
        })
        result = payment._create_payment_moves()
        self.assertFalse(result)

    def test_21_create_payment_moves_with_igtf(self):
        journal = self.env["account.journal"].create({
            "name": "Bank Journal IGTF",
            "code": "BNKJIGTF",
            "type": "bank",
            "company_id": self.company.id,
        })
        self.pos_config.journal_id = journal
        payment_method = self.env["pos.payment.method"].create({
            "name": "Bank with IGTF",
            "split_transactions": False,
            "apply_igtf": True,
            "type": "bank",
        })

        payment = self.env["pos.payment"].create({
            "pos_order_id": self.order.id,
            "payment_method_id": payment_method.id,
            "amount": 100.0,
            "foreign_amount": 2500.0,
            "foreign_rate": 25.0,
            "foreign_inverse_rate": 0.04,
            "include_igtf": True,
            "igtf_amount": 3.0,
            "foreign_igtf_amount": 75.0,
        })

        with patch.object(type(self.pos_session), "_update_amounts") as mock_update:
            mock_update.return_value = {"amount": 100.0, "amount_converted": 100.0}
            with patch.object(type(payment), "_create_payment_move") as mock_create:
                mock_move = MagicMock()
                mock_move.id = 1
                mock_create.return_value = mock_move
                with patch.object(type(payment), "_get_igtf_amounts_for_move") as mock_igtf:
                    mock_igtf.return_value = (3.0, 3.0, 75.0)
                    with patch.object(type(payment), "_build_credit_line_igtf") as mock_credit_igtf:
                        mock_credit_igtf.return_value = {"credit": 3.0}
                        with patch.object(type(payment), "_build_debit_line") as mock_debit:
                            mock_debit.return_value = {"debit": 100.0}
                            with patch.object(type(self.env["account.move.line"]), "create") as mock_aml:
                                mock_aml.return_value = self.env["account.move.line"]
                                with patch.object(mock_move, "_post") as mock_post:
                                    mock_post.return_value = True
                                    result = payment._create_payment_moves()
                                    self.assertIsNotNone(result)

    def test_22_create_payment_moves_without_igtf(self):
        payment_method = self.env["pos.payment.method"].create({
            "name": "Bank without IGTF",
            "split_transactions": False,
            "apply_igtf": False,
            "type": "bank",
        })
        journal = self.env["account.journal"].create({
            "name": "Bank Journal No IGTF",
            "code": "BNKJNOIGTF",
            "type": "bank",
            "company_id": self.company.id,
        })
        self.pos_config.journal_id = journal

        payment = self.env["pos.payment"].create({
            "pos_order_id": self.order.id,
            "payment_method_id": payment_method.id,
            "amount": 100.0,
            "foreign_amount": 2500.0,
            "foreign_rate": 25.0,
            "foreign_inverse_rate": 0.04,
            "include_igtf": False,
            "igtf_amount": 0.0,
        })

        with patch.object(type(self.pos_session), "_update_amounts") as mock_update:
            mock_update.return_value = {"amount": 100.0, "amount_converted": 100.0}
            with patch.object(type(payment), "_create_payment_move") as mock_create:
                mock_move = MagicMock()
                mock_move.id = 1
                mock_create.return_value = mock_move
                with patch.object(type(payment), "_build_credit_line_without_igtf") as mock_credit:
                    mock_credit.return_value = {"credit": 100.0}
                    with patch.object(type(payment), "_build_debit_line") as mock_debit:
                        mock_debit.return_value = {"debit": 100.0}
                        with patch.object(type(self.env["account.move.line"]), "create") as mock_aml:
                            mock_aml.return_value = self.env["account.move.line"]
                            with patch.object(mock_move, "_post") as mock_post:
                                mock_post.return_value = True
                                result = payment._create_payment_moves()
                                self.assertIsNotNone(result)

    def test_23_create_payment_move_returns_move(self):
        journal = self.env["account.journal"].create({
            "name": "Bank Journal PM",
            "code": "BNKJPM",
            "type": "bank",
            "company_id": self.company.id,
        })
        result = self.pos_payment._create_payment_move(
            self.pos_payment, self.order, self.payment_method, journal
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.journal_id, journal)
        self.assertIn("foreign_rate", result)
        self.assertIn("manually_set_rate", result)
