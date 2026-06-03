import json
from unittest.mock import patch
from odoo.tests import TransactionCase, tagged
from odoo import fields


@tagged("post_install", "-at_install", "l10n_ve_iot_mf")
class TestApiIoT(TransactionCase):

    def setUp(self):
        super().setUp()

    def test_get_fiscal_ports_empty(self):
        """Sin IoT boxes con máquina fiscal, debe retornar {}."""
        response = self.url_open("/iot_fiscal/ports")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data, {})

    def test_get_fiscal_ports_with_data(self):
        """Con IoT box fiscal, debe retornar sus puertos."""
        box = self.env["iot.box"].create({
            "name": "Test Box",
            "identifier": "box-001",
            "has_fiscal_machine": True,
        })
        port = self.env["iot.port"].create({"name": "COM1"})
        box.write({"fiscal_port_ids": [(4, port.id)]})
        response = self.url_open("/iot_fiscal/ports")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("box-001", data)
        self.assertIn("COM1", data["box-001"])

    def test_get_blacklist_ports_empty(self):
        """Sin IoT boxes con blacklist, debe retornar {}."""
        response = self.url_open("/iot_blacklist/ports")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data, {})

    def test_get_blacklist_ports_with_data(self):
        """Con IoT box blacklist, debe retornar sus puertos bloqueados."""
        box = self.env["iot.box"].create({
            "name": "Test Box",
            "identifier": "box-002",
            "blacklist": True,
        })
        port = self.env["iot.port"].create({"name": "COM3"})
        box.write({"blacklist_port_ids": [(4, port.id)]})
        response = self.url_open("/iot_blacklist/ports")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("box-002", data)
        self.assertIn("COM3", data["box-002"])
