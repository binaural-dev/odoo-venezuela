from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_iot_mf")
class TestIotBox(TransactionCase):

    def setUp(self):
        super().setUp()

    def test_has_fiscal_machine_default_false(self):
        """has_fiscal_machine debe ser False por defecto."""
        box = self.env["iot.box"].create({"name": "Test Box"})
        self.assertFalse(box.has_fiscal_machine)

    def test_has_fiscal_machine_true(self):
        """Se puede activar has_fiscal_machine."""
        box = self.env["iot.box"].create({
            "name": "Test Box",
            "has_fiscal_machine": True,
        })
        self.assertTrue(box.has_fiscal_machine)

    def test_blacklist_default_false(self):
        """blacklist debe ser False por defecto."""
        box = self.env["iot.box"].create({"name": "Test Box"})
        self.assertFalse(box.blacklist)

    def test_blacklist_true(self):
        """Se puede activar blacklist."""
        box = self.env["iot.box"].create({
            "name": "Test Box",
            "blacklist": True,
        })
        self.assertTrue(box.blacklist)

    def test_ip_public_default_false(self):
        """ip_public debe ser False por defecto."""
        box = self.env["iot.box"].create({"name": "Test Box"})
        self.assertFalse(box.ip_public)

    def test_ip_public_custom(self):
        """Se puede asignar una IP pública."""
        box = self.env["iot.box"].create({
            "name": "Test Box",
            "ip_public": "203.0.113.1",
        })
        self.assertEqual(box.ip_public, "203.0.113.1")


@tagged("post_install", "-at_install", "l10n_ve_iot_mf")
class TestSerialPort(TransactionCase):

    def setUp(self):
        super().setUp()
        self.port = self.env["iot.port"].create({"name": "COM1"})

    def test_port_creation(self):
        """Se puede crear un puerto serial."""
        self.assertTrue(self.port)
        self.assertEqual(self.port.name, "COM1")

    def test_port_name_empty(self):
        """El nombre del puerto puede estar vacío."""
        port = self.env["iot.port"].create({"name": False})
        self.assertFalse(port.name)

    def test_port_fiscal_port_ids_relation(self):
        """fiscal_port_ids debe estar vacío por defecto."""
        self.assertFalse(self.port.iot_box_ids)

    def test_port_blacklist_port_ids_relation(self):
        """blacklist_port_ids debe estar vacío por defecto."""
        self.assertFalse(self.port.iot_box_blacklist_ids)
