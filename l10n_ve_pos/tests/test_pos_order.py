from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from unittest.mock import patch


@tagged("post_install", "-at_install", "pos_order")
class PosOrderTest(TransactionCase):

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

        cls.partner = cls.env["res.partner"].create({
            "name": "Test Partner",
        })

        cls.product = cls.env["product.product"].create({
            "name": "Test Product",
            "type": "consu",
        })

    def _patch_parent(self, model_name, method_name, **kwargs):
        model_class = self.env[model_name].__class__
        for klass in model_class.__mro__[1:]:
            if method_name in klass.__dict__:
                return patch.object(klass, method_name, **kwargs)
        return patch.object(model_class.__bases__[0], method_name, **kwargs)

    def _create_order(self, **kwargs):
        vals = {
            "session_id": self.pos_session.id,
            "partner_id": self.partner.id,
            "amount_total": 100.0,
            "foreign_amount_total": 2500.0,
            "foreign_currency_rate": 25.0,
            "amount_tax": 0.0,
            "amount_paid": 100.0,
            "last_order_preparation_change": False,
        }
        vals.update(kwargs)
        return self.env["pos.order"].create(vals)

    def test_01_process_order_sets_foreign_fields(self):
        order_data = {
            "foreign_amount_total": "2500.0",
            "foreign_currency_rate": "25.0",
            "lines": [],
            "statement_ids": [],
        }
        with self._patch_parent("pos.order", "_process_order", return_value=self.env["pos.order"]):
            self.env["pos.order"]._process_order(order_data, None)
            self.assertEqual(order_data["foreign_amount_total"], 2500.0)
            self.assertEqual(order_data["foreign_currency_rate"], 25.0)

    def test_02_process_order_handles_none_values(self):
        order_data = {
            "foreign_amount_total": None,
            "foreign_currency_rate": None,
            "lines": [],
            "statement_ids": [],
        }
        with self._patch_parent("pos.order", "_process_order", return_value=self.env["pos.order"]):
            self.env["pos.order"]._process_order(order_data, None)
            self.assertEqual(order_data["foreign_amount_total"], 0.0)
            self.assertEqual(order_data["foreign_currency_rate"], 0.0)

    def test_03_process_order_handles_invalid_values(self):
        order_data = {
            "foreign_amount_total": "invalid",
            "foreign_currency_rate": "invalid",
            "lines": [],
            "statement_ids": [],
        }
        with self._patch_parent("pos.order", "_process_order", return_value=self.env["pos.order"]):
            self.env["pos.order"]._process_order(order_data, None)
            self.assertEqual(order_data["foreign_amount_total"], 0.0)
            self.assertEqual(order_data["foreign_currency_rate"], 0.0)

    def test_04_payment_fields_standard(self):
        order = self._create_order()
        ui_paymentline = {
            "amount": 100.0,
            "foreign_amount": 2500.0,
            "foreign_rate": 25.0,
            "foreign_inverse_rate": 0.04,
        }
        with self._patch_parent("pos.order", "_payment_fields", return_value={}):
            result = order._payment_fields(order, ui_paymentline)
            self.assertAlmostEqual(result["foreign_amount"], 2500.0)
            self.assertAlmostEqual(result["foreign_rate"], 25.0)
            self.assertAlmostEqual(result["foreign_inverse_rate"], 0.04)

    def test_05_payment_fields_without_foreign_amount(self):
        order = self._create_order()
        ui_paymentline = {
            "amount": 100.0,
            "foreign_amount": 0.0,
            "foreign_rate": 25.0,
            "foreign_inverse_rate": 0.0,
        }
        with self._patch_parent("pos.order", "_payment_fields", return_value={}):
            result = order._payment_fields(order, ui_paymentline)
            expected_foreign = 100.0 / 25.0
            self.assertAlmostEqual(result["foreign_amount"], expected_foreign)
            self.assertAlmostEqual(result["foreign_rate"], 25.0)

    def test_06_payment_fields_with_only_inverse_rate(self):
        order = self._create_order()
        ui_paymentline = {
            "amount": 100.0,
            "foreign_amount": 0.0,
            "foreign_rate": 0.0,
            "foreign_inverse_rate": 0.04,
        }
        with self._patch_parent("pos.order", "_payment_fields", return_value={}):
            result = order._payment_fields(order, ui_paymentline)
            self.assertAlmostEqual(result["foreign_inverse_rate"], 0.04)
            self.assertAlmostEqual(result["foreign_rate"], 25.0)

    def test_07_payment_fields_with_alt_keys(self):
        order = self._create_order()
        ui_paymentline = {
            "amount": 100.0,
            "foreignAmount": 2500.0,
            "foreignRate": 25.0,
            "foreignInverseRate": 0.04,
        }
        with self._patch_parent("pos.order", "_payment_fields", return_value={}):
            result = order._payment_fields(order, ui_paymentline)
            self.assertAlmostEqual(result["foreign_amount"], 2500.0)
            self.assertAlmostEqual(result["foreign_rate"], 25.0)
            self.assertAlmostEqual(result["foreign_inverse_rate"], 0.04)

    def test_08_payment_fields_with_invalid_values(self):
        order = self._create_order()
        ui_paymentline = {
            "amount": None,
            "foreign_amount": None,
            "foreign_rate": "invalid",
            "foreign_inverse_rate": None,
        }
        with self._patch_parent("pos.order", "_payment_fields", return_value={}):
            result = order._payment_fields(order, ui_paymentline)
            self.assertAlmostEqual(result["foreign_amount"], 0.0)
            self.assertAlmostEqual(result["foreign_rate"], 0.0)
            self.assertAlmostEqual(result["foreign_inverse_rate"], 0.0)

    def test_09_prepare_invoice_vals(self):
        order = self._create_order()
        with self._patch_parent("pos.order", "_prepare_invoice_vals", return_value={}):
            result = order._prepare_invoice_vals()
            self.assertEqual(result["foreign_rate"], 25.0)
            self.assertEqual(result["manually_set_rate"], True)

    def test_10_convert_amount_model_method(self):
        result = self.env["pos.order"].convert_amount(100.0)
        self.assertIsInstance(result, float)

    def test_11_convert_amount_with_invalid(self):
        result = self.env["pos.order"].convert_amount(None)
        self.assertIsInstance(result, float)
        result2 = self.env["pos.order"].convert_amount("invalid")
        self.assertIsInstance(result2, float)

    def test_12_order_line_refund_data(self):
        order = self._create_order()
        order_line = self.env["pos.order.line"].create({
            "order_id": order.id,
            "product_id": self.product.id,
            "price_unit": 100.0,
            "qty": 1,
            "price_subtotal": 100.0,
            "price_subtotal_incl": 100.0,
            "foreign_price": 2500.0,
        })
        refund_order = self._create_order(name="REF/001")
        result = order_line._prepare_refund_data(refund_order, None)
        self.assertEqual(result.get("foreign_price"), 2500.0)

    def test_13_order_line_export_for_ui(self):
        order = self._create_order()
        order_line = self.env["pos.order.line"].create({
            "order_id": order.id,
            "product_id": self.product.id,
            "price_unit": 100.0,
            "qty": 1,
            "price_subtotal": 100.0,
            "price_subtotal_incl": 100.0,
            "foreign_price": 2500.0,
        })
        result = order_line._export_for_ui(order_line)
        self.assertEqual(result.get("foreign_price"), 2500.0)
        self.assertEqual(result.get("foreign_currency_rate"), order.foreign_currency_rate)

    def test_14_order_line_convert_amount(self):
        result = self.env["pos.order.line"].convert_amount(100.0)
        self.assertIsInstance(result, float)
