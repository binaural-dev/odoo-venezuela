from dateutil.relativedelta import relativedelta

from odoo.tests import TransactionCase, tagged

from .common import MONTHLY_VALUE, AcquisitionRateMixin


@tagged("post_install", "-at_install", "l10n_ve_accountant_asset")
class TestDepreciationFuture(AcquisitionRateMixin, TransactionCase):
    """
    Las cuotas de depreciación futuras nacen en borrador con su fecha real y el
    ``auto_post='at_date'`` nativo; las de fechas pasadas se publican al validar el activo.

    `create_date` viene del reloj real de la BD (no de freeze_time): las fechas se calculan a
    partir del "hoy" real y `freeze_time` se usa solo alrededor de la llamada al cron.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_acquisition_case("99101")
        cls.old_acquisition = cls.today.replace(day=1) - relativedelta(months=3)
        cls.old_rate = cls._seed_rate(cls.old_acquisition, 35.0)

    def setUp(self):
        super().setUp()
        self._patch_commit_progress()

    def test_future_moves_are_at_date_drafts_with_real_date(self):
        asset = self._create_asset()

        moves = asset.depreciation_move_ids
        self.assertEqual(len(moves), 12)
        self.assertEqual(set(moves.mapped("state")), {"draft"})
        self.assertEqual(set(moves.mapped("auto_post")), {"at_date"})
        drafts = self._future_drafts(asset)
        self.assertEqual(drafts[0].date, self.first_date)
        self.assertEqual(
            drafts[-1].date, self.acquisition_date + relativedelta(months=12, days=-1)
        )
        self.assertEqual(drafts[0].asset_depreciation_beginning_date, self.acquisition_date)
        for move in drafts:
            self.assertEqual(move.depreciation_value, MONTHLY_VALUE)
            self._assert_acquisition_rate(move)

    def test_past_moves_are_posted_and_future_ones_are_at_date(self):
        asset = self._create_asset(acquisition_date=self.old_acquisition)

        posted = self._posted(asset)
        drafts = self._future_drafts(asset)
        self.assertGreaterEqual(len(posted), 3)
        self.assertEqual(len(posted) + len(drafts), 12)
        self.assertTrue(all(move_date <= self.today for move_date in posted.mapped("date")))
        self.assertEqual(set(drafts.mapped("auto_post")), {"at_date"})
        self.assertGreater(drafts[0].date, self.today)
        # Todas, publicadas o no, llevan la tasa de la fecha de adquisición del activo.
        for move in posted | drafts:
            self.assertTrue(move.manually_set_rate)
            self.assertAlmostEqual(move.foreign_rate, self.old_rate["foreign_rate"], places=6)

    def test_cron_posts_only_the_installment_of_its_date(self):
        asset = self._create_asset()
        first = self._future_drafts(asset)[0]

        self._publish(first)

        self.assertEqual(first.state, "posted")
        self.assertEqual(first.date, self.first_date)
        self.assertEqual(
            set(asset.depreciation_move_ids.filtered(lambda m: m != first).mapped("state")),
            {"draft"},
        )

    def test_recompute_board_does_not_duplicate_drafts(self):
        asset = self._create_asset()

        asset.compute_depreciation_board()
        self.assertEqual(len(asset.depreciation_move_ids), 12)

        self._skip_if_real_binaural()
        asset.compute_depreciation_board(self.today + relativedelta(months=2))
        dates = asset.depreciation_move_ids.mapped("date")
        self.assertEqual(len(dates), len(set(dates)))
        self.assertEqual(set(asset.depreciation_move_ids.mapped("state")), {"draft"})

    def test_pause_after_posted_installments_does_not_double_depreciate(self):
        asset = self._create_asset(acquisition_date=self.old_acquisition)
        posted = self._posted(asset)
        posted_before = sum(posted.mapped("depreciation_value"))
        rates_before = {move: move.foreign_rate for move in posted}

        asset.pause(self.today, "Pause")

        self.assertEqual(asset.state, "paused")
        self.assertFalse(self._future_drafts(asset))
        depreciated = sum(self._posted(asset).mapped("depreciation_value"))
        # Solo se agrega el tramo del periodo en curso (menos de una cuota), no el acumulado
        # desde el inicio del activo.
        self.assertGreaterEqual(depreciated, posted_before)
        self.assertLessEqual(depreciated - posted_before, MONTHLY_VALUE)
        for move, rate in rates_before.items():
            self.assertEqual(move.foreign_rate, rate)
        for move in self._posted(asset):
            self._assert_rate_of(move, self.old_rate)

    def test_modify_after_posted_installments_keeps_their_rate(self):
        self._skip_if_real_binaural()
        asset = self._create_asset(acquisition_date=self.old_acquisition)
        posted = self._posted(asset)
        rates_before = {move: (move.foreign_rate, move.foreign_inverse_rate) for move in posted}
        foreign_before = {move: self._foreign_by_line(move) for move in posted}

        wizard = self.env["asset.modify"].create(
            {"asset_id": asset.id, "name": "Modify", "date": self.today}
        )
        wizard.modify()

        self.assertEqual(asset.state, "open")
        self.assertTrue(self._future_drafts(asset))
        for move in posted:
            self.assertEqual((move.foreign_rate, move.foreign_inverse_rate), rates_before[move])
            self.assertEqual(self._foreign_by_line(move), foreign_before[move])
        for move in self._future_drafts(asset):
            self._assert_rate_of(move, self.old_rate)

    def test_dispose_without_exact_rate_does_not_fail(self):
        asset = self._create_asset()
        Rate = self.env["res.currency.rate"].with_company(self.company)
        # Sin tasa exacta el día de la baja: se usa la última anterior, no falla.
        Rate.search(
            [
                ("name", "=", self.today),
                ("currency_id", "=", self.foreign_currency.id),
                ("company_id", "=", self.company.id),
            ]
        ).unlink()
        previous = self._seed_rate(self.today - relativedelta(days=15), self.acquisition_value)
        self.assertTrue(previous)

        asset.set_to_close(self.env["account.move.line"], date=self.today, message="Dispose")

        self.assertEqual(asset.state, "close")
        self.assertTrue(asset.depreciation_move_ids.filtered(lambda m: m.asset_move_type == "disposal"))
        self.assertFalse(self._future_drafts(asset))
