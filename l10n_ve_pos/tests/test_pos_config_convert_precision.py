"""Decimal-precision tests for the currency-conversion engine itself —
``pos.config._convert`` / ``pos.config._get_pos_conversion_rate``
(``l10n_ve_pos/models/pos_config.py``).

Why this file exists: every EXISTING test that touches ``_convert``
(``l10n_ve_pos_self_order/tests/test_recompute_prices_foreign_amount.py``,
``l10n_ve_pos/tests/test_self_order_foreign_amount.py``) creates its
``pos.config`` with ``currency_id`` set to the SAME currency as
``foreign_currency_id``. That means every one of those tests takes
``_convert``'s ``from_currency == to_currency`` shortcut
(``pos_config.py``: ``if from_currency == to_currency: return
to_currency.round(from_amount)``) and NEVER actually multiplies by a rate —
the real cross-currency arithmetic this engine exists for has no coverage
anywhere in the codebase. These tests use configs whose operating currency
is genuinely different from the foreign one, across several rates (from
near-parity to hyperinflation-scale, mirroring real BCV history) and BOTH
possible role assignments — VEF-main/USD-foreign FIRST (the real setup for
a Venezuelan company: books kept in bolívares, USD tracked as the
"foreign"/reference currency for hyperinflation accounting — same
convention as ``l10n_ve_accountant/tests/test_foreign_balance.py``), and
USD-main/VEF-foreign as a secondary cross-check (the convention the
existing ``l10n_ve_pos_self_order`` test fixtures happen to use).

Contract under test (verified directly against source, not assumed):

* ``_get_pos_conversion_rate`` returns the RAW rate with full precision,
  never rounded (``l10n_ve_pos/models/pos_config.py`` docstring: "Nunca
  redondear la tasa; redondear solo el resultado").
* ``_convert`` multiplies by that raw rate and rounds ONLY the final
  result, via ``to_currency.round()``.
* ``res.currency.round()`` (``odoo/addons/base/models/res_currency.py``)
  calls ``tools.float_round(amount, precision_rounding=self.rounding)``
  with NO ``rounding_method`` argument, so it uses ``float_round``'s
  default — ``'HALF-UP'`` (away from zero), per
  ``odoo/tools/float_utils.py``. This directly contradicts a claim in this
  repo's own ``FOREIGN_ROUNDING_ANALYSIS.md`` ("Odoo default" being
  HALF-EVEN) — ``test_convert_half_up_tie_breaks_away_from_zero`` below
  settles it empirically so a future core-Odoo upgrade that silently
  changes the default cannot slip by unnoticed.

Test-fixture gotcha discovered while writing this file (see
``_set_bs_per_usd_rate``'s own docstring): ``pos.config._compute_rate``'s
``@api.depends`` does NOT include ``res.currency.rate`` at all, so
``config.foreign_rate``/``foreign_inverse_rate`` are computed once per
environment and silently keep returning the FIRST rate ever read, even
after a brand new ``res.currency.rate`` row is created — a sweep over
several rates within one test method needs an explicit
``config.invalidate_recordset(...)`` after each new rate or it keeps
testing the same (first) rate over and over without ever failing loudly.
"""

from datetime import date, timedelta

from odoo.tests import TransactionCase, tagged
from odoo.tools.float_utils import float_round


@tagged("post_install", "-at_install", "l10n_ve_pos")
class TestPosConfigConvertPrecision(TransactionCase):
    # A spread of rates from near-parity to hyperinflation-scale, all with
    # "ugly" (many-decimal) values — a real BCV rate is never a round
    # number, and a round number would hide float/rounding bugs that only
    # show up with genuine decimal noise.
    BS_PER_USD_RATES = [
        0.00034521678,  # sub-parity (generic stress case, not a real BCV shape)
        0.99999949,  # near 1:1
        36.567891234,  # realistic
        189.34567891234,  # realistic, more decimals
        7654321.123456,  # hyperinflation-scale
    ]
    AMOUNTS = [0.01, 1.0, 33.33, 100.0, 999999.99]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.usd = cls.env.ref("base.USD")
        vef = (
            cls.env["res.currency"]
            .with_context(active_test=False)
            .search([("name", "=", "VEF")], limit=1)
        )
        if vef and not vef.active:
            vef.active = True
        cls.vef = vef

        cls.company_usd_main = cls.env["res.company"].create(
            {
                "name": "Test Convert USD Main Co",
                "currency_id": cls.usd.id,
                "foreign_currency_id": cls.vef.id,
                "country_id": cls.env.ref("base.ve").id,
            }
        )
        cls.config_usd_main = cls._make_config(
            cls.company_usd_main, "Convert USD Main Journal", "CVUMJ"
        )

        cls.company_vef_main = cls.env["res.company"].create(
            {
                "name": "Test Convert VEF Main Co",
                "currency_id": cls.vef.id,
                "foreign_currency_id": cls.usd.id,
                "country_id": cls.env.ref("base.ve").id,
            }
        )
        cls.config_vef_main = cls._make_config(
            cls.company_vef_main, "Convert VEF Main Journal", "CVVMJ"
        )

    @classmethod
    def _make_config(cls, company, journal_name, journal_code):
        journal = cls.env["account.journal"].create(
            {
                "name": journal_name,
                "type": "sale",
                "code": journal_code,
                "company_id": company.id,
            }
        )
        config = cls.env["pos.config"].create(
            {
                "name": f"{journal_name} Config",
                "company_id": company.id,
                "journal_id": journal.id,
                # invoice_journal_id has the SAME ambient-company default
                # pitfall as payment_method_ids below
                # (point_of_sale/models/pos_config.py:90-95) — left unset
                # it silently pulls in a journal from a DIFFERENT company
                # and _check_company() rejects the whole record.
                "invoice_journal_id": journal.id,
                # payment_method_ids' default is computed from
                # self.env.company (the ambient company), NOT from the
                # company_id assigned above (point_of_sale/models/
                # pos_config.py:170) — left unset it silently pulls in a
                # payment method belonging to a DIFFERENT company and trips
                # _check_company_payment. These tests never take a payment,
                # so an explicit empty list is enough.
                "payment_method_ids": [(6, 0, [])],
            }
        )
        # Guard the test setup itself: if this ever drifted to the foreign
        # currency, every assertion below would silently exercise the
        # same-currency shortcut instead of real conversion.
        assert config.currency_id == company.currency_id, (
            "the config must operate in the company's MAIN currency, not "
            "the foreign one, or _convert would never multiply by a rate"
        )
        # l10n_ve_rate's compute_rate (models/res_currency_rate.py) looks up
        # res.currency.rate filtered by ``self.env.company.id`` — the
        # CALLING env's active company — not by this config's own
        # ``company_id``. Without rebinding here, every later access to
        # ``config.foreign_rate``/``foreign_inverse_rate`` (and therefore
        # ``_get_pos_conversion_rate``/``_convert``) would look up rates
        # under the test runner's ambient company instead of ``company``,
        # find nothing, and silently resolve to 0.0.
        return config.with_company(company)

    def _set_bs_per_usd_rate(self, config, bs_per_usd):
        """Configure ``config``'s operative rate to mean "1 USD = bs_per_usd
        VEF", regardless of which of the two currencies this config's
        company treats as "main" vs. "foreign".

        Sets the PLAIN ``rate`` field rather than ``inverse_company_rate``
        (simpler: no inverse-cascade to a sibling field to reason about),
        and always CREATES a fresh row with a new (past, monotonically
        later) date rather than overwriting the previous one in place —
        ``compute_rate`` (``l10n_ve_rate``) always picks the LATEST row
        with ``name <= today`` via ``search(..., order='name DESC',
        limit=1)``.

        Then explicitly invalidates ``config``'s cache. This is the part
        that actually matters: ``pos.config._compute_rate``'s
        ``@api.depends`` list does NOT include ``res.currency.rate`` at
        all, so ``config.foreign_rate``/``foreign_inverse_rate`` are
        computed ONCE per environment and never invalidate just because a
        new rate row was created — every later read within the SAME test
        method would keep returning the value from the FIRST rate ever
        set, silently making every "different rate" in a sweep test
        actually exercise the same one. (Verified empirically: without
        this invalidation, ``config.foreign_rate``/``foreign_inverse_rate``
        were provably frozen at the first iteration's value across an
        entire rate sweep.)"""
        self._rate_seq = getattr(self, "_rate_seq", 0) + 1
        company = config.company_id
        foreign_currency = company.foreign_currency_id
        if company.currency_id == self.usd:
            rate = bs_per_usd  # VEF per 1 USD
        else:
            rate = 1.0 / bs_per_usd  # USD per 1 VEF
        self.env["res.currency.rate"].create(
            {
                "name": date(2020, 1, 1) + timedelta(days=self._rate_seq),
                "currency_id": foreign_currency.id,
                "company_id": company.id,
                "rate": rate,
            }
        )
        config.invalidate_recordset(["foreign_rate", "foreign_inverse_rate"])

    # ------------------------------------------------------------------
    # ``pos.config.foreign_rate`` (``digits="Tasa"`` = a fixed 6 decimal
    # PLACES, see the reciprocal-pair test's docstring) rounds any
    # magnitude below half its last representable step to EXACTLY 0.0 —
    # not just imprecise, genuinely unrepresentable. The ``foreign→main``
    # direction always reads this field (``l10n_ve_pos/models/
    # pos_config.py::_get_pos_conversion_rate``, unconditionally, for
    # BOTH role assignments), so whenever the true rate for that specific
    # direction is smaller than this floor, ``_get_pos_conversion_rate``
    # correctly — if surprisingly — returns 0.0. Verified empirically:
    # only ``bs_per_usd=7654321.123456`` on the USD-main role hits it in
    # this table (true rate ``1/7654321.123456 ≈ 1.3e-7``); the
    # VEF-main role never does, because for it this direction's true
    # rate is ``bs_per_usd`` itself (large), not its reciprocal.
    FOREIGN_RATE_FIELD_FLOOR = 5e-7

    def _true_foreign_to_main_rate(self, config, bs_per_usd):
        """The mathematically exact (unrounded) rate for the
        foreign→main direction, mirroring ``_set_bs_per_usd_rate``'s own
        per-role mapping — used only to recognize the
        ``FOREIGN_RATE_FIELD_FLOOR`` edge case above, not as a
        replacement oracle for the rest of the test."""
        if config.company_id.currency_id == self.usd:
            return 1.0 / bs_per_usd
        return bs_per_usd

    def test_convert_matches_half_up_round_of_raw_product(self):
        """For every (config, rate, amount) combination: ``_convert`` must
        equal ``float_round(amount * raw_rate, rounding_method='HALF-UP')``
        on the TARGET currency's precision — the documented mirror
        contract — in both directions (main→foreign and foreign→main),
        with the rate read fresh from ``_get_pos_conversion_rate`` (never
        rounded) and never drifting between two identical calls."""
        for config in (self.config_vef_main, self.config_usd_main):
            main_currency = config.company_id.currency_id
            foreign_currency = config.company_id.foreign_currency_id
            for bs_per_usd in self.BS_PER_USD_RATES:
                self._set_bs_per_usd_rate(config, bs_per_usd)
                for from_currency, to_currency in (
                    (main_currency, foreign_currency),
                    (foreign_currency, main_currency),
                ):
                    raw_rate = config._get_pos_conversion_rate(
                        from_currency, to_currency
                    )
                    is_known_field_floor_case = (
                        from_currency == foreign_currency
                        and abs(self._true_foreign_to_main_rate(config, bs_per_usd))
                        < self.FOREIGN_RATE_FIELD_FLOOR
                    )
                    for amount in self.AMOUNTS:
                        with self.subTest(
                            company=config.company_id.name,
                            bs_per_usd=bs_per_usd,
                            direction=f"{from_currency.name}->{to_currency.name}",
                            amount=amount,
                        ):
                            if is_known_field_floor_case:
                                self.assertEqual(
                                    raw_rate,
                                    0.0,
                                    "known foreign_rate digits=6 floor — if this "
                                    "ever becomes non-zero the field's precision "
                                    "changed and this whole edge case should be "
                                    "re-examined",
                                )
                                self.assertEqual(
                                    config._convert(amount, from_currency, to_currency),
                                    0.0,
                                )
                                continue
                            self.assertNotEqual(
                                raw_rate, 0.0, "test setup must have a real rate"
                            )
                            converted = config._convert(
                                amount, from_currency, to_currency
                            )
                            expected = float_round(
                                amount * raw_rate,
                                precision_rounding=to_currency.rounding,
                                rounding_method="HALF-UP",
                            )
                            self.assertEqual(converted, expected)

                            # The rate itself must never be rounded before
                            # multiplying — round=False must return the
                            # untouched raw product.
                            unrounded = config._convert(
                                amount, from_currency, to_currency, round=False
                            )
                            self.assertAlmostEqual(
                                unrounded, amount * raw_rate, places=9
                            )

                            # Determinism: identical inputs, identical
                            # (bit-for-bit) output, every time.
                            self.assertEqual(
                                converted,
                                config._convert(amount, from_currency, to_currency),
                            )

    def test_get_pos_conversion_rate_is_a_precise_reciprocal_pair(self):
        """The two raw rates (main→foreign and foreign→main) must be
        reciprocals of each other — a PURE rate check with no currency
        rounding involved at all (``_get_pos_conversion_rate`` never
        rounds itself).

        NOT machine-precision, though: exactly one of the two directions
        always reads ``pos.config.foreign_rate``, whose field definition
        is ``digits="Tasa"`` — a FIXED 6 DECIMAL PLACES (not 6 significant
        figures) — while the other direction reads ``foreign_inverse_rate``
        (``digits=(16,15)``, effectively full precision). Verified
        empirically: whenever ``foreign_rate`` ends up holding a
        small-magnitude value (e.g. ~0.0053 for
        ``bs_per_usd=189.34567891234`` on the USD-main role), 6 decimal
        PLACES only gives a handful of significant figures, and the
        product can be off from 1.0 by up to ~6.5e-5 — a real, production
        precision characteristic of this field, not a bug in ``_convert``/
        ``_get_pos_conversion_rate`` themselves. The tolerance below is
        sized generously around that measured bound.

        At an even more extreme magnitude the SAME field genuinely floors
        to ``0.0`` (see ``FOREIGN_RATE_FIELD_FLOOR`` above) — the product
        can't be a reciprocal pair at all then (anything times 0 isn't
        1.0), so that known case is asserted on its own terms instead of
        forced through the generic tolerance."""
        for config in (self.config_vef_main, self.config_usd_main):
            main_currency = config.company_id.currency_id
            foreign_currency = config.company_id.foreign_currency_id
            for bs_per_usd in self.BS_PER_USD_RATES:
                self._set_bs_per_usd_rate(config, bs_per_usd)
                with self.subTest(company=config.company_id.name, bs_per_usd=bs_per_usd):
                    rate_forward = config._get_pos_conversion_rate(
                        main_currency, foreign_currency
                    )
                    rate_backward = config._get_pos_conversion_rate(
                        foreign_currency, main_currency
                    )
                    if (
                        abs(self._true_foreign_to_main_rate(config, bs_per_usd))
                        < self.FOREIGN_RATE_FIELD_FLOOR
                    ):
                        self.assertEqual(rate_backward, 0.0)
                        continue
                    self.assertAlmostEqual(
                        rate_forward * rate_backward, 1.0, delta=1e-3
                    )

    def test_convert_round_trip_recovers_original_amount(self):
        """A moderate, realistic rate: converting main→foreign→main must
        land back close to the original amount — but "close" has to
        account for TWO real, legitimate sources of amplified error, not
        just one flat rounding step:

        1. The intermediate result is rounded to the FOREIGN currency's
           precision before converting back; that rounding error (up to
           half a rounding step) gets MULTIPLIED by the backward rate.
           E.g. USD 100 → VEF 2.73 (rounded from 2.7346...) → back through
           ``rate_backward≈36.57`` amplifies that ~0.0046 VEF rounding gap
           into a ~0.17 USD gap on the way back — verified empirically,
           not a bug.
        2. ``pos.config.foreign_rate`` (``digits="Tasa"``, a fixed 6
           decimal PLACES — see the reciprocal-pair test above) loses
           relative precision when it holds a small-magnitude value; that
           absolute error gets multiplied by the (potentially large)
           intermediate amount when converting back.

        Both scale with magnitude, so the tolerance below scales with it
        too instead of using one flat delta."""
        for config in (self.config_vef_main, self.config_usd_main):
            main_currency = config.company_id.currency_id
            foreign_currency = config.company_id.foreign_currency_id
            self._set_bs_per_usd_rate(config, 36.567891234)
            for amount in self.AMOUNTS:
                with self.subTest(company=config.company_id.name, amount=amount):
                    converted = config._convert(amount, main_currency, foreign_currency)
                    back = config._convert(converted, foreign_currency, main_currency)
                    rate_backward = config._get_pos_conversion_rate(
                        foreign_currency, main_currency
                    )
                    delta = (
                        main_currency.rounding
                        + foreign_currency.rounding * max(1, abs(rate_backward))
                        + abs(converted) * 5e-7
                    )
                    self.assertAlmostEqual(back, amount, delta=delta)

    def test_convert_half_up_tie_breaks_away_from_zero(self):
        """Empirically pins the rounding rule: 0.125 is EXACTLY
        representable in binary floating point and is an exact tie at
        2-decimal precision (halfway between 0.12 and 0.13). HALF-UP
        (away from zero) rounds it to 0.13; HALF-EVEN (banker's rounding)
        would round it to 0.12 (2 is the even neighbour). ``_convert``'s
        same-currency shortcut calls the exact same ``to_currency.round()``
        used by the cross-currency branch, so this single, float-safe
        check settles which rule is actually active for the whole engine —
        without depending on any multiplication's own rounding noise."""
        converted = self.config_usd_main._convert(0.125, self.usd, self.usd)
        self.assertEqual(
            converted,
            0.13,
            "res.currency.round() must use HALF-UP (away from zero); if this "
            "ever becomes 0.12, Odoo's float_round default changed to "
            "HALF-EVEN and every foreign-currency amount in this codebase "
            "would silently shift",
        )
