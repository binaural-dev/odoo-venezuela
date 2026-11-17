"""Guarda de regresion: documentos contables a las 8 pm de Caracas.

A las 8 pm de Caracas el servidor (UTC) ya esta en el dia siguiente. Facturas,
asientos y pagos toman su fecha de `context_today` (invoice_date_display / date),
asi que HOY ESTAS PRUEBAS PASAN: el flujo estandar de `account.move` y
`account.payment` no reproduce el error. Fallarian si alguien cambia esas fechas
por `fields.Date.today()` (fecha UTC), que buscaria la tasa de "manana" y lanzaria
"no hay tasa asignada". Los sitios que SI reproducen el error estan en
l10n_ve_sale, l10n_ve_pos y binaural_purchase.
"""

import logging

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged

from .common_tz_boundary import (
    CARACAS_DAY,
    FROZEN_UTC_NOW,
    USD_PER_VEF_INVERSE,
    TzBoundaryMixin,
    freeze_time,
)

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_accountant_tz_boundary")
class TestMoveServerDateVsUserTz(TzBoundaryMixin, TransactionCase):
    def setUp(self):
        super().setUp()
        self._setup_tz_boundary()
        country = self.env.ref("base.ve")
        self.company.write(
            {"account_fiscal_country_id": country.id, "country_id": country.id}
        )
        Account = self.env["account.account"]

        def acc(code, name, acc_type, reconcile=False):
            found = Account.search(
                [("code", "=", code), ("company_ids", "in", self.company.id)], limit=1
            )
            return found or Account.create(
                {
                    "code": code,
                    "name": name,
                    "account_type": acc_type,
                    "company_ids": [(6, 0, [self.company.id])],
                    "reconcile": reconcile,
                }
            )

        self.acc_rec = acc("120000", "Receivable", "asset_receivable", True)
        self.acc_pay = acc("210000", "Payable", "liability_payable", True)
        self.acc_inc = acc("400000", "Income", "income")
        self.acc_exp = acc("500000", "Expense", "expense")

        Journal = self.env["account.journal"]

        def journal(jtype, code, **extra):
            return Journal.search(
                [("type", "=", jtype), ("company_id", "=", self.company.id)], limit=1
            ) or Journal.sudo().create(
                {
                    "name": f"TZ {jtype}",
                    "code": code,
                    "type": jtype,
                    "company_id": self.company.id,
                    **extra,
                }
            )

        self.sale_journal = journal("sale", "TZSAL", default_account_id=self.acc_inc.id)
        self.purchase_journal = journal(
            "purchase", "TZPUR", default_account_id=self.acc_exp.id
        )
        self.general_journal = journal("general", "TZGEN")

        self.partner = self.env["res.partner"].create(
            {
                "name": "TZ Partner",
                "country_id": country.id,
                "property_account_receivable_id": self.acc_rec.id,
                "property_account_payable_id": self.acc_pay.id,
            }
        )

    def _product(self):
        return self.env["product.product"].create(
            {
                "name": "TZ Servicio",
                "type": "service",
                "list_price": 100.0,
                "property_account_income_id": self.acc_inc.id,
                "property_account_expense_id": self.acc_exp.id,
                "taxes_id": [(5, 0, 0)],
                "supplier_taxes_id": [(5, 0, 0)],
            }
        )

    def _invoice_vals(self, move_type, journal, account):
        return {
            "move_type": move_type,
            "partner_id": self.partner.id,
            "journal_id": journal.id,
            "currency_id": self.currency_vef.id,
            "invoice_line_ids": [
                Command.create(
                    {
                        "product_id": self._product().id,
                        "name": "Servicio",
                        "quantity": 1.0,
                        "price_unit": 100.0,
                        "account_id": account.id,
                        "tax_ids": [(5, 0, 0)],
                    }
                )
            ],
        }

    def _assert_caracas_day_rate(self, move):
        self.assertAlmostEqual(
            move.foreign_rate,
            USD_PER_VEF_INVERSE,
            places=4,
            msg=(
                "A las 8 pm de Caracas el documento debe tomar la tasa del dia "
                f"del usuario ({CARACAS_DAY}), no la del dia UTC."
            ),
        )

    def test_scenario_is_8pm_caracas(self):
        """Control: el reloj congelado es 8:30 pm en Caracas y 00:30 en UTC."""
        with freeze_time(FROZEN_UTC_NOW):
            self.assertCaracasDay()
            self.assertNotEqual(fields.Date.today(), fields.Date.context_today(self.env.user))

    def test_customer_invoice_at_8pm_uses_user_day_rate(self):
        with freeze_time(FROZEN_UTC_NOW):
            move = self.env["account.move"].create(
                self._invoice_vals("out_invoice", self.sale_journal, self.acc_inc)
            )
            self._assert_caracas_day_rate(move)

    def test_vendor_bill_at_8pm_uses_user_day_rate(self):
        with freeze_time(FROZEN_UTC_NOW):
            move = self.env["account.move"].create(
                self._invoice_vals("in_invoice", self.purchase_journal, self.acc_exp)
            )
            self._assert_caracas_day_rate(move)

    def test_journal_entry_at_8pm_uses_user_day_rate(self):
        with freeze_time(FROZEN_UTC_NOW):
            move = self.env["account.move"].create(
                {"move_type": "entry", "journal_id": self.general_journal.id}
            )
            self._assert_caracas_day_rate(move)

    def test_customer_invoice_with_user_date_but_no_rate_date_at_8pm(self):
        """El usuario pone fecha de factura = su "hoy"; la tasa debe ser la de ese dia."""
        with freeze_time(FROZEN_UTC_NOW):
            vals = self._invoice_vals("out_invoice", self.sale_journal, self.acc_inc)
            vals["invoice_date_display"] = CARACAS_DAY
            move = self.env["account.move"].create(vals)
            self._assert_caracas_day_rate(move)

    def test_payment_at_8pm_uses_user_day_rate(self):
        with freeze_time(FROZEN_UTC_NOW):
            bank = self.env["account.journal"].search(
                [("type", "in", ("bank", "cash")), ("company_id", "=", self.company.id)],
                limit=1,
            ) or self.env["account.journal"].sudo().create(
                {
                    "name": "TZ Bank",
                    "code": "TZBNK",
                    "type": "bank",
                    "company_id": self.company.id,
                }
            )
            payment = self.env["account.payment"].create(
                {
                    "payment_type": "inbound",
                    "partner_type": "customer",
                    "partner_id": self.partner.id,
                    "amount": 100.0,
                    "currency_id": self.currency_vef.id,
                    "journal_id": bank.id,
                }
            )
            self.assertEqual(payment.date, CARACAS_DAY)
            self._assert_caracas_day_rate(payment)
