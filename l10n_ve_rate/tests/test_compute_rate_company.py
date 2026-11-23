from datetime import date, datetime

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, freeze_time, tagged


@tagged("post_install", "-at_install", "l10n_ve_rate")
class TestComputeRateCompany(TransactionCase):
    """La tasa se busca en la compañía del documento (`with_company`), se puede
    usar la última anterior si la compañía no exige la tasa del día, y la fecha es
    la local aunque el usuario no tenga zona horaria."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vef = cls.env.ref("base.VEF")
        cls.usd = cls.env.ref("base.USD")
        cls.company_a = cls.env["res.company"].create({
            "name": "Compañía A sin tasa",
            "currency_id": cls.vef.id,
            "foreign_currency_id": cls.usd.id,
        })
        cls.company_b = cls.env["res.company"].create({
            "name": "Compañía B con tasa",
            "currency_id": cls.vef.id,
            "foreign_currency_id": cls.usd.id,
        })
        cls.env.user.company_ids |= cls.company_a | cls.company_b
        cls.Rate = cls.env["res.currency.rate"]
        cls.rate_b = cls.Rate.with_company(cls.company_b).create({
            "currency_id": cls.usd.id,
            "company_id": cls.company_b.id,
            "name": date(2026, 10, 26),
            "rate": 1.0 / 40.0,
        })
        # VEF = 1 también: hay localizaciones (turaser) que exigen la tasa del día de
        # la moneda de la compañía.
        cls.Rate.with_company(cls.company_b).create({
            "currency_id": cls.vef.id,
            "company_id": cls.company_b.id,
            "name": date(2026, 10, 26),
            "rate": 1.0,
        })

    def _rate_env(self, *companies):
        """`res.currency.rate` con varias compañías seleccionadas y la primera activa."""
        return self.Rate.with_context(allowed_company_ids=[c.id for c in companies])

    def test_document_company_rate_with_other_active_company(self):
        """Con A activa (sin tasa) y B también seleccionada, la tasa del documento de B
        se encuentra con `with_company(B)`."""
        Rate = self._rate_env(self.company_a, self.company_b)
        self.assertEqual(Rate.env.company, self.company_a)

        result = Rate.with_company(self.company_b).compute_rate(self.usd.id, date(2026, 10, 26))

        self.assertAlmostEqual(result["foreign_rate"], 40.0)
        with self.assertRaisesRegex(UserError, "no rate assigned"):
            Rate.compute_rate(self.usd.id, date(2026, 10, 26))

    def test_require_daily_rate_is_on_by_default(self):
        self.assertTrue(self.company_b.l10n_ve_require_daily_rate)
        with self.assertRaisesRegex(UserError, "no rate assigned"):
            self.Rate.with_company(self.company_b).compute_rate(self.usd.id, date(2026, 10, 28))

    def test_without_daily_rate_uses_most_recent_previous_rate(self):
        self.company_b.l10n_ve_require_daily_rate = False

        result = self.Rate.with_company(self.company_b).compute_rate(
            self.usd.id, date(2026, 10, 28)
        )

        self.assertAlmostEqual(result["foreign_rate"], 40.0)

    def test_without_daily_rate_and_no_previous_rate_raises(self):
        self.company_b.l10n_ve_require_daily_rate = False

        with self.assertRaisesRegex(UserError, "no rate assigned"):
            self.Rate.with_company(self.company_b).compute_rate(self.usd.id, date(2026, 10, 25))

    def test_option_is_per_company(self):
        """Apagar la opción en A no cambia B."""
        self.company_a.l10n_ve_require_daily_rate = False

        with self.assertRaisesRegex(UserError, "no rate assigned"):
            self.Rate.with_company(self.company_b).compute_rate(self.usd.id, date(2026, 10, 28))

    # 2026-10-27 01:00 UTC = 2026-10-26 21:00 en Caracas
    @freeze_time("2026-10-27 01:00:00")
    def test_local_date_without_user_timezone(self):
        """Sin zona en el contexto ni en el usuario se usa America/Caracas, no UTC:
        a las 9 pm del 26 la fecha de la tasa sigue siendo el 26."""
        self.env.user.tz = False
        Rate = self.Rate.with_context(tz=False).with_company(self.company_b)

        self.assertAlmostEqual(Rate.compute_rate(self.usd.id, False)["foreign_rate"], 40.0)
        self.assertAlmostEqual(
            Rate.compute_rate(self.usd.id, datetime(2026, 10, 27, 1, 0))["foreign_rate"], 40.0
        )

    @freeze_time("2026-10-27 01:00:00")
    def test_local_date_uses_company_timezone_first(self):
        """Sin zona del usuario, la de la compañía gana sobre America/Caracas: en UTC ya
        es el 27, que no tiene tasa."""
        self.env.user.tz = False
        self.company_b.partner_id.tz = "UTC"
        Rate = self.Rate.with_context(tz=False).with_company(self.company_b)

        with self.assertRaisesRegex(UserError, "no rate assigned"):
            Rate.compute_rate(self.usd.id, False)
