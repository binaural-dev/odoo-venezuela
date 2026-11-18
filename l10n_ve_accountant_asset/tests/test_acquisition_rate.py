
from odoo import Command
from odoo.tests import TransactionCase, tagged

from .common import (
    MONTHLY_VALUE,
    AcquisitionRateMixin,
)


class BinauralEmulationTests:
    """Casos con binaural_account_asset emulado, en cada orden del MRO (ver
    ``AcquisitionRateMixin._emulate_binaural``). No es un TestCase: lo heredan las clases
    concretas de abajo."""

    def setUp(self):
        super().setUp()
        self._patch_commit_progress()
        self._emulate_binaural()

    def test_acquisition_rate_beats_invoice_rate(self):
        asset = self._create_asset()
        move = self._custom_drafts(asset)[0]
        self._assert_acquisition_rate(move)
        expected = round(MONTHLY_VALUE / self.acquisition_value, 2)
        self.assertEqual(self._debit_line(move).foreign_debit, expected)

        self._publish(move)

        self.assertEqual(move.state, "posted")
        self._assert_acquisition_rate(move)
        self.assertEqual(self._debit_line(move).foreign_debit, expected)

    def test_zero_invoice_rate_uses_acquisition_rate_not_daily_rate(self):
        self.invoice_rates = (0.0, 0.0)
        asset = self._create_asset()
        move = self._custom_drafts(asset)[0]
        self._assert_acquisition_rate(move)
        self.assertEqual(
            self._debit_line(move).foreign_debit,
            round(MONTHLY_VALUE / self.acquisition_value, 2),
        )

    def test_recompute_restores_published_installment_rate(self):
        asset = self._create_asset()
        move = self._custom_drafts(asset)[0]
        self._publish(move)
        # Cuota ya publicada con una tasa distinta a la de adquisición (histórica).
        move.write(
            {"manually_set_rate": True, "foreign_rate": 45.0, "foreign_inverse_rate": 1 / 45.0}
        )
        rate = (move.foreign_rate, move.foreign_inverse_rate)
        foreign = self._foreign_by_line(move)

        asset.compute_depreciation_board()

        self.assertEqual((move.foreign_rate, move.foreign_inverse_rate), rate)
        self.assertTrue(move.manually_set_rate)
        self.assertEqual(self._foreign_by_line(move), foreign)
        for draft in self._custom_drafts(asset):
            self._assert_acquisition_rate(draft)


@tagged("post_install", "-at_install", "l10n_ve_accountant_asset")
class TestBinauralInsideChain(BinauralEmulationTests, AcquisitionRateMixin, TransactionCase):
    """binaural dentro de la cadena del super de este addon (el MRO real)."""

    binaural_order = "inner"
    # El runner de Odoo solo recoge los test_* definidos en la propia clase; sin esto no
    # corrían los heredados de BinauralEmulationTests.
    allow_inherited_tests_method = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_acquisition_case("99002")


@tagged("post_install", "-at_install", "l10n_ve_accountant_asset")
class TestBinauralOutsideChain(BinauralEmulationTests, AcquisitionRateMixin, TransactionCase):
    """binaural por fuera de este addon (orden inverso); requiere el campo del activo."""

    binaural_order = "outer"
    allow_inherited_tests_method = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_acquisition_case("99003")


@tagged("post_install", "-at_install", "l10n_ve_accountant_asset")
class TestInstallmentRateWithoutBinaural(AcquisitionRateMixin, TransactionCase):
    """Sin binaural: cuota ya publicada intacta tras recalcular y asientos comunes."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_acquisition_case("99004")

    def setUp(self):
        super().setUp()
        self._patch_commit_progress()

    def test_recompute_does_not_touch_published_installment(self):
        asset = self._create_asset()
        move = self._custom_drafts(asset)[0]
        self._publish(move)
        move.write(
            {"manually_set_rate": True, "foreign_rate": 45.0, "foreign_inverse_rate": 1 / 45.0}
        )
        rate = (move.foreign_rate, move.foreign_inverse_rate)
        foreign = self._foreign_by_line(move)
        messages = move.message_ids

        asset.compute_depreciation_board()

        self.assertEqual((move.foreign_rate, move.foreign_inverse_rate), rate)
        self.assertEqual(self._foreign_by_line(move), foreign)
        if "foreign_rate" not in self.env["account.asset"]._fields:
            # Con binaural real instalado, este escribe y luego se restaura (mensajes propios).
            self.assertEqual(move.message_ids, messages)

    def test_recompute_does_not_write_when_rate_is_already_right(self):
        asset = self._create_asset()

        asset.compute_depreciation_board()

        # Las cuotas se recrean ya con la tasa correcta: no hay mensajes de "rate updated".
        for draft in self._custom_drafts(asset):
            self._assert_acquisition_rate(draft)
            self.assertFalse(draft.message_ids.filtered("tracking_value_ids"))

    def test_plain_custom_entry_is_revalued_at_publication_day_rate(self):
        journal = self.env["account.journal"].create(
            {"name": "Misc custom", "code": "TCUS", "type": "general"}
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
                "auto_post": "custom",
                "auto_post_custom_date": self.first_date,
                "line_ids": [
                    Command.create({"account_id": accounts[0].id, "debit": 1000.0}),
                    Command.create({"account_id": accounts[1].id, "credit": 1000.0}),
                ],
            }
        )

        self._publish(move)

        self.assertEqual(move.state, "posted")
        self.assertAlmostEqual(
            move.foreign_rate, self.publication_rate["foreign_rate"], places=6
        )
        self.assertEqual(
            self._debit_line(move).foreign_debit, round(1000.0 / self.publication_value, 2)
        )


@tagged("post_install", "-at_install", "l10n_ve_accountant_asset")
class TestForeignCurrencyVEFInUSDCompany(AcquisitionRateMixin, TransactionCase):
    """Compañía en USD con alterna VEF: ``foreign_rate`` sigue siendo moneda de la compañía
    por unidad de la alterna (0.025 USD por VEF), así que el valor alterno es
    ``balance / foreign_rate`` (antes se dividía entre ``max()`` de ambas tasas)."""

    own_company = True
    company_currency_xmlid = "base.USD"
    foreign_currency_xmlid = "base.VEF"
    acquisition_value = 0.025
    publication_value = 0.02

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_acquisition_case("99005")

    def setUp(self):
        super().setUp()
        self._patch_commit_progress()

    def test_foreign_value_is_balance_over_foreign_rate(self):
        asset = self._create_asset()
        move = self._custom_drafts(asset)[0]
        self._assert_acquisition_rate(move)
        self.assertEqual(
            self._debit_line(move).foreign_debit, round(MONTHLY_VALUE / 0.025, 2)
        )

        self._publish(move)

        self.assertEqual(move.state, "posted")
        self.assertEqual(
            self._debit_line(move).foreign_debit, round(MONTHLY_VALUE / 0.025, 2)
        )


@tagged("post_install", "-at_install", "l10n_ve_accountant_asset")
class TestModulesOrder(TransactionCase):
    """Si binaural_account_asset está instalado, este addon debe ir antes en el MRO: su
    ``_prepare_move_for_asset_depreciation`` y ``compute_depreciation_board`` envuelven a los
    de binaural y las correcciones post-super los alcanzan (la cadena es frágil: depende del
    orden alfabético de módulos)."""

    def _modules_in_mro(self, model):
        return [
            klass._module
            for klass in type(self.env[model]).__mro__
            if getattr(klass, "_module", None)
        ]

    def test_this_addon_precedes_binaural_in_the_mro(self):
        if "foreign_rate" not in self.env["account.asset"]._fields:
            self.skipTest("binaural_account_asset no está instalado.")
        for model in ("account.asset", "account.move"):
            modules = self._modules_in_mro(model)
            if "binaural_account_asset" not in modules:
                continue
            self.assertLess(
                modules.index("l10n_ve_accountant_asset"),
                modules.index("binaural_account_asset"),
                model,
            )
