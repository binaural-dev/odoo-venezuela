from datetime import datetime as real_datetime
from unittest.mock import patch

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged

# 2026-09-15 02:30 UTC is already the "next day" in UTC while it's still
# 2026-09-14 22:30 in Caracas (UTC-4). This is the exact shape of the TI-15211
# symptom: registering a document late at night local time, past midnight UTC.
_FROZEN_UTC_NOW = real_datetime(2026, 9, 15, 2, 30, 0)
_EXPECTED_CARACAS_DATE = fields.Date.to_date("2026-09-14")
_EXPECTED_UTC_DATE = fields.Date.to_date("2026-09-15")


class _FrozenDatetime(real_datetime):
    """Minimal stand-in for `datetime.now()` -- `Date.context_today` (see
    `odoo/orm/fields_temporal.py`) always calls `datetime.now()` with no
    arguments (naive, then localized as UTC), so only that path needs to be
    frozen."""

    @classmethod
    def now(cls, tz=None):
        if tz is not None:
            return _FROZEN_UTC_NOW.astimezone(tz)
        return _FROZEN_UTC_NOW


@tagged("post_install", "-at_install")
class TestTi15211InvoiceDateTimezone(TransactionCase):
    """Reproduces the ticket's actual symptom end-to-end: an `account.move`
    created by a user without a timezone gets its accounting date shifted to
    the next day (server/UTC), while the fix (`l10n_ve_base`'s default +
    backfill migration) keeps `invoice_date`, `invoice_date_display` and
    `date` aligned to the correct local day.

    Lives in `l10n_ve_invoice` (not `l10n_ve_accountant`, where the rest of
    the date chain is defined) because `invoice_date`'s own
    `default=fields.Date.context_today` is declared in
    `l10n_ve_invoice/models/account_move.py`, not in `l10n_ve_accountant`
    (which doesn't depend on `l10n_ve_invoice`) -- installing only
    `l10n_ve_accountant` leaves `invoice_date` with no default at all.
    """

    def setUp(self):
        super().setUp()

        # Deliberately minimal: this test is only about the timezone/date
        # chain (`invoice_date` -> `invoice_date_display` -> `date`), not
        # about VE-specific taxes/currency handling (already covered
        # elsewhere, e.g. `test_account_move_core.py`). No fiscal
        # country/currency/tax setup is touched, to avoid tripping
        # `_validate_taxes_country` unrelated to this fix.
        self.company = self.env.ref("base.main_company")

        self.acc_rec = self._get_or_create("120000", "Receivable", "asset_receivable", reconcile=True)
        self.acc_inc = self._get_or_create("400000", "Income", "income")

        self.sale_journal = self.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", self.company.id)], limit=1
        ) or self.env["account.journal"].sudo().create({
            "name": "Sales TI-15211 Test", "code": "S15211",
            "type": "sale", "company_id": self.company.id,
            "default_account_id": self.acc_inc.id,
        })

        self.partner = self.env["res.partner"].create({
            "name": "TI-15211 Test Partner",
            "property_account_receivable_id": self.acc_rec.id,
        })

        self.product = self.env["product.product"].create({
            "name": "TI-15211 Service", "type": "service", "list_price": 100.0,
            "property_account_income_id": self.acc_inc.id,
            "taxes_id": [(5, 0, 0)], "supplier_taxes_id": [(5, 0, 0)],
        })

    def _get_or_create(self, code, name, acc_type, reconcile=False):
        acc = self.env["account.account"].search([
            ("code", "=", code), ("company_ids", "in", self.company.id),
        ], limit=1)
        if not acc:
            acc = self.env["account.account"].create({
                "code": code, "name": name, "account_type": acc_type,
                "company_ids": [(6, 0, [self.company.id])],
                "reconcile": reconcile,
            })
        return acc

    def _create_user(self, login, tz):
        return self.env["res.users"].create({
            "name": login,
            "login": login,
            "email": f"{login}@example.com",
            "group_ids": [(6, 0, [self.env.ref("account.group_account_invoice").id])],
            # Explicit value bypasses l10n_ve_base's create-time default, so
            # the user reproduces the bug regardless of that default.
            "tz": tz,
        })

    def _create_invoice_as(self, user):
        return self.env["account.move"].with_user(user).with_context(
            check_move_validity=False,
        ).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 1.0,
                    "price_unit": 100.0,
                    "account_id": self.acc_inc.id,
                }),
            ],
        })

    def test_user_without_tz_gets_next_day_utc_date(self):
        """Without the fix (user with `tz=False`), `context_today()` has no
        timezone to resolve and falls back to raw UTC -- the exact bug
        reported in TI-15211."""
        user = self._create_user("ti_15211_no_tz", tz=False)

        with patch("odoo.orm.fields_temporal.datetime", _FrozenDatetime):
            invoice = self._create_invoice_as(user)

        self.assertEqual(invoice.invoice_date, _EXPECTED_UTC_DATE)
        self.assertEqual(invoice.invoice_date_display, _EXPECTED_UTC_DATE)
        self.assertEqual(invoice.date, _EXPECTED_UTC_DATE)

    def test_user_with_caracas_tz_keeps_local_date(self):
        """With a resolved `tz` (either set directly or backfilled by
        migrations/19.0.1.0.1/post-migrate.py), `invoice_date`,
        `invoice_date_display` and `date` must all agree on the correct
        local day instead of drifting to the next one."""
        user = self._create_user("ti_15211_caracas_tz", tz="America/Caracas")

        with patch("odoo.orm.fields_temporal.datetime", _FrozenDatetime):
            invoice = self._create_invoice_as(user)

        self.assertEqual(invoice.invoice_date, _EXPECTED_CARACAS_DATE)
        self.assertEqual(invoice.invoice_date_display, _EXPECTED_CARACAS_DATE)
        self.assertEqual(invoice.date, _EXPECTED_CARACAS_DATE)
        self.assertEqual(invoice.invoice_date, invoice.invoice_date_display)
        self.assertEqual(invoice.invoice_date_display, invoice.date)

        # DoD item 2 (TI-15211): the accounting entries (`account.move.line`)
        # must also settle on the correct local date, not just the move's
        # own `date`/`invoice_date_display` fields.
        self.assertTrue(invoice.line_ids)
        for line in invoice.line_ids:
            self.assertEqual(line.date, _EXPECTED_CARACAS_DATE)
