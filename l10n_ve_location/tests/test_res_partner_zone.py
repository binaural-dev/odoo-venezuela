from psycopg2 import IntegrityError

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_location")
class TestResPartnerZone(TransactionCase):

    def test_create_zone_with_name(self):
        zone = self.env["res.partner.zone"].create({"name": "Zona Norte"})
        self.assertTrue(zone)
        self.assertEqual(zone.name, "Zona Norte")

    def test_create_zone_without_name_raises(self):
        # `name` es required=True en res.partner.zone: al no proveerlo, la
        # violación surge como un error de integridad de PostgreSQL
        # (NOT NULL constraint) al hacer flush del create, no como una
        # ValidationError de aplicación.
        with self.assertRaises(IntegrityError):
            self.env["res.partner.zone"].create({})
            self.env.flush_all()

    def test_partner_zone_id_assignment(self):
        zone = self.env["res.partner.zone"].create({"name": "Zona Este"})
        partner = self.env["res.partner"].create({
            "name": "Cliente Prueba",
            "zone_id": zone.id,
        })
        self.assertEqual(partner.zone_id.name, "Zona Este")

    def test_partner_without_zone_id_is_falsy(self):
        partner = self.env["res.partner"].create({"name": "Cliente Sin Zona"})
        self.assertFalse(partner.zone_id)

    def test_multiple_partners_same_zone(self):
        zone = self.env["res.partner.zone"].create({"name": "Zona Compartida"})
        partner_1 = self.env["res.partner"].create({
            "name": "Cliente Uno",
            "zone_id": zone.id,
        })
        partner_2 = self.env["res.partner"].create({
            "name": "Cliente Dos",
            "zone_id": zone.id,
        })
        self.assertEqual(partner_1.zone_id, zone)
        self.assertEqual(partner_2.zone_id, zone)
