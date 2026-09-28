from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_invoice_digital")
class TestTfhkaServiceBase(TransactionCase):
    def setUp(self):
        super().setUp()
        self.service = self.env["tfhka.service.base"]

    def _set_city(self, vals, name, state, country):
        """``l10n_ve_location`` (no es dependencia de este módulo, pero suele
        convivir instalado junto a él) convierte ``res.partner.city`` en un
        campo ``related`` de solo lectura sobre ``city_id`` (Many2one a
        ``res.country.city``): asignar el string directo no tiene efecto.
        Si ese módulo está instalado, resuelve/crea el ``res.country.city``
        y usa ``city_id``; si no, usa el ``city`` Char normal.
        """
        if "city_id" in self.env["res.partner"]._fields:
            city = self.env["res.country.city"].search(
                [("name", "=", name), ("state_id", "=", state.id)], limit=1
            )
            if not city:
                city = self.env["res.country.city"].create(
                    {"name": name, "state_id": state.id, "country_id": country.id}
                )
            return {**vals, "city_id": city.id}
        return {**vals, "city": name}

    def test_get_party_address_full(self):
        """Se arma localmente (sin contact_address ni
        contact_address_complete, ver _get_party_address): calle, calle 2,
        código postal + ciudad, estado y país, sin repetir el nombre del
        contacto (ya va en razonSocial) y sin saltos de línea."""
        country = self.env.ref("base.ve")
        state = self.env["res.country.state"].search(
            [("country_id", "=", country.id)], limit=1
        )
        vals = self._set_city(
            {
                "name": "Tercero de prueba",
                "street": "Carrera 20 con calle 19 y 20",
                "street2": "Calle 11",
                "zip": "3001",
                "state_id": state.id,
                "country_id": country.id,
            },
            "Barquisimeto",
            state,
            country,
        )
        partner = self.env["res.partner"].create(vals)
        address = self.service._get_party_address(partner)
        self.assertEqual(
            address,
            "Carrera 20 con calle 19 y 20, Calle 11, 3001 Barquisimeto, "
            f"{state.name}, Venezuela",
        )
        self.assertNotIn(partner.name, address)
        self.assertNotIn("\n", address)

    def test_get_party_address_skips_missing_fields(self):
        """Sin street2/código postal/ciudad/estado, no deja comas ni
        segmentos vacíos de más."""
        partner = self.env["res.partner"].create(
            {
                "name": "Tercero sin datos completos",
                "street": "Av. Principal",
                "country_id": self.env.ref("base.ve").id,
            }
        )
        self.assertEqual(
            self.service._get_party_address(partner),
            "Av. Principal, Venezuela",
        )

    def test_get_party_address_falls_back_when_empty(self):
        """``l10n_ve_contact`` (dependencia de este módulo) pone
        ``country_id`` por defecto en Venezuela para cualquier partner
        nuevo: hay que forzarlo vacío para probar el caso realmente sin
        dirección."""
        partner = self.env["res.partner"].create(
            {"name": "Sin dirección", "country_id": False}
        )
        self.assertEqual(self.service._get_party_address(partner), "no definida")
