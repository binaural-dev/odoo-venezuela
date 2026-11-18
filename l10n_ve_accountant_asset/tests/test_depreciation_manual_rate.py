from datetime import date

from dateutil.relativedelta import relativedelta
from lxml import etree

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, freeze_time, tagged

from odoo.addons.l10n_ve_accountant.tests.common_rates import set_rate

from .common import MONTHLY_VALUE, AcquisitionRateMixin


@tagged("post_install", "-at_install", "l10n_ve_accountant_asset")
class TestDepreciationManualRate(AcquisitionRateMixin, TransactionCase):
    """
    Las cuotas de depreciación llevan la tasa de la FECHA DE ADQUISICIÓN como tasa manual: el
    cron las publica en su fecha sin revalorizar el valor alterno (con o sin factura de compra
    y con o sin binaural_account_asset, que aquí no se emula: ver test_acquisition_rate).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_acquisition_case("99001")

    def setUp(self):
        super().setUp()
        self._patch_commit_progress()

    def test_installment_keeps_acquisition_rate_in_draft_and_after_cron(self):
        asset = self._create_asset()
        move = self._custom_drafts(asset)[0]
        expected = round(MONTHLY_VALUE / self.acquisition_value, 2)
        self.assertEqual(move.depreciation_value, MONTHLY_VALUE)
        # En borrador: fecha contable = adquisición; la fecha real del periodo, en custom_date.
        self.assertEqual(move.date, self.acquisition_date)
        self.assertEqual(move.auto_post_custom_date, self.first_date)
        self._assert_acquisition_rate(move)
        foreign = self._foreign_by_line(move)
        self.assertEqual(self._debit_line(move).foreign_debit, expected)
        self.assertAlmostEqual(sum(foreign.values()), 0.0, places=2)

        # Con otra tasa el día de publicación (ya sembrada: PUBLICATION_RATE) nada cambia.
        self._publish(move)

        self.assertEqual(move.state, "posted")
        self.assertEqual(move.date, self.first_date)
        self.assertEqual(move.auto_post_custom_date, self.first_date)
        self._assert_acquisition_rate(move)
        self.assertEqual(self._foreign_by_line(move), foreign)

    def test_asset_without_purchase_invoice_uses_acquisition_rate(self):
        asset = self._create_asset()
        self.assertFalse(asset.original_move_line_ids)
        for move in asset.depreciation_move_ids:
            self._assert_acquisition_rate(move)

    def test_missing_acquisition_rate_blocks_the_board(self):
        asset = self._create_asset(
            validate=False, acquisition_date=date(1990, 1, 1)
        )
        with self.assertRaises(UserError) as caught:
            asset.validate()
        self.assertIn(self.foreign_currency.name, str(caught.exception))
        self.assertIn(str(asset.acquisition_date), str(caught.exception))
        self.assertFalse(asset.depreciation_move_ids)

    def test_reversal_returns_the_original_foreign_value(self):
        asset = self._create_asset()
        move = self._custom_drafts(asset)[0]
        self._publish(move)
        original_foreign = self._foreign_by_line(move)
        reversal_date = move.auto_post_custom_date + relativedelta(days=1)
        set_rate(self.env, self.foreign_currency, reversal_date.isoformat(), self.env.company, 60.0)

        with freeze_time(f"{reversal_date} 15:00:00"):
            reversal = move._reverse_moves(
                default_values_list=[{"date": reversal_date, "auto_post": "no"}]
            )
            reversal._post()

        self.assertEqual(reversal.state, "posted")
        reversal_foreign = self._foreign_by_line(reversal)
        for account, value in original_foreign.items():
            self.assertEqual(reversal_foreign[account], -value)

    def test_large_amount_does_not_use_truncated_inverse(self):
        asset = self._create_asset(original_value=12000000.0)
        move = self._custom_drafts(asset)[0]
        self.assertEqual(move.depreciation_value, 1000000.0)
        debit_line = self._debit_line(move)
        self.assertEqual(debit_line.foreign_debit, round(1000000.0 / self.acquisition_value, 2))

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
        # La tabla manda: el valor alterno sale de la tasa del día, no de la manual de 500.
        table_rate = (
            self.env["res.currency.rate"]
            .with_company(self.company)
            .compute_rate(self.foreign_currency.id, self.today)["foreign_rate"]
        )
        self.assertEqual(self._debit_line(move).foreign_debit, round(4000.0 / table_rate, 2))

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
        move = self._custom_drafts(asset)[0].with_context(lang="es_VE")
        with self.assertRaises(UserError) as caught:
            move.action_post()
        self.assertIn("programado para publicarse", str(caught.exception))
