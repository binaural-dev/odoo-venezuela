from datetime import timedelta

from odoo import fields
from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_accountant_core")
class TestMoveRateDateForm(TransactionCase):
    """foreign_rate / foreign_inverse_rate must follow the invoice date when it
    is edited from the form: sales (customer invoice) and purchases (vendor
    bill), on a new record and on a saved draft."""

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.usd = self.env.ref("base.USD")
        self.company.write({
            "currency_id": self.env.ref("base.VEF").id,
            "foreign_currency_id": self.usd.id,
        })
        self.today = fields.Date.today()
        self.past = self.today - timedelta(days=5)
        for day, rate in ((self.today, 1 / 40.0), (self.past, 1 / 30.0)):
            self.env["res.currency.rate"].create({
                "currency_id": self.usd.id,
                "company_id": self.company.id,
                "name": day,
                "rate": rate,
            })
        self.partner = self.env["res.partner"].create({"name": "Rate Form Partner"})

    def _expected(self, day):
        return self.env["res.currency.rate"].compute_rate(self.usd.id, day)

    def _new_form(self, move_type):
        return Form(
            self.env["account.move"].with_context(default_move_type=move_type)
        )

    def _assert_rates(self, rec, day):
        expected = self._expected(day)
        self.assertAlmostEqual(rec.foreign_rate, expected["foreign_rate"], places=6)
        self.assertAlmostEqual(
            rec.foreign_inverse_rate, expected["foreign_inverse_rate"], places=6
        )

    def _set_date(self, form, move_type, day):
        # La tasa sigue a invoice_date ("Rate Date"). En ventas el onchange de
        # invoice_date_display la copia; en compras el usuario la edita directo.
        if move_type == "in_invoice":
            form.invoice_date = day
        else:
            form.invoice_date_display = day

    def _check_new(self, move_type):
        self.assertNotAlmostEqual(
            self._expected(self.past)["foreign_rate"],
            self._expected(self.today)["foreign_rate"],
        )
        with self._new_form(move_type) as form:
            form.partner_id = self.partner
            self._set_date(form, move_type, self.past)
            # Los campos estan en la vista: el onchange los recalcula ya en el form
            self._assert_rates(form, self.past)
        # force_save: lo que calculo el form es lo que se guarda
        self._assert_rates(form.save(), self.past)

    def _check_existing(self, move_type):
        move = self.env["account.move"].create({
            "move_type": move_type,
            "partner_id": self.partner.id,
            "invoice_date_display": self.today,
        })
        with Form(move) as form:
            self._set_date(form, move_type, self.past)
            self._assert_rates(form, self.past)
        self._assert_rates(move, self.past)

    def test_sale_invoice_new_date_change(self):
        self._check_new("out_invoice")

    def test_sale_invoice_existing_date_change(self):
        self._check_existing("out_invoice")

    def test_purchase_bill_new_date_change(self):
        self._check_new("in_invoice")

    def test_purchase_bill_existing_date_change(self):
        self._check_existing("in_invoice")

    def test_new_invoice_with_past_invoice_date_uses_that_date_rate(self):
        # Sin default propio en la tasa: la factura (cliente y proveedor) creada con fecha pasada
        # toma la tasa de esa fecha, no la de hoy, y es lo que se guarda.
        for move_type in ("out_invoice", "in_invoice"):
            with self._new_form(move_type) as form:
                form.partner_id = self.partner
                self._set_date(form, move_type, self.past)
            self._assert_rates(form.save(), self.past)

    def test_reopening_saved_invoice_keeps_its_rate_if_official_rate_changes(self):
        # Si se corrige la tasa oficial de un dia ya usado, abrir la factura guardada y
        # volver a la misma fecha no la mueve a la tasa corregida.
        for move_type in ("out_invoice", "in_invoice"):
            move = self.env["account.move"].create({
                "move_type": move_type,
                "partner_id": self.partner.id,
                "invoice_date": self.past,
            })
            saved = move.foreign_rate
            self.assertAlmostEqual(saved, self._expected(self.past)["foreign_rate"], places=6)
            self.env["res.currency.rate"].search([
                ("currency_id", "=", self.usd.id),
                ("company_id", "=", self.company.id),
                ("name", "=", self.past),
            ]).rate = 1 / 20.0
            self.assertNotAlmostEqual(self._expected(self.past)["foreign_rate"], saved, places=6)
            with Form(move) as form:
                # abrir y editar otro campo no recalcula la tasa guardada
                self.assertAlmostEqual(form.foreign_rate, saved, places=6)
                form.narration = "reopened"
            self.assertAlmostEqual(move.foreign_rate, saved, places=6, msg=move_type)
            with Form(move) as form:
                # cambiar la fecha y volver a la original conserva la tasa en el form
                self._set_date(form, move_type, self.today)
                self._set_date(form, move_type, self.past)
                self.assertAlmostEqual(form.foreign_rate, saved, places=6)
            # deja la tasa del dia como estaba para la siguiente vuelta
            self.env["res.currency.rate"].search([
                ("currency_id", "=", self.usd.id),
                ("company_id", "=", self.company.id),
                ("name", "=", self.past),
            ]).rate = 1 / 30.0

    def test_manual_invoice_without_rate_gets_one(self):
        # manually_set_rate sin ninguna tasa fijada aun: igual se calcula; con una, se respeta.
        for move_type in ("out_invoice", "in_invoice"):
            move = self.env["account.move"].create({
                "move_type": move_type,
                "partner_id": self.partner.id,
                "invoice_date": self.past,
                "manually_set_rate": True,
            })
            self._assert_rates(move, self.past)
            move = self.env["account.move"].create({
                "move_type": move_type,
                "partner_id": self.partner.id,
                "invoice_date": self.past,
                "manually_set_rate": True,
                "foreign_rate": 77.0,
            })
            self.assertEqual(move.foreign_rate, 77.0)

    def test_residual_rate_is_treated_as_no_rate(self):
        # Un residuo de redondeo no cuenta como "ya tiene tasa": se recalcula.
        move = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "invoice_date": self.past,
            "manually_set_rate": True,
            "foreign_rate": 1e-12,
        })
        self._assert_rates(move, self.past)
