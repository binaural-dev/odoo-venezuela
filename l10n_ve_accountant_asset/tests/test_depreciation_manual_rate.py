from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import Command
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
        cls._setup_acquisition_case("99201")

    def setUp(self):
        super().setUp()
        self._patch_commit_progress()

    def _vendor_bill_line(self):
        product = self.env["product.product"].create({"name": "Vehicle", "type": "service"})
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.env["res.partner"].create({"name": "Asset supplier"}).id,
                "invoice_date": self.acquisition_date,
                # por defecto es "hoy" y l10n_ve_invoice exige que no pase de `date`
                "invoice_date_display": self.acquisition_date,
                "date": self.acquisition_date,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Vehicle",
                            "product_id": product.id,
                            "account_id": self.asset_vals["account_asset_id"],
                            "quantity": 1,
                            "price_unit": MONTHLY_VALUE * 12,
                        }
                    )
                ],
            }
        )
        return bill.invoice_line_ids

    def test_installment_keeps_acquisition_rate_in_draft_and_after_cron(self):
        asset = self._create_asset()
        move = self._future_drafts(asset)[0]
        expected = round(MONTHLY_VALUE / self.acquisition_value, 2)
        self.assertEqual(move.depreciation_value, MONTHLY_VALUE)
        # Nace con su fecha real y el auto_post nativo.
        self.assertEqual(move.date, self.first_date)
        self.assertEqual(move.auto_post, "at_date")
        self._assert_acquisition_rate(move)
        foreign = self._foreign_by_line(move)
        self.assertEqual(self._debit_line(move).foreign_debit, expected)
        self.assertAlmostEqual(sum(foreign.values()), 0.0, places=2)

        # Con otra tasa el día de publicación (ya sembrada: PUBLICATION_RATE) nada cambia.
        self.assertNotEqual(self.publication_rate["foreign_rate"], self.acquisition_value)
        self._publish(move)

        self.assertEqual(move.state, "posted")
        self.assertEqual(move.date, self.first_date)
        self._assert_acquisition_rate(move)
        self.assertEqual(self._foreign_by_line(move), foreign)
        self.assertEqual(self._debit_line(move).foreign_debit, expected)

    def test_asset_without_purchase_invoice_uses_acquisition_rate(self):
        asset = self._create_asset()
        self.assertFalse(asset.original_move_line_ids)
        for move in asset.depreciation_move_ids:
            self._assert_acquisition_rate(move)

    def test_asset_with_purchase_invoice_uses_acquisition_rate(self):
        line = self._vendor_bill_line()
        asset = self._create_asset(original_move_line_ids=[Command.set(line.ids)])
        self.assertTrue(asset.original_move_line_ids)
        for move in asset.depreciation_move_ids:
            self._assert_acquisition_rate(move)
        self.assertEqual(
            self._debit_line(asset.depreciation_move_ids[0]).foreign_debit,
            round(MONTHLY_VALUE / self.acquisition_value, 2),
        )

    def test_weekend_acquisition_uses_last_previous_rate(self):
        friday, saturday = date(2024, 1, 5), date(2024, 1, 6)
        set_rate(self.env, self.foreign_currency, friday.isoformat(), self.company, 33.0)
        self.env["res.currency.rate"].search(
            [("name", "=", saturday), ("currency_id", "=", self.foreign_currency.id)]
        ).unlink()

        asset = self._create_asset(acquisition_date=saturday)

        self.assertTrue(asset.depreciation_move_ids)
        for move in asset.depreciation_move_ids:
            self.assertTrue(move.manually_set_rate)
            self.assertAlmostEqual(move.foreign_rate, 33.0, places=6)
            self.assertEqual(
                self._debit_line(move).foreign_debit, round(move.depreciation_value / 33.0, 2)
            )

    def test_missing_acquisition_rate_blocks_the_board(self):
        asset = self._create_asset(validate=False, acquisition_date=date(1990, 1, 1))
        with self.assertRaises(UserError) as caught:
            asset.validate()
        self.assertIn(self.foreign_currency.name, str(caught.exception))
        self.assertIn(str(asset.acquisition_date), str(caught.exception))
        self.assertFalse(asset.depreciation_move_ids)

    def test_reversal_returns_the_original_foreign_value(self):
        asset = self._create_asset()
        move = self._future_drafts(asset)[0]
        self._publish(move)
        original_foreign = self._foreign_by_line(move)
        reversal_date = move.date + relativedelta(days=1)
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
        move = self._future_drafts(asset)[0]
        self.assertEqual(move.depreciation_value, 1000000.0)
        debit_line = self._debit_line(move)
        self.assertEqual(debit_line.foreign_debit, round(1000000.0 / self.acquisition_value, 2))

    def test_non_asset_entry_with_manual_rate_keeps_table_rate(self):
        journal = self.env["account.journal"].create(
            {"name": "Misc manual", "code": "TMAN", "type": "general"}
        )
        accounts = self.env["account.account"].search(
            [
                ("account_type", "in", ("expense", "asset_current")),
                ("company_ids", "in", self.env.company.id),
            ],
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
                    Command.create({"account_id": accounts[0].id, "debit": 4000.0}),
                    Command.create({"account_id": accounts[1].id, "credit": 4000.0}),
                ],
            }
        )
        # Comportamiento previo, sin cambio: el valor alterno de un asiento común sale de la
        # tasa del día, no de la manual de 500 (solo las cuotas de activo usan la manual).
        table_rate = (
            self.env["res.currency.rate"]
            .with_company(self.company)
            .compute_rate(self.foreign_currency.id, self.today)["foreign_rate"]
        )
        self.assertEqual(self._debit_line(move).foreign_debit, round(4000.0 / table_rate, 2))
