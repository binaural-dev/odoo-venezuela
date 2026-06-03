from datetime import date, timedelta
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged("post_install", "-at_install", "l10n_ve_iot_mf")
class TestIotDeviceInherit(TransactionCase):

    def setUp(self):
        super().setUp()

    def _create_device(self, **kwargs):
        vals = {
            "name": kwargs.get("name", "Test Fiscal Printer HKA"),
            "type": "fiscal_data_module",
            "identifier": kwargs.get("identifier", "test-identifier-001"),
        }
        vals.update(kwargs)
        return self.env["iot.device"].create(vals)

    # --- _compute_manufacturer_type ---

    def test_manufacturer_type_hka(self):
        """Nombre con 'HKA' debe dar manufacturer_type='HKA'."""
        dev = self._create_device(name="Fiscal Printer HKA Model X")
        self.assertEqual(dev.manufacturer_type, "HKA")

    def test_manufacturer_type_pnp(self):
        """Nombre con 'PnP' debe dar manufacturer_type='PnP'."""
        dev = self._create_device(name="PnP Fiscal Printer Model Y")
        self.assertEqual(dev.manufacturer_type, "PnP")

    def test_manufacturer_type_unknown(self):
        """Nombre sin HKA ni PnP debe dar manufacturer_type=False."""
        dev = self._create_device(name="Generic Printer")
        self.assertFalse(dev.manufacturer_type)

    def test_manufacturer_type_hka_in_substring(self):
        """Nombre con 'HKA' en cualquier parte debe detectarse."""
        dev = self._create_device(name="something HKA something")
        self.assertEqual(dev.manufacturer_type, "HKA")

    def test_manufacturer_type_pnp_in_substring(self):
        """Nombre con 'PnP' en cualquier parte debe detectarse."""
        dev = self._create_device(name="something PnP something")
        self.assertEqual(dev.manufacturer_type, "PnP")

    # --- _compute_iot_ip ---

    def test_iot_ip_with_iot_box(self):
        """iot_ip debe tomar el ip del iot.box asociado."""
        box = self.env["iot.box"].create({
            "name": "Box Test",
            "ip": "192.168.1.100",
        })
        dev = self._create_device(iot_box=box.id)
        self.assertEqual(dev.iot_ip, "192.168.1.100")

    def test_iot_ip_with_iot_id(self):
        """iot_ip debe tomar el ip desde iot_id si existe el campo."""
        box = self.env["iot.box"].create({
            "name": "Box Test 2",
            "ip": "10.0.0.50",
        })
        dev = self._create_device(iot_id=box.id)
        self.assertEqual(dev.iot_ip, "10.0.0.50")

    def test_iot_ip_no_box(self):
        """Sin IoT box asociado, iot_ip debe ser False."""
        dev = self._create_device()
        self.assertFalse(dev.iot_ip)

    # --- configure_device ---

    def test_configure_device_default(self):
        """configure_device con valores por defecto."""
        dev = self._create_device()
        config = dev.configure_device()
        self.assertEqual(config["flag_21"], "00")
        self.assertEqual(config["flag_24"], "00")
        self.assertEqual(config["show_version"], "00")

    def test_configure_device_with_show_version(self):
        """show_version=True debe retornar '77'."""
        dev = self._create_device(show_version=True)
        config = dev.configure_device()
        self.assertEqual(config["show_version"], "77")

    def test_configure_device_custom_flags(self):
        """Flags personalizados deben reflejarse."""
        dev = self._create_device(flag_21="30", flag_24="01")
        config = dev.configure_device()
        self.assertEqual(config["flag_21"], "30")
        self.assertEqual(config["flag_24"], "01")

    # --- get_data_to_payment_method ---

    def test_get_data_to_payment_method_ok(self):
        """Datos válidos deben retornar el dict correcto."""
        dev = self._create_device(
            payment_method_name="Transferencia",
            payment_methods="01",
        )
        result = dev.get_data_to_payment_method()
        self.assertEqual(result["payment_method_name"], "Transferencia")
        self.assertEqual(result["payment_methods"], "01")

    def test_get_data_to_payment_method_no_name(self):
        """Sin payment_method_name debe levantar ValidationError."""
        dev = self._create_device(payment_methods="01")
        with self.assertRaises(ValidationError):
            dev.get_data_to_payment_method()

    def test_get_data_to_payment_method_no_methods(self):
        """Sin payment_methods debe levantar ValidationError."""
        dev = self._create_device(payment_method_name="Efectivo")
        with self.assertRaises(ValidationError):
            dev.get_data_to_payment_method()

    # --- get_command ---

    def test_get_command_ok(self):
        """Comando válido debe retornar el dict."""
        dev = self._create_device(command="TEST_CMD")
        result = dev.get_command()
        self.assertEqual(result["command"], "TEST_CMD")

    def test_get_command_empty(self):
        """Comando vacío debe levantar ValidationError."""
        dev = self._create_device()
        with self.assertRaises(ValidationError):
            dev.get_command()

    def test_get_command_false(self):
        """Comando False debe levantar ValidationError."""
        dev = self._create_device(command=False)
        with self.assertRaises(ValidationError):
            dev.get_command()

    # --- get_range_resume ---

    def test_get_range_resume_ok(self):
        """Rango válido debe retornar fechas formateadas en DDMMYY."""
        dev = self._create_device(
            resume_range_from=date(2024, 1, 15),
            resume_range_to=date(2024, 1, 20),
        )
        result = dev.get_range_resume()
        self.assertEqual(result["resume_range_from"], "150124")
        self.assertEqual(result["resume_range_to"], "200124")

    def test_get_range_resume_missing_from(self):
        """Falta resume_range_from debe levantar ValidationError."""
        dev = self._create_device(resume_range_to=date(2024, 1, 20))
        with self.assertRaises(ValidationError):
            dev.get_range_resume()

    def test_get_range_resume_missing_to(self):
        """Falta resume_range_to debe levantar ValidationError."""
        dev = self._create_device(resume_range_from=date(2024, 1, 15))
        with self.assertRaises(ValidationError):
            dev.get_range_resume()

    def test_get_range_resume_to_less_than_from(self):
        """range_to < range_from debe levantar ValidationError."""
        dev = self._create_device(
            resume_range_from=date(2024, 1, 20),
            resume_range_to=date(2024, 1, 15),
        )
        with self.assertRaises(ValidationError):
            dev.get_range_resume()

    def test_get_range_resume_same_date(self):
        """Rango con misma fecha debe ser válido."""
        dev = self._create_device(
            resume_range_from=date(2024, 1, 15),
            resume_range_to=date(2024, 1, 15),
        )
        result = dev.get_range_resume()
        self.assertEqual(result["resume_range_from"], "150124")
        self.assertEqual(result["resume_range_to"], "150124")

    # --- get_range_reprint ---

    def test_get_range_reprint_by_number_ok(self):
        """Reprint por número debe retornar rangos y mode."""
        dev = self._create_device(
            reprint_type="number",
            reprint_range_from_number="100",
            reprint_range_to_number="200",
            reprint_type_number="RF",
        )
        result = dev.get_range_reprint()
        self.assertEqual(result["reprint_range_from"], "100")
        self.assertEqual(result["reprint_range_to"], "200")
        self.assertEqual(result["mode"], "RF")

    def test_get_range_reprint_by_date_ok(self):
        """Reprint por fecha debe retornar fechas formateadas."""
        dev = self._create_device(
            reprint_type="date",
            reprint_range_from_date=date(2024, 3, 1),
            reprint_range_to_date=date(2024, 3, 10),
            reprint_type_date="Rf",
        )
        result = dev.get_range_reprint()
        self.assertEqual(result["reprint_range_from"], "010324")
        self.assertEqual(result["reprint_range_to"], "100324")
        self.assertEqual(result["mode"], "Rf")

    def test_get_range_reprint_number_missing_fields(self):
        """Reprint por número sin rangos debe levantar ValidationError."""
        dev = self._create_device(reprint_type="number")
        with self.assertRaises(ValidationError):
            dev.get_range_reprint()

    def test_get_range_reprint_date_missing_fields(self):
        """Reprint por fecha sin rangos debe levantar ValidationError."""
        dev = self._create_device(reprint_type="date")
        with self.assertRaises(ValidationError):
            dev.get_range_reprint()

    def test_get_range_reprint_number_to_less_than_from(self):
        """range_to < range_from en number debe levantar ValidationError."""
        dev = self._create_device(
            reprint_type="number",
            reprint_range_from_number="200",
            reprint_range_to_number="100",
        )
        with self.assertRaises(ValidationError):
            dev.get_range_reprint()

    def test_get_range_reprint_date_to_less_than_from(self):
        """range_to < range_from en date debe levantar ValidationError."""
        dev = self._create_device(
            reprint_type="date",
            reprint_range_from_date=date(2024, 3, 10),
            reprint_range_to_date=date(2024, 3, 1),
        )
        with self.assertRaises(ValidationError):
            dev.get_range_reprint()

    def test_get_range_reprint_number_from_only(self):
        """Solo reprint_range_from_number sin to debe levantar error."""
        dev = self._create_device(
            reprint_type="number",
            reprint_range_from_number="100",
            reprint_range_to_number=False,
        )
        with self.assertRaises(ValidationError):
            dev.get_range_reprint()

    def test_get_range_reprint_date_from_only(self):
        """Solo reprint_range_from_date sin to debe levantar error."""
        dev = self._create_device(
            reprint_type="date",
            reprint_range_from_date=date(2024, 3, 1),
            reprint_range_to_date=False,
        )
        with self.assertRaises(ValidationError):
            dev.get_range_reprint()

    # --- _compute_max_amounts ---

    def test_compute_max_amounts_flag_21_30(self):
        """flag_21='30' debe setear max_amounts."""
        dev = self._create_device(flag_21="30")
        self.assertEqual(dev.max_amount_int, 14)
        self.assertEqual(dev.max_amount_decimal, 2)
        self.assertEqual(dev.max_qty_int, 14)
        self.assertEqual(dev.max_qty_decimal, 3)
        self.assertEqual(dev.max_payment_amount_int, 15)
        self.assertEqual(dev.max_payment_amount_decimal, 2)

    def test_compute_max_amounts_flag_21_00(self):
        """flag_21='00' no debe setear max_amounts (todos False)."""
        dev = self._create_device(flag_21="00")
        self.assertFalse(dev.max_amount_int)
        self.assertFalse(dev.max_amount_decimal)
        self.assertFalse(dev.max_qty_int)
        self.assertFalse(dev.max_qty_decimal)
        self.assertFalse(dev.max_payment_amount_int)
        self.assertFalse(dev.max_payment_amount_decimal)

    def test_compute_max_amounts_flag_21_01(self):
        """flag_21='01' no debe setear max_amounts."""
        dev = self._create_device(flag_21="01")
        self.assertFalse(dev.max_amount_int)

    def test_compute_max_amounts_flag_21_02(self):
        """flag_21='02' no debe setear max_amounts."""
        dev = self._create_device(flag_21="02")
        self.assertFalse(dev.max_amount_int)

    # --- set_serial_machine ---

    def test_set_serial_machine_ok(self):
        """set_serial_machine debe actualizar serial_machine y name."""
        dev = self._create_device()
        response = {
            "data": {
                "_registeredMachineNumber": "SN123456",
            }
        }
        dev.set_serial_machine(response)
        self.assertEqual(dev.serial_machine, "SN123456")
        self.assertIn("SN123456", dev.name)
        self.assertIn("Fiscal Printer HKA", dev.name)

    # --- serial_machine default ---

    def test_serial_machine_default_false(self):
        """serial_machine debe ser False por defecto."""
        dev = self._create_device()
        self.assertFalse(dev.serial_machine)

    # --- traditional_line default ---

    def test_traditional_line_default_true(self):
        """traditional_line debe ser True por defecto."""
        dev = self._create_device()
        self.assertTrue(dev.traditional_line)

    # --- has_cashbox default ---

    def test_has_cashbox_default_false(self):
        """has_cashbox debe ser False por defecto."""
        dev = self._create_device()
        self.assertFalse(dev.has_cashbox)

    # --- max_description default ---

    def test_max_description_default_127(self):
        """max_description debe ser 127 por defecto (deprecated)."""
        dev = self._create_device()
        self.assertEqual(dev.max_description, 127)
