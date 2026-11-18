"""Utilidades compartidas de los tests de la tasa de adquisición de las cuotas.

No es un TestCase: es un mixin, para que el cargador de tests no recoja el módulo dos veces.
"""

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests import freeze_time

from odoo.addons.account_asset.models.account_asset import AccountAsset as EnterpriseAsset
from odoo.addons.account_asset.models.account_move import AccountMove as EnterpriseMove
from odoo.addons.l10n_ve_accountant.tests.common_rates import set_rate

ACQUISITION_RATE = 40.0
PUBLICATION_RATE = 50.0
# Tasa de la "factura de compra" que emula binaural_account_asset (distinta a las demás).
INVOICE_RATE = 857.0058
INVOICE_INVERSE_RATE = round(1 / INVOICE_RATE, 6)
MONTHLY_VALUE = 3527.70


class AcquisitionRateMixin:
    """Activo de 12 cuotas mensuales adquirido el primer día del mes actual, con tasa propia
    en la fecha de adquisición y otra distinta en la fecha de la primera cuota futura.

    `create_date` viene del reloj real de la BD: las fechas se calculan con el "hoy" real y
    `freeze_time` solo envuelve la llamada al cron.
    """

    # None (solo este addon), "inner" (binaural dentro de la cadena del super, como en el
    # MRO real) o "outer" (binaural por fuera de este addon, orden inverso).
    binaural_order = None
    invoice_rates = (INVOICE_RATE, INVOICE_INVERSE_RATE)
    own_company = False
    company_currency_xmlid = "base.VEF"
    foreign_currency_xmlid = "base.USD"
    acquisition_value = ACQUISITION_RATE
    publication_value = PUBLICATION_RATE

    @classmethod
    def _setup_acquisition_case(cls, code_prefix):
        currencies = {
            "currency_id": cls.env.ref(cls.company_currency_xmlid).id,
            "foreign_currency_id": cls.env.ref(cls.foreign_currency_xmlid).id,
        }
        cls.env.ref(cls.foreign_currency_xmlid).active = True
        company = cls.env.company
        if cls.own_company:
            # Cambiar la moneda de una compañía con apuntes está prohibido: se usa una nueva.
            company = cls.env["res.company"].create(
                {"name": f"Asset rate {code_prefix}", "currency_id": currencies["currency_id"]}
            )
            company.foreign_currency_id = currencies["foreign_currency_id"]
            cls.env.user.company_ids |= company
            cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=company.ids))
        elif any(company[fname].id != value for fname, value in currencies.items()):
            company.write(currencies)
        company.partner_id.tz = "America/Caracas"
        cls.env = cls.env(context=dict(cls.env.context, tz="America/Caracas"))
        cls.company = company
        cls.foreign_currency = cls.env.ref(cls.foreign_currency_xmlid)
        cls.today = fields.Date.context_today(cls.env["account.move"])
        cls.acquisition_date = cls.today.replace(day=1)
        cls.first_date = cls.acquisition_date + relativedelta(months=1, days=-1)
        # Las tasas se siembran con el "inverse_company_rate" (set_rate): foreign_rate es
        # unidades de moneda de la compañía por unidad de la alterna.
        # Hoy primero: si coincide con otra fecha, esa tasa la pisa (las de abajo mandan).
        cls._seed_rate(cls.today, cls.acquisition_value)
        cls.acquisition_rate = cls._seed_rate(cls.acquisition_date, cls.acquisition_value)
        cls.publication_rate = cls._seed_rate(cls.first_date, cls.publication_value)
        Account = cls.env["account.account"]
        cls.asset_vals = {
            "name": "Vehicle",
            "account_asset_id": Account.create(
                {"name": "Fixed Asset", "code": f"{code_prefix}1", "account_type": "asset_fixed"}
            ).id,
            "account_depreciation_id": Account.create(
                {"name": "Depreciation", "code": f"{code_prefix}2", "account_type": "asset_fixed"}
            ).id,
            "account_depreciation_expense_id": Account.create(
                {"name": "Depreciation Expense", "code": f"{code_prefix}3", "account_type": "expense"}
            ).id,
            "journal_id": cls.env["account.journal"]
            .create({"name": "Assets", "code": f"T{code_prefix[-2:]}", "type": "general"})
            .id,
            "original_value": MONTHLY_VALUE * 12,
            "acquisition_date": cls.acquisition_date,
            "method_number": 12,
            "method_period": "1",
        }

    @classmethod
    def _seed_rate(cls, rate_date, value):
        """Siembra la tasa ``value`` (moneda de la compañía por unidad de la alterna) en
        ``rate_date`` y devuelve el dict de ``compute_rate``."""
        set_rate(cls.env, cls.foreign_currency, rate_date.isoformat(), cls.company, value)
        return (
            cls.env["res.currency.rate"]
            .with_company(cls.company)
            .compute_rate(cls.foreign_currency.id, rate_date)
        )

    def _patch_commit_progress(self):
        self.patch(
            self.registry["ir.cron"],
            "_commit_progress",
            lambda cron_model, processed=0, remaining=None, **kwargs: 1,
        )

    # -- emulación de binaural_account_asset -----------------------------
    def _emulate_binaural(self):
        """Emula binaural_account_asset (no es dependencia) en la posición pedida.

        Parchea la clase de enterprise (``inner``: queda DENTRO de la cadena del super de
        este addon, que es el MRO real) o la clase final del registro (``outer``: queda por
        fuera). Binaural escribe la tasa manual en las cuotas al prepararlas y en TODAS al
        recalcular el plan. En ``outer`` usa la tasa del activo si el campo existe (así se
        prueba que este addon la fija antes); en ``inner`` usa siempre la de la factura de
        prueba, como un binaural "terco" que este addon debe corregir después.
        """
        outer = self.binaural_order == "outer"
        asset_has_rate = "foreign_rate" in self.env["account.asset"]._fields
        if outer and not asset_has_rate:
            self.skipTest("El orden 'outer' necesita foreign_rate en account.asset (binaural).")
        move_cls = self.registry["account.move"] if outer else EnterpriseMove
        asset_cls = self.registry["account.asset"] if outer else EnterpriseAsset
        original_prepare = move_cls._prepare_move_for_asset_depreciation
        original_board = asset_cls.compute_depreciation_board
        test = self

        def rates_of(asset):
            if outer:
                return asset.foreign_rate, asset.foreign_inverse_rate
            return test.invoice_rates

        def prepare(model, vals):
            move_vals = original_prepare(model, vals)
            rate, inverse_rate = rates_of(vals["asset_id"])
            move_vals.update(
                {
                    "manually_set_rate": True,
                    "foreign_rate": rate,
                    "foreign_inverse_rate": inverse_rate,
                }
            )
            return move_vals

        def board(assets, *args):
            result = original_board(assets, *args)
            for asset in assets:
                rate, inverse_rate = rates_of(asset)
                asset.depreciation_move_ids.write(
                    {
                        "manually_set_rate": True,
                        "foreign_rate": rate,
                        "foreign_inverse_rate": inverse_rate,
                    }
                )
            return result

        self.patch(move_cls, "_prepare_move_for_asset_depreciation", prepare)
        self.patch(asset_cls, "compute_depreciation_board", board)

    # -- helpers ---------------------------------------------------------
    def _create_asset(self, validate=True, **vals):
        asset_vals = dict(self.asset_vals, **vals)
        if "foreign_rate" in self.env["account.asset"]._fields:
            # Con binaural_account_asset instalado la tasa de la factura vive en el activo.
            rate, inverse_rate = self.invoice_rates
            asset_vals.update({"foreign_rate": rate, "foreign_inverse_rate": inverse_rate})
        asset = self.env["account.asset"].create(asset_vals)
        if validate:
            asset.validate()
        return asset

    def _custom_drafts(self, asset):
        return asset.depreciation_move_ids.filtered(
            lambda m: m.state == "draft" and m.auto_post == "custom"
        ).sorted("auto_post_custom_date")

    def _debit_line(self, move):
        return move.line_ids.filtered(lambda line: line.debit)

    def _foreign_by_line(self, move):
        return {
            line.account_id: line.foreign_debit - line.foreign_credit
            for line in move.line_ids
        }

    def _publish(self, move):
        with freeze_time(f"{move.auto_post_custom_date} 15:00:00"):
            self.env["account.move"]._autopost_draft_entries()

    def _assert_acquisition_rate(self, move):
        self.assertTrue(move.manually_set_rate)
        self.assertAlmostEqual(move.foreign_rate, self.acquisition_rate["foreign_rate"], places=6)
        self.assertAlmostEqual(
            move.foreign_inverse_rate, self.acquisition_rate["foreign_inverse_rate"], places=6
        )
