from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests import TransactionCase, freeze_time, tagged

from odoo.addons.l10n_ve_accountant.tests.common_rates import set_rate


@tagged("post_install", "-at_install", "l10n_ve_accountant_asset")
class TestDepreciationFuture(TransactionCase):
    """
    Cuotas de depreciación futuras: borrador 'custom' con la fecha de adquisición como fecha
    contable que el cron publica en la fecha real. El módulo no fija tasas: se siembran las de
    cada fecha usada.

    `create_date` viene del reloj real de la BD (no de freeze_time), y la restricción de
    `auto_post_custom_date` la compara contra él: las fechas se calculan a partir del "hoy"
    real y `freeze_time` se usa solo alrededor de la llamada al cron.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        company.write(
            {
                "currency_id": cls.env.ref("base.VEF").id,
                "foreign_currency_id": cls.env.ref("base.USD").id,
            }
        )
        company.partner_id.tz = "America/Caracas"
        cls.env = cls.env(context=dict(cls.env.context, tz="America/Caracas"))
        cls.today = fields.Date.context_today(cls.env["account.move"])
        cls.current_month_start = cls.today.replace(day=1)
        cls.old_acquisition = cls.current_month_start - relativedelta(months=3)
        # Hoy y los fines de mes (cuotas) desde la adquisición antigua hasta ~15 meses adelante.
        # La tasa de la fecha de adquisición manda en las cuotas de depreciación.
        rate_dates = {cls.today, cls.old_acquisition, cls.current_month_start}
        month_start = cls.old_acquisition
        for _i in range(20):
            rate_dates.add(month_start + relativedelta(months=1, days=-1))
            month_start += relativedelta(months=1)
        for rate_date in sorted(rate_dates):
            set_rate(cls.env, cls.env.ref("base.USD"), rate_date.isoformat(), company, 40.0)
        Account = cls.env["account.account"]
        # La baja crea una línea con la diferencia (valor - depreciado) en la cuenta de ganancia
        # o pérdida de la compañía (account_asset); sin ellas se descarta y el asiento queda
        # descuadrado.
        company.write(
            {
                "gain_account_id": Account.create(
                    {"name": "Asset Disposal Gain", "code": "990004", "account_type": "income_other"}
                ).id,
                "loss_account_id": Account.create(
                    {"name": "Asset Disposal Loss", "code": "990005", "account_type": "expense"}
                ).id,
            }
        )
        cls.asset_vals = {
            "name": "Vehicle",
            "account_asset_id": Account.create(
                {"name": "Fixed Asset", "code": "990001", "account_type": "asset_fixed"}
            ).id,
            "account_depreciation_id": Account.create(
                {"name": "Depreciation", "code": "990002", "account_type": "asset_fixed"}
            ).id,
            "account_depreciation_expense_id": Account.create(
                {"name": "Depreciation Expense", "code": "990003", "account_type": "expense"}
            ).id,
            "journal_id": cls.env["account.journal"]
            .create({"name": "Assets", "code": "TASS", "type": "general"})
            .id,
            "original_value": 1200.0,
            "acquisition_date": cls.current_month_start,
            "method_number": 12,
            "method_period": "1",
        }
        cls.asset = cls.env["account.asset"].create(cls.asset_vals)

    def setUp(self):
        super().setUp()
        self.patch(
            self.registry["ir.cron"],
            "_commit_progress",
            lambda cron_model, processed=0, remaining=None, **kwargs: 1,
        )

    def _custom_moves(self, asset=None):
        asset = asset or self.asset
        return asset.depreciation_move_ids.filtered(lambda m: m.auto_post == "custom").sorted(
            "auto_post_custom_date"
        )

    def test_future_moves_are_custom_drafts_dated_at_acquisition(self):
        self.asset.validate()

        moves = self.asset.depreciation_move_ids
        self.assertEqual(len(moves), 12)
        self.assertEqual(set(moves.mapped("state")), {"draft"})
        self.assertEqual(set(moves.mapped("date")), {self.asset.acquisition_date})
        self.assertEqual(self.asset.acquisition_date, self.current_month_start)
        custom = self._custom_moves()
        self.assertEqual(len(custom), 12)
        self.assertGreaterEqual(custom[0].auto_post_custom_date, self.today)
        self.assertEqual(
            custom[0].auto_post_custom_date,
            self.current_month_start + relativedelta(months=1, days=-1),
        )
        self.assertEqual(
            custom[-1].auto_post_custom_date,
            self.current_month_start + relativedelta(months=12, days=-1),
        )
        self.assertEqual(custom[0].asset_depreciation_beginning_date, self.current_month_start)
        self.assertFalse(moves.filtered(lambda m: m.state == "posted"))

    def test_past_moves_are_posted_and_future_ones_are_custom(self):
        asset = self.env["account.asset"].create(
            dict(self.asset_vals, name="Old vehicle", acquisition_date=self.old_acquisition)
        )
        asset.validate()

        posted = asset.depreciation_move_ids.filtered(lambda m: m.state == "posted")
        self.assertGreaterEqual(len(posted), 3)
        self.assertTrue(all(move_date <= self.today for move_date in posted.mapped("date")))
        self.assertFalse(posted.filtered(lambda m: m.auto_post == "custom"))
        custom = self._custom_moves(asset)
        self.assertEqual(len(custom) + len(posted), 12)
        self.assertEqual(set(custom.mapped("state")), {"draft"})
        self.assertGreaterEqual(custom[0].auto_post_custom_date, self.today)
        # Los borradores llevan la fecha de adquisición; las publicadas, su fecha real.
        self.assertEqual(set(custom.mapped("date")), {self.old_acquisition})
        self.assertFalse(posted.filtered(lambda m: m.date == self.old_acquisition))

    def test_remaining_value_follows_period_order_with_acquisition_dated_drafts(self):
        asset = self.env["account.asset"].create(
            dict(self.asset_vals, name="Old vehicle", acquisition_date=self.old_acquisition)
        )
        asset.validate()

        moves = asset.depreciation_move_ids.sorted(
            lambda m: (m.auto_post_custom_date or m.date, m.id)
        )
        self.assertEqual(len(moves), 12)
        remaining = moves.mapped("asset_remaining_value")
        self.assertEqual(remaining, [1200.0 - 100.0 * (i + 1) for i in range(12)])
        asset._check_depreciations()

    def test_cron_keeps_period_order_and_remaining_value(self):
        self.asset.validate()
        custom = self._custom_moves()

        with freeze_time(f"{custom[0].auto_post_custom_date} 15:00:00"):
            self.env["account.move"]._autopost_draft_entries()

        moves = self.asset.depreciation_move_ids.sorted(
            lambda m: (m.auto_post_custom_date or m.date, m.id)
        )
        self.assertEqual(
            moves.mapped("asset_remaining_value"),
            [1200.0 - 100.0 * (i + 1) for i in range(12)],
        )
        self.asset._check_depreciations()

    def test_pause_after_posted_installments_does_not_double_depreciate(self):
        asset = self.env["account.asset"].create(
            dict(self.asset_vals, name="Old vehicle", acquisition_date=self.old_acquisition)
        )
        asset.validate()
        posted_before = sum(
            asset.depreciation_move_ids.filtered(lambda m: m.state == "posted").mapped(
                "depreciation_value"
            )
        )

        asset.pause(self.today, "Pause")

        self.assertEqual(asset.state, "paused")
        self.assertFalse(asset.depreciation_move_ids.filtered(lambda m: m.state == "draft"))
        posted = asset.depreciation_move_ids.filtered(lambda m: m.state == "posted")
        depreciated = sum(posted.mapped("depreciation_value"))
        # Solo se agrega el tramo del periodo en curso (menos de una cuota), no el acumulado
        # desde el inicio del activo.
        self.assertGreaterEqual(depreciated, posted_before)
        self.assertLessEqual(depreciated - posted_before, 100.0)

    def test_recompute_board_does_not_duplicate_custom_drafts(self):
        self.asset.validate()

        self.asset.compute_depreciation_board()
        self.assertEqual(len(self.asset.depreciation_move_ids), 12)
        self.assertEqual(
            set(self.asset.depreciation_move_ids.mapped("date")), {self.asset.acquisition_date}
        )

        self.asset.compute_depreciation_board(self.today + relativedelta(months=2))
        moves = self.asset.depreciation_move_ids
        custom_dates = self._custom_moves().mapped("auto_post_custom_date")
        self.assertEqual(len(moves), len(custom_dates))
        self.assertEqual(len(set(custom_dates)), len(custom_dates))
        self.assertEqual(set(moves.mapped("state")), {"draft"})
        self.assertEqual(set(moves.mapped("date")), {self.asset.acquisition_date})

    def test_dispose_removes_pending_custom_drafts(self):
        self.asset.validate()

        self.asset.set_to_close(
            self.env["account.move.line"], date=self.today, message="Dispose"
        )

        self.assertFalse(self._custom_moves())
        # El asiento de baja (asset_move_type 'disposal') puede quedar en borrador: lo que no
        # debe quedar son cuotas de depreciación pendientes.
        pending_depreciations = self.asset.depreciation_move_ids.filtered(
            lambda m: m.state == "draft" and m.asset_move_type == "depreciation"
        )
        self.assertFalse(pending_depreciations)

    def test_modify_is_not_blocked_by_future_custom_drafts(self):
        self.asset.validate()

        wizard = self.env["asset.modify"].create(
            {"asset_id": self.asset.id, "name": "Modify", "date": self.today}
        )
        wizard.modify()

        self.assertEqual(self.asset.state, "open")
        self.assertTrue(self.asset.depreciation_move_ids)

    def test_modify_after_posted_installments_keeps_acquisition_dated_drafts(self):
        asset = self.env["account.asset"].create(
            dict(self.asset_vals, name="Old vehicle", acquisition_date=self.old_acquisition)
        )
        asset.validate()

        wizard = self.env["asset.modify"].create(
            {"asset_id": asset.id, "name": "Modify", "date": self.today}
        )
        wizard.modify()

        self.assertEqual(asset.state, "open")
        custom = self._custom_moves(asset)
        self.assertTrue(custom)
        self.assertEqual(set(custom.mapped("date")), {self.old_acquisition})
        self.assertEqual(len(set(custom.mapped("auto_post_custom_date"))), len(custom))
        asset._check_depreciations()

    def test_cron_posts_custom_draft_on_its_date(self):
        self.asset.validate()
        custom = self._custom_moves()
        first_date = custom[0].auto_post_custom_date

        with freeze_time(f"{first_date} 15:00:00"):  # 11:00 en Caracas, el mismo día
            self.env["account.move"]._autopost_draft_entries()

        self.assertEqual(custom[0].state, "posted")
        self.assertEqual(custom[0].date, first_date)
        self.assertEqual(custom[0].auto_post_custom_date, first_date)
        self.assertEqual(set(custom[1:].mapped("state")), {"draft"})
