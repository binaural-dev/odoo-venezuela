from datetime import date

from psycopg2 import IntegrityError

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install", "l10n_ve_rate")
class TestComputeRateFallback(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.company.currency_id = self.env.ref("base.VEF")
        self.foreign_currency = self.env.ref("base.USD")
        self.Rate = self.env["res.currency.rate"]
        # the database may already ship USD rates: start without any
        self.Rate.search([
            ("currency_id", "=", self.foreign_currency.id),
            ("company_id", "=", self.company.id),
        ]).unlink()

    def _create_rate(self, day, rate_value):
        return self.Rate.create({
            "currency_id": self.foreign_currency.id,
            "company_id": self.company.id,
            "name": day,
            "rate": rate_value,
        })

    def test_compute_rate_uses_rate_of_the_exact_date(self):
        """Con tasa para la fecha exacta se usa esa, no otra."""
        self._create_rate(date(2023, 1, 1), 40.0)
        exact = self._create_rate(date(2023, 6, 1), 45.0)
        self._create_rate(date(2023, 12, 1), 50.0)

        result = self.Rate.compute_rate(self.foreign_currency.id, date(2023, 6, 1))

        self.assertEqual(result["foreign_rate"], exact.inverse_company_rate)
        self.assertEqual(result["foreign_inverse_rate"], exact.company_rate)

    def test_rate_of_zero_cannot_be_stored(self):
        """Evidencia: Odoo 19 (`CHECK (rate>0)`) impide guardar una tasa en 0,
        asi que una tasa existente nunca produce un asiento con tasa 0,00; la
        unica falla posible es la ausencia del registro (ver
        test_compute_rate_raises_when_no_rate_for_exact_date).
        """
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.env.cr.savepoint():
            self._create_rate(date(2023, 6, 1), 0.0)

    def test_compute_rate_raises_when_no_rate_for_exact_date(self):
        """No se usa la tasa más cercana: ni la anterior ni la posterior."""
        self._create_rate(date(2023, 1, 1), 40.0)
        self._create_rate(date(2023, 12, 1), 50.0)

        for day in (date(2020, 1, 1), date(2023, 6, 1), date(2030, 1, 1)):
            with self.subTest(day=day), self.assertRaisesRegex(UserError, "no rate assigned"):
                self.Rate.compute_rate(self.foreign_currency.id, day)

    def test_compute_rate_returns_empty_when_raise_is_disabled(self):
        """raise_if_not_found=False keeps the silent behaviour: {} (sin ninguna tasa)."""
        result = self.Rate.compute_rate(
            self.foreign_currency.id, date(2020, 1, 1), raise_if_not_found=False,
        )

        self.assertEqual(result, {})

    def test_compute_rate_of_company_currency_without_rate_is_one(self):
        """The company currency against itself is 1 even with no recorded rate."""
        self.Rate.search([("currency_id", "=", self.company.currency_id.id)]).unlink()
        self.assertEqual(
            self.Rate.compute_rate(self.company.currency_id.id, date(2023, 1, 1)),
            {"foreign_rate": 1.0, "foreign_inverse_rate": 1.0},
        )

    def test_compute_rate_without_foreign_currency_returns_empty(self):
        """No foreign currency means nothing to look up: not a missing rate."""
        self.assertEqual(self.Rate.compute_rate(False, date(2023, 1, 1)), {})

    def test_compute_rate_raises_by_default_when_no_rate_exists_at_all(self):
        """With no rate at all for this currency/company compute_rate raises."""
        with self.assertRaisesRegex(UserError, "no rate assigned"):
            self.Rate.compute_rate(self.foreign_currency.id, date(2023, 1, 1))

    def test_compute_inverse_rate_raises_without_rate(self):
        for rate in (0, 0.0, False, None):
            with self.subTest(rate=rate), self.assertRaisesRegex(UserError, "no rate assigned"):
                self.Rate.compute_inverse_rate(rate)


@tagged("post_install", "-at_install", "l10n_ve_rate")
class TestRateBranchInheritance(TransactionCase):
    """Sucursales nativas (res.company con parent_id): las tasas y la moneda
    extranjera definidas solo en la matriz deben resolverse desde la sucursal
    en lugar de devolver {} / 0.0.
    """

    def setUp(self):
        super().setUp()
        self.vef = self.env.ref("base.VEF")
        self.usd = self.env.ref("base.USD")
        self.parent = self.env["res.company"].create({
            "name": "Matriz Test",
            "currency_id": self.vef.id,
            "foreign_currency_id": self.usd.id,
        })
        self.branch = self.env["res.company"].create({
            "name": "Sucursal Test",
            "parent_id": self.parent.id,
            "currency_id": self.vef.id,
        })
        self.Rate = self.env["res.currency.rate"]

    def _create_rate(self, company, day, rate_value):
        return self.Rate.with_company(company).create({
            "currency_id": self.usd.id,
            "company_id": company.id,
            "name": day,
            "rate": rate_value,
        })

    def test_branch_inherits_parent_rate(self):
        """La sucursal sin tasa propia usa la tasa de la matriz."""
        parent_rate = self._create_rate(self.parent, date(2023, 6, 1), 0.025)

        result = self.Rate.with_company(self.branch).compute_rate(
            self.usd.id, date(2023, 6, 1),
        )

        self.assertTrue(result, "La sucursal debe heredar la tasa de la matriz")
        self.assertEqual(result["foreign_rate"], parent_rate.inverse_company_rate)
        self.assertEqual(result["foreign_inverse_rate"], parent_rate.company_rate)
        self.assertNotEqual(result["foreign_rate"], 0.0)

    def test_branch_without_any_rate_in_hierarchy_raises(self):
        """Sin tasas en sucursal ni matriz se lanza el error de tasa no asignada."""
        with self.assertRaisesRegex(UserError, "no rate assigned"):
            self.Rate.with_company(self.branch).compute_rate(
                self.usd.id, date(2023, 6, 1),
            )

    def test_branch_without_rate_returns_empty_when_raise_is_disabled(self):
        result = self.Rate.with_company(self.branch).compute_rate(
            self.usd.id, date(2023, 6, 1), raise_if_not_found=False,
        )
        self.assertEqual(result, {})

    def test_branch_uses_exact_date_rate_of_parent(self):
        """La sucursal usa la tasa de la matriz con la fecha exacta."""
        self._create_rate(self.parent, date(2023, 1, 1), 0.020)
        exact = self._create_rate(self.parent, date(2023, 6, 1), 0.025)
        self._create_rate(self.parent, date(2023, 12, 1), 0.030)

        result = self.Rate.with_company(self.branch).compute_rate(
            self.usd.id, date(2023, 6, 1),
        )

        self.assertEqual(result["foreign_rate"], exact.inverse_company_rate)

    def test_branch_raises_when_parent_has_no_rate_for_exact_date(self):
        """Sin tasa de la matriz para esa fecha exacta la sucursal también falla."""
        self._create_rate(self.parent, date(2023, 6, 1), 0.025)

        with self.assertRaisesRegex(UserError, "no rate assigned"):
            self.Rate.with_company(self.branch).compute_rate(
                self.usd.id, date(2023, 6, 2),
            )

    def test_branch_does_not_use_unrelated_company_rates(self):
        """Tasas de una compañía fuera de la jerarquía no deben usarse."""
        other = self.env["res.company"].create({
            "name": "Otra Compañía",
            "currency_id": self.vef.id,
        })
        self._create_rate(other, date(2023, 6, 1), 0.050)

        with self.assertRaisesRegex(UserError, "no rate assigned"):
            self.Rate.with_company(self.branch).compute_rate(
                self.usd.id, date(2023, 6, 1),
            )

    def test_parent_company_still_resolves_own_rate(self):
        """Regresión: la matriz sigue resolviendo su propia tasa."""
        parent_rate = self._create_rate(self.parent, date(2023, 6, 1), 0.025)

        result = self.Rate.with_company(self.parent).compute_rate(
            self.usd.id, date(2023, 6, 1),
        )

        self.assertEqual(result["foreign_rate"], parent_rate.inverse_company_rate)

    def test_compute_inverse_rate_branch_without_currency_returns_rate(self):
        """La moneda alterna es configuración propia de cada compañía: una
        sucursal sin foreign_currency_id no hereda la de la matriz, igual que
        una matriz mal configurada (la tasa no se invierte)."""
        self.assertFalse(self.branch.foreign_currency_id)

        inverse = self.Rate.with_company(self.branch).compute_inverse_rate(40.0)

        self.assertEqual(inverse, 40.0)

    def test_compute_inverse_rate_parent_unchanged(self):
        inverse = self.Rate.with_company(self.parent).compute_inverse_rate(40.0)
        self.assertAlmostEqual(inverse, 1 / 40.0)

    def _create_hierarchy(self, foreign_currency):
        # Se crea con la moneda ya definida: cambiarla vía write() dispara
        # el override de res.company que consulta account.move.line.
        parent = self.env["res.company"].create({
            "name": "Matriz Test 2",
            "currency_id": self.vef.id,
            "foreign_currency_id": foreign_currency.id if foreign_currency else False,
        })
        return self.env["res.company"].create({
            "name": "Sucursal Test 2",
            "parent_id": parent.id,
            "currency_id": self.vef.id,
        })

    def test_compute_inverse_rate_no_foreign_currency_returns_rate(self):
        """Sin moneda extranjera en la compañía, se devuelve la tasa tal cual."""
        branch = self._create_hierarchy(False)

        inverse = self.Rate.with_company(branch).compute_inverse_rate(40.0)

        self.assertEqual(inverse, 40.0)

    def test_compute_inverse_rate_non_usd_foreign_currency_returns_rate(self):
        eur = self.env.ref("base.EUR")
        eur.active = True
        branch = self._create_hierarchy(eur)

        inverse = self.Rate.with_company(branch).compute_inverse_rate(40.0)

        self.assertEqual(inverse, 40.0)


@tagged("post_install", "-at_install", "l10n_ve_rate")
class TestBranchOwnCurrencyAndRate(TransactionCase):
    """Si la sucursal tiene moneda extranjera y/o tasa propia debe usar esas;
    solo si no las tiene se hereda de la matriz."""

    def setUp(self):
        super().setUp()
        self.vef = self.env.ref("base.VEF")
        self.usd = self.env.ref("base.USD")
        self.eur = self.env.ref("base.EUR")
        self.eur.active = True
        self.Rate = self.env["res.currency.rate"]
        self.Company = self.env["res.company"]

    def _hierarchy(self, parent_foreign, branch_foreign):
        parent = self.Company.create({
            "name": "Matriz Own",
            "currency_id": self.vef.id,
            "foreign_currency_id": parent_foreign.id,
        })
        branch = self.Company.create({
            "name": "Sucursal Own",
            "parent_id": parent.id,
            "currency_id": self.vef.id,
            "foreign_currency_id": branch_foreign.id if branch_foreign else False,
        })
        return parent, branch

    def _rate(self, company, currency, day, value):
        return self.Rate.with_company(company).create({
            "currency_id": currency.id,
            "company_id": company.id,
            "name": day,
            "rate": value,
        })

    def test_branch_cannot_have_its_own_rate(self):
        """Odoo 19 solo permite crear tasas en compañías principales, por lo
        que una sucursal nativa nunca tiene tasa propia: siempre se usa la de
        la matriz (cubierto en TestRateBranchInheritance)."""
        _parent, branch = self._hierarchy(self.usd, None)

        with self.assertRaisesRegex(
            ValidationError, "Currency rates should only be created for main companies",
        ):
            self._rate(branch, self.usd, date(2023, 6, 1), 0.020)

    def test_branch_own_foreign_currency_wins_over_parent(self):
        """Matriz USD, sucursal EUR: la sucursal usa EUR (no se invierte)."""
        _parent, branch = self._hierarchy(self.usd, self.eur)

        inverse = self.Rate.with_company(branch).compute_inverse_rate(40.0)

        self.assertEqual(inverse, 40.0)

    def test_branch_own_usd_wins_over_parent_eur(self):
        """Matriz EUR, sucursal USD: la sucursal usa USD (se invierte)."""
        _parent, branch = self._hierarchy(self.eur, self.usd)

        inverse = self.Rate.with_company(branch).compute_inverse_rate(40.0)

        self.assertAlmostEqual(inverse, 1 / 40.0)

    def test_branch_without_currency_does_not_fall_back_to_parent(self):
        _parent, branch = self._hierarchy(self.usd, None)

        inverse = self.Rate.with_company(branch).compute_inverse_rate(40.0)

        self.assertEqual(inverse, 40.0)

    def test_branch_user_without_parent_active_resolves_parent_rate(self):
        """Un usuario interno (no superusuario ni admin) con solo la sucursal
        activa debe resolver la tasa de la matriz sin AccessError."""
        parent, branch = self._hierarchy(self.usd, self.usd)
        self._rate(parent, self.usd, date(2023, 6, 1), 0.025)
        user = self.env["res.users"].create({
            "name": "Facturador Sucursal",
            "login": "facturador_sucursal_rate",
            "company_id": branch.id,
            "company_ids": [(6, 0, [branch.id])],
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        # sin caché: las lecturas deben pasar por las reglas de acceso del usuario
        self.env.invalidate_all()
        Rate = self.Rate.with_user(user).with_context(allowed_company_ids=[branch.id])
        Rate = Rate.with_company(branch)

        result = Rate.compute_rate(self.usd.id, date(2023, 6, 1))

        self.assertAlmostEqual(result["foreign_rate"], 1 / 0.025)
