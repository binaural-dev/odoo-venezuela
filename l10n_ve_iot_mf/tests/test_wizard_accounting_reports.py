from datetime import date
from odoo.tests import TransactionCase, tagged
from odoo import fields


@tagged("post_install", "-at_install", "l10n_ve_iot_mf")
class TestWizardAccountingReports(TransactionCase):

    def setUp(self):
        super().setUp()
        self.currency_vef = self.env.ref("base.VEF")
        self.company = self.env.ref("base.main_company")
        self.company.write({
            "invoice_print_type": "fiscal",
        })

        self.tax_iva16 = self.env["account.tax"].create({
            "name": "IVA 16%",
            "amount": 16,
            "amount_type": "percent",
            "type_tax_use": "sale",
            "fiscal_code": 1,
        })
        self.tax_iva08 = self.env["account.tax"].create({
            "name": "IVA 8%",
            "amount": 8,
            "amount_type": "percent",
            "type_tax_use": "sale",
            "fiscal_code": 2,
        })

        self.product = self.env["product.product"].create({
            "name": "Producto Prueba",
            "type": "service",
            "list_price": 100,
            "taxes_id": [(6, 0, [self.tax_iva16.id])],
        })

        self.partner = self.env["res.partner"].create({
            "name": "Test Partner",
            "customer_rank": 1,
            "vat": "12345678",
            "prefix_vat": "J",
            "taxpayer_type": "ordinary",
        })

        self.partner_natural = self.env["res.partner"].create({
            "name": "Test Partner Natural",
            "customer_rank": 1,
            "vat": "12345678",
            "prefix_vat": "V",
            "taxpayer_type": "ordinary",
        })

        self.journal = self.env["account.journal"].create({
            "name": "Diario Ventas Test",
            "code": "TVEN",
            "type": "sale",
            "company_id": self.company.id,
        })

        self.iot_box = self.env["iot.box"].create({
            "name": "IoT Box Test",
            "ip": "192.168.1.100",
        })

        self.iot_device = self.env["iot.device"].create({
            "name": "Fiscal Printer HKA",
            "type": "fiscal_data_module",
            "identifier": "iot-test-001",
            "serial_machine": "SN-TEST-001",
            "iot_box": self.iot_box.id,
        })

    def _create_invoice(self, **kwargs):
        invoice_vals = {
            "move_type": kwargs.get("move_type", "out_invoice"),
            "partner_id": kwargs.get("partner", self.partner).id,
            "journal_id": self.journal.id,
            "invoice_date": fields.Date.today(),
            "invoice_date_display": fields.Date.today(),
            "company_id": self.company.id,
            "currency_id": self.currency_vef.id,
            "state": "posted",
            "iot_mf": self.iot_device.id,
            "mf_invoice_number": kwargs.get("mf_invoice_number"),
            "mf_serial": kwargs.get("mf_serial", "SN-TEST-001"),
            "mf_reportz": kwargs.get("mf_reportz"),
            "invoice_line_ids": [
                (0, 0, {
                    "product_id": self.product.id,
                    "quantity": 1,
                    "price_unit": 100,
                    "tax_ids": [(6, 0, [self.tax_iva16.id])],
                })
            ],
        }
        invoice_vals.update(kwargs)
        return self.env["account.move"].create(invoice_vals)

    # --- _get_domain ---

    def test_get_domain_with_fiscal_machine(self):
        """with_fiscal_machine=True debe agregar filtros de campos fiscales."""
        wizard = self.env["wizard.accounting.reports"].create({
            "with_fiscal_machine": True,
        })
        domain = wizard._get_domain()
        self.assertIn(("mf_invoice_number", "!=", False), domain)
        self.assertIn(("mf_reportz", "!=", False), domain)
        self.assertIn(("mf_serial", "!=", False), domain)

    def test_get_domain_without_fiscal_machine(self):
        """with_fiscal_machine=False no debe modificar el domain."""
        wizard = self.env["wizard.accounting.reports"].create({
            "with_fiscal_machine": False,
        })
        domain = wizard._get_domain()
        has_fiscal_filters = any(
            f[0] in ("mf_invoice_number", "mf_reportz", "mf_serial")
            for f in domain if isinstance(f, tuple)
        )
        self.assertFalse(has_fiscal_filters)

    # --- search_moves ---

    def test_search_moves_with_fiscal_machine(self):
        """search_moves con with_fiscal_machine=True debe filtrar por mf_serial."""
        self._create_invoice(mf_invoice_number="100", mf_reportz="5")
        self._create_invoice(mf_invoice_number="101", mf_reportz="5", mf_serial=False)
        wizard = self.env["wizard.accounting.reports"].create({
            "with_fiscal_machine": True,
        })
        moves = wizard.search_moves()
        for move in moves:
            self.assertTrue(move.mf_serial)

    def test_search_moves_without_fiscal_machine(self):
        """search_moves sin filtro debe retornar facturas."""
        self._create_invoice(mf_invoice_number="100", mf_reportz="5")
        wizard = self.env["wizard.accounting.reports"].create({
            "with_fiscal_machine": False,
        })
        moves = wizard.search_moves()
        self.assertTrue(len(moves) > 0)

    # --- _get_sale_book_field_groups ---

    def test_get_sale_book_field_groups_with_fiscal(self):
        """Con with_fiscal_machine, debe inyectar columnas Reporte Z y Serial."""
        wizard = self.env["wizard.accounting.reports"].create({
            "with_fiscal_machine": True,
        })
        groups = wizard._get_sale_book_field_groups()
        found = False
        for group in groups:
            if group.get("header") == "DETALLE DEL DOCUMENTO":
                fields_list = group["fields"]
                field_names = [f["field"] for f in fields_list]
                self.assertIn("mf_reportz", field_names)
                self.assertIn("mf_serial", field_names)
                found = True
                break
        self.assertTrue(found)

    def test_get_sale_book_field_groups_without_fiscal(self):
        """Sin with_fiscal_machine, no debe inyectar columnas."""
        wizard = self.env["wizard.accounting.reports"].create({
            "with_fiscal_machine": False,
        })
        groups = wizard._get_sale_book_field_groups()
        for group in groups:
            if group.get("header") == "DETALLE DEL DOCUMENTO":
                field_names = [f["field"] for f in group["fields"]]
                self.assertNotIn("mf_reportz", field_names)
                self.assertNotIn("mf_serial", field_names)

    # --- _fields_sale_book_line ---

    def test_fields_sale_book_line_with_fiscal(self):
        """_fields_sale_book_line con fiscal debe usar mf_invoice_number."""
        move = self._create_invoice(mf_invoice_number="100", mf_reportz="5")
        wizard = self.env["wizard.accounting.reports"].create({
            "with_fiscal_machine": True,
        })
        taxes = []
        result = wizard._fields_sale_book_line(move, taxes)
        self.assertEqual(result.get("document_number"), "100")
        self.assertEqual(result.get("mf_reportz"), "5")
        self.assertEqual(result.get("mf_serial"), "SN-TEST-001")

    def test_fields_sale_book_line_without_fiscal(self):
        """_fields_sale_book_line sin fiscal debe usar correlative del super."""
        move = self._create_invoice(mf_invoice_number="100", mf_reportz="5")
        wizard = self.env["wizard.accounting.reports"].create({
            "with_fiscal_machine": False,
        })
        taxes = []
        result = wizard._fields_sale_book_line(move, taxes)
        self.assertIn("correlative", result)

    # --- update_amounts ---

    def test_update_amounts_empty_to_some(self):
        """update_amounts desde vacío debe acumular correctamente."""
        wizard = self.env["wizard.accounting.reports"].create({})
        cumulative = {
            "amount_taxed": 0,
            "tax_base_exempt_aliquot": 0,
            "tax_base_reduced_aliquot": 0,
            "amount_reduced_aliquot": 0,
            "tax_base_general_aliquot": 0,
            "amount_general_aliquot": 0,
        }
        amounts = {
            "amount_taxed": 100,
            "tax_base_exempt_aliquot": 50,
            "tax_base_reduced_aliquot": 30,
            "amount_reduced_aliquot": 10,
            "tax_base_general_aliquot": 20,
            "amount_general_aliquot": 5,
        }
        result = wizard.update_amounts(cumulative, amounts)
        self.assertEqual(result["amount_taxed"], 100)
        self.assertEqual(result["tax_base_general_aliquot"], 20)

    def test_update_amounts_accumulate(self):
        """update_amounts debe acumular correctamente."""
        wizard = self.env["wizard.accounting.reports"].create({})
        cumulative = {
            "amount_taxed": 100,
            "tax_base_exempt_aliquot": 50,
            "tax_base_reduced_aliquot": 30,
            "amount_reduced_aliquot": 10,
            "tax_base_general_aliquot": 20,
            "amount_general_aliquot": 5,
        }
        amounts = {
            "amount_taxed": 200,
            "tax_base_exempt_aliquot": 25,
            "tax_base_reduced_aliquot": 15,
            "amount_reduced_aliquot": 5,
            "tax_base_general_aliquot": 10,
            "amount_general_aliquot": 3,
        }
        result = wizard.update_amounts(cumulative, amounts)
        self.assertEqual(result["amount_taxed"], 300)
        self.assertEqual(result["tax_base_general_aliquot"], 30)

    # --- _fields_sale_book_group_line ---

    def test_fields_sale_book_group_line(self):
        """_fields_sale_book_group_line debe generar línea de resumen."""
        wizard = self.env["wizard.accounting.reports"].create({})
        data = {
            "date": date.today(),
            "range_start": "100",
            "range_end": "105",
            "mf_reportz": "5",
            "mf_serial": "SN-TEST-001",
            "move_type": "out_invoice",
        }
        amounts = {
            "amount_taxed": 500,
            "tax_base_exempt_aliquot": 0,
            "tax_base_reduced_aliquot": 0,
            "amount_reduced_aliquot": 0,
            "tax_base_general_aliquot": 400,
            "amount_general_aliquot": 64,
        }
        result = wizard._fields_sale_book_group_line(data, amounts)
        self.assertEqual(result["vat"], "RESUMEN")
        self.assertEqual(result["partner_name"], "Resumen Diario de Ventas")
        self.assertEqual(result["document_number"], "Desde 100 Hasta 105")
        self.assertEqual(result["mf_reportz"], "5")
        self.assertEqual(result["mf_serial"], "SN-TEST-001")
