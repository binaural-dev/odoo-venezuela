"""Validaciones del método de pago del PdV al guardarlo (ticket 15399).

1. Un método en moneda alterna o con moneda de cobro no puede tener su diario
   y su diario afectado (``cross_journal``) en la misma cuenta transitoria: el
   cruce de la venta en efectivo iría de una cuenta a ella misma.
2. El diario del método tiene que estar en la moneda de cada una de sus cajas
   (la regla del core ``pos.config._check_currencies``), revisado también al
   guardar el método y no solo al guardar la caja o al abrir la sesión.

La compañía está en Bs con USD de alterna, como en producción: los diarios del
fixture y la caja trabajan en la moneda de la compañía.
"""

from contextlib import contextmanager

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .test_pos_session_accounting_common import TestPosSessionAccountingBase

SAME_SUSPENSE = "use the same suspense account"
OTHER_CURRENCY = "must be in the currency of its Point of Sale"


@tagged("post_install", "-at_install", "l10n_ve_pos")
class TestPosPaymentMethodValidations(TestPosSessionAccountingBase):
    company_currency_name = "VEF"
    foreign_currency_name = "USD"
    sales_in_foreign = False

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.usd = cls.foreign_currency
        cls.eur = cls.env.ref("base.EUR")
        cls.eur.active = True
        Journal = cls.env["account.journal"]
        cls.suspense_method = cls._account("T Transitoria del metodo", "190150T")
        cls.suspense_real = cls._account("T Transitoria de la caja real", "190151T")
        cls.suspense_other = cls._account("T Otra transitoria", "190152T")

        # Diario del método (el transitorio, en la moneda de la compañía) y
        # caja real en USD, cada uno con su transitoria.
        cls.method_journal = cls._cash_journal(
            "T Efectivo USD (transitorio)", "TM150", suspense=cls.suspense_method
        )
        cls.real_journal = cls._cash_journal(
            "T Caja USD", "TR150", currency=cls.usd, suspense=cls.suspense_real
        )
        cls.cross_account_journal = Journal.create(
            {"name": "T Cruce", "type": "general", "code": "TC150", "company_id": cls.company.id}
        )

    @classmethod
    def _account(cls, name, code, account_type="asset_current"):
        return cls.env["account.account"].create(
            {
                "name": name,
                "code": code,
                "account_type": account_type,
                "company_ids": [Command.set(cls.company.ids)],
            }
        )

    @classmethod
    def _cash_journal(cls, name, code, currency=None, suspense=None):
        vals = {
            "name": name,
            "type": "cash",
            "code": code,
            "company_id": cls.company.id,
            "default_account_id": cls._account(name, code + "0", "asset_cash").id,
        }
        if currency:
            vals["currency_id"] = currency.id
        if suspense:
            vals["suspense_account_id"] = suspense.id
        return cls.env["account.journal"].create(vals)

    @contextmanager
    def _rejected(self, message):
        """``assertRaises`` de Odoo, que deshace en un savepoint lo que la
        escritura rechazada alcanzó a guardar (``assertRaisesRegex`` no lo
        hace), y el mensaje esperado."""
        with self.assertRaises(ValidationError) as catcher:
            yield
        self.assertIn(message, str(catcher.exception))

    def _foreign_method(self, **vals):
        """Método en moneda alterna con sus dos diarios de cruce."""
        return self.env["pos.payment.method"].create(
            {
                "name": "T Efectivo USD",
                "company_id": self.company.id,
                "journal_id": self.method_journal.id,
                "is_foreign_currency": True,
                "cross_journal": self.real_journal.id,
                "cross_account_journal": self.cross_account_journal.id,
                **vals,
            }
        )

    # ------------------------------------------------------------------
    # 1. Cuentas transitorias distintas en los dos diarios del cruce
    # ------------------------------------------------------------------

    def test_same_suspense_account_rejected_on_method(self):
        self.real_journal.suspense_account_id = self.suspense_other
        self.method_journal.suspense_account_id = self.suspense_other
        with self._rejected(SAME_SUSPENSE):
            self._foreign_method()

    def test_company_default_suspense_account_rejected(self):
        """La configuración por defecto de Odoo: los dos diarios toman la
        transitoria de la compañía."""
        self.company.account_journal_suspense_account_id = self.suspense_other
        method_journal = self._cash_journal("T Metodo por defecto", "TD150")
        real_journal = self._cash_journal("T Real por defecto", "TE150", currency=self.usd)
        self.assertEqual(method_journal.suspense_account_id, self.suspense_other)
        self.assertEqual(real_journal.suspense_account_id, self.suspense_other)
        with self._rejected(SAME_SUSPENSE):
            self._foreign_method(journal_id=method_journal.id, cross_journal=real_journal.id)

    def test_same_suspense_account_rejected_on_tender_currency_method(self):
        eur_journal = self._cash_journal(
            "T Caja EUR", "TU150", currency=self.eur, suspense=self.suspense_method
        )
        with self._rejected(SAME_SUSPENSE):
            self._foreign_method(
                is_foreign_currency=False,
                tender_currency_id=self.eur.id,
                cross_journal=eur_journal.id,
            )

    def test_same_suspense_account_rejected_from_the_journals(self):
        self._foreign_method()
        with self._rejected(SAME_SUSPENSE):
            self.real_journal.suspense_account_id = self.suspense_method
        with self._rejected(SAME_SUSPENSE):
            self.method_journal.suspense_account_id = self.suspense_real

    def test_distinct_suspense_accounts_are_saved(self):
        method = self._foreign_method()
        self.real_journal.suspense_account_id = self.suspense_other
        self.assertEqual(method.cross_journal.suspense_account_id, self.suspense_other)

    def test_incomplete_configuration_is_saved(self):
        """Sin diario afectado o sin transitoria en el diario del método no hay
        nada que comparar: lo reporta la apertura de la sesión."""
        self._foreign_method(cross_journal=False)
        journal = self._cash_journal("T Sin transitoria", "TS150")
        journal.suspense_account_id = False
        self.real_journal.suspense_account_id = False
        self._foreign_method(journal_id=journal.id)

    def test_method_without_cross_move_is_not_checked(self):
        self.real_journal.suspense_account_id = self.suspense_method
        method = self.env["pos.payment.method"].create(
            {
                "name": "T Efectivo Bs",
                "company_id": self.company.id,
                "journal_id": self.method_journal.id,
                "cross_journal": self.real_journal.id,
            }
        )
        self.assertFalse(method.is_foreign_currency)

    def test_method_saved_before_the_rule(self):
        """Un método guardado con las dos transitorias iguales antes de la
        regla sigue en uso; al cambiarle un diario se rechaza."""
        method = self._foreign_method()
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE account_journal SET suspense_account_id = %s WHERE id = %s",
            (self.suspense_method.id, self.real_journal.id),
        )
        self.env.invalidate_all()
        method.name = "T Efectivo USD renombrado"
        with self._rejected(SAME_SUSPENSE):
            method.write({"cross_journal": self.real_journal.id})

    # ------------------------------------------------------------------
    # 2. Diario del método en la moneda de sus cajas
    # ------------------------------------------------------------------

    def test_journal_in_other_currency_than_pos_rejected_on_method(self):
        self.assertEqual(self.config.currency_id, self.company.currency_id)
        usd_journal = self._cash_journal("T Banco USD", "TB150", currency=self.usd)
        with self._rejected(OTHER_CURRENCY):
            self.combined_bank_method.journal_id = usd_journal

    def test_pos_added_from_method_rejected(self):
        usd_journal = self._cash_journal("T Efectivo USD sin caja", "TF150", currency=self.usd)
        method = self.env["pos.payment.method"].create(
            {"name": "T USD sin caja", "company_id": self.company.id, "journal_id": usd_journal.id}
        )
        with self._rejected(OTHER_CURRENCY):
            method.config_ids = [Command.link(self.config.id)]

    def test_journal_in_pos_currency_is_saved(self):
        journal = self._cash_journal("T Efectivo Bs", "TV150", currency=self.company.currency_id)
        method = self.env["pos.payment.method"].create(
            {
                "name": "T Efectivo Bs",
                "company_id": self.company.id,
                "journal_id": journal.id,
                "config_ids": [Command.link(self.config.id)],
            }
        )
        self.assertIn(method, self.config.payment_method_ids)

    def test_journal_without_currency_is_saved(self):
        journal = self._cash_journal("T Efectivo sin moneda", "TN150")
        method = self.env["pos.payment.method"].create(
            {
                "name": "T Efectivo sin moneda",
                "company_id": self.company.id,
                "journal_id": journal.id,
                "config_ids": [Command.link(self.config.id)],
            }
        )
        self.assertIn(method, self.config.payment_method_ids)

    def test_method_without_pos_accepts_any_journal_currency(self):
        """Sin caja no se valida la moneda, tampoco en un método en moneda
        alterna; se valida cuando se le agrega una caja."""
        usd_journal = self._cash_journal("T Efectivo USD alterna", "TA150", currency=self.usd)
        method = self._foreign_method(journal_id=usd_journal.id, cross_journal=False)
        with self._rejected(OTHER_CURRENCY):
            method.config_ids = [Command.link(self.config.id)]
