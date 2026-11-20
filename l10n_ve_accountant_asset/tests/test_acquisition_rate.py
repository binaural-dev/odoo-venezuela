from dateutil.relativedelta import relativedelta

from odoo.tests import TransactionCase, tagged

from .common import (
    INVOICE_INVERSE_RATE,
    INVOICE_RATE,
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

    def test_asset_own_rate_beats_table_rate(self):
        own = {"foreign_rate": INVOICE_RATE, "foreign_inverse_rate": INVOICE_INVERSE_RATE}
        asset = self._create_asset(own_rate=self.invoice_rates)
        move = self._future_drafts(asset)[0]
        self._assert_rate_of(move, own)
        expected = round(MONTHLY_VALUE / INVOICE_RATE, 2)
        self.assertEqual(self._debit_line(move).foreign_debit, expected)

        self._publish(move)

        self.assertEqual(move.state, "posted")
        self._assert_rate_of(move, own)
        self.assertEqual(self._debit_line(move).foreign_debit, expected)

    def test_recompute_with_own_rate_keeps_it_in_drafts(self):
        own = {"foreign_rate": INVOICE_RATE, "foreign_inverse_rate": INVOICE_INVERSE_RATE}
        asset = self._create_asset(own_rate=self.invoice_rates)

        asset.compute_depreciation_board()

        for draft in self._future_drafts(asset):
            self._assert_rate_of(draft, own)

    def test_zero_own_rate_uses_table_rate_not_daily_rate(self):
        # Con binaural "terco" (inner) las cuotas nacen con 0.0 y se corrigen a la efectiva.
        self.invoice_rates = (0.0, 0.0)
        asset = self._create_asset(own_rate=(0.0, 0.0))
        move = self._future_drafts(asset)[0]
        self._assert_acquisition_rate(move)
        self.assertEqual(
            self._debit_line(move).foreign_debit,
            round(MONTHLY_VALUE / self.acquisition_value, 2),
        )

    def test_stubborn_invoice_rate_is_corrected_to_the_table_rate(self):
        """Solo con binaural "terco" (inner), que escribe SIEMPRE la tasa de la factura: sin
        tasa propia en el activo, la efectiva es la de la tabla y el puente la restituye."""
        if self.binaural_order != "inner":
            self.skipTest("Solo aplica al orden 'inner' (binaural escribe la tasa de la factura).")
        asset = self._create_asset()
        for move in asset.depreciation_move_ids:
            self._assert_acquisition_rate(move)

    def test_recompute_restores_published_installment_rate(self):
        asset = self._create_asset()
        move = self._future_drafts(asset)[0]
        self._publish(move)
        # Cuota ya publicada con una tasa distinta a la de adquisición (histórica).
        move.write(
            {"manually_set_rate": True, "foreign_rate": 45.0, "foreign_inverse_rate": 1 / 45.0}
        )
        rate = (move.foreign_rate, move.foreign_inverse_rate)
        foreign = self._foreign_by_line(move)

        asset.compute_depreciation_board()

        # Con binaural por fuera de este addon nada protege a las publicadas (su escritura
        # va después de la nuestra): ese orden lo evita test_this_addon_precedes_binaural.
        if self.binaural_order == "inner":
            self.assertEqual((move.foreign_rate, move.foreign_inverse_rate), rate)
            self.assertTrue(move.manually_set_rate)
            self.assertEqual(self._foreign_by_line(move), foreign)
        for draft in self._future_drafts(asset):
            self._assert_acquisition_rate(draft)

    def test_modify_with_published_installments_keeps_their_rate(self):
        self._skip_if_real_binaural()
        old_acquisition = self.today.replace(day=1) - relativedelta(months=3)
        old_rate = self._seed_rate(old_acquisition, 35.0)
        asset = self._create_asset(acquisition_date=old_acquisition)
        posted = self._posted(asset)
        self.assertTrue(posted)
        foreign = {move: self._foreign_by_line(move) for move in posted}

        wizard = self.env["asset.modify"].create(
            {"asset_id": asset.id, "name": "Modify", "date": self.today}
        )
        wizard.modify()

        for move in posted:
            self._assert_rate_of(move, old_rate)
            self.assertEqual(self._foreign_by_line(move), foreign[move])
        for move in self._future_drafts(asset):
            self._assert_rate_of(move, old_rate)


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
        cls._setup_acquisition_case("99302")


@tagged("post_install", "-at_install", "l10n_ve_accountant_asset")
class TestBinauralOutsideChain(BinauralEmulationTests, AcquisitionRateMixin, TransactionCase):
    """binaural por fuera de este addon (orden inverso); requiere el campo del activo."""

    binaural_order = "outer"
    allow_inherited_tests_method = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_acquisition_case("99303")


@tagged("post_install", "-at_install", "l10n_ve_accountant_asset")
class TestInstallmentRateWithoutBinaural(AcquisitionRateMixin, TransactionCase):
    """Sin binaural: cuota ya publicada intacta tras recalcular el plan."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_acquisition_case("99304")

    def setUp(self):
        super().setUp()
        self._patch_commit_progress()

    def test_recompute_does_not_touch_published_installment(self):
        asset = self._create_asset()
        move = self._future_drafts(asset)[0]
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
        for draft in self._future_drafts(asset):
            self._assert_acquisition_rate(draft)
            self.assertFalse(draft.message_ids.filtered("tracking_value_ids"))


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
        cls._setup_acquisition_case("99305")

    def setUp(self):
        super().setUp()
        self._patch_commit_progress()

    def test_foreign_value_is_balance_over_foreign_rate(self):
        asset = self._create_asset()
        move = self._future_drafts(asset)[0]
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
