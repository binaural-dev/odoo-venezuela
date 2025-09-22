
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
        cls.category_all = cls.env.ref("product.product_category_all")
        cls.location_stock = cls.env.ref("stock.stock_location_stock")
        cls.location_supplier = cls.env.ref("stock.stock_location_suppliers")
        cls.location_customer = cls.env.ref("stock.stock_location_customers")
        cls.picking_type_in = cls.env.ref("stock.picking_type_in")
        cls.picking_type_out = cls.env.ref("stock.picking_type_out")

        tmpl = cls.env["product.template"].create({
        "name": "Producto de Prueba",
        "type": "service",
        "uom_id": cls.uom_unit.id,
        "uom_po_id": cls.uom_unit.id,
        "categ_id": cls.category_all.id,
        })

        cls.product = tmpl.product_variant_id


        cls.today = fields.Date.today()
        cls.tomorrow = cls.today + timedelta(days=1)

        cls.wizard = cls.env["wizard.stock.book.report"].create({
            "company_id": cls.company.id,
            "date_from": cls.today,
            "date_to": cls.tomorrow,
        })

        cls.old_move = cls.env["stock.move"].create({
            "name": "Movimiento Viejo",
            "product_id": cls.product.id,
            "product_uom_qty": 2,
            "product_uom": cls.uom_unit.id,
            "company_id": cls.company.id,
            "location_id": cls.location_supplier.id,
            "location_dest_id": cls.location_stock.id,
            "state": "done",
            "picking_type_id": cls.picking_type_in.id,
        })
        cls.old_layer = cls.env["stock.valuation.layer"].create({
            "product_id": cls.product.id,
            "quantity": 2,
            "value": 20,
            "company_id": cls.company.id,
            "stock_move_id": cls.old_move.id,
            "unit_cost": 10,
            "description": "Capa vieja",
        })

        old_datetime = datetime.combine(cls.today - timedelta(days=10), datetime.min.time())
        cls.env.cr.execute(
            "UPDATE stock_valuation_layer SET create_date = %s WHERE id = %s",
            (fields.Datetime.to_string(old_datetime), cls.old_layer.id),
        )

        cls.incoming_move = cls.env["stock.move"].create({
            "name": "Entrada",
            "product_id": cls.product.id,
            "product_uom_qty": 5,
            "product_uom": cls.uom_unit.id,
            "company_id": cls.company.id,
            "location_id": cls.location_supplier.id,
            "location_dest_id": cls.location_stock.id,
            "state": "done",
            "picking_type_id": cls.picking_type_in.id,
        })
        cls.incoming_layer = cls.env["stock.valuation.layer"].create({
            "product_id": cls.product.id,
            "quantity": 5,
            "value": 50,
            "company_id": cls.company.id,
            "stock_move_id": cls.incoming_move.id,
            "unit_cost": 10,
            "description": "Capa de entrada",
        })

        cls.outgoing_move = cls.env["stock.move"].create({
            "name": "Salida",
            "product_id": cls.product.id,
            "product_uom_qty": 3,
            "product_uom": cls.uom_unit.id,
            "company_id": cls.company.id,
            "location_id": cls.location_stock.id,
            "location_dest_id": cls.location_customer.id,
            "state": "done",
            "picking_type_id": cls.picking_type_out.id,
        })
        cls.outgoing_layer = cls.env["stock.valuation.layer"].create({
            "product_id": cls.product.id,
            "quantity": -3,
            "value": -30,
            "company_id": cls.company.id,
            "stock_move_id": cls.outgoing_move.id,
            "unit_cost": 10,
            "description": "Capa de salida",
        })

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
        self.assertIn(("create_date", ">=", self.today), domain)
        self.assertIn(("create_date", "<=", self.tomorrow), domain)
        self.assertIn(("stock_move_id.state", "=", "done"), domain)

    def test_search_valuation_layers_includes_current_period(self):
        layers = self.wizard.search_valuation_layers()
        self.assertIn(self.incoming_layer, layers)
        self.assertIn(self.outgoing_layer, layers)
        self.assertNotIn(self.old_layer, layers)

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
        self.assertEqual(line["incoming_stock"], 0.0)
        self.assertEqual(line["outgoing_stock"], -0.0)
        self.assertEqual(line["stock"], 2)
        self.assertEqual(line["incoming_total"], 0.0)
        self.assertEqual(line["outgoing_total"], -0.0)
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
            "uom_po_id": self.uom_unit.id,
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
            "uom_po_id": self.uom_unit.id,
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
