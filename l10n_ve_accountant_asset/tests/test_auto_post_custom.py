"""Publicacion personalizada (`auto_post = 'custom'`).

Un documento 'custom' espera en BORRADOR con las fechas de hoy y solo el cron lo
publica, el dia `auto_post_custom_date`, con esa fecha y la tasa exacta de ese dia.

`_commit_progress` hace commit y el cursor de pruebas lo prohibe: se parchea. La fecha
del cron se simula con `freeze_time`; `create_date` sigue siendo el reloj real, por eso
las fechas de publicacion se calculan hacia adelante a partir del "hoy" real.
"""

import inspect
from datetime import timedelta
from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, freeze_time, tagged

from odoo.addons.l10n_ve_accountant.tests.test_indexed_payments import TestIndexedPayments

CARACAS_TZ = "America/Caracas"


@tagged("post_install", "-at_install", "l10n_ve_accountant_asset")
class TestAutoPostCustom(TestIndexedPayments):
    def setUp(self):
        super().setUp()
        self.company.partner_id.tz = CARACAS_TZ
        self.env = self.env(
            context=dict(
                self.env.context,
                tz=CARACAS_TZ,
                allowed_company_ids=[self.company.id],
            )
        )
        self.today = fields.Date.context_today(self.env["account.move"])
        self.pub_date = self.today + timedelta(days=5)
        self._set_rate(self.currency_usd, self.today, 40.0)
        self.patch(
            self.registry["ir.cron"],
            "_commit_progress",
            lambda cron_model, processed=0, remaining=None, **kwargs: 1,
        )
        self.general_journal = self.env["account.journal"].sudo().create(
            {
                "name": "General Custom",
                "code": "GCUST",
                "type": "general",
                "company_id": self.company.id,
            }
        )
        self.Move = self.env["account.move"]

    # -- helpers ---------------------------------------------------------
    def _entry(self, **kwargs):
        vals = {
            "move_type": "entry",
            "journal_id": self.general_journal.id,
            "date": self.today,
            "line_ids": [
                Command.create(
                    {"account_id": self.account_receivable.id, "debit": 100.0, "credit": 0.0}
                ),
                Command.create(
                    {"account_id": self.account_income.id, "debit": 0.0, "credit": 100.0}
                ),
            ],
        }
        vals.update(kwargs)
        return self.Move.create(vals)

    def _custom_entry(self, pub_date=None, **kwargs):
        return self._entry(
            auto_post="custom",
            auto_post_custom_date=pub_date or self.pub_date,
            **kwargs,
        )

    def _custom_invoice(self, pub_date=None):
        return self.Move.create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.sale_journal.id,
                "invoice_date": self.today,
                "invoice_date_display": self.today,
                "date": self.today,
                "auto_post": "custom",
                "auto_post_custom_date": pub_date or self.pub_date,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 100.0,
                            "tax_ids": [Command.set(self.test_tax.ids)],
                        }
                    )
                ],
            }
        )

    def _run_cron(self, on_date, **kwargs):
        with freeze_time(f"{on_date} 15:00:00"):  # 11:00 en Caracas, el mismo dia
            self.Move._autopost_draft_entries(**kwargs)

    # -- no se publica a mano --------------------------------------------
    def test_custom_cannot_be_posted_manually(self):
        move = self._custom_entry()
        self.assertEqual(move.state, "draft")
        self.assertTrue(move.hide_post_button)
        with self.assertRaises(UserError):
            move.action_post()
        with self.assertRaisesRegex(UserError, "scheduled to be posted automatically"):
            move._post(soft=False)
        # soft: se excluye del lote sin error
        self.assertFalse(move._post(soft=True))
        self.assertEqual(move.state, "draft")
        self.assertEqual(move.auto_post, "custom")

    def test_custom_cannot_be_forced_by_wizard(self):
        move = self._custom_entry()
        wizard = self.env["validate.account.move"].create(
            {"move_ids": [Command.set(move.ids)], "force_post": True}
        )
        with self.assertRaises(UserError):
            wizard.validate_move()
        self.assertEqual(move.state, "draft")
        self.assertEqual(move.auto_post, "custom")

    def test_saved_custom_auto_post_is_readonly_in_form(self):
        move = self._custom_entry()
        with Form(move) as form, self.assertRaises(AssertionError):
            form.auto_post = "no"

    def test_cancel_abandons_the_schedule(self):
        move = self._custom_entry()
        move.button_cancel()
        self.assertEqual(move.state, "cancel")
        self.assertEqual(move.auto_post, "no")

    # -- constraints -------------------------------------------------------
    def test_custom_requires_a_date(self):
        with self.assertRaises(ValidationError):
            self._entry(auto_post="custom")

    def test_custom_date_cannot_precede_creation(self):
        with self.assertRaises(ValidationError):
            self._custom_entry(pub_date=self.today - timedelta(days=3))

    def test_custom_not_available_for_receipts(self):
        with self.assertRaises(ValidationError):
            self.Move.create(
                {
                    "move_type": "out_receipt",
                    "partner_id": self.partner.id,
                    "journal_id": self.sale_journal.id,
                    "auto_post": "custom",
                    "auto_post_custom_date": self.pub_date,
                }
            )

    # -- creacion ----------------------------------------------------------
    def test_custom_entry_created_with_today_even_if_publication_is_future(self):
        """No hay tasa en la fecha de publicacion y aun asi se crea: la fecha es la de hoy."""
        move = self._custom_entry()
        self.assertEqual(move.state, "draft")
        self.assertEqual(move.date, self.today)
        self.assertEqual(move.auto_post_custom_date, self.pub_date)
        self.assertTrue(move.foreign_rate)

    # -- cron -------------------------------------------------------------
    def test_cron_does_not_publish_before_the_date(self):
        move = self._custom_entry()
        self._set_rate(self.currency_usd, self.pub_date, 50.0)
        self._run_cron(self.pub_date - timedelta(days=1))
        self.assertEqual(move.state, "draft")
        self.assertEqual(move.auto_post, "custom")

    def test_cron_posts_entry_on_its_date(self):
        move = self._custom_entry()
        self._set_rate(self.currency_usd, self.pub_date, 50.0)
        self._run_cron(self.pub_date)
        self.assertEqual(move.state, "posted")
        self.assertEqual(move.auto_post, "no")
        self.assertEqual(move.date, self.pub_date)
        self.assertEqual(move.invoice_date_display, self.pub_date)
        self.assertEqual(move.auto_post_custom_date, self.pub_date)
        self.assertAlmostEqual(move.foreign_rate, 50.0, places=4)

    def test_cron_posts_invoice_with_publication_dates_and_rate(self):
        invoice = self._custom_invoice()
        self.assertEqual(invoice.invoice_date, self.today)
        self._set_rate(self.currency_usd, self.pub_date, 50.0)
        self._run_cron(self.pub_date)
        self.assertEqual(invoice.state, "posted")
        self.assertEqual(invoice.auto_post, "no")
        self.assertEqual(invoice.date, self.pub_date)
        self.assertEqual(invoice.invoice_date, self.pub_date)
        self.assertEqual(invoice.invoice_date_display, self.pub_date)
        self.assertAlmostEqual(invoice.foreign_rate, 50.0, places=4)

    def test_cron_respects_manual_rate(self):
        move = self._custom_entry(
            manually_set_rate=True, foreign_rate=45.0, foreign_inverse_rate=45.0
        )
        self._set_rate(self.currency_usd, self.pub_date, 50.0)
        self._run_cron(self.pub_date)
        self.assertEqual(move.state, "posted")
        self.assertEqual(move.foreign_rate, 45.0)

    def test_cron_not_starved_by_custom_batch(self):
        """Las custom no entran al lote del core: un at_date vencido se publica aunque haya
        mas custom que el tamano del lote, y las custom se procesan por lotes."""
        at_date = self._entry(auto_post="at_date")
        customs = self._custom_entry() | self._custom_entry() | self._custom_entry()
        for _i in range(3):
            customs |= self._custom_entry()
        self._set_rate(self.currency_usd, self.pub_date, 50.0)
        self._run_cron(self.pub_date, batch_size=2)
        self.assertEqual(at_date.state, "posted")
        self.assertEqual(len(customs.filtered(lambda m: m.state == "posted")), 2)
        self._run_cron(self.pub_date, batch_size=2)
        self._run_cron(self.pub_date, batch_size=2)
        self.assertEqual(set(customs.mapped("state")), {"posted"})

    def test_cron_overdue_custom_without_rate_waits_and_is_retried(self):
        move = self._custom_entry()
        self._run_cron(self.pub_date)
        # Sin tasa exacta ese dia: sigue 'custom' con sus fechas originales y avisa.
        self.assertEqual(move.state, "draft")
        self.assertEqual(move.auto_post, "custom")
        self.assertEqual(move.date, self.today)
        self.assertEqual(move.auto_post_custom_last_attempt, self.pub_date)
        self.assertIn("retried", " ".join(move.message_ids.mapped("body")))
        # Se carga la tasa; el mismo dia no se reintenta...
        self._set_rate(self.currency_usd, self.pub_date, 50.0)
        self._run_cron(self.pub_date)
        self.assertEqual(move.state, "draft")
        # ...al dia siguiente si, con la fecha de publicacion original.
        self._run_cron(self.pub_date + timedelta(days=1))
        self.assertEqual(move.state, "posted")
        self.assertEqual(move.date, self.pub_date)
        self.assertAlmostEqual(move.foreign_rate, 50.0, places=4)

    # -- contrato con el core (upgrades) --------------------------------------
    def test_core_autopost_domain_is_the_one_we_replicate(self):
        """`_autopost_draft_entries` se reemplaza sin super copiando el core: si el core cambia
        este dominio o el mecanismo de lotes hay que revisar el override."""
        core_cls = next(
            cls
            for cls in type(self.Move).__mro__
            if cls.__module__ == "odoo.addons.account.models.account_move"
            and "_autopost_draft_entries" in vars(cls)
        )
        source = inspect.getsource(vars(core_cls)["_autopost_draft_entries"])
        self.assertIn("('state', '=', 'draft')", source)
        self.assertIn("('date', '<=', fields.Date.context_today(self))", source)
        self.assertIn("('auto_post', '!=', 'no')", source)
        self.assertIn("try_lock_for_update", source)
        self.assertIn("_commit_progress", source)
