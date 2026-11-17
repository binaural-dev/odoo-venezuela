from dateutil.relativedelta import relativedelta
from lxml import etree

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, freeze_time, tagged

from odoo.addons.l10n_ve_accountant.tests.common_rates import set_rate

ASSET_RATE = 857.0058
# El activo (binaural_account_asset, digits=(12, 6)) guarda el inverso truncado a 6 decimales.
ASSET_INVERSE_RATE = round(1 / ASSET_RATE, 6)


@tagged("post_install", "-at_install", "l10n_ve_accountant_asset")
class TestDepreciationManualRate(TransactionCase):
    """
    La tasa manual del asiento de la cuota de depreciación manda sobre la tasa del día para
    el valor alterno de las líneas (override de `_get_non_invoice_foreign_value`).

    `binaural_account_asset` (quien escribe la tasa del activo en la cuota) no es dependencia:
    su efecto se emula parcheando `_prepare_move_for_asset_depreciation`. Las fechas se
    calculan con el "hoy" real y `freeze_time` solo envuelve el cron.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        currencies = {
            "currency_id": cls.env.ref("base.VEF").id,
            "foreign_currency_id": cls.env.ref("base.USD").id,
        }
        if any(company[fname].id != value for fname, value in currencies.items()):
            company.write(currencies)
        company.partner_id.tz = "America/Caracas"
        cls.env = cls.env(context=dict(cls.env.context, tz="America/Caracas"))
        cls.usd = cls.env.ref("base.USD")
        cls.today = fields.Date.context_today(cls.env["account.move"])
        cls.current_month_start = cls.today.replace(day=1)
        cls.first_date = cls.current_month_start + relativedelta(months=1, days=-1)
        cls.after_first_date = cls.first_date + relativedelta(days=1)
        for rate_date in (cls.today, cls.first_date, cls.after_first_date):
            set_rate(cls.env, cls.usd, rate_date.isoformat(), company, 40.0)
        Account = cls.env["account.account"]
        cls.asset_vals = {
            "name": "Vehicle",
            "account_asset_id": Account.create(
                {"name": "Fixed Asset", "code": "990011", "account_type": "asset_fixed"}
            ).id,
            "account_depreciation_id": Account.create(
                {"name": "Depreciation", "code": "990012", "account_type": "asset_fixed"}
            ).id,
            "account_depreciation_expense_id": Account.create(
                {"name": "Depreciation Expense", "code": "990013", "account_type": "expense"}
            ).id,
            "journal_id": cls.env["account.journal"]
            .create({"name": "Assets", "code": "TASM", "type": "general"})
            .id,
            "original_value": 3527.70 * 12,
            "acquisition_date": cls.current_month_start,
            "method_number": 12,
            "method_period": "1",
        }

    def setUp(self):
        super().setUp()
        self.patch(
            self.registry["ir.cron"],
            "_commit_progress",
            lambda cron_model, processed=0, remaining=None, **kwargs: 1,
        )
        self.asset_rates = (ASSET_RATE, ASSET_INVERSE_RATE)
        move_model = self.registry["account.move"]
        original = move_model._prepare_move_for_asset_depreciation
        test = self

        def prepare_with_asset_rate(model, vals):
            # Emula binaural_account_asset: cuota con la tasa del activo como tasa manual.
            move_vals = original(model, vals)
            rate, inverse_rate = test.asset_rates
            move_vals.update(
                {
                    "manually_set_rate": True,
                    "foreign_rate": rate,
                    "foreign_inverse_rate": inverse_rate,
                }
            )
            return move_vals

        self.patch(move_model, "_prepare_move_for_asset_depreciation", prepare_with_asset_rate)

    def _create_asset(self, **vals):
        asset_vals = dict(self.asset_vals, **vals)
        if "foreign_rate" in self.env["account.asset"]._fields:
            # Si binaural_account_asset está instalado, la tasa viene del propio activo.
            rate, inverse_rate = self.asset_rates
            asset_vals.update({"foreign_rate": rate, "foreign_inverse_rate": inverse_rate})
        asset = self.env["account.asset"].create(asset_vals)
        asset.validate()
        return asset

    def _first_move(self, asset):
        return asset.depreciation_move_ids.sorted("auto_post_custom_date")[0]

    def _foreign_by_line(self, move):
        return {
            line.account_id: line.foreign_debit - line.foreign_credit
            for line in move.line_ids
        }

    def _publish(self, move):
        with freeze_time(f"{move.auto_post_custom_date} 15:00:00"):
            self.env["account.move"]._autopost_draft_entries()

    def test_manual_rate_wins_in_draft_and_after_cron(self):
        asset = self._create_asset()
        move = self._first_move(asset)
        expected = round(3527.70 / ASSET_RATE, 2)
        self.assertEqual(move.depreciation_value, 3527.70)
        self.assertEqual(move.foreign_rate, ASSET_RATE)
        foreign = self._foreign_by_line(move)
        debit_line = move.line_ids.filtered(lambda line: line.debit)
        self.assertEqual(foreign[debit_line.account_id], expected)
        self.assertAlmostEqual(sum(foreign.values()), 0.0, places=2)

        # Otra tasa de tabla el día de publicación: no debe alterar nada.
        set_rate(self.env, self.usd, move.auto_post_custom_date.isoformat(), self.env.company, 50.0)
        self._publish(move)

        self.assertEqual(move.state, "posted")
        self.assertEqual(move.foreign_rate, ASSET_RATE)
        self.assertEqual(self._foreign_by_line(move), foreign)

    def test_zero_asset_rate_uses_daily_rate(self):
        self.asset_rates = (0.0, 0.0)
        asset = self._create_asset()
        move = self._first_move(asset)
        debit_line = move.line_ids.filtered(lambda line: line.debit)
        self.assertEqual(debit_line.foreign_debit, round(3527.70 / 40.0, 2))

    def test_reversal_returns_the_original_foreign_value(self):
        asset = self._create_asset()
        move = self._first_move(asset)
        self._publish(move)
        original_foreign = self._foreign_by_line(move)
        set_rate(self.env, self.usd, self.after_first_date.isoformat(), self.env.company, 60.0)

        with freeze_time(f"{self.after_first_date} 15:00:00"):
            reversal = move._reverse_moves(
                default_values_list=[{"date": self.after_first_date, "auto_post": "no"}]
            )
            reversal._post()

        self.assertEqual(reversal.state, "posted")
        reversal_foreign = self._foreign_by_line(reversal)
        for account, value in original_foreign.items():
            self.assertEqual(reversal_foreign[account], -value)

    def test_large_amount_does_not_use_truncated_inverse(self):
        asset = self._create_asset(original_value=12000000.0)
        move = self._first_move(asset)
        self.assertEqual(move.depreciation_value, 1000000.0)
        debit_line = move.line_ids.filtered(lambda line: line.debit)
        self.assertEqual(debit_line.foreign_debit, round(1000000.0 / ASSET_RATE, 2))
        self.assertNotEqual(debit_line.foreign_debit, round(1000000.0 * ASSET_INVERSE_RATE, 2))

    def test_non_asset_entry_with_manual_rate_keeps_table_rate(self):
        journal = self.env["account.journal"].create(
            {"name": "Misc manual", "code": "TMAN", "type": "general"}
        )
        accounts = self.env["account.account"].search(
            [("account_type", "in", ("expense", "asset_current")), ("company_ids", "in", self.env.company.id)],
            limit=2,
        )
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": journal.id,
                "date": self.today,
                "manually_set_rate": True,
                "foreign_rate": 500.0,
                "foreign_inverse_rate": 1 / 500.0,
                "line_ids": [
                    (0, 0, {"account_id": accounts[0].id, "debit": 4000.0}),
                    (0, 0, {"account_id": accounts[1].id, "credit": 4000.0}),
                ],
            }
        )
        debit_line = move.line_ids.filtered(lambda line: line.debit)
        self.assertEqual(debit_line.foreign_debit, 100.0)

    def test_asset_form_shows_publication_date_column(self):
        arch = self.env["account.asset"].get_view(view_type="form")["arch"]
        tree = etree.fromstring(arch)
        fields_in_list = tree.xpath("//field[@name='depreciation_move_ids']/list/field")
        by_name = {node.get("name"): node for node in fields_in_list}
        self.assertIn("auto_post_custom_publish_date", by_name)
        self.assertIn(by_name["date"].get("column_invisible"), ("1", "True"))

    def test_user_error_is_translated_to_spanish(self):
        self.env["res.lang"]._activate_lang("es_VE")
        asset = self._create_asset()
        move = self._first_move(asset).with_context(lang="es_VE")
        with self.assertRaises(UserError) as caught:
            move.action_post()
        self.assertIn("programado para publicarse", str(caught.exception))
