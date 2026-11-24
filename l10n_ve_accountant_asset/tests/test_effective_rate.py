from datetime import date

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from .common import MONTHLY_VALUE, AcquisitionRateMixin

OWN_RATE = (20.0, 0.05)


@tagged("post_install", "-at_install", "l10n_ve_accountant_asset")
class TestEffectiveRate(AcquisitionRateMixin, TransactionCase):
    """Tasa efectiva de las cuotas: la propia del activo si es > 0; si no, la de la tabla en
    la fecha de adquisición (última anterior o igual). Sin binaural instalado, la tasa propia
    se emula parchando ``account.asset._get_own_rate_values`` (ver ``_create_asset``)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_acquisition_case("99306")

    def setUp(self):
        super().setUp()
        self._patch_commit_progress()

    def _has_asset_rate_field(self):
        return "foreign_rate" in self.env["account.asset"]._fields

    # -- (a) tasa propia -------------------------------------------------
    def test_own_rate_is_used_without_any_table_rate(self):
        # Sin ninguna tasa en la fecha de adquisición ni antes: no se consulta la tabla.
        self._remove_rates_until(self.acquisition_date)
        asset = self._create_asset(own_rate=OWN_RATE)

        self.assertEqual(len(asset.depreciation_move_ids), 12)
        for move in asset.depreciation_move_ids:
            self._assert_rate_of(
                move, {"foreign_rate": OWN_RATE[0], "foreign_inverse_rate": OWN_RATE[1]}
            )
        move = self._future_drafts(asset)[0]
        # Igual que _get_non_invoice_foreign_value: balance / foreign_rate redondeado con la
        # moneda alterna (half-up de Odoo; el round() de Python da 176.38 por el float).
        self.assertEqual(
            self._debit_line(move).foreign_debit,
            self.foreign_currency.round(MONTHLY_VALUE / OWN_RATE[0]),
        )

    def test_own_rate_wins_over_the_table_rate(self):
        # Hay tasa de la tabla en la fecha de adquisición (acquisition_value) y no se usa.
        asset = self._create_asset(own_rate=OWN_RATE)
        self.assertNotEqual(OWN_RATE[0], self.acquisition_value)
        for move in asset.depreciation_move_ids:
            self.assertAlmostEqual(move.foreign_rate, OWN_RATE[0], places=6)

    def test_own_rate_without_inverse_derives_it(self):
        asset = self._create_asset(own_rate=(OWN_RATE[0], 0.0))
        rates = self.env["res.currency.rate"].with_company(self.company)
        expected = rates.compute_inverse_rate(OWN_RATE[0])
        for move in asset.depreciation_move_ids:
            self.assertAlmostEqual(move.foreign_rate, OWN_RATE[0], places=6)
            self.assertAlmostEqual(move.foreign_inverse_rate, expected, places=6)

    def test_own_rate_allows_acquisition_date_without_rates(self):
        asset = self._create_asset(own_rate=OWN_RATE, acquisition_date=date(1990, 1, 1))
        self.assertTrue(asset.depreciation_move_ids)
        for move in asset.depreciation_move_ids:
            self.assertAlmostEqual(move.foreign_rate, OWN_RATE[0], places=6)

    # -- (b) tasa propia vacía: tabla ------------------------------------
    def test_zero_own_rate_uses_the_table(self):
        asset = self._create_asset(own_rate=(0.0, 0.0))
        for move in asset.depreciation_move_ids:
            self._assert_acquisition_rate(move)

    def test_zero_own_rate_weekend_acquisition_uses_last_previous_rate(self):
        from odoo.addons.l10n_ve_accountant.tests.common_rates import set_rate

        friday, saturday = date(2024, 1, 5), date(2024, 1, 6)
        set_rate(self.env, self.foreign_currency, friday.isoformat(), self.company, 33.0)
        self.env["res.currency.rate"].search(
            [("name", "=", saturday), ("currency_id", "=", self.foreign_currency.id)]
        ).unlink()

        asset = self._create_asset(own_rate=(0.0, 0.0), acquisition_date=saturday)

        self.assertTrue(asset.depreciation_move_ids)
        for move in asset.depreciation_move_ids:
            self.assertAlmostEqual(move.foreign_rate, 33.0, places=6)

    def test_table_rate_is_written_in_the_asset_only_without_own_rate(self):
        if not self._has_asset_rate_field():
            self.skipTest("Sin foreign_rate en account.asset (binaural no instalado).")
        asset = self._create_asset(own_rate=(0.0, 0.0))
        self.assertAlmostEqual(asset.foreign_rate, self.acquisition_rate["foreign_rate"], places=6)

    # -- (c) sin fecha de adquisición ------------------------------------
    def test_missing_acquisition_date_without_own_rate_raises(self):
        # La BD impide el caso real: account.asset.prorata_date es NOT NULL y se deriva de
        # acquisition_date, asi que un activo guardado siempre trae fecha y la guarda de
        # _get_acquisition_rate_values es defensiva. Se prueba con un registro virtual
        # (new(), sin persistir): el metodo solo lee y lanza, no escribe.
        asset = self.env["account.asset"].new(
            {"name": "Asset without acquisition date", "company_id": self.company.id}
        )
        # El cálculo de Enterprise rellena la fecha con hoy al crear el virtual: se vacía a
        # mano para simular lo que la BD no deja persistir.
        asset.acquisition_date = False
        self.assertFalse(asset.acquisition_date)
        with self.assertRaises(UserError) as caught:
            asset._get_acquisition_rate_values()
        self.assertIn(asset.name, str(caught.exception))

    # -- (d) sin ninguna tasa --------------------------------------------
    def test_no_rate_at_or_before_acquisition_date_raises(self):
        asset = self._create_asset(validate=False)
        self._remove_rates_until(self.acquisition_date)
        with self.assertRaises(UserError) as caught:
            asset.validate()
        message = str(caught.exception)
        self.assertIn(asset.name, message)
        self.assertIn(str(self.acquisition_date), message)
        self.assertIn(self.foreign_currency.name, message)
        self.assertFalse(asset.depreciation_move_ids)

    # -- (e) recálculo con tasa propia -----------------------------------
    def test_recompute_with_own_rate_does_not_write_the_asset_nor_published_moves(self):
        asset = self._create_asset(own_rate=OWN_RATE)
        move = self._future_drafts(asset)[0]
        self._publish(move)
        move.write(
            {"manually_set_rate": True, "foreign_rate": 45.0, "foreign_inverse_rate": 1 / 45.0}
        )
        rate = (move.foreign_rate, move.foreign_inverse_rate)
        foreign = self._foreign_by_line(move)
        asset_writes = []
        asset_cls = self.registry["account.asset"]
        original_write = asset_cls.write

        def recording_write(records, vals):
            asset_writes.append(set(vals))
            return original_write(records, vals)

        self.patch(asset_cls, "write", recording_write)

        asset.compute_depreciation_board()

        self.assertFalse(
            [vals for vals in asset_writes if vals & {"foreign_rate", "foreign_inverse_rate"}]
        )
        self.assertEqual((move.foreign_rate, move.foreign_inverse_rate), rate)
        self.assertEqual(self._foreign_by_line(move), foreign)
        for draft in self._future_drafts(asset):
            self._assert_rate_of(
                draft, {"foreign_rate": OWN_RATE[0], "foreign_inverse_rate": OWN_RATE[1]}
            )
