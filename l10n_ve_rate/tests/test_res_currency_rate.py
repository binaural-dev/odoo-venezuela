from datetime import date

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_rate")
class TestComputeRateFallback(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.company.currency_id = self.env.ref("base.VEF")
        self.foreign_currency = self.env.ref("base.USD")
        self.Rate = self.env["res.currency.rate"]

    def _create_rate(self, day, rate_value):
        return self.Rate.create({
            "currency_id": self.foreign_currency.id,
            "company_id": self.company.id,
            "name": day,
            "rate": rate_value,
        })

    def test_compute_rate_returns_empty_by_default_when_date_predates_all_rates(self):
        """By default (raise_if_not_found=False), if rate_date is older than
        every recorded rate for this currency/company, compute_rate returns
        {} instead of raising - this is the path taken by automatic callers
        (record defaults, create()-time comparisons, and the ORM re-triggering
        a compute simply because something read the field), none of which can
        meaningfully react to a hard error.
        """
        self._create_rate(date(2023, 1, 1), 40.0)
        self._create_rate(date(2023, 6, 1), 45.0)

        result = self.Rate.compute_rate(self.foreign_currency.id, date(2020, 1, 1))

        self.assertEqual(result, {})

    def test_compute_rate_raises_when_explicitly_requested_and_date_predates_all_rates(self):
        """With raise_if_not_found=True, the same case above must raise
        UserError instead - reserved for a future call site built
        specifically to let the user act on the error in place.
        """
        self._create_rate(date(2023, 1, 1), 40.0)
        self._create_rate(date(2023, 6, 1), 45.0)

        with self.assertRaises(UserError):
            self.Rate.compute_rate(
                self.foreign_currency.id, date(2020, 1, 1), raise_if_not_found=True,
            )

    def test_compute_rate_uses_closest_earlier_rate_ignoring_later_ones(self):
        """With no rate for rate_date itself but rates both before and after
        it, compute_rate must use the closest one *before* it - rates dated
        after rate_date are excluded by the domain and must never be picked,
        no matter how close they are.
        """
        self._create_rate(date(2023, 1, 1), 40.0)
        closest_before = self._create_rate(date(2023, 6, 1), 45.0)
        self._create_rate(date(2023, 12, 1), 50.0)

        result = self.Rate.compute_rate(self.foreign_currency.id, date(2023, 8, 1))

        self.assertEqual(result["foreign_rate"], closest_before.inverse_company_rate)

    def test_compute_rate_returns_empty_by_default_when_no_rate_exists_at_all(self):
        """With no rate at all for this currency/company, there is nothing
        at or before rate_date to use; by default compute_rate returns {}.
        """
        result = self.Rate.compute_rate(self.foreign_currency.id, date(2023, 1, 1))
        self.assertEqual(result, {})


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

    def test_branch_without_any_rate_in_hierarchy_returns_empty(self):
        """Sin tasas en sucursal ni matriz se mantiene el comportamiento previo."""
        result = self.Rate.with_company(self.branch).compute_rate(
            self.usd.id, date(2023, 6, 1),
        )
        self.assertEqual(result, {})

    def test_branch_without_rate_raises_when_requested(self):
        with self.assertRaises(UserError):
            self.Rate.with_company(self.branch).compute_rate(
                self.usd.id, date(2023, 6, 1), raise_if_not_found=True,
            )

    def test_branch_uses_closest_earlier_rate_across_hierarchy(self):
        """Se toma la tasa más reciente <= fecha dentro de la jerarquía,
        sin considerar tasas posteriores."""
        self._create_rate(self.parent, date(2023, 1, 1), 0.020)
        closest = self._create_rate(self.parent, date(2023, 6, 1), 0.025)
        self._create_rate(self.parent, date(2023, 12, 1), 0.030)

        result = self.Rate.with_company(self.branch).compute_rate(
            self.usd.id, date(2023, 8, 1),
        )

        self.assertEqual(result["foreign_rate"], closest.inverse_company_rate)

    def test_branch_does_not_use_unrelated_company_rates(self):
        """Tasas de una compañía fuera de la jerarquía no deben usarse."""
        other = self.env["res.company"].create({
            "name": "Otra Compañía",
            "currency_id": self.vef.id,
        })
        self._create_rate(other, date(2023, 6, 1), 0.050)

        result = self.Rate.with_company(self.branch).compute_rate(
            self.usd.id, date(2023, 6, 1),
        )

        self.assertEqual(result, {})

    def test_parent_company_still_resolves_own_rate(self):
        """Regresión: la matriz sigue resolviendo su propia tasa."""
        parent_rate = self._create_rate(self.parent, date(2023, 6, 1), 0.025)

        result = self.Rate.with_company(self.parent).compute_rate(
            self.usd.id, date(2023, 6, 1),
        )

        self.assertEqual(result["foreign_rate"], parent_rate.inverse_company_rate)

    def test_compute_inverse_rate_branch_inherits_parent_foreign_currency(self):
        """La sucursal sin foreign_currency_id usa la de la matriz (USD),
        por lo que la tasa se invierte."""
        self.assertFalse(self.branch.foreign_currency_id)

        inverse = self.Rate.with_company(self.branch).compute_inverse_rate(40.0)

        self.assertAlmostEqual(inverse, 1 / 40.0)

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
        """Sin moneda extranjera en toda la jerarquía, se devuelve la tasa tal cual."""
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

    def test_branch_without_currency_falls_back_to_parent(self):
        _parent, branch = self._hierarchy(self.usd, None)

        inverse = self.Rate.with_company(branch).compute_inverse_rate(40.0)

        self.assertAlmostEqual(inverse, 1 / 40.0)
