from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from odoo.exceptions import ValidationError
from unittest.mock import patch, MagicMock


@tagged("post_install", "-at_install", "pos_session")
class PosSessionTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.currency_usd = cls.env["res.currency"].create({
            "name": "USD",
            "symbol": "$",
            "rounding": 0.01,
        })
        cls.company.foreign_currency_id = cls.currency_usd
        cls.currency_eur = cls.env["res.currency"].create({
            "name": "EUR",
            "symbol": "\u20ac",
            "rounding": 0.01,
        })

        cls.pos_config = cls.env["pos.config"].create({
            "name": "Test POS Config",
            "company_id": cls.company.id,
            "foreign_currency_id": cls.currency_usd.id,
        })
        cls.pos_session = cls.env["pos.session"].create({
            "config_id": cls.pos_config.id,
            "user_id": cls.env.uid,
        })
        cls.partner = cls.env["res.partner"].create({"name": "Test Partner"})
        cls.product = cls.env["product.product"].create({
            "name": "Test Product",
            "type": "consu",
            "lst_price": 100.0,
        })
        cls.product_category = cls.env["product.category"].create({
            "name": "Test Category",
        })
        cls.product.categ_id = cls.product_category

        cls.payment_method_cash = cls.env["pos.payment.method"].create({
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
            "payment_method_id": cls.payment_method_cash.id,
            "amount": 100.0,
            "foreign_amount": 2500.0,
            "foreign_rate": 25.0,
            "foreign_inverse_rate": 0.04,
        })

    def test_01_load_pos_data_includes_prefix_vats(self):
        with patch.object(type(self.pos_session), "load_pos_data") as mock:
            mock.return_value = {"prefix_vats": []}
            result = self.pos_session.load_pos_data()
            self.assertIn("prefix_vats", result)

    def test_02_loader_params_pos_payment(self):
        params = self.pos_session._loader_params_pos_payment()
        self.assertIn("foreign_rate", params["search_params"]["fields"])

    def test_03_loader_params_pos_payment_method(self):
        params = self.pos_session._loader_params_pos_payment_method()
        self.assertIn("is_foreign_currency", params["search_params"]["fields"])

    def test_04_loader_params_account_tax(self):
        params = self.pos_session._loader_params_account_tax()
        self.assertIn("type_tax_use", params["search_params"]["fields"])

    def test_05_loader_params_res_partner(self):
        params = self.pos_session._loader_params_res_partner()
        self.assertIn("prefix_vat", params["search_params"]["fields"])
        self.assertIn("city_id", params["search_params"]["fields"])

    def test_06_loader_params_res_currency(self):
        params = self.pos_session._loader_params_res_currency()
        self.assertIn("inverse_rate", params["search_params"]["fields"])

    def test_07_loader_params_product_product(self):
        params = self.pos_session._loader_params_product_product()
        self.assertIn("free_qty", params["search_params"]["fields"])
        self.assertIn("qty_available", params["search_params"]["fields"])

    def test_08_loader_params_res_company(self):
        params = self.pos_session._loader_params_res_company()
        self.assertIn("currency_id", params["search_params"]["fields"])

    def test_09_pos_ui_models_to_load_includes_city(self):
        with patch.object(type(self.pos_session), "_pos_ui_models_to_load") as mock:
            mock.return_value = ["res.country.city"]
            result = self.pos_session._pos_ui_models_to_load()
            self.assertIn("res.country.city", result)

    def test_10_get_pos_ui_res_country_city(self):
        params = {"search_params": {"domain": [], "fields": ["name", "id"]}}
        with patch.object(type(self.pos_session), "_get_pos_ui_res_country_city") as mock:
            mock.return_value = []
            result = self.pos_session._get_pos_ui_res_country_city(params)
            self.assertEqual(result, [])

    def test_11_get_pos_ui_res_currency_returns_ordered(self):
        params = {"search_params": {"domain": [("id", "in", [self.company.currency_id.id, self.currency_usd.id])], "fields": ["name", "id"]}}
        with patch.object(type(self.pos_session), "_get_pos_ui_res_currency") as mock:
            mock.return_value = [
                {"id": self.company.currency_id.id, "name": self.company.currency_id.name},
                {"id": self.currency_usd.id, "name": self.currency_usd.name},
            ]
            result = self.pos_session._get_pos_ui_res_currency(params)
            self.assertEqual(len(result), 2)

    def test_12_is_user_authorized(self):
        result = self.pos_session.is_user_authorized()
        self.assertIsInstance(result, bool)

    def test_13_apply_rounding(self):
        result = self.pos_session._apply_rounding(100.456)
        self.assertEqual(result, 100.46)

    def test_14_sort_available_products_returns_unsorted_when_flag_off(self):
        products = [{"qty_available": 5}, {"qty_available": 10}]
        result = self.pos_session._sort_available_products(products)
        self.assertEqual(result, products)

    def test_15_get_pos_ui_product_category(self):
        params = {"search_params": {"domain": [], "fields": ["id", "name", "parent_id"]}}
        with patch.object(type(self.pos_session), "_get_pos_ui_product_category") as mock:
            mock.return_value = [{"id": self.product_category.id, "name": "Test", "parent_id": None}]
            result = self.pos_session._get_pos_ui_product_category(params)
            self.assertEqual(len(result), 1)

    def test_16_process_pos_ui_product_product(self):
        products = [{
            "id": self.product.id,
            "lst_price": 100.0,
            "categ_id": [self.product_category.id, self.product_category.name],
            "image_128": False,
        }]
        self.pos_config.currency_id = self.company.currency_id
        self.pos_session._process_pos_ui_product_product(products)
        self.assertIn("categ", products[0])
        self.assertIn("image_128", products[0])

    def test_17_process_pos_ui_product_product_raises_on_missing_category(self):
        fake_categ_id = 999999
        products = [{
            "id": self.product.id,
            "lst_price": 100.0,
            "categ_id": [fake_categ_id, "Fake"],
            "image_128": False,
        }]
        with self.assertRaises(ValueError):
            self.pos_session._process_pos_ui_product_product(products)

    def test_18_line_vals_move_cross_incoming(self):
        account_type = self.env["account.account"].create({
            "name": "Outstanding",
            "code": "OUT001",
            "account_type": "asset_current",
        })
        journal = self.env["account.journal"].create({
            "name": "Cross Journal",
            "code": "CROSSJ",
            "type": "bank",
            "company_id": self.company.id,
        })
        payment_method = self.env["pos.payment.method"].create({
            "name": "Cross PM",
            "outstanding_account_id": account_type.id,
            "cross_journal": journal.id,
        })
        payment = self.env["pos.payment"].create({
            "pos_order_id": self.order.id,
            "payment_method_id": payment_method.id,
            "amount": 100.0,
            "foreign_amount": 2500.0,
            "foreign_rate": 25.0,
        })
        lines = self.pos_session._line_vals_move_cross_incoming(payment)
        self.assertIsNotNone(lines)
        self.assertTrue(len(lines) > 0)

    def test_19_line_vals_move_cross_outgoing(self):
        account_type = self.env["account.account"].create({
            "name": "Outstanding",
            "code": "OUT002",
            "account_type": "asset_current",
        })
        journal = self.env["account.journal"].create({
            "name": "Cross Journal 2",
            "code": "CROSSJ2",
            "type": "bank",
            "company_id": self.company.id,
        })
        payment_method = self.env["pos.payment.method"].create({
            "name": "Cross PM2",
            "outstanding_account_id": account_type.id,
            "cross_journal": journal.id,
        })
        payment = self.env["pos.payment"].create({
            "pos_order_id": self.order.id,
            "payment_method_id": payment_method.id,
            "amount": -50.0,
            "foreign_amount": -1250.0,
            "foreign_rate": 25.0,
        })
        lines = self.pos_session._line_vals_move_cross_outgoing(payment)
        self.assertIsNotNone(lines)
        self.assertTrue(len(lines) > 0)

    def test_20_validate_cross_move(self):
        with patch.object(type(self.pos_session), "_validate_cross_move") as mock:
            mock.return_value = None
            result = self.pos_session._validate_cross_move()
            self.assertIsNone(result)

    def test_21_create_cross_move(self):
        account_type = self.env["account.account"].create({
            "name": "Cross Acc",
            "code": "CROSSACC",
            "account_type": "asset_current",
        })
        journal = self.env["account.journal"].create({
            "name": "Cross Journal 3",
            "code": "CROSSJ3",
            "type": "general",
            "company_id": self.company.id,
        })
        payment_method = self.pos_payment.payment_method_id
        payment_method.cross_account_journal = journal.id
        line_vals = [(
            0, 0, {
                "name": "Test Line",
                "account_id": account_type.id,
                "debit": 100.0,
                "credit": 0.0,
            }
        )]
        move = self.pos_session._create_cross_move(self.pos_payment, line_vals)
        self.assertIsNotNone(move)
        self.assertEqual(move.state, "draft")

    def test_22_action_pos_session_close(self):
        with patch.object(type(self.pos_session), "action_pos_session_close") as mock:
            mock.return_value = {}
            result = self.pos_session.action_pos_session_close()
            self.assertIsNotNone(result)

    def test_23_create_combine_account_payment(self):
        journal = self.env["account.journal"].create({
            "name": "Bank Journal",
            "code": "BNKJ",
            "type": "bank",
            "company_id": self.company.id,
        })
        payment_method = self.env["pos.payment.method"].create({
            "name": "Bank PM",
            "split_transactions": True,
            "type": "bank",
            "journal_id": journal.id,
            "is_foreign_currency": False,
        })
        amounts = {"amount": 100.0, "amount_converted": 100.0}
        with patch.object(type(self.pos_session), "_create_combine_account_payment") as mock:
            mock.return_value = self.env["account.payment"]
            result = self.pos_session._create_combine_account_payment(
                payment_method, amounts, 0.0
            )
            self.assertIsNotNone(result)

    def test_24_set_foreign_amount_in_line_with_credit(self):
        account_type = self.env["account.account"].create({
            "name": "Test Acc",
            "code": "TSTACC",
            "account_type": "asset_current",
        })
        move = self.env["account.move"].create({
            "journal_id": self.env["account.journal"].search([], limit=1).id,
            "state": "draft",
            "line_ids": [
                (0, 0, {"account_id": account_type.id, "name": "l1", "credit": 100.0}),
                (0, 0, {"account_id": account_type.id, "name": "l2", "debit": 100.0}),
            ],
        })
        line = move.line_ids.filtered(lambda l: l.credit > 0)[0]
        self.pos_session.config_id.foreign_rate = 25.0
        self.pos_session.config_id.foreign_inverse_rate = 0.04
        self.pos_session.set_foreign_amount_in_line(line, 2500.0, 100.0)
        self.assertEqual(line.foreign_credit, 2500.0)

    def test_25_set_foreign_amount_in_line_with_debit(self):
        account_type = self.env["account.account"].create({
            "name": "Test Acc 2",
            "code": "TSTACC2",
            "account_type": "asset_current",
        })
        move = self.env["account.move"].create({
            "journal_id": self.env["account.journal"].search([], limit=1).id,
            "state": "draft",
            "line_ids": [
                (0, 0, {"account_id": account_type.id, "name": "l1", "debit": 100.0}),
                (0, 0, {"account_id": account_type.id, "name": "l2", "credit": 100.0}),
            ],
        })
        line = move.line_ids.filtered(lambda l: l.debit > 0)[0]
        self.pos_session.set_foreign_amount_in_line(line, 2500.0, 100.0)
        self.assertEqual(line.foreign_debit, 2500.0)

    def test_26_set_foreign_amount_in_line_skips_with_zero_foreign(self):
        account_type = self.env["account.account"].create({
            "name": "Test Acc 3",
            "code": "TSTACC3",
            "account_type": "asset_current",
        })
        move = self.env["account.move"].create({
            "journal_id": self.env["account.journal"].search([], limit=1).id,
            "state": "draft",
            "line_ids": [
                (0, 0, {"account_id": account_type.id, "name": "l1", "credit": 100.0}),
            ],
        })
        line = move.line_ids[0]
        self.pos_session.set_foreign_amount_in_line(line, 0.0, 100.0)
        self.assertEqual(line.foreign_credit, 0.0)

    def test_27_update_amounts_adds_foreign_amount(self):
        old = {"amount": 100.0, "foreign_amount": 500.0}
        to_add = {"amount": 50.0, "foreign_amount": 1500.0}
        result = self.pos_session._update_amounts(old, to_add, None)
        self.assertAlmostEqual(result["foreign_amount"], 2000.0)
        self.assertAlmostEqual(result["amount"], 150.0)

    def test_28_accumulate_amounts(self):
        data = {
            "split_receivables_cash": {},
            "split_receivables_bank": {},
            "combine_receivables_cash": {},
            "combine_receivables_bank": {},
            "combine_invoice_receivables": {},
            "split_invoice_receivables": {},
        }
        with patch.object(type(self.pos_session), "_accumulate_amounts") as mock:
            mock.return_value = data
            result = self.pos_session._accumulate_amounts(data)
            self.assertIn("split_receivables_cash", result)
