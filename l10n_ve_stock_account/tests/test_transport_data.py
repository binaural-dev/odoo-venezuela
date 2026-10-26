from lxml import etree

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestTransportData(TransactionCase):
    """Datos de transporte (conductor y vehículo) de la guía de despacho."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env["res.partner"].create({"name": "Cliente Guía Transporte"})
        cls.picking_type_out = cls.env.ref("stock.picking_type_out")
        cls.picking_type_in = cls.env.ref("stock.picking_type_in")
        cls.reason_other_causes = cls.env.ref(
            "l10n_ve_stock_account.transfer_reason_other_causes"
        )
        cls.stock_location = cls.env.ref("stock.stock_location_stock")
        cls.customer_location = cls.env.ref("stock.stock_location_customers")
        cls.product = cls.env["product.product"].create({
            "name": "Producto Transporte",
            "type": "consu",
            "is_storable": True,
        })
        cls.env["stock.quant"].create({
            "product_id": cls.product.id,
            "location_id": cls.stock_location.id,
            "quantity": 100.0,
        })

    def _create_guide(self, picking_type=None, **vals):
        """Guía de despacho de salida sin venta (motivo 'otras causas')."""
        picking_type = picking_type or self.picking_type_out
        location = picking_type.default_location_src_id or self.stock_location
        location_dest = picking_type.default_location_dest_id or self.customer_location
        picking = self.env["stock.picking"].create({
            "picking_type_id": picking_type.id,
            "partner_id": self.partner.id,
            "location_id": location.id,
            "location_dest_id": location_dest.id,
            "transfer_reason_id": self.reason_other_causes.id,
            "other_causes_transfer_reason": "Traslado de prueba",
            "is_dispatch_guide": True,
            "move_ids": [Command.create({
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "product_uom": self.product.uom_id.id,
                "location_id": location.id,
                "location_dest_id": location_dest.id,
            })],
            **vals,
        })
        picking.is_dispatch_guide = True
        return picking

    def _validate(self, picking):
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
        return picking.button_validate()

    def test_plates_and_vat_are_normalized(self):
        picking = self._create_guide(
            transport_vehicle_plate="a12 bc-3d",
            transport_trailer_plate="b45-ef 6g",
            transport_driver_vat="v-12.345.678",
        )
        self.assertEqual(picking.transport_vehicle_plate, "A12BC3D")
        self.assertEqual(picking.transport_trailer_plate, "B45EF6G")
        self.assertEqual(picking.transport_driver_vat, "V12345678")

        picking.write({"transport_vehicle_plate": "zz 99-zz9"})
        self.assertEqual(picking.transport_vehicle_plate, "ZZ99ZZ9")

    def test_company_vat_as_driver_is_rejected(self):
        for prefix in ("J", "G", "C"):
            with self.assertRaises(ValidationError):
                self._create_guide(transport_driver_vat=f"{prefix}123456789")

    def test_person_vat_as_driver_is_allowed(self):
        for prefix in ("V", "E", "P"):
            picking = self._create_guide(transport_driver_vat=f"{prefix}12345678")
            self.assertEqual(picking.transport_driver_vat, f"{prefix}12345678")

    def test_required_transport_data_blocks_validation(self):
        self.company.transport_data_required = True
        picking = self._create_guide(transport_driver_name="Pedro Pérez")
        with self.assertRaises(UserError) as error:
            self._validate(picking)
        self.assertIn(picking.name, str(error.exception))
        self.assertNotEqual(picking.state, "done")
        labels = {
            fname: picking._fields[fname]._description_string(self.env)
            for fname in ("transport_driver_vat", "transport_vehicle_plate")
        }
        self.assertEqual(
            picking._get_transport_missing_fields(),
            [labels["transport_driver_vat"], labels["transport_vehicle_plate"]],
        )

    def test_complete_transport_data_validates(self):
        self.company.transport_data_required = True
        picking = self._create_guide(
            transport_driver_name="Pedro Pérez",
            transport_driver_vat="V12345678",
            transport_vehicle_plate="A12BC3D",
        )
        self._validate(picking)
        self.assertEqual(picking.state, "done")

    def test_not_required_does_not_block(self):
        self.company.transport_data_required = False
        picking = self._create_guide()
        self._validate(picking)
        self.assertEqual(picking.state, "done")

    def test_incoming_is_not_checked(self):
        self.company.transport_data_required = True
        picking = self._create_guide(picking_type=self.picking_type_in)
        self.assertFalse(picking._must_check_transport_data())

    def test_not_dispatch_guide_is_not_checked(self):
        self.company.transport_data_required = True
        picking = self._create_guide()
        picking.is_dispatch_guide = False
        self.assertFalse(picking._must_check_transport_data())

    def test_transport_data_not_copied(self):
        picking = self._create_guide(
            transport_driver_name="Pedro Pérez",
            transport_vehicle_plate="A12BC3D",
        )
        new_picking = picking.copy()
        self.assertFalse(new_picking.transport_driver_name)
        self.assertFalse(new_picking.transport_vehicle_plate)

    def test_default_source_is_manual(self):
        company = self.env["res.company"].create({"name": "Compañía Transporte"})
        self.assertEqual(company.transport_data_source, "manual")
        self.assertFalse(company.transport_data_required)

    def test_report_footer_shows_transport_data(self):
        picking = self._create_guide(
            transport_driver_name="Pedro Pérez",
            transport_driver_vat="V12345678",
            transport_vehicle_brand="Ford",
            transport_vehicle_model="Cargo 1721",
            transport_vehicle_plate="A12BC3D",
            transport_trailer_plate="B45EF6G",
        )
        html = self.env["ir.qweb"]._render(
            "l10n_ve_stock_account.dispatch_layout_footer", {"o": picking}
        )
        for value in ("Pedro Pérez", "V12345678", "Ford Cargo 1721", "A12BC3D", "B45EF6G"):
            self.assertIn(value, str(html))

    def test_new_transport_fields_not_copied_and_printed(self):
        picking = self._create_guide(
            transport_driver_name="Pedro Pérez",
            transport_driver_license_type="5",
            transport_driver_contact="04141234567",
            transport_vehicle_type="Camión",
            transport_vehicle_number="U-07",
        )
        new_picking = picking.copy()
        for fname in (
            "transport_driver_license_type",
            "transport_driver_contact",
            "transport_vehicle_type",
            "transport_vehicle_number",
        ):
            self.assertFalse(new_picking[fname])
        html = str(self.env["ir.qweb"]._render(
            "l10n_ve_stock_account.dispatch_layout_footer", {"o": picking}
        ))
        label = dict(
            picking._fields["transport_driver_license_type"]._description_selection(self.env)
        )["5"]
        for value in (label, "04141234567", "Camión", "U-07"):
            self.assertIn(value, html)

    def test_transport_data_not_locked_without_fleet(self):
        # Sin l10n_ve_stock_account_fleet instalado, 'fleet' no es una
        # fuente disponible: los datos de transporte nunca están bloqueados.
        picking = self._create_guide()
        self.assertFalse(picking.transport_data_locked)

    def test_transport_settings_visible_without_tfhka_gate(self):
        # La config de "Flota" vive en Inventario/Contabilidad, sin el
        # invisible atado a TFHKA que antes la ocultaba.
        info = self.env["res.config.settings"].get_view(view_type="form")
        doc = etree.fromstring(info["arch"])
        nodes = doc.xpath("//div[@id='l10n_ve_settings_transport_data']")
        self.assertTrue(nodes)
        self.assertNotIn("invisible", nodes[0].attrib)
        self.assertTrue(nodes[0].xpath(".//field[@name='transport_data_required']"))

    def test_transport_settings_field_is_persisted_on_company(self):
        settings = self.env["res.config.settings"].create(
            {"transport_data_required": True}
        )
        settings.execute()
        self.assertTrue(self.company.transport_data_required)
