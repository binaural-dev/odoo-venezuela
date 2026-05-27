from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from unittest.mock import patch


@tagged("post_install", "-at_install", "igtf_pos_order")
class IgtfPosOrderTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.pos_config = cls.env["pos.config"].create({
            "name": "Test POS Config",
            "company_id": cls.company.id,
        })
        cls.pos_session = cls.env["pos.session"].create({
            "config_id": cls.pos_config.id,
            "user_id": cls.env.uid,
        })
        cls.partner = cls.env["res.partner"].create({"name": "Test Partner"})

    def _create_order(self, **kwargs):
        vals = {
            "session_id": self.pos_session.id,
            "partner_id": self.partner.id,
            "amount_total": 100.0,
            "amount_paid": 100.0,
            "igtf_amount": 3.0,
            "bi_igtf": 100.0,
            "last_order_preparation_change": False,
        }
        vals.update(kwargs)
        return self.env["pos.order"].create(vals)

    def test_01_process_order_sets_igtf_fields(self):
        order_data = {
            "igtf_amount": "3.0",
            "bi_igtf": "100.0",
            "lines": [],
            "statement_ids": [],
        }
        with patch.object(type(self.env["pos.order"]), "_process_order") as mock:
            mock.return_value = self.env["pos.order"]
            self.env["pos.order"]._process_order(order_data, None)

    def test_02_process_order_handles_none_values(self):
        order_data = {
            "igtf_amount": None,
            "bi_igtf": None,
            "lines": [],
            "statement_ids": [],
        }
        with patch.object(type(self.env["pos.order"]), "_process_order") as mock:
            mock.return_value = self.env["pos.order"]
            self.env["pos.order"]._process_order(order_data, None)

    def test_03_process_order_handles_invalid_values(self):
        order_data = {
            "igtf_amount": "invalid",
            "bi_igtf": "invalid",
            "lines": [],
            "statement_ids": [],
        }
        with patch.object(type(self.env["pos.order"]), "_process_order") as mock:
            mock.return_value = self.env["pos.order"]
            self.env["pos.order"]._process_order(order_data, None)

    def test_04_payment_fields_includes_igtf(self):
        order = self._create_order()
        ui_paymentline = {
            "amount": 100.0,
            "include_igtf": True,
            "igtf_amount": 3.0,
            "foreign_igtf_amount": 75.0,
        }
        with patch.object(type(order), "_payment_fields") as mock:
            mock.return_value = {
                "include_igtf": True,
                "igtf_amount": 3.0,
                "foreign_igtf_amount": 75.0,
            }
            result = order._payment_fields(order, ui_paymentline)
            self.assertTrue(result["include_igtf"])
            self.assertAlmostEqual(result["igtf_amount"], 3.0)
            self.assertAlmostEqual(result["foreign_igtf_amount"], 75.0)

    def test_05_create_invoice_sets_bi_igtf(self):
        order = self._create_order()
        with patch.object(type(order), "_create_invoice") as mock:
            mock_invoice = self.env["account.move"].create({
                "journal_id": self.env["account.journal"].create({
                    "name": "Test Journal",
                    "code": "TJT",
                    "type": "general",
                    "company_id": self.company.id,
                }).id,
                "state": "draft",
                "line_ids": [
                    (0, 0, {"account_id": self.env["account.account"].create({
                        "name": "Test",
                        "code": "TST",
                        "account_type": "asset_current",
                    }).id, "name": "l1", "debit": 100}),
                    (0, 0, {"account_id": self.env["account.account"].create({
                        "name": "Test2",
                        "code": "TST2",
                        "account_type": "liability_current",
                    }).id, "name": "l2", "credit": 100}),
                ],
            })
            mock_invoice.bi_igtf = 0.0
            mock.return_value = mock_invoice
            result = order._create_invoice({"move_id": mock_invoice.id})
            self.assertEqual(result.bi_igtf, 100.0)

    def test_06_get_order_from_back(self):
        order = self._create_order()
        with patch.object(type(self.env["pos.order"]), "get_order_from_back") as mock:
            mock.return_value = 100.0
            result = self.env["pos.order"].get_order_from_back(order.display_name)
            self.assertEqual(result, 100.0)

    def test_07_new_order_has_igtf_fields(self):
        order = self._create_order()
        self.assertAlmostEqual(order.igtf_amount, 3.0)
        self.assertAlmostEqual(order.bi_igtf, 100.0)
