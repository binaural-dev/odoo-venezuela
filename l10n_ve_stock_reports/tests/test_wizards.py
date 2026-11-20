
from datetime import datetime, timedelta
from io import BytesIO
from unittest.mock import patch, PropertyMock
import zipfile

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('bin', 'l10n_ve_stock_reports', '-at_install', 'post_install')
class TestWizardStockBookReport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.uom_unit = cls.env.ref("uom.product_uom_unit")
        cls.category_all = cls.env.ref("product.product_category_goods")
        cls.location_stock = cls.env.ref("stock.stock_location_stock")
        cls.location_supplier = cls.env.ref("stock.stock_location_suppliers")
        cls.location_customer = cls.env.ref("stock.stock_location_customers")
        cls.picking_type_in = cls.env.ref("stock.picking_type_in")
        cls.picking_type_out = cls.env.ref("stock.picking_type_out")

        # Since Odoo 19 the valuation lives on the done moves (value, is_in, is_out):
        # the book reads them instead of stock.valuation.layer.
        cls.product = cls.env["product.product"].create({
            "name": "Producto de Prueba",
            "type": "consu",
            "is_storable": True,
            "uom_id": cls.uom_unit.id,
            "categ_id": cls.category_all.id,
            "standard_price": 10.0,
        })

        cls.today = fields.Date.today()
        cls.tomorrow = cls.today + timedelta(days=1)

        cls.wizard = cls.env["wizard.stock.book.report"].create({
            "company_id": cls.company.id,
            "date_from": cls.today,
            "date_to": cls.tomorrow,
        })

        cls.old_move = cls._done_move(2, cls.location_supplier, cls.location_stock, cls.picking_type_in)
        old_datetime = datetime.combine(cls.today - timedelta(days=10), datetime.min.time())
        cls.env.cr.execute(
            "UPDATE stock_move SET date = %s WHERE id = %s",
            (fields.Datetime.to_string(old_datetime), cls.old_move.id),
        )
        cls.old_move.invalidate_recordset(["date"])

        cls.incoming_move = cls._done_move(5, cls.location_supplier, cls.location_stock, cls.picking_type_in)
        cls.outgoing_move = cls._done_move(3, cls.location_stock, cls.location_customer, cls.picking_type_out)

    @classmethod
    def _done_move(cls, qty, location, location_dest, picking_type):
        move = cls.env["stock.move"].create({
            "product_id": cls.product.id,
            "product_uom_qty": qty,
            "uom_id": cls.uom_unit.id,
            "company_id": cls.company.id,
            "location_id": location.id,
            "location_dest_id": location_dest.id,
            "picking_type_id": picking_type.id,
        })
        move._action_confirm()
        move.quantity = qty
        move.picked = True
        move._action_done()
        return move

    def test_download_stock_book_returns_action(self):
        wizard = self.env["wizard.stock.book.report"].create({
            "company_id": self.company.id,
            "date_from": self.today,
            "date_to": self.tomorrow,
        })
        action = wizard.download_stock_book()
        self.assertEqual(action["type"], "ir.actions.act_url")
        self.assertIn("/web/download_stock_book", action["url"])
        self.assertIn(str(self.company.id), action["url"])

    def test_generate_report_delegates_to_download(self):
        wizard = self.env["wizard.stock.book.report"].create({
            "company_id": self.company.id,
            "date_from": self.today,
            "date_to": self.tomorrow,
        })
        with patch(
            "odoo.addons.l10n_ve_stock_reports.wizard.stock_book_report.WizardStockBookReport.download_stock_book",
            return_value={"type": "ir.actions.act_url"},
        ) as mock_download:
            result = wizard.generate_report()
        self.assertEqual(result, {"type": "ir.actions.act_url"})
        mock_download.assert_called_once()

    def test_get_domain_stock_move_filters_by_dates_and_company(self):
        domain = self.wizard._get_domain_stock_move()
        self.assertIn(("company_id", "=", self.company.id), domain)
        self.assertIn(("date", ">=", self.today), domain)
        self.assertIn(("date", "<=", self.tomorrow), domain)
        self.assertIn(("state", "=", "done"), domain)

    def test_search_valuation_layers_includes_current_period(self):
        moves = [entry.stock_move_id for entry in self.wizard.search_valuation_layers()]
        self.assertIn(self.incoming_move, moves)
        self.assertIn(self.outgoing_move, moves)
        self.assertNotIn(self.old_move, moves)

    def test_get_old_stock_by_product_returns_previous_balances(self):
        data = self.wizard.get_old_stock_by_product(self.product.id)
        self.assertEqual(data["total_stock_qty"], 2)
        self.assertEqual(data["old_stock_total"], 20)

    def test_parse_stock_book_data_aggregates_movements(self):
        lines = self.wizard.parse_stock_book_data()
        self.assertEqual(len(lines), 1)
        line = lines[0]
        self.assertEqual(line["description"], self.product.name)
        self.assertEqual(line["old_stock"], 2)
        # The moves of the period have their picking type: 5 in, 3 out.
        self.assertEqual(line["incoming_stock"], 5)
        self.assertEqual(line["outgoing_stock"], 3)
        self.assertEqual(line["stock"], 2)
        self.assertEqual(line["incoming_total"], 50)
        self.assertEqual(line["outgoing_total"], 30)
        self.assertEqual(line["old_stock_bs"], 20)
        self.assertEqual(line["total_stock_qty_product_bs"], 20)

    def test_parse_stock_book_data_returns_empty_when_no_layers(self):
        wizard = self.env["wizard.stock.book.report"].create({
            "company_id": self.company.id,
            "date_from": self.today - timedelta(days=60),
            "date_to": self.today - timedelta(days=30),
        })
        self.assertEqual(wizard.parse_stock_book_data(), [])

    def test_generate_stocks_book_builds_workbook_with_lines(self):
        content = self.wizard.generate_stocks_book(self.company.id)
        self.assertTrue(content)
        self.assertTrue(content.startswith(b"PK"))
        with zipfile.ZipFile(BytesIO(content)) as archive:
            sheet = archive.read("xl/worksheets/sheet1.xml").decode()
            shared_strings = archive.read("xl/sharedStrings.xml").decode()
        self.assertIn(self.product.name, shared_strings)


    def test_default_date_from_and_to(self):
        assert self.wizard.date_from is not None
        assert self.wizard.date_to is not None

    def test_search_valuation_layers_empty(self):
        # Crea un producto nuevo sin movimientos ni capas
        tmpl = self.env["product.template"].create({
            "name": "Producto Sin Movimientos",
            "type": "service",
            "uom_id": self.uom_unit.id,
            "categ_id": self.category_all.id,
        })
        product = tmpl.product_variant_id
        wizard = self.env["wizard.stock.book.report"].create({
            "company_id": self.company.id,
            "date_from": self.today - timedelta(days=60),
            "date_to": self.today - timedelta(days=30),
        })
        layers = wizard.search_valuation_layers()
        assert len(layers) == 0

    def test_get_old_stock_by_product_empty(self):
        # Crea un producto nuevo sin capas de valoración
        tmpl = self.env["product.template"].create({
            "name": "Producto Sin Movimientos",
            "type": "service",
            "uom_id": self.uom_unit.id,
            "categ_id": self.category_all.id,
        })
        product = tmpl.product_variant_id
        wizard = self.env["wizard.stock.book.report"].create({
            "company_id": self.company.id,
            "date_from": self.today,
            "date_to": self.tomorrow,
        })
        result = wizard.get_old_stock_by_product(product.id)
        assert result["total_stock_qty"] == 0
        assert result["old_stock_total"] == 0

    def test_parse_stock_book_data_empty(self):
        wizard = self.env["wizard.stock.book.report"].create({
            "company_id": self.company.id,
            "date_from": self.today - timedelta(days=60),
            "date_to": self.today - timedelta(days=30),
        })
        layers = wizard.search_valuation_layers()
        for layer in layers:
            move = layer.stock_move_id
            if not hasattr(move, "production_id"):
                setattr(move, "production_id", None)
        lines = wizard.parse_stock_book_data()
        assert isinstance(lines, list)
        assert len(lines) == 0

    def test_fields_stock_book_line(self):
        movements = {
            "stock_move_id": 1,
            "old_stock": 10,
            "incoming": 5,
            "withdraw": -2,
            "outgoing": -3,
            "total_stock_qty_product": 10,
            "old_stock_total": 100,
            "self_consumption": -1,
            "self_consumption_total": -50,
            "incoming_total": 200,
            "outgoing_total": -150,
            "total_stock_qty_product_bs": 250,
            "withdraw_total": -20,
        }
        line = self.wizard._fields_stock_book_line(self.product.id, movements)
        assert line["description"] == self.product.name
        assert line["old_stock"] == 10
        assert line["incoming_stock"] == 5
        assert line["withdraw"] == 2
        assert line["outgoing_stock"] == 3
        assert line["self_con"] == 1
        assert line["self_consumption_total"] == 50
        assert line["incoming_total"] == 200
        assert line["outgoing_total"] == 150
        assert line["withdraw_total"] == 20

    def test_stock_book_fields_structure(self):
        fields = self.wizard.stock_book_fields()
        assert isinstance(fields, list)
        assert any(f["field"] == "description" for f in fields)
