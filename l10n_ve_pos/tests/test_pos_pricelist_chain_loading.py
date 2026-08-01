from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_pos", "slice_b")
class TestPosPricelistChainLoading(TransactionCase):
    """Carga de listas de precios encadenadas en el PdV.

    Contrato en
    ``openspec/changes/l10n-ve-pos-chained-pricelist-loading/specs/pos-chained-pricelist-loading/spec.md``.

    Escenario venezolano: la lista operativa en Bs se ancla a una lista
    intermedia en EUR, que se ancla a la lista de referencia en USD donde viven
    los precios fijos. El core resuelve un solo nivel, así que la lista en USD
    nunca llegaba a la caja y ``getPrice()`` caía a ``list_price``.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vef = cls.env["res.currency"].with_context(active_test=False).search(
            [("name", "=", "VEF")], limit=1
        )
        if cls.vef and not cls.vef.active:
            cls.vef.active = True
        cls.usd = cls.env.ref("base.USD")
        cls.eur = cls.env.ref("base.EUR")
        if not cls.eur.active:
            cls.eur.active = True

        # Compañía en Bs con divisa USD: la forma real de una instalación VE.
        cls.company = cls.env["res.company"].create(
            {
                "name": "Test VE Chain Co",
                "currency_id": cls.vef.id,
                "country_id": cls.env.ref("base.ve").id,
            }
        )
        cls.company.write({"foreign_currency_id": cls.usd.id})

        # Tasas relativas a la moneda de la compañía (VEF): 1 VEF = rate divisa.
        cls.env["res.currency.rate"].search(
            [("company_id", "=", cls.company.id)]
        ).unlink()
        for currency, rate in ((cls.usd, 0.00134), (cls.eur, 0.00116)):
            cls.env["res.currency.rate"].create(
                {
                    "currency_id": currency.id,
                    "rate": rate,
                    "name": "2026-01-01",
                    "company_id": cls.company.id,
                }
            )

        cls.product = cls.env["product.product"].create(
            {
                "name": "Producto Cadena",
                # list_price es un placeholder: el precio real vive en la lista
                # en USD. Si el PdV cae al fallback, se ve este 1.0.
                "lst_price": 1.0,
                "available_in_pos": True,
            }
        )
        cls.fixed_usd_price = 2.0

        # Eslabón 3: precios fijos en USD.
        cls.pl_usd = cls.env["product.pricelist"].create(
            {
                "name": "BASE USD",
                "currency_id": cls.usd.id,
                "company_id": cls.company.id,
                "item_ids": [
                    (
                        0,
                        0,
                        {
                            "applied_on": "1_product",
                            "product_tmpl_id": cls.product.product_tmpl_id.id,
                            "compute_price": "fixed",
                            "fixed_price": cls.fixed_usd_price,
                        },
                    )
                ],
            }
        )
        # Eslabón 2: intermedia en EUR, anclada a la de USD.
        cls.pl_eur = cls.env["product.pricelist"].create(
            {
                "name": "Detal Euro",
                "currency_id": cls.eur.id,
                "company_id": cls.company.id,
                "item_ids": [
                    (
                        0,
                        0,
                        {
                            "applied_on": "3_global",
                            "compute_price": "formula",
                            "base": "pricelist",
                            "base_pricelist_id": cls.pl_usd.id,
                        },
                    )
                ],
            }
        )
        # Eslabón 1: la operativa en Bs, la única disponible en la caja.
        cls.pl_vef = cls.env["product.pricelist"].create(
            {
                "name": "DETAL VEF",
                "currency_id": cls.vef.id,
                "company_id": cls.company.id,
                "item_ids": [
                    (
                        0,
                        0,
                        {
                            "applied_on": "3_global",
                            "compute_price": "formula",
                            "base": "pricelist",
                            "base_pricelist_id": cls.pl_eur.id,
                        },
                    )
                ],
            }
        )

        journal = cls.env["account.journal"].create(
            {
                "name": "POS Chain Sale",
                "type": "sale",
                "code": "POSCH",
                "company_id": cls.company.id,
            }
        )
        # ``pos.config`` exige que los métodos de pago sean de su compañía; los
        # que se asignan por defecto pertenecen a otra.
        cls.payment_method = cls.env["pos.payment.method"].create(
            {
                "name": "Efectivo Bs",
                "is_cash_count": True,
                "company_id": cls.company.id,
                "journal_id": cls.env["account.journal"]
                .create(
                    {
                        "name": "POS Chain Cash",
                        "type": "cash",
                        "code": "POSCC",
                        "company_id": cls.company.id,
                    }
                )
                .id,
            }
        )
        cls.config = cls.env["pos.config"].create(
            {
                "name": "Test POS Chain",
                "company_id": cls.company.id,
                "journal_id": journal.id,
                "invoice_journal_id": cls.env["account.journal"]
                .create(
                    {
                        "name": "POS Chain Invoice",
                        "type": "sale",
                        "code": "POSCI",
                        "company_id": cls.company.id,
                    }
                )
                .id,
                "use_pricelist": True,
                "pricelist_id": cls.pl_vef.id,
                "available_pricelist_ids": [(6, 0, [cls.pl_vef.id])],
                "payment_method_ids": [(6, 0, cls.payment_method.ids)],
            }
        )
        cls.session = cls.env["pos.session"].create(
            {
                "config_id": cls.config.id,
                "user_id": cls.env.ref("base.user_admin").id,
            }
        )

    # -- cierre transitivo ------------------------------------------------

    def test_expand_base_pricelists_walks_the_whole_chain(self):
        """El cierre incluye los tres eslabones, no solo el primero."""
        chain = self.env["product.pricelist"]._pos_expand_base_pricelists(
            [self.pl_vef.id]
        )
        self.assertEqual(
            chain, {self.pl_vef.id, self.pl_eur.id, self.pl_usd.id}
        )

    def test_cycles_are_rejected_by_the_orm(self):
        """Un ciclo nunca llega al loader: el ORM lo rechaza al escribirlo.

        Documenta por qué el guard ``seen`` de ``_pos_expand_base_pricelists``
        es defensa en profundidad (datos cargados por SQL saltándose el ORM) y
        no el manejo de una configuración soportada.
        """
        self.pl_usd.item_ids.unlink()
        with self.assertRaises(ValidationError):
            self.pl_usd.write(
                {
                    "item_ids": [
                        (
                            0,
                            0,
                            {
                                "applied_on": "3_global",
                                "compute_price": "formula",
                                "base": "pricelist",
                                "base_pricelist_id": self.pl_vef.id,
                            },
                        )
                    ]
                }
            )

    def test_expand_base_pricelists_is_idempotent_on_a_flat_pricelist(self):
        """Una lista sin cadena devuelve solo a sí misma.

        Fija que el override no cambia nada en instalaciones sin listas
        encadenadas, que son la mayoría fuera de Venezuela.
        """
        flat = self.env["product.pricelist"].create(
            {
                "name": "Plana",
                "currency_id": self.vef.id,
                "company_id": self.company.id,
            }
        )
        self.assertEqual(
            self.env["product.pricelist"]._pos_expand_base_pricelists([flat.id]),
            {flat.id},
        )

    # -- carga inicial ----------------------------------------------------

    def test_load_data_includes_the_whole_pricelist_chain(self):
        """La lista base de segundo nivel debe llegar a la caja."""
        data = self.session.load_data([])
        loaded_ids = {p["id"] for p in data["product.pricelist"]}
        self.assertIn(self.pl_vef.id, loaded_ids)
        self.assertIn(self.pl_eur.id, loaded_ids)
        self.assertIn(
            self.pl_usd.id,
            loaded_ids,
            "sin la lista base de 2do nivel, getPrice() cae a list_price",
        )

    def test_load_data_includes_fixed_items_of_the_base_pricelist(self):
        """Los items donde viven los precios fijos deben viajar también."""
        data = self.session.load_data([])
        usd_items = [
            item
            for item in data["product.pricelist.item"]
            if item["pricelist_id"] == self.pl_usd.id
        ]
        self.assertTrue(usd_items, "no llegó ningún item de la lista en USD")
        self.assertEqual(usd_items[0]["fixed_price"], self.fixed_usd_price)

    # -- carga on-demand --------------------------------------------------

    def test_on_demand_product_load_includes_base_pricelist_items(self):
        """Un producto que entra por búsqueda debe traer su precio fijo.

        El core restringe esta ruta a ``_get_available_pricelists()``, que nunca
        puede contener las listas base (están en otra moneda y ``pos.config`` lo
        prohíbe), así que sin el override el producto llega sin precio.
        """
        res = self.session.get_pos_ui_product_pricelist_item_by_product(
            self.product.product_tmpl_id.ids, self.product.ids, self.config.id
        )
        item_pricelist_ids = {
            item["pricelist_id"] for item in res["product.pricelist.item"]
        }
        self.assertIn(self.pl_usd.id, item_pricelist_ids)
        loaded_pricelist_ids = {p["id"] for p in res["product.pricelist"]}
        self.assertIn(
            self.pl_usd.id,
            loaded_pricelist_ids,
            "sin el registro de la lista, base_pricelist_id no resuelve en el navegador",
        )

    # -- paridad con el servidor -----------------------------------------

    def test_chain_price_matches_server_side_computation(self):
        """El precio de la cadena no es el placeholder de ``list_price``.

        Fija la referencia contra la que el PdV debe coincidir: el cálculo del
        servidor, no 1.0. Con tasas 1 VEF = 0.00134 USD, 2 USD ≈ 1492.54 Bs.
        """
        server_price = self.pl_vef.with_company(self.company)._get_product_price(
            self.product, 1.0
        )
        self.assertNotAlmostEqual(
            server_price,
            self.product.lst_price,
            places=2,
            msg="el escenario no discrimina: la cadena da lo mismo que list_price",
        )
        expected = self.fixed_usd_price / 0.00134
        self.assertAlmostEqual(server_price, expected, delta=1.0)
