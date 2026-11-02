from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestTransportFleet(TransactionCase):
    """Copia de los datos de transporte de la guía de despacho desde Flota."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.transport_data_source = "fleet"
        brand = cls.env["fleet.vehicle.model.brand"].create({"name": "Ford Prueba"})
        cls.category = cls.env["fleet.vehicle.model.category"].create({"name": "Camión Prueba"})
        cls.model = cls.env["fleet.vehicle.model"].create({
            "name": "Cargo 1721",
            "brand_id": brand.id,
            "category_id": cls.category.id,
        })
        cls.driver = cls.env["res.partner"].create({
            "name": "Pedro Pérez Conductor",
            "prefix_vat": "V",
            "vat": "39876543",
            "phone": "02125551234",
            "driver_license_type": "5",
        })
        cls.vehicle = cls.env["fleet.vehicle"].create({
            "model_id": cls.model.id,
            "license_plate": "A12BC3D",
            "driver_id": cls.driver.id,
            "company_id": cls.company.id,
        })
        cls.trailer = cls.env["fleet.vehicle"].create({
            "model_id": cls.model.id,
            "license_plate": "B45EF6G",
            "is_trailer": True,
            "company_id": cls.company.id,
        })
        cls.partner = cls.env["res.partner"].create({"name": "Cliente Guía Flota"})
        cls.picking_type = cls.env.ref("stock.picking_type_out")
        cls.reason_other_causes = cls.env.ref(
            "l10n_ve_stock_account.transfer_reason_other_causes"
        )

    def _create_picking(self, **vals):
        return self.env["stock.picking"].create({
            "picking_type_id": self.picking_type.id,
            "partner_id": self.partner.id,
            "location_id": self.picking_type.default_location_src_id.id,
            "location_dest_id": self.env.ref("stock.stock_location_customers").id,
            **vals,
        })

    def test_fleet_option_available(self):
        selection = dict(
            self.env["res.company"]._fields["transport_data_source"]._description_selection(self.env)
        )
        self.assertIn("fleet", selection)
        self.assertIn("manual", selection)

    def test_create_with_vehicle_fills_transport_data(self):
        picking = self._create_picking(
            transport_vehicle_id=self.vehicle.id,
            transport_trailer_id=self.trailer.id,
        )
        self.assertEqual(picking.transport_vehicle_plate, "A12BC3D")
        self.assertEqual(picking.transport_vehicle_brand, "Ford Prueba")
        self.assertEqual(picking.transport_vehicle_model, "Cargo 1721")
        self.assertEqual(picking.transport_driver_name, "Pedro Pérez Conductor")
        self.assertEqual(picking.transport_driver_vat, "V39876543")
        self.assertEqual(picking.transport_trailer_plate, "B45EF6G")

    def test_write_vehicle_fills_transport_data(self):
        picking = self._create_picking()
        picking.write({"transport_vehicle_id": self.vehicle.id})
        self.assertEqual(picking.transport_vehicle_plate, "A12BC3D")
        self.assertEqual(picking.transport_driver_name, "Pedro Pérez Conductor")

    def test_write_removing_vehicle_clears_transport_data(self):
        picking = self._create_picking(transport_vehicle_id=self.vehicle.id)
        picking.write({"transport_vehicle_id": False})
        self.assertFalse(picking.transport_vehicle_plate)
        self.assertFalse(picking.transport_vehicle_brand)
        self.assertFalse(picking.transport_vehicle_model)
        self.assertFalse(picking.transport_vehicle_type)
        self.assertFalse(picking.transport_driver_name)
        self.assertFalse(picking.transport_driver_vat)
        self.assertFalse(picking.transport_driver_license_type)
        self.assertFalse(picking.transport_driver_contact)

    def test_write_removing_trailer_clears_trailer_plate(self):
        picking = self._create_picking(transport_trailer_id=self.trailer.id)
        picking.write({"transport_trailer_id": False})
        self.assertFalse(picking.transport_trailer_plate)

    def test_onchange_removing_vehicle_clears_transport_data(self):
        with Form(self.env["stock.picking"]) as form:
            form.picking_type_id = self.picking_type
            form.partner_id = self.partner
            form.transfer_reason_id = self.reason_other_causes
            form.other_causes_transfer_reason = "Prueba Flota"
            form.transport_vehicle_id = self.vehicle
            self.assertEqual(form.transport_vehicle_plate, "A12BC3D")
            form.transport_vehicle_id = self.env["fleet.vehicle"]
            self.assertFalse(form.transport_vehicle_plate)
            self.assertFalse(form.transport_driver_name)

    def test_explicit_driver_overrides_fleet(self):
        picking = self._create_picking(
            transport_vehicle_id=self.vehicle.id,
            transport_driver_name="Juan González",
        )
        self.assertEqual(picking.transport_driver_name, "Juan González")
        self.assertEqual(picking.transport_vehicle_plate, "A12BC3D")

    def test_fleet_changes_do_not_alter_existing_guide(self):
        picking = self._create_picking(transport_vehicle_id=self.vehicle.id)
        self.vehicle.license_plate = "ZZ99ZZ9"
        self.driver.name = "Otro Nombre"
        self.assertEqual(picking.transport_vehicle_plate, "A12BC3D")
        self.assertEqual(picking.transport_driver_name, "Pedro Pérez Conductor")

    def test_onchange_fills_form_and_fields_are_locked(self):
        with Form(self.env["stock.picking"]) as form:
            form.picking_type_id = self.picking_type
            form.partner_id = self.partner
            # La pestaña Transporte solo se ve en guías de despacho.
            form.transfer_reason_id = self.reason_other_causes
            form.other_causes_transfer_reason = "Prueba Flota"
            self.assertTrue(form.is_dispatch_guide)
            form.transport_vehicle_id = self.vehicle
            self.assertEqual(form.transport_vehicle_plate, "A12BC3D")
            self.assertEqual(form.transport_driver_name, "Pedro Pérez Conductor")
            form.transport_trailer_id = self.trailer
            self.assertEqual(form.transport_trailer_plate, "B45EF6G")
            # Con origen "Flota", los campos de VEHÍCULO que se completan
            # solos quedan bloqueados, pero el conductor del día siempre se
            # puede corregir a mano (Escenario 12).
            self.assertFalse(form._get_modifier("transport_driver_name", "readonly"))
            self.assertTrue(form._get_modifier("transport_vehicle_plate", "readonly"))
            self.assertTrue(form._get_modifier("transport_trailer_plate", "readonly"))
        picking = form.record
        self.assertEqual(picking.transport_driver_name, "Pedro Pérez Conductor")
        self.assertEqual(picking.transport_vehicle_plate, "A12BC3D")

    def test_fleet_source_without_vehicle_leaves_fields_editable(self):
        # Transportista externo sin ficha en Flota: el origen de la compañía
        # es 'fleet' pero esta guía no tiene vehículo/batea elegido, así que
        # los datos se pueden seguir cargando a mano.
        with Form(self.env["stock.picking"]) as form:
            form.picking_type_id = self.picking_type
            form.partner_id = self.partner
            form.transfer_reason_id = self.reason_other_causes
            form.other_causes_transfer_reason = "Transportista externo"
            self.assertFalse(form._get_modifier("transport_driver_name", "readonly"))
            self.assertFalse(form._get_modifier("transport_vehicle_plate", "readonly"))
            form.transport_driver_name = "Carlos Externo"
            form.transport_vehicle_plate = "X11YY22"
        picking = form.record
        self.assertEqual(picking.transport_driver_name, "Carlos Externo")
        self.assertEqual(picking.transport_vehicle_plate, "X11YY22")
        self.assertFalse(picking.transport_data_locked)

    def test_fleet_source_with_vehicle_locks_data(self):
        picking = self._create_picking(transport_vehicle_id=self.vehicle.id)
        self.assertTrue(picking.transport_data_locked)

    def test_removing_vehicle_and_trailer_unlocks_transport_data(self):
        picking = self._create_picking(
            transport_vehicle_id=self.vehicle.id,
            transport_trailer_id=self.trailer.id,
        )
        self.assertTrue(picking.transport_data_locked)
        picking.write({"transport_vehicle_id": False, "transport_trailer_id": False})
        self.assertFalse(picking.transport_data_locked)

    def test_write_driver_name_with_vehicle_already_chosen(self):
        # Escenario 12: con un vehículo de Flota ya elegido, el usuario debe
        # poder corregir a mano "el conductor del día" sin quitar el
        # vehículo ni perder la selección.
        picking = self._create_picking(transport_vehicle_id=self.vehicle.id)
        self.assertEqual(picking.transport_driver_name, "Pedro Pérez Conductor")
        picking.write({
            "transport_driver_name": "Suplente del día",
            "transport_driver_vat": "V11223344",
        })
        self.assertEqual(picking.transport_driver_name, "Suplente del día")
        self.assertEqual(picking.transport_driver_vat, "V11223344")
        self.assertEqual(picking.transport_vehicle_id, self.vehicle)
        self.assertEqual(picking.transport_vehicle_plate, "A12BC3D")

    def test_onchange_driver_field_stays_editable_with_vehicle_chosen(self):
        with Form(self.env["stock.picking"]) as form:
            form.picking_type_id = self.picking_type
            form.partner_id = self.partner
            form.transfer_reason_id = self.reason_other_causes
            form.other_causes_transfer_reason = "Prueba Flota"
            form.transport_vehicle_id = self.vehicle
            self.assertFalse(form._get_modifier("transport_driver_name", "readonly"))
            form.transport_driver_name = "Suplente del día"
        picking = form.record
        self.assertEqual(picking.transport_driver_name, "Suplente del día")
        self.assertEqual(picking.transport_vehicle_id, self.vehicle)

    def test_vehicle_field_rejects_trailer(self):
        with self.assertRaises(ValidationError):
            self._create_picking(transport_vehicle_id=self.trailer.id)

    def test_trailer_field_rejects_non_trailer_vehicle(self):
        with self.assertRaises(ValidationError):
            self._create_picking(transport_trailer_id=self.vehicle.id)

    def test_manual_source_leaves_fields_editable(self):
        self.company.transport_data_source = "manual"
        with Form(self.env["stock.picking"]) as form:
            form.picking_type_id = self.picking_type
            form.partner_id = self.partner
            form.transfer_reason_id = self.reason_other_causes
            form.other_causes_transfer_reason = "Prueba Manual"
            self.assertFalse(form._get_modifier("transport_driver_name", "readonly"))
            form.transport_driver_name = "Juan González"
            form.transport_vehicle_plate = "Z99ZZ99"
        picking = form.record
        self.assertEqual(picking.transport_driver_name, "Juan González")
        self.assertEqual(picking.transport_vehicle_plate, "Z99ZZ99")

    def test_vehicle_without_driver(self):
        vehicle = self.env["fleet.vehicle"].create({
            "model_id": self.model.id,
            "license_plate": "C78GH9J",
            "company_id": self.company.id,
        })
        picking = self._create_picking(transport_vehicle_id=vehicle.id)
        self.assertEqual(picking.transport_vehicle_plate, "C78GH9J")
        self.assertFalse(picking.transport_driver_name)
        self.assertFalse(picking.transport_driver_vat)

    def test_vehicle_from_other_company_is_rejected(self):
        other_company = self.env["res.company"].create({"name": "Otra Compañía Flota"})
        vehicle = self.env["fleet.vehicle"].create({
            "model_id": self.model.id,
            "license_plate": "OTR0001",
            "company_id": other_company.id,
        })
        with self.assertRaises(UserError):
            self._create_picking(transport_vehicle_id=vehicle.id)

    def test_vehicle_copies_type_license_and_contact(self):
        picking = self._create_picking(transport_vehicle_id=self.vehicle.id)
        self.assertEqual(picking.transport_vehicle_type, "Camión Prueba")
        self.assertEqual(picking.transport_driver_license_type, "5")
        # Sin móvil: toma el teléfono.
        self.assertEqual(picking.transport_driver_contact, "02125551234")

    def test_driver_mobile_preferred_over_phone(self):
        if "mobile" not in self.driver._fields:
            self.skipTest("res.partner.mobile no existe sin l10n_ve_contact")
        self.driver.mobile = "04141234567"
        picking = self._create_picking(transport_vehicle_id=self.vehicle.id)
        self.assertEqual(picking.transport_driver_contact, "04141234567")

    def test_company_as_driver_is_rejected(self):
        company_contact = self.env["res.partner"].create({
            "name": "Transportes Prueba C.A.",
            "is_company": True,
        })
        with self.assertRaises(ValidationError):
            self.env["fleet.vehicle"].create({
                "model_id": self.model.id,
                "license_plate": "D12EFG3",
                "driver_id": company_contact.id,
                "company_id": self.company.id,
            })

    def test_company_as_future_driver_is_rejected(self):
        company_contact = self.env["res.partner"].create({
            "name": "Transportes Prueba C.A.",
            "is_company": True,
        })
        with self.assertRaises(ValidationError):
            self.vehicle.future_driver_id = company_contact

    def test_vehicle_with_company_driver_blocks_picking(self):
        # Simula un vehiculo guardado antes de que existiera la validacion
        # de Flota (o con datos cargados directo en la base): el driver_id
        # queda apuntando a una empresa sin pasar por el constrains.
        company_contact = self.env["res.partner"].create({
            "name": "Empresa Vieja Flota",
            "is_company": True,
        })
        vehicle = self.env["fleet.vehicle"].create({
            "model_id": self.model.id,
            "license_plate": "E99ZZ99",
            "company_id": self.company.id,
        })
        self.env.cr.execute(
            "UPDATE fleet_vehicle SET driver_id = %s WHERE id = %s",
            (company_contact.id, vehicle.id),
        )
        vehicle.invalidate_recordset()
        with self.assertRaises(ValidationError):
            self._create_picking(transport_vehicle_id=vehicle.id)
