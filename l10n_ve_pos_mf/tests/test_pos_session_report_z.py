"""Reporte Z de la sesión del PdV (ticket 16406).

``pos.session.set_report_z`` registra en la sesión el número de Z, el serial de
la máquina que la imprimió y la fecha y hora, sin tocar el serial de la caja.
Lo usan la caja (``ClosePosPopup``) y el Kiosko (``l10n_ve_pos_mf_self_order``).
"""

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_pos_mf")
class TestPosSessionReportZ(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        usd = cls.env.ref("base.USD")
        cls.company = cls.env["res.company"].create(
            {
                "name": "MF Report Z Co",
                "currency_id": usd.id,
                "country_id": cls.env.ref("base.ve").id,
            }
        )
        vef = (
            cls.env["res.currency"]
            .with_context(active_test=False)
            .search([("name", "=", "VEF")], limit=1)
        )
        if vef and not vef.active:
            vef.active = True
        cls.company.write({"foreign_currency_id": vef.id})
        cls.env.ref("base.user_admin").company_ids |= cls.company
        sale_journal = cls.env["account.journal"].create(
            {
                "name": "MF Report Z Sale Journal",
                "type": "sale",
                "code": "MFRZS",
                "company_id": cls.company.id,
                "currency_id": vef.id,
            }
        )
        cls.config = cls.env["pos.config"].create(
            {
                "name": "MF Report Z Box",
                "company_id": cls.company.id,
                "currency_id": vef.id,
                "journal_id": sale_journal.id,
                "invoice_journal_id": sale_journal.id,
                "payment_method_ids": [(6, 0, [])],
            }
        )
        cls.session = cls.env["pos.session"].create(
            {"config_id": cls.config.id, "user_id": cls.env.ref("base.user_admin").id}
        )

    def _value(self, serial="Z7C0000001", counter=41):
        return {
            "valid": True,
            "data": {"_registeredMachineNumber": serial, "_dailyClosureCounter": counter},
        }

    def test_set_report_z_stores_z_serial_and_date(self):
        before = fields.Datetime.now()

        self.session.set_report_z(self._value(counter=41))

        self.assertEqual(self.session.report_z, "42")
        self.assertEqual(self.session.serial_machine, "Z7C0000001")
        self.assertTrue(self.session.report_z_date)
        self.assertGreaterEqual(self.session.report_z_date, before.replace(microsecond=0))

    def test_set_report_z_does_not_touch_box_serial(self):
        """La sesión guarda el serial de la máquina que imprimió la Z; el de la
        caja no cambia, esté vacío o cargado."""
        self.session.set_report_z(self._value(serial="Z7C0000001"))
        self.assertFalse(self.config.serial_machine)

        self.config.serial_machine = "Z7C0000099"
        self.session.set_report_z(self._value(serial="Z7C0000001"))

        self.assertEqual(self.config.serial_machine, "Z7C0000099")
        self.assertEqual(self.session.serial_machine, "Z7C0000001")

    def test_session_serial_is_kept_when_box_changes_machine(self):
        """El serial es de la sesión: cambiar la máquina de la caja no cambia
        el de las sesiones que ya sacaron su Z."""
        self.session.set_report_z(self._value(serial="Z7C0000001"))

        self.config.serial_machine = "Z7C0000777"

        self.assertEqual(self.session.serial_machine, "Z7C0000001")

    def test_set_report_z_as_pos_user(self):
        """El cajero (usuario de PdV, sin permisos sobre la caja) puede
        registrar la Z de su sesión."""
        cashier = self.env["res.users"].create(
            {
                "name": "MF Report Z Cashier",
                "login": "mf_report_z_cashier",
                "company_id": self.company.id,
                "company_ids": [(6, 0, [self.company.id])],
                "group_ids": [(6, 0, [self.env.ref("point_of_sale.group_pos_user").id])],
            }
        )

        self.session.with_user(cashier).with_company(self.company).set_report_z(self._value())

        self.assertEqual(self.session.report_z, "42")
        self.assertEqual(self.session.serial_machine, "Z7C0000001")
