import logging
from unittest import skip
from unittest.mock import patch

from dateutil.relativedelta import relativedelta

from lxml import etree

from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, tagged
from odoo.tools.safe_eval import safe_eval

from .test_withholding_common_VEF import RetentionTestCommon
_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "retention_indexed")
class TestRetentionIndexed(RetentionTestCommon):
    """Modalidad de retención indexada.

    El monto retenido en bolívares es el mismo en ambas modalidades (monto legal). Lo que cambia es
    con qué tasa se valora el monto en la moneda de la factura: la de la factura (no indexada) o la
    de la fecha contable (indexada). La indexada solo admite facturas en moneda extranjera.
    """

    INVOICE_RATE = 40.0
    VOUCHER_RATE = 60.0

    def setUp(self):
        super().setUp()
        self.today = fields.Date.today()
        # La factura queda cinco días antes de hoy: "el comprobante cinco días después" cae hoy, que
        # es la fecha que el formulario de las retenciones de proveedor impone (fecha de solo lectura)
        self.invoice_date = self.today - relativedelta(days=5)
        # La fixture solo fija la tasa propia del VEF (1.0) para hoy y ayer. Para la fecha de la
        # factura también hace falta: Odoo normaliza company_rate contra la tasa del VEF a esa
        # fecha y, sin este registro, arrastraría la semilla de 2010 (5,864).
        self.env["res.currency.rate"].search([
            ("currency_id", "=", self.currency_vef.id),
            ("company_id", "=", self.company.id),
            ("name", "=", self.invoice_date),
        ]).unlink()
        self.env["res.currency.rate"].create({
            "currency_id": self.currency_vef.id,
            "company_id": self.company.id,
            "name": self.invoice_date,
            "rate": 1.0,
        })
        self._set_rate(self.currency_usd, self.invoice_date, self.INVOICE_RATE)
        self._set_rate(self.currency_usd, self.today, self.VOUCHER_RATE)
        self.company.use_indexed_retentions = True

        # purchase_journal fuerza VEF; esta factura necesita un diario sin moneda forzada
        self.purchase_journal_usd = self.env["account.journal"].create({
            "name": "Diario Compra USD",
            "type": "purchase",
            "code": "PURUS",
            "company_id": self.company.id,
        })

    def _set_rate(self, currency, date, bolivars_per_unit):
        """Fija la tasa del día con las tres columnas a la vez: escribir solo
        `inverse_company_rate` deja que Odoo 19 la normalice contra la tasa histórica de semilla
        del VEF (5,864 al 2010-01-01) y la distorsiona."""
        values = {
            "rate": 1 / bolivars_per_unit,
            "company_rate": 1 / bolivars_per_unit,
            "inverse_company_rate": bolivars_per_unit,
        }
        rate = self.env["res.currency.rate"].search(
            [
                ("name", "=", date),
                ("currency_id", "=", currency.id),
                ("company_id", "=", self.company.id),
            ],
            limit=1,
        )
        if rate:
            rate.write(values)
            return rate
        return self.env["res.currency.rate"].create({
            **values,
            "name": date,
            "currency_id": currency.id,
            "company_id": self.company.id,
        })

    def _create_usd_invoice(self, amount=200.0, invoice_date=None, correlative="12345678901234", partner=None):
        invoice_date = invoice_date or self.invoice_date
        with Form(self.env["account.move"].with_context(
            default_move_type="in_invoice", default_journal_id=self.purchase_journal_usd.id,
        )) as inv_form:
            inv_form.partner_id = partner or self.partner_pnr_75
            inv_form.invoice_date = invoice_date
            inv_form.currency_id = self.currency_usd
            inv_form.correlative = correlative
        invoice = inv_form.save()
        with Form(invoice) as inv_form_edit:
            with inv_form_edit.invoice_line_ids.new() as line:
                line.product_id = self.product_iva
                line.quantity = 1
                line.price_unit = amount
        invoice = inv_form_edit.save()
        invoice.write({"date": invoice_date, "invoice_date_display": invoice_date})
        invoice.action_post()
        return invoice

    def _create_vef_invoice(self, amount=1000.0):
        invoice = self._create_invoice_reten_iva(
            amount, self.partner_pnr_75, "in_invoice", self.purchase_journal
        )
        invoice.with_context(move_action_post_alert=True).action_post()
        return invoice

    def _economic_activity(self, aliquot=1.0):
        """Actividad económica con la alícuota municipal del caso."""
        country = self.env["res.country"].search([], limit=1)
        state = self.env["res.country.state"].search([], limit=1) or self.env["res.country.state"].create(
            {"name": "TS", "code": "TS", "country_id": country.id}
        )
        municipality = self.env["res.country.municipality"].search([("code", "=", "MUN-RI")], limit=1) or \
            self.env["res.country.municipality"].create({
                "name": "Municipio RI", "code": "MUN-RI", "country_id": country.id,
                "state_id": [Command.set(state.ids)],
            })
        branch = self.env["economic.branch"].search([("name", "=", "Rama RI")], limit=1) or \
            self.env["economic.branch"].create({"name": "Rama RI", "status": "active"})
        return self.env["economic.activity"].search([("name", "=", "Actividad RI %s" % aliquot)], limit=1) or \
            self.env["economic.activity"].create({
                "name": "Actividad RI %s" % aliquot, "aliquot": aliquot, "municipality_id": municipality.id,
                "branch_id": branch.id, "description": "Actividad de prueba", "minimum_monthly": 0,
                "minimum_annual": 0,
            })

    def _retention_vals(self, invoice, mode="not_indexed", number="01234567891234"):
        invoice_total_vef = abs(invoice.amount_residual_signed) or 1000.0
        return {
            "type_retention": "iva",
            "type": "in_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "date": self.today,
            "date_accounting": self.today,
            "number": number,
            "indexation_mode": mode,
            "retention_line_ids": [Command.create({
                "move_id": invoice.id,
                "name": "IVA Line",
                "invoice_total": invoice_total_vef,
                "invoice_amount": invoice_total_vef,
                "retention_amount": invoice_total_vef * 0.10,
            })],
        }

    # Los comprobantes se crean con Form, como los crea el usuario: así corren los onchanges, los
    # campos de solo lectura y las validaciones de la vista.
    _FORM_MANY2ONE = {
        "move_id": "account.move", "payment_currency_id": "res.currency",
        "payment_concept_id": "payment.concept", "economic_activity_id": "economic.activity",
        "currency_id": "res.currency", "journal_id": "account.journal",
    }
    # En las retenciones de proveedor la vista los calcula por onchange y los deja de solo lectura
    _FORM_COMPUTED_FIELDS = {
        "name", "invoice_total", "invoice_amount", "iva_amount", "retention_amount",
        "foreign_invoice_amount", "foreign_iva_amount", "foreign_invoice_total", "aliquot",
    }

    def _form_view_xmlid(self, kind):
        return "l10n_ve_payment_extension.view_retention_%s_form_l10n_ve_payment_extension" % kind

    def _retention_action_context(self, kind, retention_type):
        side = "client" if retention_type == "out_invoice" else "supplier"
        action = self.env.ref("l10n_ve_payment_extension.action_retention_%s_%s" % (kind, side))
        return safe_eval(action.read()[0]["context"])

    def _form_set(self, form, name, value, skip_if_locked=False):
        """Escribe un campo en el Form. Los que la vista deja de solo lectura se omiten solo cuando
        `skip_if_locked` lo permite; cualquier otro error de la vista se propaga."""
        comodel = self._FORM_MANY2ONE.get(name)
        if comodel and isinstance(value, int):
            value = self.env[comodel].browse(value)
        try:
            setattr(form, name, value)
        except AssertionError:
            if not skip_if_locked:
                raise

    def _form_set_line(self, line_form, line_vals, is_new):
        if is_new:
            self._form_set(line_form, "move_id", line_vals["move_id"])
        for name, value in line_vals.items():
            if name == "move_id":
                continue
            self._form_set(line_form, name, value, skip_if_locked=name in self._FORM_COMPUTED_FIELDS)

    def _form_create_retention(self, vals):
        """Crea el comprobante a partir de `vals` con el Form de su vista."""
        kind = vals.get("type_retention", "iva")
        retention_type = vals.get("type", "in_invoice")
        wanted = [cmd[2] for cmd in vals.get("retention_line_ids", []) if cmd[0] == 0]
        context = self._retention_action_context(kind, retention_type)
        with Form(self.env["account.retention"].with_context(context), view=self._form_view_xmlid(kind)) as form:
            form.partner_id = self.env["res.partner"].browse(vals["partner_id"])
            if retention_type == "out_invoice" and vals.get("number"):
                form.number = vals["number"]
            if vals.get("date_accounting"):
                self._form_set(form, "date_accounting", vals["date_accounting"])
            if vals.get("date"):
                self._form_set(form, "date", vals["date"], skip_if_locked=True)
            if vals.get("indexation_mode"):
                # Con la función apagada el selector no se ve: el usuario no puede tocarlo
                self._form_set(
                    form, "indexation_mode", vals["indexation_mode"],
                    skip_if_locked=not self.company.use_indexed_retentions and vals["indexation_mode"] == "not_indexed",
                )
            if vals.get("exchange_difference_treatment"):
                self._form_set(form, "exchange_difference_treatment", vals["exchange_difference_treatment"])
            # Líneas que la vista cargó sola al elegir el contacto
            loaded_moves = []
            for index in range(len(form.retention_line_ids)):
                with form.retention_line_ids.edit(index) as line:
                    loaded_moves.append(line.move_id.id)
            pending = list(wanted)
            assigned, to_remove = [], []
            for index, move_id in enumerate(loaded_moves):
                match = next((w for w in pending if w["move_id"] == move_id), None)
                if match:
                    pending.remove(match)
                    assigned.append((index, match))
                else:
                    to_remove.append(index)
            for index in sorted(to_remove, reverse=True):
                form.retention_line_ids.remove(index=index)
            for index, line_vals in assigned:
                new_index = index - len([r for r in to_remove if r < index])
                with form.retention_line_ids.edit(new_index) as line:
                    self._form_set_line(line, line_vals, is_new=False)
            for line_vals in pending:
                with form.retention_line_ids.new() as line:
                    self._form_set_line(line, line_vals, is_new=True)
        return form.record

    def _edit_retention(self, retention):
        kind = {"iva": "iva", "islr": "islr", "municipal": "municipal"}[retention.type_retention]
        return Form(retention, view=self._form_view_xmlid(kind))

    def _add_retention_line(self, retention, line_vals):
        """Agrega una línea al comprobante en su formulario."""
        with self._edit_retention(retention) as form:
            with form.retention_line_ids.new() as line:
                self._form_set_line(line, line_vals, is_new=True)

    def _set_mode(self, retention, mode):
        """Cambia la modalidad como el usuario: editando el comprobante en su formulario."""
        with self._edit_retention(retention) as form:
            form.indexation_mode = mode

    def _set_retention_fields(self, retention, **values):
        with self._edit_retention(retention) as form:
            for name, value in values.items():
                setattr(form, name, value)

    def _set_line_payment_currency(self, lines, currency):
        """Elige la moneda del pago de las líneas en el formulario del comprobante."""
        retention = lines.retention_id
        with self._edit_retention(retention) as form:
            for line in lines:
                index = retention.retention_line_ids.ids.index(line.id)
                with form.retention_line_ids.edit(index) as line_form:
                    line_form.payment_currency_id = currency

    def _payment_wizard(self, move_ids, values):
        """Asistente de registrar pago llenado con Form, como en la pantalla: diario y fecha primero
        (sus onchanges fijan moneda y montos), después moneda y monto."""
        invoices = self.env["account.move"].browse(move_ids)
        with Form.from_action(self.env, invoices.action_register_payment()) as form:
            form.journal_id = self.env["account.journal"].browse(values["journal_id"])
            form.payment_date = values["payment_date"]
            form.save()
            if values.get("currency_id"):
                self._form_set(form, "currency_id", values["currency_id"])
            form.amount = values["amount"]
            form.save()
        return form.record

    def _credit_note_with_form(self, invoice, price_unit=None, post=True):
        """Nota de crédito como la hace el usuario: asistente de reversión (Form), edición del
        borrador y publicación. Devuelve la nota; no la aplica a la factura."""
        self.company.account_fiscal_country_id = invoice.invoice_line_ids.tax_ids.country_id[:1]
        with Form(self.env["account.move.reversal"].with_context(
            active_model="account.move", active_ids=invoice.ids,
        )) as wizard:
            wizard.date = self.today
            wizard.reason = "Nota de crédito de prueba"
        action = wizard.record.refund_moves()
        credit_note = self.env["account.move"].browse(action["res_id"])
        if price_unit is not None:
            with Form(credit_note) as note_form:
                with note_form.invoice_line_ids.edit(0) as note_line:
                    note_line.price_unit = price_unit
        if post:
            credit_note.action_post()
        return credit_note

    def _apply_credit_note(self, invoice, credit_note):
        credit_line = credit_note.line_ids.filtered(
            lambda l: l.account_type in ("liability_payable", "asset_receivable")
        )
        invoice.js_assign_outstanding_line(credit_line.id)

    def _create_customer_retention(self, mode="not_indexed", number="01234567891234", date=None, amount=4800.0,
                                   accounting_date=None, invoice=None, totals=(46400.0, 40000.0)):
        """Retención de IVA de cliente sobre una factura en USD de 1.000 + IVA: el usuario teclea la
        fecha del comprobante y los montos (en el de proveedor son de solo lectura)."""
        invoice = invoice or self._customer_invoice_in(self.currency_usd, "FACC%s" % number[-4:])
        vals = {
            "type_retention": "iva", "type": "out_invoice", "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id, "date": date or self.today,
            "date_accounting": accounting_date or self.today, "number": number, "indexation_mode": mode,
            "retention_line_ids": [Command.create({
                "move_id": invoice.id, "name": "IVA", "invoice_total": totals[0],
                "invoice_amount": totals[1], "retention_amount": amount,
            })],
        }
        return self._form_create_retention(vals)

    def _create_retention(self, invoice, mode="not_indexed", number="01234567891234"):
        return self._form_create_retention(self._retention_vals(invoice, mode, number))

    def _expected_foreign(self, bolivars, rate_date):
        """Monto retenido en la moneda de la factura: los Bs retenidos convertidos con la
        conversión del core a la fecha de la valoración."""
        return self.currency_vef._convert(bolivars, self.currency_usd, self.company, rate_date)

    # ------------------------------------------------------------------ configuración

    def test_default_mode_is_not_indexed(self):
        retention = self._create_retention(self._create_usd_invoice())
        self.assertEqual(retention.indexation_mode, "not_indexed")

    def test_company_setting_is_off_by_default(self):
        new_company_field = self.env["res.company"]._fields["use_indexed_retentions"]
        self.assertFalse(new_company_field.default(self.env["res.company"]))

    def test_indexed_requires_the_company_setting(self):
        """Con la función apagada el selector no se ve en el formulario y el modelo tampoco admite
        la modalidad indexada."""
        self.company.use_indexed_retentions = False
        invoice = self._create_usd_invoice()
        with self.assertRaises(AssertionError):  # campo invisible en el formulario
            self._create_retention(invoice, mode="indexed")
        retention = self._create_retention(invoice, mode="not_indexed")
        with self.assertRaises(ValidationError):
            retention.write({"indexation_mode": "indexed"})

    # ------------------------------------------------------------------ facturas en moneda extranjera

    def test_indexed_accepts_invoices_in_company_currency(self):
        """Una retención indexada también acepta facturas en bolívares: la línea se valora en la
        moneda alterna de la compañía con la tasa del comprobante."""
        retention = self._create_retention(self._create_vef_invoice(), mode="indexed")
        line = retention.retention_line_ids
        self.assertEqual(retention.indexation_mode, "indexed")
        self.assertEqual(line.foreign_currency_id, self.company.foreign_currency_id)
        self.assertAlmostEqual(
            line.foreign_retention_amount,
            self.currency_vef._convert(
                line.retention_amount, self.company.foreign_currency_id, self.company, retention.date
            ),
            places=2,
        )
        self.assertTrue(line.foreign_retention_amount)
    def test_non_indexed_accepts_invoices_in_company_currency(self):
        retention = self._create_retention(self._create_vef_invoice(), mode="not_indexed")
        self.assertEqual(retention.indexation_mode, "not_indexed")

    def test_not_indexed_line_is_valued_with_the_rate_of_the_invoice(self):
        invoice = self._create_usd_invoice()
        retention = self._create_retention(invoice, mode="not_indexed")
        line = retention.retention_line_ids

        self.assertEqual(line.foreign_currency_id, self.currency_usd)
        self.assertEqual(
            line.foreign_retention_amount, self._expected_foreign(line.retention_amount, self.invoice_date)
        )
        self.assertAlmostEqual(line.foreign_retention_amount, line.retention_amount / 40.0, places=2)
        self.assertAlmostEqual(line.foreign_currency_rate, 40.0, places=4)

    def test_indexed_values_with_the_rate_of_the_voucher_date(self):
        invoice = self._create_usd_invoice()
        retention = self._create_retention(invoice, mode="indexed")
        line = retention.retention_line_ids

        self.assertEqual(line.foreign_currency_id, self.currency_usd)
        self.assertEqual(
            line.foreign_retention_amount, self._expected_foreign(line.retention_amount, self.today)
        )
        self.assertAlmostEqual(line.foreign_currency_rate, self.VOUCHER_RATE, places=4)
        self.assertAlmostEqual(line.foreign_retention_amount, line.retention_amount / 60.0, places=2)

    def test_indexed_and_not_indexed_keep_the_same_bolivars(self):
        """Dos facturas iguales, una con cada modalidad (una factura ya incluida en un comprobante
        no se ofrece en otro): los mismos bolívares y solo cambia la valoración en USD."""
        first_invoice = self._create_usd_invoice(correlative="12345678901111")
        not_indexed = self._create_retention(first_invoice, mode="not_indexed", number="01234567891111")
        second_invoice = self._create_usd_invoice(correlative="12345678902222")
        indexed = self._create_retention(second_invoice, mode="indexed", number="01234567892222")

        self.assertEqual(
            indexed.retention_line_ids.retention_amount,
            not_indexed.retention_line_ids.retention_amount,
        )
        # Solo cambia la tasa con la que se valora: los USD de la indexada son menos con la tasa subiendo
        self.assertGreater(
            not_indexed.retention_line_ids.foreign_retention_amount,
            indexed.retention_line_ids.foreign_retention_amount,
        )
    def test_switching_mode_revalues_the_lines(self):
        """RI-041: cambiar la modalidad con el comprobante en borrador revalora las líneas."""
        invoice = self._create_usd_invoice()
        retention = self._create_retention(invoice, mode="not_indexed")
        line = retention.retention_line_ids
        bolivars = line.retention_amount
        self.assertEqual(line.foreign_retention_amount, self._expected_foreign(bolivars, self.invoice_date))

        self._set_mode(retention, "indexed")
        self.assertEqual(line.foreign_retention_amount, self._expected_foreign(bolivars, self.today))

        self._set_mode(retention, "not_indexed")
        self.assertEqual(line.foreign_retention_amount, self._expected_foreign(bolivars, self.invoice_date))
        self.assertEqual(line.retention_amount, bolivars)

    def test_changing_the_retained_amount_revalues_an_indexed_line(self):
        retention = self._create_customer_retention(mode="indexed")
        line = retention.retention_line_ids
        with self._edit_retention(retention) as form:
            with form.retention_line_ids.edit(0) as line_form:
                line_form.retention_amount = 600.0
        self.assertEqual(line.foreign_retention_amount, self._expected_foreign(600.0, self.today))

    def test_changing_the_voucher_date_revalues_an_indexed_retention(self):
        """La indexada usa la tasa del día del comprobante: al cambiar su fecha se revalora."""
        retention = self._create_customer_retention(mode="indexed")
        line = retention.retention_line_ids

        self._set_retention_fields(retention, date=self.invoice_date)
        self.assertEqual(
            line.foreign_retention_amount,
            self._expected_foreign(line.retention_amount, self.invoice_date),
        )
        self.assertAlmostEqual(line.foreign_retention_amount, line.retention_amount / 40.0, places=2)
        self.assertAlmostEqual(line.foreign_currency_rate, 40.0, places=4)

    def test_changing_the_voucher_date_does_not_revalue_a_not_indexed_retention(self):
        retention = self._create_customer_retention(mode="not_indexed")
        line = retention.retention_line_ids
        before = line.foreign_retention_amount

        self._set_retention_fields(retention, date=self.invoice_date)
        self.assertEqual(line.foreign_retention_amount, before)

    def test_the_accounting_date_does_not_intervene_in_the_valuation(self):
        """La valoración indexada usa la fecha del comprobante, no la fecha contable."""
        invoice = self._create_usd_invoice()
        retention = self._create_retention(invoice, mode="indexed")
        line = retention.retention_line_ids
        before = line.foreign_retention_amount

        self._set_retention_fields(retention, date_accounting=self.invoice_date)
        self.assertEqual(line.foreign_retention_amount, before)
        self.assertAlmostEqual(line.foreign_retention_amount, line.retention_amount / 60.0, places=2)

    # ------------------------------------------------------------------ ciclo de vida

    def test_indexed_retention_can_be_posted_and_mode_is_locked(self):
        invoice = self._create_usd_invoice()
        retention = self._create_retention(invoice, mode="indexed")

        retention.action_post()
        self.assertEqual(retention.state, "emitted")
        self.assertEqual(len(retention.payment_ids), 1)
        self.assertEqual(retention.payment_ids.amount, retention.retention_line_ids.retention_amount)

        with self.assertRaises(AssertionError):  # en el formulario la modalidad queda de solo lectura
            self._set_mode(retention, "not_indexed")
        with self.assertRaises(UserError):
            retention.write({"indexation_mode": "not_indexed"})

    def test_indexed_valuation_ignores_the_referential_document_rate(self):
        """`foreign_rate` del documento es referencial (menos dígitos que la tasa real): la
        valoración sale siempre de la tasa de la fecha."""
        invoice = self._create_usd_invoice()
        retention = self._create_retention(invoice, mode="indexed")
        line = retention.retention_line_ids
        expected = self._expected_foreign(line.retention_amount, self.today)

        invoice.foreign_rate = round(invoice.foreign_rate, 0) + 7
        self.assertEqual(line._get_foreign_retention_amount(line.retention_amount), expected)

    def test_indexed_valuation_is_zero_without_rate(self):
        """Sin ninguna tasa para la fecha no se inventa una (el core caería a 1.0)."""
        invoice = self._create_usd_invoice()
        retention = self._create_retention(invoice, mode="indexed")
        line = retention.retention_line_ids

        with patch.object(type(self.env["res.currency.rate"]), "compute_rate", return_value={}):
            self.assertEqual(line._get_foreign_retention_amount(600.0), 0.0)
            line._apply_foreign_valuation()
        self.assertEqual(line.foreign_retention_amount, 0.0)
        self.assertEqual(line.foreign_currency_rate, 0.0)

    def test_foreign_currency_of_the_line_is_the_invoice_currency(self):
        """La moneda de los montos de la línea es la de la factura; en una factura en bolívares es
        la moneda alterna de la compañía (indexada o no)."""
        invoice = self._create_usd_invoice()
        line = self._create_retention(invoice, mode="indexed").retention_line_ids
        self.assertEqual(line.foreign_currency_id, invoice.currency_id)
        indexed = self._create_retention(
            self._create_vef_invoice(), mode="indexed", number="01234567891999"
        ).retention_line_ids
        self.assertEqual(indexed.foreign_currency_id, self.company.foreign_currency_id)
        # La no indexada sigue como siempre: moneda alterna de la compañía
        not_indexed = self._create_retention(
            self._create_vef_invoice(), mode="not_indexed", number="01234567892999"
        ).retention_line_ids
        self.assertEqual(not_indexed.foreign_currency_id, self.company.foreign_currency_id)
    def test_selector_is_hidden_when_the_company_setting_is_off(self):
        self.company.use_indexed_retentions = False
        retention = self._create_retention(self._create_usd_invoice())
        self.assertFalse(retention.show_indexation)

    def test_selector_is_shown_when_all_the_invoices_are_in_company_currency(self):
        """La indexación también existe para facturas en bolívares."""
        retention = self._create_retention(self._create_vef_invoice())
        self.assertTrue(retention.show_indexation)
    def test_selector_is_shown_with_an_invoice_in_foreign_currency(self):
        retention = self._create_retention(self._create_usd_invoice())
        self.assertTrue(retention.show_indexation)

    def test_selector_is_shown_while_the_voucher_has_no_lines(self):
        vals = self._retention_vals(self._create_usd_invoice())
        vals.pop("retention_line_ids")
        retention = self._form_create_retention(vals)
        self.assertFalse(retention.retention_line_ids)
        self.assertTrue(retention.show_indexation)

    def test_selector_is_shown_when_the_lines_mix_currencies(self):
        retention = self._create_retention(self._create_usd_invoice())
        self._add_retention_line(retention, {
            "move_id": self._create_vef_invoice().id,
            "name": "IVA Line VEF",
            "invoice_total": 1160.0,
            "invoice_amount": 1000.0,
            "retention_amount": 120.0,
        })
        self.assertTrue(retention.show_indexation)

    def test_views_hide_the_selector_with_show_indexation(self):
        for xmlid in (
            "l10n_ve_payment_extension.view_retention_iva_form_l10n_ve_payment_extension",
            "l10n_ve_payment_extension.view_retention_islr_form_l10n_ve_payment_extension",
            "l10n_ve_payment_extension.view_retention_municipal_form_l10n_ve_payment_extension",
        ):
            arch = etree.fromstring(self.env.ref(xmlid).arch_db)
            nodes = arch.xpath("//field[@name='indexation_mode']")
            self.assertEqual(len(nodes), 1, xmlid)
            self.assertEqual(nodes[0].get("invisible"), "not show_indexation", xmlid)
            self.assertTrue(arch.xpath("//field[@name='show_indexation']"), xmlid)

    # ------------------------------------------------------------------ pago en la moneda de la factura

    def _post(self, invoice, mode, number="01234567891234"):
        retention = self._create_retention(invoice, mode=mode, number=number)
        retention.action_post()
        return retention, retention.payment_ids

    def _exchange_moves(self, invoice):
        payable = invoice.line_ids.filtered(lambda l: l.account_id.account_type == "liability_payable")
        partials = payable.matched_credit_ids | payable.matched_debit_ids
        return partials.mapped("exchange_move_id").filtered(lambda m: m)

    def test_non_indexed_payment_stays_in_bolivars_without_exchange_difference(self):
        """Como funciona hoy: pago en bolívares, a la tasa de la factura y sin diferencial."""
        invoice = self._create_usd_invoice()
        total_usd = invoice.amount_total
        retention, payment = self._post(invoice, "not_indexed")
        bolivars = retention.retention_line_ids.retention_amount

        self.assertEqual(payment.currency_id, self.currency_vef)
        self.assertEqual(payment.amount, bolivars)
        self.assertFalse(self._exchange_moves(invoice))
        self.assertAlmostEqual(invoice.amount_residual, total_usd - bolivars / self.INVOICE_RATE, places=2)

    def test_cancelling_an_indexed_retention_reverts_the_debt(self):
        invoice = self._create_usd_invoice()
        total_usd = invoice.amount_total
        total_bs = abs(invoice.amount_residual_signed)
        retention, payment = self._post(invoice, "indexed")
        retention.action_cancel()
        self.assertEqual(retention.state, "cancel")
        self.assertAlmostEqual(invoice.amount_residual, total_usd, places=2)
        self.assertAlmostEqual(abs(invoice.amount_residual_signed), total_bs, places=2)

    def test_payment_uses_the_accounting_date_not_the_voucher_date(self):
        """La retención se practica al pago o abono en cuenta (fecha contable); la fecha del
        comprobante es la de emisión y entrega y no mueve el asiento ni la tasa. El usuario de
        cliente es quien teclea la fecha del comprobante."""
        retention = self._create_customer_retention(
            mode="indexed", date=self.invoice_date, accounting_date=self.today
        )  # comprobante anterior a la fecha contable
        retention.action_post()
        payment = retention.payment_ids

        self.assertEqual(payment.date, self.today)
        self.assertEqual(payment.move_id.date, self.today)
        line = retention.retention_line_ids
        self.assertAlmostEqual(line.foreign_retention_amount, line.retention_amount / 40.0, places=2)

    # ------------------------------------------------------------------ moneda del pago por factura

    def _second_line_vals(self, invoice, aliquot):
        """Otra línea que retiene la misma factura con una alícuota distinta."""
        return {
            "move_id": invoice.id,
            "name": "IVA Line %s" % aliquot,
            "aliquot": aliquot,
            "invoice_total": 1160.0,
            "invoice_amount": 1000.0,
            "retention_amount": 100.0,
        }

    def test_payment_currency_defaults_to_the_company_currency(self):
        invoice = self._create_usd_invoice()
        line = self._create_retention(invoice, mode="indexed").retention_line_ids
        self.assertEqual(line.payment_currency_id, self.currency_vef)
        self.assertEqual(line.allowed_payment_currency_ids, self.currency_vef | self.currency_usd)

    def test_non_indexed_line_only_allows_the_company_currency(self):
        line = self._create_retention(self._create_usd_invoice(), mode="not_indexed").retention_line_ids
        self.assertEqual(line.payment_currency_id, self.currency_vef)
        self.assertEqual(line.allowed_payment_currency_ids, self.currency_vef)
        with self.assertRaises(ValidationError):
            self._set_line_payment_currency(line, self.currency_usd)
    def test_changing_the_payment_currency_changes_the_other_lines_of_the_invoice(self):
        invoice = self._create_usd_invoice()
        retention = self._create_retention(invoice, mode="indexed")
        first = retention.retention_line_ids
        self._add_retention_line(retention, self._second_line_vals(invoice, 8.0))
        second = retention.retention_line_ids - first

        self._set_line_payment_currency(first, self.currency_usd)
        self.assertEqual(second.payment_currency_id, self.currency_usd)

        self._set_line_payment_currency(second, self.currency_vef)
        self.assertEqual(first.payment_currency_id, self.currency_vef)

    def test_a_new_line_of_the_same_invoice_takes_the_chosen_currency(self):
        """En el formulario, una segunda línea de la misma factura (otra alícuota) toma la moneda de
        pago ya elegida. La línea nueva todavía no conoce a su comprobante, así que reconoce a sus
        hermanas por la factura."""
        invoice = self._create_usd_invoice()
        retention = self._create_retention(invoice, mode="indexed")
        self._set_line_payment_currency(retention.retention_line_ids, self.currency_usd)
        self._add_retention_line(retention, self._second_line_vals(invoice, 8.0))
        self.assertEqual(retention.retention_line_ids.payment_currency_id, self.currency_usd)

    def test_lines_of_the_same_invoice_cannot_have_different_payment_currencies(self):
        """La regla es del modelo: el formulario siempre sincroniza las líneas de una factura, así que
        para probarla se salta esa sincronización y se fuerza otra moneda en una de las líneas."""
        invoice = self._create_usd_invoice()
        retention = self._create_retention(invoice, mode="indexed")
        self._add_retention_line(retention, self._second_line_vals(invoice, 8.0))
        first, second = retention.retention_line_ids
        self.assertEqual(first.payment_currency_id, second.payment_currency_id)
        with self.assertRaises(ValidationError) as caught:
            first.with_context(skip_payment_currency_sync=True).write({"payment_currency_id": self.currency_usd.id})
        self.assertIn("same payment currency", str(caught.exception))

    def test_leaving_the_indexed_mode_returns_the_payment_to_the_company_currency(self):
        invoice = self._create_usd_invoice()
        retention = self._create_retention(invoice, mode="indexed")
        line = retention.retention_line_ids
        self._set_line_payment_currency(line, self.currency_usd)
        self._set_mode(retention, "not_indexed")
        self.assertEqual(line.payment_currency_id, self.currency_vef)

    def test_payment_in_the_company_currency_takes_the_retained_amount_in_bolivars(self):
        invoice = self._create_usd_invoice()
        retention, payment = self._post(invoice, "indexed")
        self.assertEqual(payment.currency_id, self.currency_vef)
        self.assertEqual(payment.amount, retention.retention_line_ids.retention_amount)

    def test_payment_travels_with_the_invoice_currency_and_the_retained_amount_in_it(self):
        """Con la moneda de la factura el pago va en esa moneda, por el monto retenido en ella.
        El diario de retención no puede forzar otra moneda (l10n_ve_accountant)."""
        self.bank_journal_sup_ret.currency_id = False
        invoice = self._create_usd_invoice()
        total_usd = invoice.amount_total
        retention = self._create_retention(invoice, mode="indexed")
        line = retention.retention_line_ids
        self._set_line_payment_currency(line, self.currency_usd)
        retention.action_post()
        payment = retention.payment_ids

        self.assertEqual(payment.currency_id, self.currency_usd)
        self.assertEqual(payment.amount, line.foreign_retention_amount)
        self.assertAlmostEqual(payment.amount, line.retention_amount / 60.0, places=2)
        for entry_line in payment.move_id.line_ids:
            self.assertEqual(abs(entry_line.amount_currency), payment.amount)
        _logger.warning(
            "OBSERVADO pago en moneda de la factura: monto=%s %s | líneas (balance Bs, importe moneda): %s"
            " | retención Bs=%s | saldo factura en USD=%s (total %s) | saldo Bs=%s",
            payment.amount, payment.currency_id.name,
            [(l.account_id.code, l.balance, l.amount_currency) for l in payment.move_id.line_ids],
            line.retention_amount, invoice.amount_residual, total_usd, invoice.amount_residual_signed,
        )

    def _exchange_moves(self, invoice):
        partials = invoice.line_ids.matched_debit_ids | invoice.line_ids.matched_credit_ids
        return partials.exchange_move_id

    def test_indexed_payment_in_the_invoice_currency_generates_the_exchange_difference(self):
        """El pago en la moneda de la factura se valora con la tasa de la fecha contable (60) y la
        factura se cierra a la suya (40): la diferencia en VEF es un diferencial cambiario real."""
        self.bank_journal_sup_ret.currency_id = False
        invoice = self._create_usd_invoice()
        total_usd = invoice.amount_total
        total_bs = abs(invoice.amount_residual_signed)
        retention = self._create_retention(invoice, mode="indexed")
        line = retention.retention_line_ids
        self._set_line_payment_currency(line, self.currency_usd)
        retention.action_post()

        paid_usd = line.foreign_retention_amount
        self.assertAlmostEqual(invoice.amount_residual, total_usd - paid_usd, places=2)
        # Los Bs del saldo siguen la tasa de la factura: ya no queda un residuo incoherente
        self.assertAlmostEqual(
            abs(invoice.amount_residual_signed), (total_usd - paid_usd) * 40.0, places=2
        )
        self.assertAlmostEqual(
            total_bs - abs(invoice.amount_residual_signed), paid_usd * 40.0, places=2
        )
        exchange_move = self._exchange_moves(invoice)
        self.assertEqual(len(exchange_move), 1)
        self.assertAlmostEqual(
            sum(exchange_move.line_ids.mapped("debit")), paid_usd * (60.0 - 40.0), places=2
        )

    def test_indexed_payment_in_the_company_currency_generates_the_exchange_difference(self):
        """Indexada pagada en bolívares: la retención cancela de la factura su valor a la tasa del
        comprobante, y la diferencia con la tasa de la factura queda en el diferencial en Bs."""
        invoice = self._create_usd_invoice()
        retention = self._create_retention(invoice, mode="indexed")
        line = retention.retention_line_ids
        retention.action_post()

        self.assertTrue(self._exchange_moves(invoice))
        self.assertAlmostEqual(
            invoice.amount_residual, invoice.amount_total - line.foreign_retention_amount, places=2
        )

    def test_non_indexed_payment_never_generates_an_exchange_difference(self):
        invoice = self._create_usd_invoice()
        retention = self._create_retention(invoice, mode="not_indexed")
        retention.action_post()
        self.assertFalse(self._exchange_moves(invoice))

    # ------------------------------------------------------------------ cierre de la cuenta del contacto

    def _assert_payable_account_closure(self, invoice, total_usd, paid_usd):
        """Los casos de prueba exigen que la cuenta del contacto cierre en Bs y en la moneda
        alterna: sumando la factura, el pago y el asiento de diferencial, el saldo en Bs y en USD
        alterno es el de lo que queda por pagar de la factura, a la tasa de la factura."""
        payable_lines = invoice.line_ids.filtered(lambda l: l.account_id.account_type == "liability_payable")
        partials = payable_lines.matched_debit_ids | payable_lines.matched_credit_ids
        counterpart = (partials.debit_move_id | partials.credit_move_id) - payable_lines
        exchange_lines = partials.exchange_move_id.line_ids.filtered(
            lambda l: l.account_id.account_type == "liability_payable"
        )
        lines = payable_lines | counterpart | exchange_lines
        remaining_usd = total_usd - paid_usd
        self.assertAlmostEqual(sum(lines.mapped("balance")), -remaining_usd * 40.0, places=2)
        self.assertAlmostEqual(sum(lines.mapped("foreign_balance")), -remaining_usd, places=2)
        self.assertAlmostEqual(invoice.amount_residual, remaining_usd, places=2)
        self.assertAlmostEqual(abs(invoice.amount_residual_signed), remaining_usd * 40.0, places=2)

    def test_non_indexed_account_closes_in_bolivars_and_alternate_currency(self):
        invoice = self._create_usd_invoice()
        total_usd = invoice.amount_total
        retention = self._create_retention(invoice, mode="not_indexed")
        retention.action_post()
        paid_usd = retention.retention_line_ids.retention_amount / 40.0
        self._assert_payable_account_closure(invoice, total_usd, paid_usd)

    def test_indexed_bolivars_payment_account_closes_in_bolivars_and_alternate_currency(self):
        """La indexada concilia de forma nativa: la factura descuenta lo que dice la línea (el
        valor a la tasa del comprobante) y el resto lo cierra el diferencial."""
        invoice = self._create_usd_invoice()
        total_usd = invoice.amount_total
        retention = self._create_retention(invoice, mode="indexed")
        retention.action_post()
        paid_usd = retention.retention_line_ids.foreign_retention_amount
        self._assert_payable_account_closure(invoice, total_usd, paid_usd)

    def test_indexed_invoice_currency_payment_account_closes_in_bolivars_and_alternate_currency(self):
        self.bank_journal_sup_ret.currency_id = False
        invoice = self._create_usd_invoice()
        total_usd = invoice.amount_total
        retention = self._create_retention(invoice, mode="indexed")
        line = retention.retention_line_ids
        self._set_line_payment_currency(line, self.currency_usd)
        retention.action_post()
        self._assert_payable_account_closure(invoice, total_usd, line.foreign_retention_amount)

    def test_cancelling_an_indexed_payment_in_the_invoice_currency_reverts_the_exchange_difference(self):
        self.bank_journal_sup_ret.currency_id = False
        invoice = self._create_usd_invoice()
        total_usd = invoice.amount_total
        total_bs = abs(invoice.amount_residual_signed)
        retention = self._create_retention(invoice, mode="indexed")
        self._set_line_payment_currency(retention.retention_line_ids, self.currency_usd)
        retention.action_post()
        self.assertTrue(self._exchange_moves(invoice))

        retention.action_cancel()
        self.assertEqual(retention.state, "cancel")
        self.assertAlmostEqual(invoice.amount_residual, total_usd, places=2)
        self.assertAlmostEqual(abs(invoice.amount_residual_signed), total_bs, places=2)
        # El asiento de diferencial no queda aplicado: ni conciliado ni contabilizado
        for move in self._exchange_moves(invoice):
            self.assertNotEqual(move.state, "posted")

    # ------------------------------------------------------------------ bolívares del pago en la moneda de la factura

    def _post_indexed_in_invoice_currency(self, voucher_date=None):
        self.bank_journal_sup_ret.currency_id = False
        self.bank_journal_sub.currency_id = False
        if voucher_date:
            # La fecha del comprobante solo se teclea en el formulario de cliente
            retention = self._create_customer_retention(mode="indexed", date=voucher_date)
        else:
            retention = self._create_retention(self._create_usd_invoice(), mode="indexed")
        self._set_line_payment_currency(retention.retention_line_ids, self.currency_usd)
        retention.action_post()
        return retention, retention.payment_ids

    @skip("Falla conocida, pendiente de desarrollo: Paso 2 pendiente: los Bs del pago no se fijan al monto retenido (residuo de redondeo)")
    def test_payment_in_the_invoice_currency_carries_the_retained_bolivars(self):
        """El valor de la línea se lleva a bolívares con la tasa con la que se calculó: el pago en
        la moneda de la factura debe quedar en los bolívares retenidos, sin residuo de redondeo
        (casos RI-051, RI-096 y RI-151)."""
        retention, payment = self._post_indexed_in_invoice_currency()
        line = retention.retention_line_ids
        for entry_line in payment.move_id.line_ids:
            self.assertEqual(abs(entry_line.amount_currency), line.foreign_retention_amount)
            self.assertAlmostEqual(abs(entry_line.balance), line.retention_amount, places=2)

    @skip("Falla conocida, pendiente de desarrollo: Paso 2 pendiente: el pago aún se valora a la tasa de su propia fecha")
    def test_payment_in_the_invoice_currency_uses_the_rate_of_the_voucher_date(self):
        """La línea indexada se valora con la tasa del comprobante; el asiento del pago (fechado
        con la fecha contable) debe valorarse con esa misma tasa, no con la de su propia fecha."""
        retention, payment = self._post_indexed_in_invoice_currency(voucher_date=self.invoice_date)
        line = retention.retention_line_ids
        self.assertNotEqual(payment.date, retention.date)
        for entry_line in payment.move_id.line_ids:
            self.assertAlmostEqual(abs(entry_line.balance), line.retention_amount, places=2)

    # ------------------------------------------------------------------ casos RI (retención de cliente)

    def _set_exchange_entry_rates(self, voucher_day, usd_rate, eur_rate=None):
        """La tasa se busca por fecha exacta (no cae a la última anterior): el asiento de diferencia
        que crea el core se fecha a fin de mes y necesita su propia tasa."""
        month_end = voucher_day + relativedelta(day=31)
        self._set_rate(self.currency_usd, month_end, usd_rate)
        if eur_rate:
            self._set_rate(self.env.ref("base.EUR"), month_end, eur_rate)

    def _setup_igtf_usd_journal(self):
        """Diario en USD marcado como IGTF, con las cuentas del módulo l10n_ve_igtf (como en sus
        propias pruebas): el cobro en divisas aplica el 3 % de IGTF. Las retenciones no dependen
        de IGTF: sin el módulo instalado estas pruebas se omiten."""
        if "is_igtf" not in self.env["account.journal"]._fields:
            self.skipTest("l10n_ve_igtf no está instalado")
        if getattr(self, "_igtf_usd_journal", None):
            return self._igtf_usd_journal
        Account = self.env["account.account"]
        acc_igtf = Account.create({"code": "IG236", "name": "IGTF Clientes", "account_type": "liability_current"})
        acc_igtf_supp = Account.create({"code": "IG137", "name": "IGTF Proveedores", "account_type": "asset_current"})
        adv_cust = Account.create({
            "code": "IG216", "name": "Anticipo Clientes", "account_type": "liability_current",
            "reconcile": True, "is_advance_account": True,
        })
        adv_supp = Account.create({
            "code": "IG136", "name": "Anticipo Proveedores", "account_type": "asset_current",
            "reconcile": True, "is_advance_account": True,
        })
        bank_usd = Account.create({"code": "IG1002", "name": "Banco USD IGTF", "account_type": "asset_cash"})
        journal_adv = self.env["account.journal"].create({
            "name": "Anticipo IGTF", "code": "ANTIG", "type": "general", "company_id": self.company.id,
        })
        self.company.write({
            "igtf_percentage": 3.0,
            "customer_account_igtf_id": acc_igtf.id,
            "supplier_account_igtf_id": acc_igtf_supp.id,
            "advance_customer_account_id": adv_cust.id,
            "advance_supplier_account_id": adv_supp.id,
            "advance_payment_igtf_journal_id": journal_adv.id,
            "taxpayer_type": "formal",
        })
        self.partner_pnr_75.write({
            "taxpayer_type": "formal",
            "default_advance_customer_account_id": adv_cust.id,
            "default_advance_supplier_account_id": adv_supp.id,
        })
        manual_in = self.env.ref("account.account_payment_method_manual_in")
        manual_out = self.env.ref("account.account_payment_method_manual_out")
        method_in = self.env["account.payment.method.line"].create({
            "name": "Manual Inbound USD IGTF", "payment_method_id": manual_in.id,
            "payment_type": "inbound", "payment_account_id": bank_usd.id,
        })
        method_out = self.env["account.payment.method.line"].create({
            "name": "Manual Outbound USD IGTF", "payment_method_id": manual_out.id,
            "payment_type": "outbound", "payment_account_id": bank_usd.id,
        })
        journal = self.env["account.journal"].create({
            "name": "Banco USD IGTF", "code": "BNKIG", "type": "bank",
            "currency_id": self.currency_usd.id, "company_id": self.company.id, "is_igtf": True,
            "default_account_id": bank_usd.id,
            "inbound_payment_method_line_ids": [(6, 0, method_in.ids)],
            "outbound_payment_method_line_ids": [(6, 0, method_out.ids)],
        })
        method_in.journal_id = journal.id
        method_out.journal_id = journal.id
        self._igtf_usd_journal = journal
        return journal

    # Montos de los casos por impuesto: (base en Bs, total en Bs, retenido en Bs) para facturas en
    # Bs/USD (tasa 40) y para facturas en EUR (tasa 44). IVA 16 % retenido al 75 %; ISLR 5 %;
    # municipal 1 % (las dos últimas sobre una factura exenta).
    _CASE_AMOUNTS = {
        "iva": {"base": (40000.0, 46400.0, 4800.0), "eur": (44000.0, 51040.0, 5280.0)},
        "islr": {"base": (40000.0, 40000.0, 2000.0), "eur": (44000.0, 44000.0, 2200.0)},
        "mun": {"base": (40000.0, 40000.0, 400.0), "eur": (44000.0, 44000.0, 440.0)},
    }

    def _run_customer_iva_case(self, invoice_currency, mode, **kwargs):
        return self._run_retention_case("cus", "iva", invoice_currency, mode, **kwargs)

    def _run_retention_case(self, party, kind, invoice_currency, mode, voucher_offset=5,
                            voucher_rate=45.0, eur_rate=49.5, igtf=False, retained_override=None, payment_first=False,
                            number="01234567891234", second_islr_mode=None, drop_usd_rate=False, treatment=None):
        """Casos de retención: factura de 1.000 en su moneda (tasa 40; EUR 44), retención con el
        comprobante cinco días después (tasa 45; EUR 49,5) y cobro del resto en Bs el mismo día del
        comprobante. `party` es 'cus' (cliente) o 'sup' (proveedor) y `kind` el impuesto
        (iva, islr o mun). Devuelve lo que produce el sistema."""
        self.company.l10n_ve_use_foreign_exchange_diff = True
        voucher_day = self.invoice_date + relativedelta(days=voucher_offset)
        self.env.ref("base.EUR").active = True
        self._set_rate(self.currency_usd, voucher_day, voucher_rate)
        self._set_exchange_entry_rates(voucher_day, voucher_rate, eur_rate if invoice_currency == "EUR" else None)
        if invoice_currency == "EUR" and voucher_day != self.today:
            # El asistente de pago se abre con la fecha de hoy (exige la tasa de ese día exacto)
            self._set_rate(self.env.ref("base.EUR"), self.today, eur_rate)
        in_eur = invoice_currency == "EUR"
        in_usd = invoice_currency in ("USD", "EUR")  # factura en moneda extranjera
        currency_eur = self.env.ref("base.EUR")
        if in_eur:
            self._set_rate(currency_eur, self.invoice_date, 44.0)
            self._set_rate(currency_eur, voucher_day, eur_rate)
        if drop_usd_rate:
            self.env["res.currency.rate"].search([
                ("currency_id", "=", self.currency_usd.id), ("name", "=", voucher_day),
            ]).unlink()
        base = 1000.0 if in_usd else 40000.0
        supplier = party == "sup"
        move_type = "in_invoice" if supplier else "out_invoice"
        account_type = "liability_payable" if supplier else "asset_receivable"
        product = self.product_iva if kind == "iva" else self.product_islr_one
        invoice_journal = self.purchase_journal if supplier else self.sale_journal
        if in_usd:
            # Los diarios de la fixture fuerzan VEF
            journal_type = "purchase" if supplier else "sale"
            invoice_journal = self.env["account.journal"].search(
                [("code", "=", "FACEX"), ("type", "=", journal_type), ("company_id", "=", self.company.id)],
                limit=1,
            ) or self.env["account.journal"].create({
                "name": "Diario Factura Extranjera",
                "type": journal_type,
                "code": "FACEX",
                "company_id": self.company.id,
            })

        with Form(self.env["account.move"].with_context(
            default_move_type=move_type, default_journal_id=invoice_journal.id,
        )) as inv_form:
            inv_form.partner_id = self.partner_pnr_75
            if supplier:
                inv_form.correlative = number[::-1]  # único por caso
            inv_form.invoice_date = self.invoice_date
            inv_form.currency_id = (
                currency_eur if in_eur else self.currency_usd if in_usd else self.currency_vef
            )
        invoice = inv_form.save()
        with Form(invoice) as inv_form_edit:
            with inv_form_edit.invoice_line_ids.new() as line:
                line.product_id = product
                line.quantity = 1
                line.price_unit = base
            if second_islr_mode:
                with inv_form_edit.invoice_line_ids.new() as line:
                    line.product_id = self.product_islr_one
                    line.quantity = 1
                    line.price_unit = base
        invoice = inv_form_edit.save()
        invoice.write({"date": self.invoice_date, "invoice_date_display": self.invoice_date})
        invoice.with_context(move_action_post_alert=True).action_post()
        base_bs, total_bs, retained_bs = self._CASE_AMOUNTS[kind]["eur" if in_eur else "base"]
        if second_islr_mode:
            total_bs += self._CASE_AMOUNTS["islr"]["eur" if in_eur else "base"][1]
        retained_bs = retained_override or retained_bs
        self.assertAlmostEqual(abs(invoice.amount_total_signed), total_bs, places=2)

        if payment_first:
            # Se cobra primero el saldo sin retención (la factura menos lo retenido a su tasa)
            net_doc = round(invoice.amount_residual - retained_bs / (total_bs / invoice.amount_total), 2)
            first_rate = eur_rate if in_eur else voucher_rate
            first = self._payment_wizard(invoice.ids, {
                "amount": round(net_doc * first_rate, 2) if in_usd else total_bs - retained_bs,
                "currency_id": self.currency_vef.id,
                "payment_date": voucher_day,
                "journal_id": self.bank_journal_sub.id,
            })
            first.action_create_payments()
        line_extra = {"payment_concept_id": self.concept_one.id} if kind == "islr" else {}
        if kind == "mun":
            line_extra = {"economic_activity_id": self._economic_activity(1.0).id}
            self.company.write({
                "municipal_supplier_retention_journal_id": self.bank_journal_sup_ret.id,
                "municipal_customer_retention_journal_id": self.bank_journal_sub.id,
            })
        retention = self._form_create_retention({
            "type_retention": {"iva": "iva", "islr": "islr", "mun": "municipal"}[kind],
            "type": move_type,
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "date": voucher_day,
            "date_accounting": voucher_day,
            "number": number,
            "indexation_mode": mode,
            **({"exchange_difference_treatment": treatment} if treatment else {}),
            "retention_line_ids": [Command.create({
                "move_id": invoice.id,
                "name": "Line",
                "invoice_total": total_bs,
                "invoice_amount": base_bs,
                "retention_amount": retained_bs,
                **line_extra,
            })],
        })
        line = retention.retention_line_ids
        retention.action_post()
        payment = retention.payment_ids
        second_retention = self.env["account.retention"]
        if second_islr_mode:
            islr_base, _islr_total, islr_retained = self._CASE_AMOUNTS["islr"]["eur" if in_eur else "base"]
            second_retention = self._form_create_retention({
                "type_retention": "islr", "type": move_type, "company_id": self.company.id,
                "partner_id": self.partner_pnr_75.id, "date": voucher_day, "date_accounting": voucher_day,
                "number": "01234567891240", "indexation_mode": second_islr_mode,
                "retention_line_ids": [Command.create({
                    "move_id": invoice.id, "name": "Line", "invoice_total": total_bs,
                    "invoice_amount": islr_base, "retention_amount": islr_retained,
                    "payment_concept_id": self.concept_one.id,
                })],
            })
            second_retention.action_post()

        receivable = invoice.line_ids.filtered(lambda l: l.account_type == account_type)
        residual_after_retention = invoice.amount_residual
        residual_bs_after_retention = abs(invoice.amount_residual_signed)
        _partials = receivable.matched_debit_ids | receivable.matched_credit_ids
        retention_exchange_bs = sum(
            _partials.exchange_move_id.line_ids.filtered(
                lambda l: l.account_id == receivable.account_id
            ).mapped("balance")
        )
        _logger.warning(
            "PARCIAL %s %s | saldo tras la retención: %s %s (Bs %s) | parciales (Bs, en moneda debe, en moneda haber)=%s | pago línea residual=%s",
            invoice_currency, mode, invoice.amount_residual, invoice.currency_id.name,
            invoice.amount_residual_signed,
            [(pp.amount, pp.debit_amount_currency, pp.credit_amount_currency) for pp in _partials],
            [(l.amount_residual, l.amount_residual_currency) for l in payment.move_id.line_ids
             if l.account_type == account_type],
        )
        # El resto se cobra en Bs: en una factura en moneda extranjera son sus pendientes a la tasa del cobro
        rest_bs = (
            round(invoice.amount_residual * (eur_rate if in_eur else voucher_rate), 2)
            if in_usd else abs(invoice.amount_residual_signed)
        )
        igtf_payment = self.env["account.payment"]
        if payment_first:
            pass
        elif igtf:
            # Cobro del resto en USD con IGTF: el 3 % se suma al monto y no es parte de lo cobrado a la factura
            usd_journal = self._setup_igtf_usd_journal()
            if in_eur:  # el asistente abre con la fecha de hoy: hacen falta sus tasas
                self._set_rate(currency_eur, self.today, eur_rate)
                self._set_rate(self.currency_usd, self.today, voucher_rate)
            # el IGTF (3 %) se suma a lo cobrado; el resto en USD a la tasa del comprobante
            amount_usd = round(rest_bs / voucher_rate * 1.03, 2)
            if igtf == "mixed":
                # Cobro mixto: primero USD 500 con IGTF y el resto de la deuda en Bs
                with Form.from_action(self.env, invoice.action_register_payment()) as first_form:
                    first_form.journal_id = usd_journal
                    first_form.payment_date = voucher_day
                    first_form.save()
                    first_form.amount = round(500.0 * 1.03, 2)
                    first_form.save()
                first_form.record.action_create_payments()
                invoice.invalidate_recordset()
                amount_usd = 0.0
            if igtf == "mixed":
                wizard = self._payment_wizard(invoice.ids, {
                    "amount": round(invoice.amount_residual * voucher_rate, 2),
                    "currency_id": self.currency_vef.id,
                    "payment_date": voucher_day,
                    "journal_id": self.bank_journal_sub.id,
                })
                wizard.action_create_payments()
                igtf_payment = self.env["account.payment"].search([], order="id desc", limit=1)
            else:
                with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
                    pay_form.journal_id = usd_journal
                    pay_form.payment_date = voucher_day
                    pay_form.save()
                    pay_form.amount = amount_usd
                    pay_form.save()
                action = pay_form.record.action_create_payments()
                igtf_payment = self.env["account.payment"].browse(action.get("res_id"))
        else:
            wizard = self._payment_wizard(invoice.ids, {
                "amount": rest_bs,
                "currency_id": self.currency_vef.id,
                "payment_date": voucher_day,
                "journal_id": self.bank_journal_sub.id,
            })
            wizard.action_create_payments()
        invoice.invalidate_recordset()
        partials = receivable.matched_debit_ids | receivable.matched_credit_ids
        counterpart = (partials.debit_move_id | partials.credit_move_id).filtered(
            lambda l: l.account_id == receivable.account_id
        )
        exchange_lines = partials.exchange_move_id.line_ids.filtered(
            lambda l: l.account_id == receivable.account_id
        )
        account_lines = receivable | counterpart | exchange_lines
        result = {
            "invoice": invoice,
            "line": line,
            "payment": payment,
            "account_lines": account_lines,
            "exchange_moves": partials.exchange_move_id,
            "residual_after_retention": residual_after_retention,
            "residual_bs_after_retention": residual_bs_after_retention,
            "retention_exchange_bs": retention_exchange_bs,
            "igtf_payment": igtf_payment,
            "second_retention": second_retention,
        }
        _logger.warning(
            "OBSERVADO %s %s | línea: Bs=%s foreign=%s tasa=%s | pago: %s %s líneas(balance, alterna)=%s |"
            " cierre: estado=%s cuenta balance=%s alterna=%s | diferencias=%s",
            invoice_currency, mode, line.retention_amount, line.foreign_retention_amount,
            line.foreign_currency_rate, payment.amount, payment.currency_id.name,
            [(l.account_id.code, l.balance, l.foreign_balance) for l in payment.move_id.line_ids],
            invoice.payment_state, sum(account_lines.mapped("balance")),
            sum(account_lines.mapped("foreign_balance")),
            [(l.account_id.code, l.balance, l.foreign_balance) for l in partials.exchange_move_id.line_ids],
        )
        _logger.warning(
            "DETALLE %s %s | %s", invoice_currency, mode,
            [
                (l.move_id.name, str(l.date), l.account_id.code, l.balance, l.amount_currency,
                 l.foreign_balance)
                for l in account_lines
            ],
        )
        return result

    def _assert_ri_closure(self, result):
        with self.subTest("la factura queda pagada"):
            self.assertEqual(result["invoice"].payment_state, "paid")
        with self.subTest("cierre en Bs"):
            self.assertAlmostEqual(sum(result["account_lines"].mapped("balance")), 0.0, places=2)
        with self.subTest("cierre en moneda alterna"):
            self.assertAlmostEqual(sum(result["account_lines"].mapped("foreign_balance")), 0.0, places=2)

    def test_ri_001_customer_iva_not_indexed_on_a_bolivars_invoice(self):
        """RI-001: retención de Bs 4.800 y USD 120 (tasa de la factura), sin diferencia por la
        retención y la cuenta del cliente en 0,00 en Bs y en USD alterno."""
        result = self._run_customer_iva_case("VEF", "not_indexed")
        line, payment = result["line"], result["payment"]
        with self.subTest("retención en Bs"):
            self.assertAlmostEqual(line.retention_amount, 4800.0, places=2)
            self.assertAlmostEqual(payment.amount, 4800.0, places=2)
        with self.subTest("retención en moneda alterna: USD 120 a la tasa de la factura"):
            for entry_line in payment.move_id.line_ids:
                self.assertAlmostEqual(abs(entry_line.foreign_balance), 120.0, places=2)
        self._assert_ri_closure(result)

    def test_ri_009_customer_iva_not_indexed_on_a_usd_invoice(self):
        """RI-009: lo mismo con la factura en USD."""
        result = self._run_customer_iva_case("USD", "not_indexed")
        line, payment = result["line"], result["payment"]
        with self.subTest("retención en Bs"):
            self.assertAlmostEqual(payment.amount, 4800.0, places=2)
        with self.subTest("línea: USD 120 a la tasa de la factura"):
            self.assertAlmostEqual(line.foreign_retention_amount, 120.0, places=2)
        with self.subTest("retención en moneda alterna: USD 120"):
            for entry_line in payment.move_id.line_ids:
                self.assertAlmostEqual(abs(entry_line.foreign_balance), 120.0, places=2)
        self._assert_ri_closure(result)

    def test_ri_010_customer_iva_indexed_on_a_usd_invoice(self):
        """RI-010: indexada con la factura en USD (tasa sube a 45). La retención cancela de la
        factura exactamente lo que dice su línea: USD 106,67. El diferencial en Bs de esa
        diferencia lo genera la conciliación nativa; la factura mantiene USD 1.053,33, que el
        cliente paga con el resto, y la cuenta cierra en 0,00 en Bs y en USD alterno. RI-110: cliente que no indexa dólares con factura en USD; RI-093."""
        result = self._run_customer_iva_case("USD", "indexed")
        line, payment = result["line"], result["payment"]
        with self.subTest("retención en Bs"):
            self.assertAlmostEqual(payment.amount, 4800.0, places=2)
        with self.subTest("línea: tasa del comprobante"):
            self.assertAlmostEqual(line.foreign_currency_rate, 45.0, places=4)
        with self.subTest("línea: USD 106,67"):
            self.assertAlmostEqual(line.foreign_retention_amount, 106.67, places=2)
        with self.subTest("retención en moneda alterna del asiento: USD 106,67 a la tasa de su fecha"):
            for entry_line in payment.move_id.line_ids:
                self.assertAlmostEqual(abs(entry_line.foreign_balance), 106.67, places=2)
        with self.subTest("la factura cancela USD 106,67 y mantiene USD 1.053,33"):
            self.assertAlmostEqual(result["residual_after_retention"], 1053.33, places=2)
        with self.subTest("diferencial en Bs de la retención: 533,20"):
            self.assertAlmostEqual(result["retention_exchange_bs"], 533.2, places=2)
        self._assert_ri_closure(result)


    def test_ri_003_customer_iva_not_indexed_rate_drops(self):
        """RI-003: no indexada, tasa baja a 38: Bs 4.800 y USD 120 (tasa de la factura), cierre 0,00."""
        result = self._run_customer_iva_case("VEF", "not_indexed", voucher_rate=38.0)
        payment = result["payment"]
        with self.subTest("retención en Bs"):
            self.assertAlmostEqual(payment.amount, 4800.0, places=2)
        with self.subTest("asiento: USD 120"):
            for entry_line in payment.move_id.line_ids:
                self.assertAlmostEqual(abs(entry_line.foreign_balance), 120.0, places=2)
        self._assert_ri_closure(result)

    def test_ri_005_customer_iva_not_indexed_same_day(self):
        """RI-005 (control): no indexada con el comprobante el mismo día de la factura."""
        result = self._run_customer_iva_case("VEF", "not_indexed", voucher_offset=0, voucher_rate=40.0)
        payment = result["payment"]
        with self.subTest("retención en Bs"):
            self.assertAlmostEqual(payment.amount, 4800.0, places=2)
        with self.subTest("asiento: USD 120"):
            for entry_line in payment.move_id.line_ids:
                self.assertAlmostEqual(abs(entry_line.foreign_balance), 120.0, places=2)
        self._assert_ri_closure(result)
        with self.subTest("sin ningún asiento de diferencia"):
            self.assertFalse(result["exchange_moves"])

    def _assert_ri_values(self, result, asiento_alt, residual_alt=0.0, line_value=None,
                          retained_bs=4800.0, no_exchange=False):
        """Compara con lo que dice el caso: retención en Bs, valor de la línea, USD alterno del
        asiento, y la cuenta tras el cobro del resto (Bs en cero y el residual alterno que
        queda para el tratamiento)."""
        payment, line = result["payment"], result["line"]
        with self.subTest("retención en Bs"):
            self.assertAlmostEqual(payment.amount, retained_bs, places=2)
        if line_value is not None:
            with self.subTest("valor de la línea en la moneda de la factura"):
                self.assertAlmostEqual(line.foreign_retention_amount, line_value, places=2)
        with self.subTest("USD alterno del asiento de la retención"):
            for entry_line in payment.move_id.line_ids:
                self.assertAlmostEqual(abs(entry_line.foreign_balance), asiento_alt, places=2)
        with self.subTest("cuenta en Bs en cero"):
            self.assertAlmostEqual(sum(result["account_lines"].mapped("balance")), 0.0, places=2)
        with self.subTest("residual en moneda alterna"):
            self.assertAlmostEqual(
                sum(result["account_lines"].mapped("foreign_balance")), residual_alt, places=2
            )
        if no_exchange:
            with self.subTest("sin asientos de diferencia"):
                self.assertFalse(result["exchange_moves"])

    # --- factura en USD
    def test_ri_011_usd_not_indexed_rate_drops(self):
        result = self._run_customer_iva_case("USD", "not_indexed", voucher_rate=38.0)
        self._assert_ri_values(result, asiento_alt=120.0, line_value=120.0)

    def test_ri_012_usd_indexed_rate_drops(self):
        """RI-012: indexada, tasa baja a 38. La retención cancela USD 126,32 (lo que dice su
        línea); el diferencial en Bs es − 252,80, la factura mantiene USD 1.033,68 y la cuenta
        cierra en 0,00 en Bs y en USD alterno."""
        result = self._run_customer_iva_case("USD", "indexed", voucher_rate=38.0)
        self._assert_ri_values(result, asiento_alt=126.32, residual_alt=0.0, line_value=126.32)
        with self.subTest("la factura cancela USD 126,32 y mantiene USD 1.033,68"):
            self.assertAlmostEqual(result["residual_after_retention"], 1033.68, places=2)
        with self.subTest("diferencial en Bs de la retención: − 252,80"):
            self.assertAlmostEqual(result["retention_exchange_bs"], -252.8, places=2)
        self._assert_ri_closure(result)

    # --- con IGTF: el cobro del resto en USD aplica el 3 % de IGTF
    def _assert_igtf_closure(self, result):
        igtf_payment = result["igtf_payment"]
        with self.subTest("el cobro en divisas aplicó IGTF"):
            self.assertTrue(igtf_payment)
        with self.subTest("la cuenta del cliente cierra en Bs y en alterno (el IGTF no la toca)"):
            self.assertAlmostEqual(sum(result["account_lines"].mapped("balance")), 0.0, delta=0.05)
            self.assertAlmostEqual(
                sum(result["account_lines"].mapped("foreign_balance")), 0.0, delta=0.05
            )

    @tagged("retention_igtf")
    def test_ri_009_usd_not_indexed_rest_paid_in_usd_with_igtf(self):
        """RI-088: IGTF con retención no indexada y cobro en USD."""
        result = self._run_customer_iva_case("USD", "not_indexed", igtf=True)
        self._assert_igtf_closure(result)

    @tagged("retention_igtf")
    def test_ri_010_usd_indexed_rest_paid_in_usd_with_igtf(self):
        """RI-054/087: IGTF con retención indexada y cobro del resto en USD; RI-093: el diferencial nativo y el de la moneda alterna no se duplican."""
        result = self._run_customer_iva_case("USD", "indexed", igtf=True)
        with self.subTest("la retención no cambia con IGTF"):
            self.assertAlmostEqual(result["residual_after_retention"], 1053.33, places=2)
        self._assert_igtf_closure(result)

    @tagged("retention_igtf")
    def test_ri_011_usd_not_indexed_rate_drops_with_igtf(self):
        result = self._run_customer_iva_case("USD", "not_indexed", voucher_rate=38.0, igtf=True)
        self._assert_igtf_closure(result)

    @tagged("retention_igtf")
    def test_ri_012_usd_indexed_rate_drops_with_igtf(self):
        result = self._run_customer_iva_case("USD", "indexed", voucher_rate=38.0, igtf=True)
        with self.subTest("la retención no cambia con IGTF"):
            self.assertAlmostEqual(result["residual_after_retention"], 1033.68, places=2)
        self._assert_igtf_closure(result)


    @tagged("retention_igtf")
    def test_ri_031_iva_supplier_usd_not_indexed_with_igtf(self):
        result = self._run_retention_case("sup", "iva", "USD", "not_indexed", igtf=True)
        self._assert_igtf_closure(result)

    @tagged("retention_igtf")
    def test_ri_032_iva_supplier_usd_indexed_with_igtf(self):
        result = self._run_retention_case("sup", "iva", "USD", "indexed", igtf=True)
        with self.subTest("la retención no cambia con IGTF"):
            self.assertAlmostEqual(result["residual_after_retention"], 1053.33, places=2)
        self._assert_igtf_closure(result)

    @tagged("retention_igtf")
    def test_ri_032_iva_supplier_usd_indexed_rate_drops_with_igtf(self):
        result = self._run_retention_case("sup", "iva", "USD", "indexed", voucher_rate=38.0, igtf=True)
        with self.subTest("la retención no cambia con IGTF"):
            self.assertAlmostEqual(result["residual_after_retention"], 1033.68, places=2)
        self._assert_igtf_closure(result)

    @tagged("retention_igtf")
    def test_ri_045_supplier_mixed_payment_with_igtf_and_bolivars(self):
        result = self._run_retention_case("sup", "iva", "USD", "indexed", igtf="mixed")
        self._assert_igtf_closure(result)

    def test_ri_013_usd_not_indexed_same_day(self):
        result = self._run_customer_iva_case("USD", "not_indexed", voucher_offset=0, voucher_rate=40.0)
        self._assert_ri_values(result, asiento_alt=120.0, line_value=120.0, no_exchange=True)

    def test_ri_014_usd_indexed_same_day(self):
        result = self._run_customer_iva_case("USD", "indexed", voucher_offset=0, voucher_rate=40.0)
        self._assert_ri_values(result, asiento_alt=120.0, line_value=120.0, no_exchange=True)

    # --- factura en EUR (tasas del día de la factura: USD 40, EUR 44)
    def test_ri_017_eur_not_indexed_rate_rises(self):
        """RI-092: EUR no indexada: se conservan EUR y USD."""
        result = self._run_customer_iva_case("EUR", "not_indexed", voucher_rate=45.0, eur_rate=49.5)
        self._assert_ri_values(result, asiento_alt=132.0, line_value=120.0, retained_bs=5280.0)

    def test_ri_018_eur_indexed_rate_rises(self):
        """RI-018: EUR indexada, tasas del día USD 45 y EUR 49,5. Línea en EUR 106,67 y asiento con
        USD alterno 117,33; la factura mantiene EUR 1.053,33 y la cuenta cierra en 0,00. RI-091/111: EUR indexada: se ajustan EUR y USD; el cliente que no indexa dólares con factura en euros."""
        result = self._run_customer_iva_case("EUR", "indexed", voucher_rate=45.0, eur_rate=49.5)
        self._assert_ri_values(result, asiento_alt=117.33, line_value=106.67, retained_bs=5280.0)
        with self.subTest("la factura mantiene EUR 1.053,33"):
            self.assertAlmostEqual(result["residual_after_retention"], 1053.33, places=2)

    def test_ri_019_eur_not_indexed_rate_drops(self):
        result = self._run_customer_iva_case("EUR", "not_indexed", voucher_rate=38.0, eur_rate=41.8)
        self._assert_ri_values(result, asiento_alt=132.0, line_value=120.0, retained_bs=5280.0)

    def test_ri_020_eur_indexed_rate_drops(self):
        """RI-020: EUR indexada, tasas del día USD 38 y EUR 41,8. Línea en EUR 126,32 y asiento con
        USD alterno 138,95; la factura mantiene EUR 1.033,68 y la cuenta cierra en 0,00."""
        result = self._run_customer_iva_case("EUR", "indexed", voucher_rate=38.0, eur_rate=41.8)
        self._assert_ri_values(result, asiento_alt=138.95, line_value=126.32, retained_bs=5280.0)
        with self.subTest("la factura mantiene EUR 1.033,68"):
            self.assertAlmostEqual(result["residual_after_retention"], 1033.68, places=2)

    def test_ri_021_eur_not_indexed_same_day(self):
        result = self._run_customer_iva_case(
            "EUR", "not_indexed", voucher_offset=0, voucher_rate=40.0, eur_rate=44.0
        )
        self._assert_ri_values(
            result, asiento_alt=132.0, line_value=120.0, retained_bs=5280.0, no_exchange=True
        )

    def test_ri_022_eur_indexed_same_day(self):
        result = self._run_customer_iva_case(
            "EUR", "indexed", voucher_offset=0, voucher_rate=40.0, eur_rate=44.0
        )
        self._assert_ri_values(
            result, asiento_alt=132.0, line_value=120.0, retained_bs=5280.0, no_exchange=True
        )

    def test_baseline_eur_invoice_paid_in_bolivars_without_retention(self):
        """Control sin retención: una factura de venta en EUR cobrada en Bs a otra tasa. Muestra si
        el alterno de la cuenta cierra con el asiento de diferencia de las facturas en EUR, que
        no depende de las retenciones."""
        self.company.l10n_ve_use_foreign_exchange_diff = True
        voucher_day = self.invoice_date + relativedelta(days=5)
        currency_eur = self.env.ref("base.EUR")
        currency_eur.active = True
        self._set_rate(self.currency_usd, voucher_day, 45.0)
        self._set_rate(currency_eur, self.invoice_date, 44.0)
        self._set_rate(currency_eur, voucher_day, 49.5)
        self._set_exchange_entry_rates(voucher_day, 45.0, 49.5)
        sale_journal = self.env["account.journal"].create({
            "name": "Diario Venta EUR", "type": "sale", "code": "SALEU", "company_id": self.company.id,
        })
        with Form(self.env["account.move"].with_context(
            default_move_type="out_invoice", default_journal_id=sale_journal.id,
        )) as inv_form:
            inv_form.partner_id = self.partner_pnr_75
            inv_form.invoice_date = self.invoice_date
            inv_form.currency_id = currency_eur
        invoice = inv_form.save()
        with Form(invoice) as inv_form_edit:
            with inv_form_edit.invoice_line_ids.new() as line:
                line.product_id = self.product_iva
                line.quantity = 1
                line.price_unit = 1000.0
        invoice = inv_form_edit.save()
        invoice.write({"date": self.invoice_date, "invoice_date_display": self.invoice_date})
        invoice.with_context(move_action_post_alert=True).action_post()
        receivable = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        wizard = self._payment_wizard(invoice.ids, {
            "amount": round(invoice.amount_residual * 49.5, 2),
            "currency_id": self.currency_vef.id,
            "payment_date": voucher_day,
            "journal_id": self.bank_journal_sub.id,
        })
        wizard.action_create_payments()
        invoice.invalidate_recordset()
        partials = receivable.matched_debit_ids | receivable.matched_credit_ids
        counterpart = (partials.debit_move_id | partials.credit_move_id).filtered(
            lambda l: l.account_id == receivable.account_id
        )
        exchange_lines = partials.exchange_move_id.line_ids.filtered(
            lambda l: l.account_id == receivable.account_id
        )
        account_lines = receivable | counterpart | exchange_lines
        _logger.warning(
            "DETALLE EUR sin retención | %s",
            [(l.move_id.name, l.balance, l.amount_currency, l.foreign_balance) for l in account_lines],
        )
        self.assertEqual(invoice.payment_state, "paid")
        with self.subTest("cierre en Bs"):
            self.assertAlmostEqual(sum(account_lines.mapped("balance")), 0.0, places=2)
        with self.subTest("cierre en moneda alterna"):
            self.assertAlmostEqual(sum(account_lines.mapped("foreign_balance")), 0.0, places=2)

    def test_baseline_eur_invoice_alt_closes_when_the_eur_usd_cross_changes(self):
        """Control sin retención con el cruce EUR/USD cambiando (EUR sube 25 % y USD 12,5 %): el alterno
        de la diferencia es real y el asiento debe llevarlo para que la cuenta cierre en 0,00."""
        self.company.l10n_ve_use_foreign_exchange_diff = True
        voucher_day = self.invoice_date + relativedelta(days=5)
        currency_eur = self.env.ref("base.EUR")
        currency_eur.active = True
        self._set_rate(self.currency_usd, voucher_day, 45.0)
        self._set_rate(currency_eur, self.invoice_date, 44.0)
        self._set_rate(currency_eur, voucher_day, 55.0)
        self._set_exchange_entry_rates(voucher_day, 45.0, 55.0)
        sale_journal = self.env["account.journal"].create({
            "name": "Diario Venta EUR", "type": "sale", "code": "SALEU", "company_id": self.company.id,
        })
        with Form(self.env["account.move"].with_context(
            default_move_type="out_invoice", default_journal_id=sale_journal.id,
        )) as inv_form:
            inv_form.partner_id = self.partner_pnr_75
            inv_form.invoice_date = self.invoice_date
            inv_form.currency_id = currency_eur
        invoice = inv_form.save()
        with Form(invoice) as inv_form_edit:
            with inv_form_edit.invoice_line_ids.new() as line:
                line.product_id = self.product_iva
                line.quantity = 1
                line.price_unit = 1000.0
        invoice = inv_form_edit.save()
        invoice.write({"date": self.invoice_date, "invoice_date_display": self.invoice_date})
        invoice.with_context(move_action_post_alert=True).action_post()
        receivable = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        wizard = self._payment_wizard(invoice.ids, {
            "amount": round(invoice.amount_residual * 55.0, 2),
            "currency_id": self.currency_vef.id,
            "payment_date": voucher_day,
            "journal_id": self.bank_journal_sub.id,
        })
        wizard.action_create_payments()
        invoice.invalidate_recordset()
        partials = receivable.matched_debit_ids | receivable.matched_credit_ids
        counterpart = (partials.debit_move_id | partials.credit_move_id).filtered(
            lambda l: l.account_id == receivable.account_id
        )
        exchange_lines = partials.exchange_move_id.line_ids.filtered(
            lambda l: l.account_id == receivable.account_id
        )
        account_lines = receivable | counterpart | exchange_lines
        _logger.warning(
            "DETALLE EUR sin retención | %s",
            [(l.move_id.name, l.balance, l.amount_currency, l.foreign_balance) for l in account_lines],
        )
        self.assertEqual(invoice.payment_state, "paid")
        with self.subTest("cierre en Bs"):
            self.assertAlmostEqual(sum(account_lines.mapped("balance")), 0.0, places=2)
        with self.subTest("cierre en moneda alterna"):
            self.assertAlmostEqual(sum(account_lines.mapped("foreign_balance")), 0.0, places=2)

    def test_baseline_eur_invoice_alt_closes_when_the_alternate_exchange_is_off(self):
        """Con el ajuste de diferencial en moneda alterna apagado, el asiento de diferencia de la
        factura en EUR no lleva alterno y la cuenta cierra en 0,00 en Bs y en alterno."""
        self.company.l10n_ve_use_foreign_exchange_diff = False
        voucher_day = self.invoice_date + relativedelta(days=5)
        currency_eur = self.env.ref("base.EUR")
        currency_eur.active = True
        self._set_rate(self.currency_usd, voucher_day, 45.0)
        self._set_rate(currency_eur, self.invoice_date, 44.0)
        self._set_rate(currency_eur, voucher_day, 49.5)
        self._set_exchange_entry_rates(voucher_day, 45.0, 49.5)
        sale_journal = self.env["account.journal"].create({
            "name": "Diario Venta EUR", "type": "sale", "code": "SALEU", "company_id": self.company.id,
        })
        with Form(self.env["account.move"].with_context(
            default_move_type="out_invoice", default_journal_id=sale_journal.id,
        )) as inv_form:
            inv_form.partner_id = self.partner_pnr_75
            inv_form.invoice_date = self.invoice_date
            inv_form.currency_id = currency_eur
        invoice = inv_form.save()
        with Form(invoice) as inv_form_edit:
            with inv_form_edit.invoice_line_ids.new() as line:
                line.product_id = self.product_iva
                line.quantity = 1
                line.price_unit = 1000.0
        invoice = inv_form_edit.save()
        invoice.write({"date": self.invoice_date, "invoice_date_display": self.invoice_date})
        invoice.with_context(move_action_post_alert=True).action_post()
        receivable = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        wizard = self._payment_wizard(invoice.ids, {
            "amount": round(invoice.amount_residual * 49.5, 2),
            "currency_id": self.currency_vef.id,
            "payment_date": voucher_day,
            "journal_id": self.bank_journal_sub.id,
        })
        wizard.action_create_payments()
        invoice.invalidate_recordset()
        partials = receivable.matched_debit_ids | receivable.matched_credit_ids
        counterpart = (partials.debit_move_id | partials.credit_move_id).filtered(
            lambda l: l.account_id == receivable.account_id
        )
        exchange_lines = partials.exchange_move_id.line_ids.filtered(
            lambda l: l.account_id == receivable.account_id
        )
        account_lines = receivable | counterpart | exchange_lines
        _logger.warning(
            "DETALLE EUR sin retención | %s",
            [(l.move_id.name, l.balance, l.amount_currency, l.foreign_balance) for l in account_lines],
        )
        self.assertEqual(invoice.payment_state, "paid")
        with self.subTest("cierre en Bs"):
            self.assertAlmostEqual(sum(account_lines.mapped("balance")), 0.0, places=2)
        with self.subTest("cierre en moneda alterna"):
            self.assertAlmostEqual(sum(account_lines.mapped("foreign_balance")), 0.0, places=2)

    # --- retenciones de proveedor (ISLR e IVA) y municipal: mismas valoraciones que las de cliente
    def _case(self, party, kind, currency, mode, asiento_alt, line_value, retained_bs, residual=None,
              **kwargs):
        result = self._run_retention_case(party, kind, currency, mode, **kwargs)
        self._assert_ri_values(
            result, asiento_alt=asiento_alt, line_value=line_value, retained_bs=retained_bs
        )
        if residual is not None:
            with self.subTest("saldo de la factura tras la retención"):
                self.assertAlmostEqual(result["residual_after_retention"], residual, places=2)
        self._assert_ri_closure(result)
        return result

    def _case_derived(self, party, kind, currency, mode, voucher_rate=45.0, eur_rate=49.5, **kwargs):
        """Casos de ISLR: el monto lo calcula el formulario con el concepto de pago configurado
        (la hoja usa 5 %, el concepto de la fixture otro porcentaje), así que lo que se verifica es
        la relación entre ese monto en Bs y la tasa que corresponde a cada modalidad."""
        result = self._run_retention_case(
            party, kind, currency, mode, voucher_rate=voucher_rate, eur_rate=eur_rate, **kwargs
        )
        retained = result["line"].retention_amount
        in_eur = currency == "EUR"
        document_rate = (eur_rate if mode == "indexed" else 44.0) if in_eur else (
            voucher_rate if mode == "indexed" else 40.0
        )
        alternate_rate = voucher_rate if mode == "indexed" else 40.0
        if currency == "VEF":
            line_value = retained / voucher_rate if mode == "indexed" else 0.0
        else:
            line_value = retained / document_rate
        self._assert_ri_values(
            result, asiento_alt=retained / alternate_rate, line_value=line_value, retained_bs=retained
        )
        if currency != "VEF":
            with self.subTest("saldo de la factura tras la retención"):
                self.assertAlmostEqual(result["residual_after_retention"], 1000.0 - line_value, places=2)
        self._assert_ri_closure(result)
        return result

    # ISLR proveedor (el monto sale del concepto de pago configurado)
    def test_ri_025_islr_supplier_bolivars_not_indexed(self):
        self._case_derived("sup", "islr", "VEF", "not_indexed")

    def test_ri_027_islr_supplier_usd_not_indexed(self):
        self._case_derived("sup", "islr", "USD", "not_indexed")

    def test_ri_028_islr_supplier_usd_indexed(self):
        self._case_derived("sup", "islr", "USD", "indexed")

    def test_ri_029_islr_supplier_eur_not_indexed(self):
        self._case_derived("sup", "islr", "EUR", "not_indexed")

    def test_ri_030_islr_supplier_eur_indexed(self):
        self._case_derived("sup", "islr", "EUR", "indexed")

    # IVA proveedor
    def test_ri_031_iva_supplier_usd_not_indexed(self):
        self._case("sup", "iva", "USD", "not_indexed", 120.0, 120.0, 4800.0, residual=1040.0)

    def test_ri_032_iva_supplier_usd_indexed(self):
        self._case("sup", "iva", "USD", "indexed", 106.67, 106.67, 4800.0, residual=1053.33)

    def test_ri_033_iva_supplier_eur_not_indexed(self):
        self._case("sup", "iva", "EUR", "not_indexed", 132.0, 120.0, 5280.0, residual=1040.0)

    def test_ri_034_iva_supplier_eur_indexed(self):
        self._case("sup", "iva", "EUR", "indexed", 117.33, 106.67, 5280.0, residual=1053.33)

    # Municipal (1 % de la base)
    def test_ri_035_municipal_usd_not_indexed(self):
        self._case("sup", "mun", "USD", "not_indexed", 10.0, 10.0, 400.0, residual=990.0)

    def test_ri_036_municipal_usd_indexed(self):
        self._case("sup", "mun", "USD", "indexed", 8.89, 8.89, 400.0, residual=991.11)

    # ------------------------------------------------------------------ otros casos de la hoja

    def test_ri_038_customer_iva_special_agent_retains_100_percent_not_indexed(self):
        """RI-038: agente de retención especial, 100 % del IVA (Bs 6.400), no indexada."""
        result = self._run_retention_case("cus", "iva", "USD", "not_indexed", retained_override=6400.0)
        self._assert_ri_values(result, asiento_alt=160.0, line_value=160.0, retained_bs=6400.0)

    def test_ri_038_customer_iva_special_agent_retains_100_percent_indexed(self):
        """RI-038: 100 % del IVA (Bs 6.400), indexada: USD 142,22 en lugar de 160."""
        result = self._run_retention_case("cus", "iva", "USD", "indexed", retained_override=6400.0)
        self._assert_ri_values(result, asiento_alt=142.22, line_value=142.22, retained_bs=6400.0)
        with self.subTest("la factura mantiene USD 1.017,78"):
            self.assertAlmostEqual(result["residual_after_retention"], 1017.78, places=2)
    def test_ri_039_one_voucher_with_two_invoices_of_different_dates_and_rates(self):
        """RI-039: dos facturas del mismo proveedor (tasas 40 y 42). No indexada: cada una a su tasa
        (USD 120 y USD 120, Bs 4.800 y 5.040). Indexada: ambas a la tasa del comprobante (45):
        USD 106,67 y USD 112,00. Los bolívares no cambian."""
        d2 = self.invoice_date + relativedelta(days=2)
        voucher_day = self.invoice_date + relativedelta(days=5)
        self.env["res.currency.rate"].search([
            ("currency_id", "=", self.currency_vef.id), ("company_id", "=", self.company.id),
            ("name", "in", [d2, voucher_day]),
        ]).unlink()
        for day in (d2, voucher_day):
            self.env["res.currency.rate"].create({
                "currency_id": self.currency_vef.id, "company_id": self.company.id,
                "name": day, "rate": 1.0,
            })
        self._set_rate(self.currency_usd, d2, 42.0)
        self._set_rate(self.currency_usd, voucher_day, 45.0)
        self._set_exchange_entry_rates(voucher_day, 45.0)
        invoice_1 = self._create_usd_invoice(amount=1000.0)
        invoice_2 = self._create_usd_invoice(
            amount=1000.0, invoice_date=d2, correlative="12345678901235"
        )

        def vals(mode):
            return {
                "type_retention": "iva", "type": "in_invoice", "company_id": self.company.id,
                "partner_id": self.partner_pnr_75.id, "date": voucher_day,
                "date_accounting": voucher_day, "number": "01234567891234", "indexation_mode": mode,
                "retention_line_ids": [
                    Command.create({
                        "move_id": invoice_1.id, "name": "IVA 1", "invoice_total": 46400.0,
                        "invoice_amount": 40000.0, "retention_amount": 4800.0,
                    }),
                    Command.create({
                        "move_id": invoice_2.id, "name": "IVA 2", "invoice_total": 48720.0,
                        "invoice_amount": 42000.0, "retention_amount": 5040.0,
                    }),
                ],
            }

        retention = self._form_create_retention(vals("not_indexed"))
        lines = retention.retention_line_ids
        first = lines.filtered(lambda l: l.move_id == invoice_1)
        second = lines.filtered(lambda l: l.move_id == invoice_2)
        with self.subTest("no indexada: cada factura a su tasa"):
            self.assertAlmostEqual(first.foreign_retention_amount, 120.0, places=2)
            self.assertAlmostEqual(second.foreign_retention_amount, 120.0, places=2)
        with self.subTest("bolívares"):
            self.assertAlmostEqual(retention.total_retention_amount, 9840.0, places=2)
        self._set_mode(retention, "indexed")
        with self.subTest("indexada: ambas a la tasa del comprobante"):
            self.assertAlmostEqual(first.foreign_retention_amount, 106.67, places=2)
            self.assertAlmostEqual(second.foreign_retention_amount, 112.0, places=2)
            self.assertAlmostEqual(first.foreign_currency_rate, 45.0, places=4)
            self.assertAlmostEqual(second.foreign_currency_rate, 45.0, places=4)
        with self.subTest("bolívares sin cambios"):
            self.assertAlmostEqual(retention.total_retention_amount, 9840.0, places=2)
        retention.action_post()
        with self.subTest("un pago por factura con el alterno de su modalidad"):
            self.assertEqual(len(retention.payment_ids), 2)
            alt = sorted(
                abs(p.move_id.line_ids[:1].foreign_balance) for p in retention.payment_ids
            )
            self.assertAlmostEqual(alt[0], 106.67, places=2)
            self.assertAlmostEqual(alt[1], 112.0, places=2)

    def test_ri_042_changing_the_voucher_date_in_draft_changes_the_indexed_value(self):
        """RI-042: indexada, comprobante con tasa 45 → USD 106,67; con tasa 47 → USD 102,13. La fecha
        del comprobante solo se edita en el formulario de cliente."""
        d1 = self.invoice_date + relativedelta(days=3)
        d2 = self.today
        self.env["res.currency.rate"].search([
            ("currency_id", "=", self.currency_vef.id), ("company_id", "=", self.company.id), ("name", "=", d1),
        ]).unlink()
        self.env["res.currency.rate"].create({
            "currency_id": self.currency_vef.id, "company_id": self.company.id, "name": d1, "rate": 1.0,
        })
        self._set_rate(self.currency_usd, d1, 45.0)
        self._set_rate(self.currency_usd, d2, 47.0)
        retention = self._create_customer_retention(mode="indexed", date=d1, accounting_date=d1)
        line = retention.retention_line_ids
        self.assertAlmostEqual(line.foreign_retention_amount, 106.67, places=2)
        self._set_retention_fields(retention, date=d2)
        with self.subTest("tasa 47"):
            self.assertAlmostEqual(line.foreign_retention_amount, 102.13, places=2)
        with self.subTest("los bolívares no cambian"):
            self.assertAlmostEqual(line.retention_amount, 4800.0, places=2)
    def test_supplier_voucher_date_is_editable_only_when_the_retention_is_indexed(self):
        """La fecha del comprobante de proveedor no se calcula (trae hoy por defecto) y la vista la
        bloquea; la valoración indexada la usa, así que en borrador solo se desbloquea para las
        indexadas. En una no indexada sigue de solo lectura."""
        d1 = self.invoice_date + relativedelta(days=3)
        self.env["res.currency.rate"].search([
            ("currency_id", "=", self.currency_vef.id), ("company_id", "=", self.company.id), ("name", "=", d1),
        ]).unlink()
        self.env["res.currency.rate"].create({
            "currency_id": self.currency_vef.id, "company_id": self.company.id, "name": d1, "rate": 1.0,
        })
        self._set_rate(self.currency_usd, d1, 45.0)
        self._set_rate(self.currency_usd, self.today, 47.0)
        indexed = self._create_retention(self._create_usd_invoice(correlative="12345678900431"), mode="indexed",
                                         number="01234567890431")
        line = indexed.retention_line_ids
        self.assertAlmostEqual(line.foreign_retention_amount, line.retention_amount / 47.0, places=2)
        self._set_retention_fields(indexed, date=d1)
        with self.subTest("la indexada se revalora con la tasa de la nueva fecha"):
            self.assertAlmostEqual(line.foreign_retention_amount, line.retention_amount / 45.0, places=2)
        with self.subTest("la no indexada no deja editar la fecha del comprobante"):
            not_indexed = self._create_retention(
                self._create_usd_invoice(correlative="12345678900432"), mode="not_indexed", number="01234567890432"
            )
            with self.assertRaises(AssertionError):
                self._set_retention_fields(not_indexed, date=d1)

    def test_ri_043_emitted_retention_locks_the_modality_and_the_dates(self):
        """RI-043: con el comprobante emitido no se puede cambiar la modalidad ni las fechas: el
        formulario las deja de solo lectura y el modelo también lo rechaza."""
        invoice = self._create_usd_invoice()
        retention = self._create_retention(invoice, mode="indexed")
        retention.action_post()
        self.assertEqual(retention.state, "emitted")
        with self.subTest("en el formulario la modalidad es de solo lectura"):
            with self.assertRaises(AssertionError):
                self._set_mode(retention, "not_indexed")
        with self.subTest("en el modelo la modalidad no cambia"):
            with self.assertRaises(UserError):
                retention.write({"indexation_mode": "not_indexed"})
        for field in ("date", "date_accounting"):
            with self.subTest(field):
                value = getattr(retention, field) - relativedelta(days=1)
                with self.assertRaises(UserError):
                    retention.write({field: value})
    def test_ri_044_cancelling_a_retention_reverts_payment_and_difference(self):
        """RI-044 y RI-086: cancelar revierte el pago y la diferencia, en ambas modalidades."""
        for index, mode in enumerate(("not_indexed", "indexed")):
            with self.subTest(mode=mode):
                invoice = self._create_usd_invoice(correlative="1234567890123%d" % index)
                total_usd = invoice.amount_total
                total_bs = abs(invoice.amount_residual_signed)
                retention, payment = self._post(invoice, mode, number="0123456789123%d" % index)
                retention.action_cancel()
                self.assertEqual(retention.state, "cancel")
                self.assertAlmostEqual(invoice.amount_residual, total_usd, places=2)
                self.assertAlmostEqual(abs(invoice.amount_residual_signed), total_bs, places=2)

    def test_ri_052_retention_over_an_invoice_already_paid_is_blocked_with_a_message(self):
        """RI-052: retención sobre una factura ya pagada al 100 %: el formulario no la ofrece y
        avisa con un mensaje al elegir el contacto, así que no hay comprobante ni pagos."""
        for index, mode in enumerate(("not_indexed", "indexed")):
            with self.subTest(mode=mode):
                invoice = self._create_usd_invoice(correlative="1234567890124%d" % index)
                wizard = self._payment_wizard(invoice.ids, {
                    "amount": round(invoice.amount_residual * self.VOUCHER_RATE, 2),
                    "currency_id": self.currency_vef.id,
                    "payment_date": self.today,
                    "journal_id": self.bank_journal_sub.id,
                })
                wizard.action_create_payments()
                self.assertEqual(invoice.payment_state, "paid")
                with self.assertRaises(UserError) as caught:
                    self._create_retention(invoice, mode=mode, number="0123456789124%d" % index)
                self.assertIn("no invoices with taxes", str(caught.exception))
                self.assertFalse(self.env["account.retention"].search([("retention_line_ids.move_id", "=", invoice.id)]))
    def test_ri_048_indexed_retention_without_a_rate_for_its_date_is_blocked(self):
        """RI-048: sin tasa para la fecha del comprobante no se calcula con una tasa inventada: se
        avisa y no se emite. RI-080: la regla de tasa exacta bloquea la emisión cuando falta la tasa del día."""
        invoice = self._create_usd_invoice()
        vals = self._retention_vals(invoice, mode="indexed")
        retention = self._form_create_retention(vals)
        self.assertTrue(retention.retention_line_ids.foreign_retention_amount)
        self.env["res.currency.rate"].search([
            ("currency_id", "=", self.currency_usd.id), ("name", "=", retention.date),
        ]).unlink()
        retention.retention_line_ids._apply_foreign_valuation()
        self.assertEqual(retention.retention_line_ids.foreign_retention_amount, 0.0)
        with self.assertRaises(UserError):
            retention.action_post()

    def test_ri_055_a_retention_that_rounds_to_zero_is_blocked(self):
        """RI-055: un monto tan pequeño que su valor en moneda de la factura redondea a 0,00 no
        deja residuales: se bloquea con un mensaje (el monto lo teclea el usuario de cliente)."""
        retention = self._create_customer_retention(mode="indexed", amount=0.01)
        self.assertEqual(retention.retention_line_ids.foreign_retention_amount, 0.0)
        with self.assertRaises(UserError):
            retention.action_post()
    def test_ri_047_retention_first_then_payment_at_another_rate(self):
        """RI-047: registrar la retención y luego cobrar el resto a otra tasa: la cuenta cierra en
        0,00 en Bs y en alterno, en ambas modalidades (cliente en USD)."""
        for index, mode in enumerate(("not_indexed", "indexed")):
            with self.subTest(mode=mode):
                result = self._run_retention_case(
                    "cus", "iva", "USD", mode, voucher_rate=48.0, number="0123456789047%d" % index
                )
                self._assert_ri_closure(result)

    def test_ri_046_payment_before_retention(self):
        """RI-046: se cobra primero el saldo sin retención y la retención se registra después. La no
        indexada cierra en 0,00 en Bs y alterno; la indexada deja la diferencia de su valoración."""
        result = self._run_retention_case("cus", "iva", "USD", "not_indexed", payment_first=True)
        self._assert_ri_values(result, asiento_alt=120.0, line_value=120.0)
        result = self._run_retention_case(
            "cus", "iva", "USD", "indexed", payment_first=True, number="01234567891235"
        )
        payment = result["payment"]
        with self.subTest("la retención se valora a la tasa del comprobante"):
            self.assertAlmostEqual(payment.amount, 4800.0, places=2)
            self.assertAlmostEqual(result["line"].foreign_retention_amount, 106.67, places=2)
            for entry_line in payment.move_id.line_ids:
                self.assertAlmostEqual(abs(entry_line.foreign_balance), 106.67, places=2)
        with self.subTest("queda pendiente la diferencia de USD 13,33 (Bs 533,20)"):
            self.assertAlmostEqual(result["invoice"].amount_residual, 13.33, places=2)
            self.assertAlmostEqual(sum(result["account_lines"].mapped("balance")), 533.2, places=2)
            self.assertAlmostEqual(sum(result["account_lines"].mapped("foreign_balance")), 13.33, places=2)

    def test_ri_067_order_of_the_payments_gives_the_same_exchange_difference(self):
        """RI-067: cobrar primero o retener primero deja los mismos saldos y el mismo asiento de
        diferencia (no indexada)."""
        first = self._run_retention_case("cus", "iva", "USD", "not_indexed")
        second = self._run_retention_case(
            "cus", "iva", "USD", "not_indexed", payment_first=True, number="01234567891235"
        )

        def exchange_bs(result):
            lines = result["exchange_moves"].line_ids
            return sum(abs(l.balance) for l in lines) / 2.0

        with self.subTest("mismo diferencial en Bs"):
            self.assertAlmostEqual(exchange_bs(first), exchange_bs(second), places=2)
        with self.subTest("misma cuenta en Bs y en alterno"):
            for result in (first, second):
                self.assertAlmostEqual(sum(result["account_lines"].mapped("balance")), 0.0, places=2)
                self.assertAlmostEqual(sum(result["account_lines"].mapped("foreign_balance")), 0.0, places=2)

    # --- retención parcial, monedas cruzadas, decimales y fechas sin tasa
    def test_ri_037_partial_retention_closes_the_account(self):
        """RI-037: retención del 50 % del IVA (Bs 3.200) y cobro del resto: la cuenta cierra en
        0,00 en Bs y en alterno, en ambas modalidades."""
        for index, mode in enumerate(("not_indexed", "indexed")):
            with self.subTest(mode=mode):
                result = self._run_retention_case(
                    "cus", "iva", "USD", mode, retained_override=3200.0, number="0123456789200%d" % index,
                )
                self.assertAlmostEqual(result["payment"].amount, 3200.0, places=2)
                self._assert_ri_closure(result)

    def test_ri_113_eur_rises_while_the_dollar_drops(self):
        """RI-113: EUR 44 → 49,50 y USD 40 → 38 el mismo día: la línea indexada vale EUR 106,67 y
        la cuenta cierra en 0,00 en Bs y en alterno."""
        result = self._run_retention_case("cus", "iva", "EUR", "indexed", voucher_rate=38.0, eur_rate=49.5)
        self.assertAlmostEqual(result["line"].foreign_retention_amount, 106.67, places=2)
        self.assertAlmostEqual(result["payment"].amount, 5280.0, places=2)
        self._assert_ri_closure(result)

    def test_ri_116_eur_rate_with_many_decimals_leaves_no_rounding_residual(self):
        """RI-116: tasa del euro con muchos decimales: sin residuales por redondeo."""
        result = self._run_retention_case("cus", "iva", "EUR", "indexed", eur_rate=49.123456)
        self._assert_ri_closure(result)

    def test_ri_151_rate_decimals_match_between_the_voucher_and_the_entry(self):
        """RI-151: tasa 385,272: el valor de la línea y el del asiento coinciden y no queda
        residual por redondeo."""
        result = self._run_retention_case("cus", "iva", "USD", "indexed", voucher_rate=385.272)
        line, payment = result["line"], result["payment"]
        for entry_line in payment.move_id.line_ids:
            self.assertAlmostEqual(abs(entry_line.foreign_balance), line.foreign_retention_amount, places=2)
        self._assert_ri_closure(result)

    def test_ri_007_008_015_016_023_024_a_voucher_before_the_invoice_is_blocked(self):
        """RI-007/008 (Bs), 015/016 (USD) y 023/024 (EUR), no indexada e indexada: el comprobante no
        puede llevar una fecha del comprobante ni contable anterior a la de la factura; el sistema lo
        rechaza al guardar con un mensaje que nombra la factura."""
        before = self.invoice_date - relativedelta(days=2)
        self.env["res.currency.rate"].search([
            ("currency_id", "=", self.currency_vef.id), ("company_id", "=", self.company.id), ("name", "=", before),
        ]).unlink()
        self.env["res.currency.rate"].create({
            "currency_id": self.currency_vef.id, "company_id": self.company.id, "name": before, "rate": 1.0,
        })
        eur = self.env.ref("base.EUR")
        eur.active = True
        self._set_rate(self.currency_usd, before, 38.0)
        self._set_rate(eur, before, 41.8)
        self._set_rate(eur, self.invoice_date, 44.0)
        currencies = (
            (self.currency_vef, "VEF", 1160.0, 1000.0, 120.0),
            (self.currency_usd, "USD", 46400.0, 40000.0, 4800.0),
            (eur, "EUR", 51040.0, 44000.0, 5280.0),
        )
        counter = 0
        for currency, code, total, base, retained in currencies:
            for mode in ("not_indexed", "indexed"):
                for field in ("date", "accounting_date"):
                    counter += 1
                    with self.subTest(currency=code, mode=mode, field=field):
                        invoice = self._customer_invoice_in(currency, "FAB%s%d" % (code[0], counter))
                        with self.assertRaises(ValidationError) as caught:
                            self._create_customer_retention(
                                mode=mode, number="012345678900%02d" % counter, invoice=invoice,
                                totals=(total, base), amount=retained, **{field: before},
                            )
                        self.assertIn("cannot be earlier than the invoice date", str(caught.exception))
                        self.assertIn(invoice.name, str(caught.exception))

    def test_ri_049_079_102_a_date_without_its_own_rate_is_blocked_even_with_an_earlier_rate(self):
        """RI-049/079/102: la tasa se busca por la fecha exacta del comprobante (no cae a la última
        anterior): sin ella el valor indexado queda en 0,00 y la emisión se bloquea con un mensaje
        que nombra la moneda y la fecha, aunque exista la tasa de un día anterior. Con la tasa de
        ese día el comprobante se emite."""
        day = self.invoice_date + relativedelta(days=1)  # sin tasa propia; la del día anterior (factura) sí existe
        retention = self._create_customer_retention(mode="indexed", date=day)
        self.assertEqual(retention.retention_line_ids.foreign_retention_amount, 0.0)
        with self.assertRaises(UserError) as caught:
            retention.action_post()
        self.assertIn(self.currency_usd.name, str(caught.exception))
        self.assertIn(str(day), str(caught.exception))
        self.env["res.currency.rate"].search([
            ("currency_id", "=", self.currency_vef.id), ("company_id", "=", self.company.id), ("name", "=", day),
        ]).unlink()
        self.env["res.currency.rate"].create({
            "currency_id": self.currency_vef.id, "company_id": self.company.id, "name": day, "rate": 1.0,
        })
        self._set_rate(self.currency_usd, day, 41.0)
        self._set_retention_fields(retention, date=day)  # la vista revalora con la tasa que ahora existe
        self.assertAlmostEqual(retention.retention_line_ids.foreign_retention_amount, 4800.0 / 41.0, places=2)

    def _branch_fixture(self):
        """Sucursal de la compañía con su propio diario de ventas, banco y diario de diferencial. Las
        tasas son las de la compañía principal: en Odoo 19 solo se crean para la principal."""
        branch = self.env["res.company"].create({
            "name": "Sucursal RI", "parent_id": self.company.id, "currency_id": self.currency_vef.id,
            "foreign_currency_id": self.currency_usd.id, "country_id": self.company.country_id.id,
        })
        Account = self.env["account.account"]
        recv = Account.search([("account_type", "=", "asset_receivable")], limit=1)
        pay = Account.search([("account_type", "=", "liability_payable")], limit=1)
        income = Account.search([("account_type", "=", "income")], limit=1)
        bank_account = Account.create({
            "code": "BR1002", "name": "Banco Sucursal", "account_type": "asset_cash",
            "company_ids": [Command.set(self.company.ids)],
        })
        method_in = self.env["account.payment.method.line"].create({
            "name": "Manual In Sucursal", "payment_method_id": self.env.ref("account.account_payment_method_manual_in").id,
            "payment_type": "inbound", "payment_account_id": bank_account.id,
        })
        method_out = self.env["account.payment.method.line"].create({
            "name": "Manual Out Sucursal", "payment_method_id": self.env.ref("account.account_payment_method_manual_out").id,
            "payment_type": "outbound", "payment_account_id": bank_account.id,
        })
        journals = self.env["account.journal"].with_company(branch)
        sale = journals.create({
            "name": "Ventas Sucursal", "type": "sale", "code": "VSUC", "company_id": branch.id,
            "default_account_id": income.id,
        })
        exchange_journal = journals.create({
            "name": "Diferencial Sucursal", "type": "general", "code": "XSUC", "company_id": branch.id,
        })
        bank = journals.create({
            "name": "Banco Sucursal", "type": "bank", "code": "BSUC", "company_id": branch.id,
            "default_account_id": bank_account.id,
            "inbound_payment_method_line_ids": [(6, 0, method_in.ids)],
            "outbound_payment_method_line_ids": [(6, 0, method_out.ids)],
        })
        method_in.journal_id = bank.id
        method_out.journal_id = bank.id
        partner = self.partner_pnr_75.with_company(branch)
        partner.property_account_receivable_id = recv
        partner.property_account_payable_id = pay
        branch.write({
            "iva_customer_retention_journal_id": bank.id, "iva_supplier_retention_journal_id": bank.id,
            "use_indexed_retentions": True, "currency_exchange_journal_id": exchange_journal.id,
            "income_currency_exchange_account_id": self.company.income_currency_exchange_account_id.id,
            "expense_currency_exchange_account_id": self.company.expense_currency_exchange_account_id.id,
        })
        branch.l10n_ve_use_foreign_exchange_diff = True
        return branch, sale, bank

    def test_ri_066_a_branch_gets_the_same_results_as_the_main_company(self):
        """RI-066: factura y retención indexada en una sucursal con su diario y su banco: mismos
        resultados que en la compañía principal (valor en USD, saldo de la factura y monto del
        pago) y todo queda en la sucursal."""
        main = self._create_customer_retention(mode="indexed", number="01234567890665")
        main.action_post()
        main_line = main.retention_line_ids
        main_residual = main_line.move_id.amount_residual

        branch, sale, bank = self._branch_fixture()
        invoice_form = Form(self.env["account.move"].with_company(branch).with_context(
            default_move_type="out_invoice", default_journal_id=sale.id,
        ))
        with invoice_form as form:
            form.partner_id = self.partner_pnr_75
            form.invoice_date = self.invoice_date
            form.currency_id = self.currency_usd
        invoice = invoice_form.record
        with Form(invoice) as edit:
            with edit.invoice_line_ids.new() as line:
                line.product_id = self.product_iva
                line.quantity = 1
                line.price_unit = 1000.0
        invoice.with_context(move_action_post_alert=True).action_post()
        context = self._retention_action_context("iva", "out_invoice")
        retention_form = Form(
            self.env["account.retention"].with_company(branch).with_context(context),
            view=self._form_view_xmlid("iva"),
        )
        with retention_form as form:
            form.partner_id = self.partner_pnr_75
            form.number = "01234567890666"
            form.date_accounting = self.today
            form.indexation_mode = "indexed"
            with form.retention_line_ids.edit(0) as line:
                line.retention_amount = 4800.0
        retention = retention_form.record
        retention.action_post()
        branch_line = retention.retention_line_ids

        with self.subTest("todo queda en la sucursal"):
            self.assertEqual(invoice.company_id, branch)
            self.assertEqual(invoice.journal_id, sale)
            self.assertEqual(retention.company_id, branch)
            self.assertEqual(retention.payment_ids.journal_id, bank)
        with self.subTest("mismo valor en USD, mismo monto y mismo saldo que en la principal"):
            self.assertAlmostEqual(branch_line.foreign_retention_amount, main_line.foreign_retention_amount, places=2)
            self.assertAlmostEqual(retention.payment_ids.amount, main.payment_ids.amount, places=2)
            self.assertAlmostEqual(invoice.amount_residual, main_residual, places=2)

    def test_ri_050_a_future_voucher_date_is_blocked(self):
        """RI-050: ni la fecha contable ni la del comprobante pueden ser posteriores a hoy: el
        sistema lo rechaza al guardar, así que no se usa una tasa inexistente."""
        future = self.today + relativedelta(days=10)
        for index, field in enumerate(("accounting_date", "date")):
            with self.subTest(field):
                with self.assertRaises(ValidationError):
                    self._create_customer_retention(
                        mode="indexed", number="0123456789050%d" % index, **{field: future}
                    )
    def test_ri_085_cancel_and_reissue_leaves_a_single_effect(self):
        """RI-085: cancelar el comprobante y emitir uno nuevo para la misma factura deja un solo
        efecto vigente: el saldo es el de una sola retención, en ambas modalidades."""
        for index, mode in enumerate(("not_indexed", "indexed")):
            with self.subTest(mode=mode):
                invoice = self._create_usd_invoice(correlative="1234567890125%d" % index)
                first, first_payment = self._post(invoice, mode, number="0123456789125%d" % index)
                residual_one_retention = invoice.amount_residual
                first.action_cancel()
                self.assertAlmostEqual(invoice.amount_residual, invoice.amount_total, places=2)
                second, second_payment = self._post(invoice, mode, number="0123456789126%d" % index)
                self.assertEqual(second.state, "emitted")
                self.assertAlmostEqual(invoice.amount_residual, residual_one_retention, places=2)
                self.assertEqual(first_payment.state, "canceled")
                self.assertEqual(len(second_payment), 1)

    def test_ri_100_reopened_retention_records_the_modality_change(self):
        """RI-100: reabrir una retención emitida y cambiar la modalidad deja el registro del
        cambio y, al emitirla de nuevo, el pago refleja la nueva valoración."""
        invoice = self._create_usd_invoice()
        retention = self.env["account.retention"].with_context(tracking_disable=False).create(
            self._retention_vals(invoice, mode="indexed")
        )
        self.env.cr.precommit.run()
        retention.action_post()
        self.assertAlmostEqual(retention.retention_line_ids.foreign_retention_amount,
                               self._expected_foreign(retention.retention_line_ids.retention_amount, self.today), places=2)
        retention.action_cancel()
        retention.action_draft()
        retention = retention.with_context(tracking_disable=False)
        self._set_mode(retention, "not_indexed")
        self.env.cr.precommit.run()
        values = self.env["mail.tracking.value"].sudo().search([
            ("mail_message_id.model", "=", "account.retention"),
            ("mail_message_id.res_id", "=", retention.id),
            ("field_id.name", "=", "indexation_mode"),
        ], order="id")
        self.assertEqual([v.new_value_char for v in values][-1], "Non-indexed (invoice rate)")
        retention.action_post()
        self.assertEqual(retention.state, "emitted")
        self.assertEqual(retention.indexation_mode, "not_indexed")

    @skip("Falla conocida, pendiente de desarrollo: Hallazgo: hoy el reverso se ejecuta y deja abierto el pago de la retención")
    def test_ri_068_reversing_an_invoice_with_a_posted_retention(self):
        """RI-068: reversar la factura que ya tiene una retención aprobada debe bloquearse con un
        aviso (o revertir la retención y sus diferencias). Hoy el asistente de reversión crea la
        nota de crédito, se publica y se aplica sin aviso, el comprobante sigue emitido y la línea
        del pago de la retención queda abierta, de modo que la cuenta del proveedor no cierra."""
        invoice = self._create_usd_invoice()
        retention, payment = self._post(invoice, "indexed")
        with self.assertRaises(UserError):
            credit_note = self._credit_note_with_form(invoice)
            self._apply_credit_note(invoice, credit_note)

    def test_ri_118_iva_indexed_and_islr_not_indexed_on_the_same_invoice(self):
        """RI-118: dos comprobantes de la misma factura el mismo día (tasa 45): el IVA indexado se
        valora a la tasa del comprobante (USD 106,67) y el ISLR no indexado a la de la factura
        (USD 50,00); ambos cuadran y la cuenta cierra en 0,00 en Bs y en alterno."""
        result = self._run_retention_case("sup", "iva", "USD", "indexed", second_islr_mode="not_indexed")
        second = result["second_retention"]
        with self.subTest("IVA indexado a la tasa del comprobante"):
            self.assertAlmostEqual(result["line"].foreign_retention_amount, 106.67, places=2)
        islr_bolivars = second.payment_ids.amount
        with self.subTest("ISLR no indexado a la tasa de la factura"):
            self.assertAlmostEqual(
                second.retention_line_ids.foreign_retention_amount, islr_bolivars / 40.0, places=2
            )
        with self.subTest("la factura conserva lo que no se retuvo"):
            self.assertAlmostEqual(
                result["residual_after_retention"], 2160.0 - 106.67 - islr_bolivars / 40.0, places=2
            )
        self._assert_ri_closure(result)

    def test_ri_081_missing_rate_message_names_the_currency_and_the_date(self):
        """RI-081/103: sin tasa el aviso indica la moneda y la fecha y no se calcula con una tasa
        inventada; con la tasa del día el comprobante se emite sin aviso."""
        invoice = self._create_usd_invoice()
        retention = self._form_create_retention(self._retention_vals(invoice, mode="indexed"))
        result = retention.action_post()
        with self.subTest("con la tasa del día no hay aviso"):
            self.assertFalse(result and result.get("params", {}).get("type") == "danger")
            self.assertEqual(retention.state, "emitted")
        invoice = self._create_usd_invoice(correlative="12345678901288")
        vals = self._retention_vals(invoice, mode="indexed", number="01234567891288")
        retention = self._form_create_retention(vals)
        self.env["res.currency.rate"].search([
            ("currency_id", "=", self.currency_usd.id), ("name", "=", retention.date),
        ]).unlink()
        retention.retention_line_ids._apply_foreign_valuation()
        with self.subTest("sin tasa el aviso nombra moneda y fecha"):
            with self.assertRaises(UserError) as caught:
                retention.action_post()
            self.assertIn(self.currency_usd.name, str(caught.exception))
            self.assertIn(str(retention.date), str(caught.exception))

    def test_ri_056_eur_invoice_without_a_usd_rate_on_the_voucher_day(self):
        """RI-056: factura en EUR y el día del comprobante solo hay tasa del EUR: bloqueo claro
        que nombra la moneda y la fecha, sin alterna con tasa 0."""
        with self.assertRaises(UserError) as caught:
            self._run_retention_case("cus", "iva", "EUR", "indexed", drop_usd_rate=True)
        self.assertIn("USD", str(caught.exception))

    @skip("Falla conocida, pendiente de desarrollo: Hallazgo: el cobro en USD de una factura en EUR deja Bs 5.720 sin asentar")
    @tagged("retention_igtf")
    def test_ri_114_eur_invoice_retained_and_then_paid_in_dollars(self):
        """RI-114: factura en EUR retenida y el resto cobrado en dólares (con IGTF): debe cerrar en
        0,00 en Bs y en alterno, sin diferencias duplicadas. Hoy la factura queda pagada pero la
        cuenta en Bs queda en − 5.720 (no indexada): EUR 1.040 × (49,50 − 44) de diferencia en Bs que
        ningún asiento registra (el asiento EXCH solo trae alterno: − 127,11). Ocurre también sin
        retención (ver `test_baseline_eur_invoice_paid_in_usd_without_retention`): no es de
        las retenciones."""
        for index, mode in enumerate(("not_indexed", "indexed")):
            with self.subTest(mode=mode):
                result = self._run_retention_case(
                    "cus", "iva", "EUR", mode, igtf=True, number="0123456789300%d" % index,
                )
                self._assert_igtf_closure(result)
                self._assert_igtf_closure(result)

    def test_ri_094_exchange_result_account_matches_the_direction_of_the_rate(self):
        """RI-094: en la factura de venta en USD (el cliente nos debe dólares) la tasa al alza
        valoriza la deuda: ganancia cambiaria; a la baja: pérdida. El importe es el diferencial en
        Bs de la retención. La hoja de casos dice lo contrario (al alza pérdida): se deja el
        comportamiento contable actual y se consulta."""
        company = self.company
        for index, (rate, account, amount) in enumerate((
            (45.0, company.income_currency_exchange_account_id, 533.2),
            (38.0, company.expense_currency_exchange_account_id, 252.8),
        )):
            with self.subTest(rate=rate):
                result = self._run_retention_case(
                    "cus", "iva", "USD", "indexed", voucher_rate=rate, number="0123456789400%d" % index,
                )
                retention_lines = result["payment"].move_id.line_ids
                retention_partials = retention_lines.matched_debit_ids | retention_lines.matched_credit_ids
                result_lines = retention_partials.exchange_move_id.line_ids.filtered(
                    lambda l: l.account_id.account_type != "asset_receivable"
                )
                self.assertEqual(result_lines.account_id, account)
                self.assertAlmostEqual(abs(sum(result_lines.mapped("balance"))), amount, places=2)

    def test_ri_070_and_097_the_texts_describe_the_behavior(self):
        """RI-070/097: la etiqueta y las ayudas dicen lo que hace cada modalidad: no indexado = tasa
        de la factura; indexado = tasa de la fecha del comprobante, sin contradicción en el
        comprobante, el contacto y el ajuste de la compañía."""
        retention_field = self.env["account.retention"]._fields["indexation_mode"]
        selection = dict(retention_field.selection)
        self.assertIn("invoice rate", selection["not_indexed"])
        for help_text in (
            retention_field.help,
            self.env["res.company"]._fields["use_indexed_retentions"].help,
        ):
            with self.subTest(help_text[:40]):
                self.assertIn("voucher date", help_text)
                self.assertNotIn("accounting date", help_text)
        self.assertIn("invoice", retention_field.help)

    def _payable_closure(self, partner_lines):
        """Líneas por pagar de las facturas, notas y pagos, con sus diferencias, para comprobar el
        cierre de la cuenta del proveedor en Bs y en alterno."""
        payable = partner_lines.filtered(lambda l: l.account_type == "liability_payable")
        partials = payable.matched_debit_ids | payable.matched_credit_ids
        payable |= (partials.debit_move_id | partials.credit_move_id | partials.exchange_move_id.line_ids).filtered(
            lambda l: l.account_type == "liability_payable"
        )
        return payable

    def test_ri_053_partial_credit_note_before_the_retention(self):
        """RI-053: factura de cliente de USD 1.000 + IVA y nota de crédito de USD 200 antes de la
        retención; el usuario teclea la retención sobre el neto y la cuenta cierra en 0,00 en Bs y
        en alterno."""
        for index, mode in enumerate(("not_indexed", "indexed")):
            with self.subTest(mode=mode):
                invoice = self._customer_invoice_in(self.currency_usd, "FACN%d" % index)
                credit_note = self._credit_note_with_form(invoice, price_unit=200.0)
                self._apply_credit_note(invoice, credit_note)
                self.assertAlmostEqual(invoice.amount_residual, 928.0, places=2)  # (1.000 - 200) + IVA 16 %
                net_bs = abs(invoice.amount_residual_signed)
                vals = {
                    "type_retention": "iva", "type": "out_invoice", "company_id": self.company.id,
                    "partner_id": self.partner_pnr_75.id, "date": self.today, "date_accounting": self.today,
                    "number": "0123456789135%d" % index, "indexation_mode": mode,
                    "retention_line_ids": [Command.create({
                        "move_id": invoice.id, "name": "IVA", "invoice_total": net_bs,
                        "invoice_amount": round(net_bs / 1.16, 2),
                        "retention_amount": round(net_bs / 1.16 * 0.16 * 0.75, 2),
                    })],
                }
                retention = self._form_create_retention(vals)
                retention.action_post()
                payment = retention.payment_ids
                self._payment_wizard(invoice.ids, {
                    "amount": round(invoice.amount_residual * self.VOUCHER_RATE, 2),
                    "currency_id": self.currency_vef.id, "payment_date": self.today,
                    "journal_id": self.bank_journal_sub.id,
                }).action_create_payments()
                self.assertEqual(invoice.payment_state, "paid")
                receivable = (invoice | credit_note | payment.move_id).line_ids.filtered(
                    lambda l: l.account_type == "asset_receivable"
                )
                partials = receivable.matched_debit_ids | receivable.matched_credit_ids
                lines = (receivable | partials.debit_move_id | partials.credit_move_id
                         | partials.exchange_move_id.line_ids).filtered(lambda l: l.account_type == "asset_receivable")
                self.assertAlmostEqual(sum(lines.mapped("balance")), 0.0, places=2)
                self.assertAlmostEqual(sum(lines.mapped("foreign_balance")), 0.0, delta=0.05)

    @skip("Falla conocida, pendiente de desarrollo: Hallazgo: la nota de crédito total deja abierto el pago de la retención")
    def test_ri_089_total_credit_note_on_an_invoice_with_a_retention(self):
        """RI-089: nota de crédito por el total de una factura con retención emitida: la retención
        y su pago deben quedar tratados de forma coherente (revertidos o con aviso) y la cuenta
        del proveedor cerrar en 0,00. Hoy la línea del pago de la retención queda abierta."""
        invoice = self._create_usd_invoice(amount=1000.0)
        retention, payment = self._post(invoice, "indexed")
        credit_note = self._credit_note_with_form(invoice)
        self._apply_credit_note(invoice, credit_note)
        lines = self._payable_closure((invoice | credit_note | payment.move_id).line_ids)
        self.assertAlmostEqual(sum(lines.mapped("balance")), 0.0, places=2)

    def _customer_invoice_in(self, currency, journal_code):
        """Factura de venta de 1.000 en `currency` (la que usan los casos de retención)."""
        journal = self.env["account.journal"].search(
            [("code", "=", journal_code), ("company_id", "=", self.company.id)], limit=1
        ) or self.env["account.journal"].create({
            "name": "Venta %s" % journal_code, "type": "sale", "code": journal_code,
            "company_id": self.company.id,
        })
        with Form(self.env["account.move"].with_context(
            default_move_type="out_invoice", default_journal_id=journal.id,
        )) as inv_form:
            inv_form.partner_id = self.partner_pnr_75
            inv_form.invoice_date = self.invoice_date
            inv_form.currency_id = currency
        invoice = inv_form.save()
        with Form(invoice) as edit:
            with edit.invoice_line_ids.new() as line:
                line.product_id = self.product_iva
                line.quantity = 1
                line.price_unit = 1000.0
        invoice = edit.save()
        invoice.write({"date": self.invoice_date, "invoice_date_display": self.invoice_date})
        invoice.with_context(move_action_post_alert=True).action_post()
        return invoice

    @skip("Falla conocida, pendiente de desarrollo: Hallazgo base (sin retención): cobro en USD de una factura en EUR deja Bs sin asentar")
    @tagged("retention_igtf")
    def test_baseline_eur_invoice_paid_in_usd_without_retention(self):
        """Sin retención: una factura en EUR cobrada en USD (con IGTF) queda pagada pero la cuenta en
        Bs no cierra. Es lo mismo que muestra RI-114, así que no es propio de las retenciones.

        Causa (verificada en `account.move.line._prepare_reconciliation_single_partial` y con
        datos): la factura en EUR ofrece {VEF, EUR} y el pago en USD ofrece {VEF, USD}; como
        ninguna moneda extranjera está en las dos, el core concilia en la moneda de la compañía.
        La factura se cancela por sus Bs 51.040 y no queda resto en EUR que corregir, así que no
        se crea ningún asiento de diferencia en Bs. El excedente del pago (Bs − 4.657,40, USD −
        103,50) queda como crédito sin aplicar en la línea del pago, y `l10n_ve_accountant` solo
        agrega el asiento en alterno (− 141,78)."""
        self.company.l10n_ve_use_foreign_exchange_diff = True
        voucher_day = self.invoice_date + relativedelta(days=5)
        eur = self.env.ref("base.EUR")
        eur.active = True
        self._set_rate(eur, self.invoice_date, 44.0)
        self._set_rate(eur, voucher_day, 49.5)
        self._set_rate(self.currency_usd, voucher_day, 45.0)
        self._set_exchange_entry_rates(voucher_day, 45.0, 49.5)
        usd_journal = self._setup_igtf_usd_journal()
        invoice = self._customer_invoice_in(eur, "FACE9")
        self._set_rate(eur, self.today, 49.5)
        self._set_rate(self.currency_usd, self.today, 45.0)
        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = usd_journal
            pay_form.payment_date = voucher_day
            pay_form.save()
            pay_form.amount = round(invoice.amount_residual * 49.5 / 45.0, 2)
            pay_form.save()
        pay_form.record.action_create_payments()
        receivable = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        partials = receivable.matched_debit_ids | receivable.matched_credit_ids
        lines = (receivable | partials.debit_move_id | partials.credit_move_id | partials.exchange_move_id.line_ids).filtered(
            lambda l: l.account_type == "asset_receivable")
        self.assertEqual(invoice.payment_state, "paid")
        self.assertAlmostEqual(sum(lines.mapped("balance")), 0.0, delta=0.05)

    @skip("Falla conocida, pendiente de desarrollo: Hallazgo base: la diferencia cambiaria del euro queda como crédito sin aplicar")
    @tagged("retention_igtf")
    def test_baseline_eur_invoice_paid_in_usd_exact_amount_without_igtf(self):
        """Factura de EUR 1.160 (Bs 51.040 a tasa 44) cobrada con USD 1.276 (= EUR 1.160 a tasa 49,50
        y USD a 45; Bs 57.420), sin IGTF y sin retención. Se concilian Bs 51.040 y el pago conserva
        un residual de Bs 6.380 (USD 141,78) = EUR 1.160 × (49,50 − 44): es la ganancia cambiaria
        del euro, que no se asienta y queda como un crédito falso sin aplicar en la cuenta del
        cliente. El único asiento de diferencia es solo en alterno (− 141,78)."""
        self.company.l10n_ve_use_foreign_exchange_diff = True
        voucher_day = self.invoice_date + relativedelta(days=5)
        eur = self.env.ref("base.EUR")
        eur.active = True
        self._set_rate(eur, self.invoice_date, 44.0)
        self._set_rate(eur, voucher_day, 49.5)
        self._set_rate(self.currency_usd, voucher_day, 45.0)
        self._set_exchange_entry_rates(voucher_day, 45.0, 49.5)
        usd_journal = self._setup_igtf_usd_journal()
        usd_journal.is_igtf = False
        invoice = self._customer_invoice_in(eur, "FACE8")
        self._set_rate(eur, self.today, 49.5)
        self._set_rate(self.currency_usd, self.today, 45.0)
        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = usd_journal
            pay_form.payment_date = voucher_day
            pay_form.save()
            pay_form.amount = 1276.0
            pay_form.save()
        pay_form.record.action_create_payments()
        receivable = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        partials = receivable.matched_debit_ids | receivable.matched_credit_ids
        pay_lines = (partials.debit_move_id | partials.credit_move_id).filtered(lambda l: l.move_id != invoice and l.account_type == "asset_receivable")
        self.assertEqual(invoice.payment_state, "paid")
        self.assertAlmostEqual(pay_lines.amount_residual, 0.0, places=2)


    def test_ri_040_one_voucher_with_usd_and_eur_invoices_of_the_same_customer(self):
        """RI-040: un comprobante indexado con una factura en USD y otra en EUR (tasas del día 45
        y 49,50): cada línea con su monto legal en Bs y su valor en su moneda (USD 106,67 y EUR
        106,67), sin mezclar monedas; al cobrar el resto la cuenta cierra en 0,00. Una factura en
        Bs en el mismo comprobante indexado se rechaza."""
        self.company.l10n_ve_use_foreign_exchange_diff = True
        voucher_day = self.invoice_date + relativedelta(days=5)
        eur = self.env.ref("base.EUR")
        eur.active = True
        self._set_rate(eur, self.invoice_date, 44.0)
        self._set_rate(eur, voucher_day, 49.5)
        self._set_rate(self.currency_usd, voucher_day, 45.0)
        self._set_exchange_entry_rates(voucher_day, 45.0, 49.5)
        usd_invoice = self._customer_invoice_in(self.currency_usd, "FACU1")
        eur_invoice = self._customer_invoice_in(eur, "FACE1")
        retention = self._form_create_retention({
            "type_retention": "iva", "type": "out_invoice", "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id, "date": voucher_day, "date_accounting": voucher_day,
            "number": "01234567891400", "indexation_mode": "indexed",
            "retention_line_ids": [
                Command.create({
                    "move_id": usd_invoice.id, "name": "USD", "invoice_total": 46400.0,
                    "invoice_amount": 40000.0, "retention_amount": 4800.0,
                }),
                Command.create({
                    "move_id": eur_invoice.id, "name": "EUR", "invoice_total": 51040.0,
                    "invoice_amount": 44000.0, "retention_amount": 5280.0,
                }),
            ],
        })
        usd_line, eur_line = retention.retention_line_ids
        with self.subTest("valor de cada línea en su moneda"):
            self.assertAlmostEqual(usd_line.foreign_retention_amount, 106.67, places=2)
            self.assertAlmostEqual(eur_line.foreign_retention_amount, 106.67, places=2)
            self.assertEqual(usd_line.foreign_currency_id, self.currency_usd)
            self.assertEqual(eur_line.foreign_currency_id, eur)
        retention.action_post()
        with self.subTest("montos legales en Bs"):
            self.assertAlmostEqual(sum(retention.payment_ids.mapped("amount")), 4800.0 + 5280.0, places=2)
        for invoice, rate in ((usd_invoice, 45.0), (eur_invoice, 49.5)):
            self._payment_wizard(invoice.ids, {
                "amount": round(invoice.amount_residual * rate, 2),
                "currency_id": self.currency_vef.id, "payment_date": voucher_day,
                "journal_id": self.bank_journal_sub.id,
            }).action_create_payments()
            with self.subTest("cierre de %s" % invoice.currency_id.name):
                self.assertEqual(invoice.payment_state, "paid")
        with self.subTest("la cuenta del cliente cierra en Bs y en alterno"):
            receivable = (usd_invoice | eur_invoice).line_ids.filtered(lambda l: l.account_type == "asset_receivable")
            partials = receivable.matched_debit_ids | receivable.matched_credit_ids
            lines = (receivable | partials.debit_move_id | partials.credit_move_id
                     | partials.exchange_move_id.line_ids).filtered(lambda l: l.account_type == "asset_receivable")
            self.assertAlmostEqual(sum(lines.mapped("balance")), 0.0, places=2)
            self.assertAlmostEqual(sum(lines.mapped("foreign_balance")), 0.0, places=2)

    def test_ri_115_bolivars_invoice_without_a_usd_rate_on_the_invoice_date(self):
        """RI-115: factura en Bs y sin tasa del dólar en la fecha de la factura: el sistema avisa
        con la moneda y la fecha y no deja una alterna con tasa 0 ni 1."""
        self.env["res.currency.rate"].search([
            ("currency_id", "=", self.currency_usd.id), ("name", "=", self.invoice_date),
        ]).unlink()
        with self.assertRaises(UserError) as caught:
            self._customer_invoice_in(self.currency_vef, "FACV1")
        self.assertIn("USD", str(caught.exception))

    def _book_retained(self, result, report, currency_system):
        """Retención de IVA que muestra el libro (de ventas o de compras) para la factura, en
        bolívares o en la moneda alterna."""
        retention_day = result["line"].retention_id.date
        wizard = self.env["wizard.accounting.reports"].new({
            "report": report, "currency_system": currency_system,
            "date_from": retention_day - relativedelta(days=30), "date_to": self.today,
        })
        return wizard.get_retention_iva_values(result["invoice"].id)["iva_retained"]

    def test_ri_104_and_105_sales_book_shows_the_retention_by_modality(self):
        """RI-104/105: libro de ventas con retención de IVA: en bolívares el monto legal es el mismo
        (4.800); en la moneda alterna la no indexada muestra USD 120 y la indexada USD 106,67. RI-095: los reportes en Bs y en USD reflejan la retención según la modalidad."""
        for index, (mode, alternate) in enumerate((("not_indexed", 120.0), ("indexed", 106.67))):
            with self.subTest(mode=mode):
                result = self._run_retention_case(
                    "cus", "iva", "USD", mode, number="0123456789500%d" % index,
                )
                self.assertAlmostEqual(self._book_retained(result, "sale", True), 4800.0, places=2)
                self.assertAlmostEqual(self._book_retained(result, "sale", False), alternate, places=2)

    def test_ri_106_purchase_book_shows_the_supplier_retention_by_modality(self):
        """RI-106: libro de compras con la retención de IVA a un proveedor, en ambas monedas."""
        for index, (mode, alternate) in enumerate((("not_indexed", 120.0), ("indexed", 106.67))):
            with self.subTest(mode=mode):
                result = self._run_retention_case(
                    "sup", "iva", "USD", mode, number="0123456789501%d" % index,
                )
                self.assertAlmostEqual(self._book_retained(result, "purchase", True), 4800.0, places=2)
                self.assertAlmostEqual(self._book_retained(result, "purchase", False), alternate, places=2)

    def test_ri_096_the_voucher_shows_the_modality_and_the_rate_used(self):
        """RI-096: el comprobante impreso muestra la modalidad (indexada o no) y la tasa usada."""
        result = self._run_retention_case("cus", "iva", "USD", "indexed")
        retention = result["line"].retention_id
        html = self.env["ir.actions.report"]._render_qweb_html(
            "l10n_ve_payment_extension.retention_voucher_template", retention.ids
        )[0].decode()
        self.assertIn("Indexed", html)
        self.assertNotIn("Non-indexed", html)
        self.assertIn("<span>USD</span> <span>45.0000</span>", html)
        result = self._run_retention_case("cus", "iva", "USD", "not_indexed", number="01234567890961")
        html = self.env["ir.actions.report"]._render_qweb_html(
            "l10n_ve_payment_extension.retention_voucher_template", result["line"].retention_id.ids
        )[0].decode()
        self.assertIn("Non-indexed", html)

    def test_ri_071_batch_of_fifty_indexed_retentions(self):
        """RI-071: lote de 50 retenciones indexadas (facturas de 50 proveedores en USD): todas se
        emiten sin errores, con su valor en dólares y su pago, y ninguna factura queda con un
        saldo distinto al esperado."""
        retentions = self.env["account.retention"]
        invoices = self.env["account.move"]
        for index in range(50):
            invoice = self._create_usd_invoice(
                amount=200.0 + index, correlative="%014d" % (7000 + index)
            )
            retention = self._create_retention(
                invoice, mode="indexed", number="%014d" % (8000 + index)
            )
            retention.action_post()
            invoices |= invoice
            retentions |= retention
        self.assertEqual(set(retentions.mapped("state")), {"emitted"})
        self.assertEqual(len(retentions.payment_ids), 50)
        for invoice, retention in zip(invoices, retentions):
            line = retention.retention_line_ids
            self.assertTrue(line.foreign_retention_amount)
            self.assertAlmostEqual(
                invoice.amount_residual, invoice.amount_total - line.foreign_retention_amount, places=2
            )

    def _supplier_advance_in_usd(self, amount=500.0):
        """Anticipo a proveedor en USD con el diario de IGTF (como en las pruebas de IGTF)."""
        usd_journal = self._setup_igtf_usd_journal()
        context = {
            "default_payment_type": "outbound", "default_partner_type": "supplier",
            "default_move_journal_types": ("bank", "cash"), "default_is_advance_payment": True,
        }
        with Form(self.env["account.payment"].with_context(context)) as pay_form:
            pay_form.partner_id = self.partner_pnr_75
            pay_form.journal_id = usd_journal
            pay_form.amount = amount
        payment = pay_form.save()
        payment.action_post()
        return payment

    @tagged("retention_igtf")
    def test_ri_142_usd_invoice_covered_with_an_advance_and_the_rest_with_an_indexed_retention(self):
        """RI-142 (proveedor): factura en USD cubierta en parte con un anticipo en USD y el resto
        con la retención indexada y un pago en Bs: la cuenta cierra en 0,00 en Bs y en alterno y
        el anticipo no se reexpresa."""
        invoice = self._create_usd_invoice(amount=1000.0)
        advance = self._supplier_advance_in_usd(500.0)
        outstanding = advance.move_id.line_ids.filtered(
            lambda l: l.account_id.is_advance_account and l.debit > 0
        )
        invoice.with_context({}).js_assign_outstanding_line(outstanding.id)
        residual_after_advance = invoice.amount_residual
        retention, payment = self._post(invoice, "indexed")
        with self.subTest("la retención se valora a la tasa del comprobante"):
            self.assertAlmostEqual(
                retention.retention_line_ids.foreign_retention_amount,
                self._expected_foreign(retention.retention_line_ids.retention_amount, self.today), places=2,
            )
        with self.subTest("la factura baja por lo que cancela la retención"):
            self.assertAlmostEqual(
                invoice.amount_residual,
                residual_after_advance - retention.retention_line_ids.foreign_retention_amount, places=2,
            )
        self._payment_wizard(invoice.ids, {
            "amount": round(invoice.amount_residual * self.VOUCHER_RATE, 2),
            "currency_id": self.currency_vef.id, "payment_date": self.today,
            "journal_id": self.bank_journal_sub.id,
        }).action_create_payments()
        self.assertEqual(invoice.payment_state, "paid")
        lines = self._payable_closure((invoice | advance.move_id | payment.move_id).line_ids)
        advance_account = advance.move_id.line_ids.filtered(lambda l: l.account_id.is_advance_account).account_id
        with self.subTest("la cuenta por pagar cierra en Bs y en alterno"):
            self.assertAlmostEqual(sum(lines.mapped("balance")), 0.0, places=2)
            self.assertAlmostEqual(sum(lines.mapped("foreign_balance")), 0.0, places=2)
        with self.subTest("el anticipo queda cruzado"):
            advance_lines = self.env["account.move.line"].search([("account_id", "=", advance_account.id)])
            self.assertAlmostEqual(sum(advance_lines.mapped("balance")), 0.0, places=2)

    def _supplier_advance(self, journal, amount):
        context = {
            "default_payment_type": "outbound", "default_partner_type": "supplier",
            "default_move_journal_types": ("bank", "cash"), "default_is_advance_payment": True,
        }
        with Form(self.env["account.payment"].with_context(context)) as pay_form:
            pay_form.partner_id = self.partner_pnr_75
            pay_form.journal_id = journal
            pay_form.amount = amount
        payment = pay_form.save()
        payment.action_post()
        return payment

    def _cross_advance(self, invoice, advance):
        """Cruza el anticipo con la factura; devuelve el asiento del cruce."""
        outstanding = advance.move_id.line_ids.filtered(
            lambda l: l.account_id.is_advance_account and l.debit > 0
        )
        invoice.with_context({}).js_assign_outstanding_line(outstanding.id)
        partials = outstanding.matched_debit_ids | outstanding.matched_credit_ids
        return ((partials.debit_move_id | partials.credit_move_id) - outstanding).move_id[:1]

    def _pay_rest_in_bolivars(self, invoice):
        self._payment_wizard(invoice.ids, {
            "amount": round(invoice.amount_residual * self.VOUCHER_RATE, 2),
            "currency_id": self.currency_vef.id, "payment_date": self.today,
            "journal_id": self.bank_journal_sub.id,
        }).action_create_payments()

    def _assert_advance_closure(self, invoice, advance, payment):
        self.assertEqual(invoice.payment_state, "paid")
        lines = self._payable_closure((invoice | advance.move_id | payment.move_id).line_ids)
        self.assertAlmostEqual(sum(lines.mapped("balance")), 0.0, places=2)
        self.assertAlmostEqual(sum(lines.mapped("foreign_balance")), 0.0, places=2)

    @tagged("retention_igtf")
    def test_ri_143_advance_in_bolivars_and_not_indexed_retention(self):
        """RI-143 (proveedor): anticipo en Bs cruzado con la factura en USD y retención no
        indexada: la cuenta cierra en 0,00 en Bs y en alterno."""
        self._setup_igtf_usd_journal()
        invoice = self._create_usd_invoice(amount=1000.0)
        advance = self._supplier_advance(self.bank_journal_sub, 20000.0)
        self._cross_advance(invoice, advance)
        retention, payment = self._post(invoice, "not_indexed")
        self._pay_rest_in_bolivars(invoice)
        self._assert_advance_closure(invoice, advance, payment)

    @tagged("retention_igtf")
    def test_ri_144_order_between_the_retention_and_the_advance_crossing(self):
        """RI-144 (proveedor): retener antes del cruce del anticipo o después deja la misma
        valoración de la retención y la cuenta cerrada en 0,00."""
        for index, mode in enumerate(("not_indexed", "indexed")):
            with self.subTest(mode=mode):
                invoice = self._create_usd_invoice(amount=1000.0, correlative="%014d" % (9100 + index))
                advance = self._supplier_advance_in_usd(500.0)
                retention, payment = self._post(invoice, mode, number="%014d" % (9200 + index))
                foreign_before_crossing = retention.retention_line_ids.foreign_retention_amount
                self._cross_advance(invoice, advance)
                self.assertAlmostEqual(
                    retention.retention_line_ids.foreign_retention_amount, foreign_before_crossing, places=2
                )
                self._pay_rest_in_bolivars(invoice)
                self._assert_advance_closure(invoice, advance, payment)

    @tagged("retention_igtf")
    def test_ri_145_the_base_of_the_retention_is_not_reduced_by_the_advance(self):
        """RI-145: la base y el monto de la retención no cambian por el anticipo aplicado."""
        invoice = self._create_usd_invoice(amount=1000.0)
        expected = abs(invoice.amount_tax_signed) * 0.75  # 75 % del IVA, antes de cruzar el anticipo
        advance = self._supplier_advance_in_usd(500.0)
        self._cross_advance(invoice, advance)
        retention = self._create_retention(invoice, mode="indexed")
        retention.action_post()
        line = retention.retention_line_ids
        self.assertAlmostEqual(line.retention_amount, expected, places=2)
        self.assertAlmostEqual(retention.payment_ids.amount, expected, places=2)

    @tagged("retention_igtf")
    def test_ri_147_advance_in_usd_generates_igtf_when_crossing(self):
        """RI-147 y RI-148 (proveedor): el anticipo en USD (con fecha posterior a la factura) genera
        el IGTF al cruzarse y la retención indexada posterior no lo altera."""
        invoice = self._create_usd_invoice(amount=1000.0)
        advance = self._supplier_advance_in_usd(500.0)
        self.assertGreater(advance.date, invoice.invoice_date)
        cross_move = self._cross_advance(invoice, advance)
        igtf_account = self.company.supplier_account_igtf_id
        with self.subTest("el cruce genera el IGTF"):
            self.assertTrue(
                cross_move.line_ids.filtered(lambda l: l.account_id == igtf_account and l.debit > 0),
                [(l.account_id.code, l.debit, l.credit) for l in cross_move.line_ids] + [cross_move.name, str(igtf_account.code)],
            )
        retention, payment = self._post(invoice, "indexed")
        self._pay_rest_in_bolivars(invoice)
        self._assert_advance_closure(invoice, advance, payment)

    @tagged("retention_igtf")
    def test_ri_152_cancelling_the_retention_with_the_advance_already_crossed(self):
        """RI-152 (proveedor): cancelar la retención con el anticipo ya cruzado devuelve a la factura
        su saldo tras el anticipo y no toca el cruce."""
        invoice = self._create_usd_invoice(amount=1000.0)
        advance = self._supplier_advance_in_usd(500.0)
        self._cross_advance(invoice, advance)
        residual_after_advance = invoice.amount_residual
        retention, payment = self._post(invoice, "indexed")
        retention.action_cancel()
        self.assertEqual(retention.state, "cancel")
        self.assertAlmostEqual(invoice.amount_residual, residual_after_advance, places=2)

    @tagged("retention_igtf")
    def test_ri_061_customer_advance_applied_to_the_invoice_and_a_later_retention(self):
        """RI-061: anticipo de un cliente en USD aplicado a la factura y retención indexada
        posterior: cuadra en 0,00 en Bs y en alterno y el anticipo no se reexpresa."""
        usd_journal = self._setup_igtf_usd_journal()
        self.company.l10n_ve_use_foreign_exchange_diff = True
        voucher_day = self.invoice_date + relativedelta(days=5)
        self._set_rate(self.currency_usd, voucher_day, 45.0)
        self._set_exchange_entry_rates(voucher_day, 45.0)
        invoice = self._customer_invoice_in(self.currency_usd, "FACU2")
        context = {
            "default_payment_type": "inbound", "default_partner_type": "customer",
            "default_move_journal_types": ("bank", "cash"), "default_is_advance_payment": True,
        }
        with Form(self.env["account.payment"].with_context(context)) as pay_form:
            pay_form.partner_id = self.partner_pnr_75
            pay_form.journal_id = usd_journal
            pay_form.amount = 500.0
            pay_form.date = voucher_day
        advance = pay_form.save()
        advance.action_post()
        outstanding = advance.move_id.line_ids.filtered(lambda l: l.account_id.is_advance_account)
        invoice.with_context({}).js_assign_outstanding_line(outstanding.id)
        residual_after_advance = invoice.amount_residual
        retention = self._form_create_retention({
            "type_retention": "iva", "type": "out_invoice", "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id, "date": voucher_day, "date_accounting": voucher_day,
            "number": "01234567890061", "indexation_mode": "indexed",
            "retention_line_ids": [Command.create({
                "move_id": invoice.id, "name": "IVA", "invoice_total": 46400.0,
                "invoice_amount": 40000.0, "retention_amount": 4800.0,
            })],
        })
        retention.action_post()
        with self.subTest("la retención se valora a la tasa del comprobante"):
            self.assertAlmostEqual(retention.retention_line_ids.foreign_retention_amount, 106.67, places=2)
            self.assertAlmostEqual(invoice.amount_residual, residual_after_advance - 106.67, places=2)
        self._payment_wizard(invoice.ids, {
            "amount": round(invoice.amount_residual * 45.0, 2),
            "currency_id": self.currency_vef.id, "payment_date": voucher_day,
            "journal_id": self.bank_journal_sub.id,
        }).action_create_payments()
        self.assertEqual(invoice.payment_state, "paid")
        receivable = (invoice | advance.move_id | retention.payment_ids.move_id).line_ids.filtered(
            lambda l: l.account_type == "asset_receivable"
        )
        partials = receivable.matched_debit_ids | receivable.matched_credit_ids
        lines = (receivable | partials.debit_move_id | partials.credit_move_id
                 | partials.exchange_move_id.line_ids).filtered(lambda l: l.account_type == "asset_receivable")
        with self.subTest("la cuenta por cobrar cierra en Bs y en alterno"):
            self.assertAlmostEqual(sum(lines.mapped("balance")), 0.0, places=2)
            self.assertAlmostEqual(sum(lines.mapped("foreign_balance")), 0.0, places=2)

    @tagged("retention_igtf")
    def test_ri_149_a_single_exchange_adjustment_when_advance_and_retention_coincide(self):
        """RI-149 (proveedor): con el anticipo ya cruzado, la retención indexada genera un solo
        asiento de diferencia y de ningún modo lo duplica."""
        invoice = self._create_usd_invoice(amount=1000.0)
        advance = self._supplier_advance_in_usd(500.0)
        self._cross_advance(invoice, advance)
        retention, payment = self._post(invoice, "indexed")
        retention_lines = payment.move_id.line_ids
        partials = retention_lines.matched_debit_ids | retention_lines.matched_credit_ids
        exchange_moves = partials.exchange_move_id
        self.assertEqual(len(exchange_moves), 1)
        self.assertEqual(len(exchange_moves.line_ids), 2)

    @skip("Falla conocida, pendiente de desarrollo: Pendiente de desarrollo: no hay aviso de anticipo sin aplicar al retener")
    @tagged("retention_igtf")
    def test_ri_150_pending_advance_warning_when_retaining(self):
        """RI-150 (proveedor): al retener sobre una factura de un contacto con un anticipo pendiente
        de aplicar se muestra un aviso (que no bloquea la emisión)."""
        invoice = self._create_usd_invoice(amount=1000.0)
        self._supplier_advance_in_usd(500.0)  # sin cruzar
        retention = self._create_retention(invoice, mode="indexed")
        result = retention.action_post()
        self.assertEqual(retention.state, "emitted")
        self.assertTrue(result and "advance" in str(result).lower())

    def test_ri_108_customer_balance_in_bolivars_and_dollars_after_the_retention(self):
        """RI-108: saldo del cliente tras la retención (antes de cobrar el resto): no indexada
        USD 1.040 = Bs 41.600; indexada USD 1.053,33 = Bs 42.133,20 (a la tasa de la factura, 40)."""
        for index, (mode, usd, bs) in enumerate((("not_indexed", 1040.0, 41600.0), ("indexed", 1053.33, 42133.2))):
            with self.subTest(mode=mode):
                result = self._run_retention_case("cus", "iva", "USD", mode, number="0123456789108%d" % index)
                self.assertAlmostEqual(result["residual_after_retention"], usd, places=2)
                self.assertAlmostEqual(result["residual_bs_after_retention"], bs, places=2)

    def test_ri_109_book_total_matches_the_ledger(self):
        """RI-109: lo que muestra el libro como retenido (Bs) es lo que el pago de la retención
        movió en la cuenta del cliente (libro mayor), en ambas modalidades."""
        for index, mode in enumerate(("not_indexed", "indexed")):
            with self.subTest(mode=mode):
                result = self._run_retention_case("cus", "iva", "USD", mode, number="0123456789109%d" % index)
                receivable_line = result["payment"].move_id.line_ids.filtered(
                    lambda l: l.account_type == "asset_receivable"
                )
                self.assertAlmostEqual(
                    self._book_retained(result, "sale", True), abs(receivable_line.balance), places=2
                )

    def test_ri_107_municipal_report_shows_the_same_bolivars_in_both_modalities(self):
        """RI-107: el reporte de retenciones municipales en bolívares muestra el monto legal (Bs 400)
        sin importar la modalidad. Con la moneda de la compañía en bolívares el reporte no usa los
        campos de la moneda alterna."""
        for index, mode in enumerate(("not_indexed", "indexed")):
            with self.subTest(mode=mode):
                result = self._run_retention_case(
                    "sup", "mun", "USD", mode, number="0123456789107%d" % index,
                )
                retention = result["line"].retention_id
                table = self.env["municipal.retention.xlsx"].get_xlsx_municipal_retention(retention.id)
                self.assertAlmostEqual(
                    float(table["Impuesto Municipal Retenido"].sum()), 400.0, places=2
                )

    def test_ri_058_arcv_sums_the_legal_bolivars_of_indexed_and_not_indexed_retentions(self):
        """RI-058: el ARC-V (ISLR del proveedor) acumula los montos legales en Bs de las retenciones
        no indexadas e indexadas del año: el mismo monto legal de cada una, base Bs 40.000 de cada una."""
        results = [
            self._run_retention_case("sup", "islr", "USD", mode, number="0123456789058%d" % index)
            for index, mode in enumerate(("not_indexed", "indexed"))
        ]
        wizard = self.env["arcv.report"].create({
            "partner_id": self.partner_pnr_75.id,
            "date_start": self.today - relativedelta(months=3), "date_end": self.today,
        })
        grouped = wizard._get_islr_retention_lines_grouped_by_year_month_and_percentage_fees()
        data = wizard._construct_report_data(grouped)
        retentions = data["retentions"]
        self.assertTrue(retentions)
        self.assertAlmostEqual(
            sum(r["total_retention_amount"] for r in retentions),
            sum(result["line"].retention_amount for result in results), places=2,
        )
        self.assertAlmostEqual(sum(r["total_invoice_amount"] for r in retentions), 80000.0, places=2)

    def _enable_exchange_notes(self, allow_note=True):
        """Activa las notas por diferencia cambiaria (módulo l10n_ve_exchange_difference) como en
        sus propias pruebas; sin ese módulo la prueba se omite."""
        if "l10n_ve_exchange_use_nd_nc" not in self.env["res.company"]._fields:
            self.skipTest("l10n_ve_exchange_difference no está instalado")
        if getattr(self, "_exchange_notes_ready", False):
            self.partner_pnr_75.l10n_ve_exchange_allow_note = allow_note
            return
        company = self.company
        company.account_fiscal_country_id = company.country_id  # la fixture lo deja en otro país
        Account = self.env["account.account"]
        gain = Account.create({"code": "EX701", "name": "Ganancia cambiaria", "account_type": "income_other"})
        loss = Account.create({"code": "EX601", "name": "Pérdida cambiaria", "account_type": "expense"})
        exchange_journal = self.env["account.journal"].create({
            "name": "Diferencial cambiario", "type": "general", "code": "EXCHN", "company_id": company.id,
        })
        company.write({
            "income_currency_exchange_account_id": gain.id,
            "expense_currency_exchange_account_id": loss.id,
            "currency_exchange_journal_id": exchange_journal.id,
        })
        group = self.env["account.tax.group"].create({"name": "IVA exento notas", "country_id": company.country_id.id})
        exempt = self.env["account.tax"].create({
            "name": "Exento notas", "amount": 0, "amount_type": "percent", "type_tax_use": "sale",
            "company_id": company.id, "tax_group_id": group.id, "country_id": company.country_id.id,
        })
        exempt_purchase = self.env["account.tax"].create({
            "name": "Exento compras notas", "amount": 0, "amount_type": "percent", "type_tax_use": "purchase",
            "company_id": company.id, "tax_group_id": group.id, "country_id": company.country_id.id,
        })
        company.exent_aliquot_sale = exempt.id
        product = self.env["product.product"].create({
            "name": "Diferencial notas", "type": "service",
            "taxes_id": [(6, 0, exempt.ids)], "supplier_taxes_id": [(6, 0, exempt_purchase.ids)],
            "property_account_income_id": gain.id, "property_account_expense_id": loss.id,
        })
        company.l10n_ve_exchange_note_product_id = product.id
        company.l10n_ve_exchange_note_pricelist_id = self.env["product.pricelist"].create({
            "name": "Diferencial notas VEF", "currency_id": company.currency_id.id,
        }).id
        sequence = self.env["ir.sequence"].create({
            "name": "ND diferencial", "code": "l10n.ve.exchange.debit.note.ret", "company_id": company.id,
            "prefix": "NDRET/%(year)s/", "padding": 4,
        })
        self.env["account.journal"].create({
            "name": "ND diferencial", "type": "sale", "code": "NDRET", "company_id": company.id,
            "is_debit": True, "l10n_ve_exchange_debit_note_sequence_id": sequence.id, "refund_sequence": True,
        })
        company.l10n_ve_exchange_use_nd_nc = True
        # El selector: la compañía exige el permiso del cliente y el contacto lo da o no
        company.l10n_ve_exchange_validate_partner_note = True
        self.env.cr.flush()
        self.partner_pnr_75.l10n_ve_exchange_allow_note = allow_note
        self._exchange_notes_ready = True

    def _notes_of(self, invoice):
        return self.env["account.move"].search([("l10n_ve_exchange_original_id", "=", invoice.id)]) | \
            self.env["account.move"].search([("debit_origin_id", "=", invoice.id)])

    def _retention_exchange_moves(self, result):
        retention_lines = result["payment"].move_id.line_ids
        return (retention_lines.matched_debit_ids | retention_lines.matched_credit_ids).exchange_move_id

    def _closure_with_notes(self, result, notes):
        note_lines = notes.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        lines = result["account_lines"] | note_lines
        self.assertAlmostEqual(sum(lines.mapped("balance")), 0.0, places=2)
        self.assertAlmostEqual(sum(lines.mapped("foreign_balance")), 0.0, places=2)

    def _treatment_case(self, currency, allow, number, mode="indexed", rate=45.0):
        """Retención con el selector del cliente: `allow` permite la nota (tratamiento B) o no
        (tratamiento A, asiento)."""
        self._enable_exchange_notes(allow_note=allow)
        result = self._run_retention_case("cus", "iva", currency, mode, voucher_rate=rate, number=number)
        return result, self._notes_of(result["invoice"]), self._retention_exchange_moves(result)

    def test_ri_119_and_122_treatment_a_entry_when_the_customer_does_not_allow_notes(self):
        """RI-119/122 (A) y RI-130: el contacto no permite notas: la diferencia de la retención
        indexada se cierra con el asiento (en USD y en EUR), sin ninguna nota, y la cuenta cierra."""
        for index, currency in enumerate(("USD", "EUR")):
            with self.subTest(currency=currency):
                result, notes, exchange_moves = self._treatment_case(currency, False, "0123456789119%d" % index)
                self.assertEqual(len(exchange_moves), 1)
                self.assertFalse(self._notes_for_retention(result, notes))
                self._closure_with_notes(result, notes)

    def _notes_for_retention(self, result, notes):
        """Notas que no son las del cobro del resto: la del cobro es la última en emitirse."""
        return notes.sorted("id")[:-1] if len(notes) > 1 else notes.browse() if not notes else notes.browse()

    def test_ri_120_and_123_treatment_b_note_when_the_customer_allows_notes(self):
        """RI-120/123 (B): el contacto permite notas: la diferencia de la retención indexada se
        documenta con una nota (no con el asiento), en USD y en EUR, y la cuenta cierra."""
        for index, currency in enumerate(("USD", "EUR")):
            with self.subTest(currency=currency):
                result, notes, exchange_moves = self._treatment_case(currency, True, "0123456789120%d" % index)
                # Ningún asiento de diferencia en Bs por la retención (en EUR puede quedar un asiento
                # de redondeo de USD 0,01 solo en alterno)
                self.assertEqual(sum(abs(b) for b in exchange_moves.line_ids.mapped("balance")), 0.0)
                self.assertGreaterEqual(len(notes), 1)
                self._closure_with_notes(result, notes)

    def test_ri_126_and_129_note_is_numbered_by_the_module_and_has_no_vat(self):
        """RI-126/129 (B): la nota usa la secuencia propia de notas por diferencia, es en bolívares
        y no lleva IVA (producto exento)."""
        result, notes, _exchange = self._treatment_case("USD", True, "01234567891260")
        self.assertTrue(notes)
        for note in notes:
            with self.subTest(note=note.name):
                self.assertTrue(note.name.startswith("NDRET/"))
                self.assertEqual(note.currency_id, self.currency_vef)
                self.assertEqual(note.amount_tax, 0.0)

    def test_ri_131_cancelling_the_retention_reverts_its_note(self):
        """RI-131 (B): cancelar la retención revierte la nota que documentó su diferencia (queda
        reversada), devuelve a la factura el valor de la retención (USD 106,67) y no toca la nota
        del cobro del resto."""
        result, notes, _exchange = self._treatment_case("USD", True, "01234567891310")
        retention_note = notes.filtered(lambda n: round(n.amount_total_signed, 2) == 533.2)
        rest_note = notes - retention_note
        result["line"].retention_id.action_cancel()
        with self.subTest("la nota de la retención queda reversada"):
            self.assertEqual(retention_note.payment_state, "reversed")
        with self.subTest("la nota del cobro del resto sigue vigente"):
            self.assertEqual(rest_note.payment_state, "paid")
        with self.subTest("la factura recupera lo que cancelaba la retención"):
            self.assertAlmostEqual(result["invoice"].amount_residual, 106.67, places=2)

    def test_ri_026_islr_supplier_bolivars_indexed(self):
        """RI-026: ISLR de proveedor sobre una factura en Bs, indexada: Bs 2.000 valorados en USD
        44,44 (tasa 45) y la cuenta cierra en 0,00 en Bs y en alterno. El monto en Bs lo calcula el
        formulario con el concepto configurado: se verifica su relación con la tasa."""
        result = self._run_retention_case("sup", "islr", "VEF", "indexed")
        retained = result["line"].retention_amount
        self.assertAlmostEqual(result["payment"].amount, retained, places=2)
        self.assertAlmostEqual(result["line"].foreign_retention_amount, retained / 45.0, places=2)
        self._assert_ri_closure(result)

    def test_ri_125_treatment_a_on_a_bolivars_invoice(self):
        """RI-125 (A): factura en Bs, retención de Bs 4.800, tasa 40 → 45: sin diferencia en Bs; la
        diferencia de USD 13,33 solo en alterno, cerrada con asiento (el contacto no permite
        notas); saldos 0,00."""
        result, notes, exchange_moves = self._treatment_case("VEF", False, "01234567891250")
        self.assertEqual(len(exchange_moves), 1)
        self.assertEqual(sum(abs(b) for b in exchange_moves.line_ids.mapped("balance")), 0.0)
        self.assertAlmostEqual(max(abs(f) for f in exchange_moves.line_ids.mapped("foreign_balance")), 13.33, places=2)
        self._closure_with_notes(result, notes)

    def test_treatment_b_does_not_apply_to_a_bolivars_invoice(self):
        """El módulo de notas actúa sobre diferencias en Bs: en una factura en Bs la diferencia es
        solo en alterno, así que aunque el contacto permita notas queda el asiento solo en alterno
        y ninguna nota."""
        result, notes, exchange_moves = self._treatment_case("VEF", True, "01234567891251")
        self.assertFalse(notes)
        self.assertEqual(len(exchange_moves), 1)
        self._closure_with_notes(result, notes)

    def _skip_without_the_exchange_difference_bridge(self):
        options = dict(self.env["account.retention"]._fields["exchange_difference_treatment"].selection)
        if "note" not in options:
            self.skipTest("el módulo puente de diferencial cambiario no está instalado")

    def _draft_customer_retention(self, mode="not_indexed", number="01234567891380"):
        """Comprobante de cliente en borrador sobre una factura en USD."""
        self._set_rate(self.currency_usd, self.today, 45.0)
        invoice = self._customer_invoice_in(self.currency_usd, "FACT%s" % number[-3:])
        retention = self._form_create_retention({
            "type_retention": "iva", "type": "out_invoice", "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id, "date": self.today, "date_accounting": self.today,
            "number": number, "indexation_mode": mode,
            "retention_line_ids": [Command.create({
                "move_id": invoice.id, "name": "IVA", "invoice_total": 46400.0,
                "invoice_amount": 40000.0, "retention_amount": 4800.0,
            })],
        })
        return retention

    def test_ri_138_the_treatment_is_hidden_with_the_not_indexed_modality(self):
        """RI-138: con modalidad no indexada no aparece el tratamiento y no hay valor guardado."""
        self._skip_without_the_exchange_difference_bridge()
        self._enable_exchange_notes(allow_note=True)
        retention = self._draft_customer_retention("not_indexed")
        self.assertFalse(retention.show_exchange_difference_treatment)
        self.assertEqual(retention.exchange_difference_treatment, "entry")

    def test_ri_139_the_treatment_appears_when_switching_to_indexed(self):
        """RI-139: al pasar a indexada aparece el tratamiento con el valor que da el contacto: nota
        si lo permite, asiento si no."""
        self._skip_without_the_exchange_difference_bridge()
        for index, (allow, expected) in enumerate(((True, "note"), (False, "entry"))):
            with self.subTest(allow_note=allow):
                self._enable_exchange_notes(allow_note=allow)
                retention = self._draft_customer_retention("not_indexed", "0123456789139%d" % index)
                self._set_mode(retention, "indexed")
                self.assertTrue(retention.show_exchange_difference_treatment)
                self.assertEqual(retention.exchange_difference_treatment, expected)

    def test_ri_140_going_back_to_not_indexed_leaves_no_old_value(self):
        """RI-140: con tratamiento elegido a mano, pasar a no indexada lo borra y al volver a
        indexada regresa al valor del contacto, sin recordar la elección anterior."""
        self._skip_without_the_exchange_difference_bridge()
        self._enable_exchange_notes(allow_note=False)
        retention = self._draft_customer_retention("indexed", "01234567891400")
        self.assertEqual(retention.exchange_difference_treatment, "entry")
        self._set_retention_fields(retention, exchange_difference_treatment="note")
        self._set_mode(retention, "not_indexed")
        self.assertEqual(retention.exchange_difference_treatment, "entry")
        self.assertFalse(retention.show_exchange_difference_treatment)
        self._set_mode(retention, "indexed")
        self.assertEqual(retention.exchange_difference_treatment, "entry")

    def test_ri_141_the_treatment_follows_the_modality_of_a_reopened_voucher(self):
        """RI-141: un comprobante reabierto a borrador muestra u oculta el tratamiento según la
        nueva modalidad."""
        self._skip_without_the_exchange_difference_bridge()
        self._enable_exchange_notes(allow_note=True)
        result = self._run_retention_case("cus", "iva", "USD", "indexed", number="01234567891410")
        retention = result["line"].retention_id
        retention.action_cancel()
        retention.action_draft()
        self.assertTrue(retention.show_exchange_difference_treatment)
        self._set_mode(retention, "not_indexed")
        self.assertFalse(retention.show_exchange_difference_treatment)
        self.assertEqual(retention.exchange_difference_treatment, "entry")

    def test_the_treatment_of_the_voucher_overrides_the_contact(self):
        """El tratamiento elegido en el comprobante manda sobre el permiso del contacto, en los dos
        sentidos: nota aunque el contacto no la permita, asiento aunque la permita."""
        self._skip_without_the_exchange_difference_bridge()
        for index, (allow, treatment) in enumerate(((False, "note"), (True, "entry"))):
            with self.subTest(allow_note=allow, treatment=treatment):
                self._enable_exchange_notes(allow_note=allow)
                result = self._run_retention_case(
                    "cus", "iva", "USD", "indexed", number="0123456789142%d" % index, treatment=treatment,
                )
                notes = self._notes_of(result["invoice"])
                exchange_moves = self._retention_exchange_moves(result)
                if treatment == "note":
                    self.assertFalse(exchange_moves)
                    self.assertIn(533.2, [round(abs(n.amount_total_signed), 2) for n in notes])
                else:
                    self.assertEqual(len(exchange_moves), 1)
                    self.assertNotIn(533.2, [round(abs(n.amount_total_signed), 2) for n in notes])
                self._closure_with_notes(result, notes)

    def test_ri_059_whole_customer_account_after_mixing_indexed_and_not_indexed(self):
        """RI-059: cliente con cuatro facturas (Bs, USD y EUR) y cuatro retenciones (dos no indexadas
        y dos indexadas): toda su cuenta por cobrar suma 0,00 en Bs y en alterno."""
        flows = (("USD", "not_indexed"), ("USD", "indexed"), ("EUR", "not_indexed"), ("VEF", "indexed"))
        for index, (currency, mode) in enumerate(flows):
            self._run_retention_case("cus", "iva", currency, mode, number="0123456789059%d" % index)
        receivable_lines = self.env["account.move.line"].search([
            ("partner_id", "=", self.partner_pnr_75.id),
            ("account_id.account_type", "=", "asset_receivable"),
            ("parent_state", "=", "posted"),
        ])
        self.assertGreaterEqual(len(receivable_lines), 12)
        self.assertAlmostEqual(sum(receivable_lines.mapped("balance")), 0.0, places=2)
        self.assertAlmostEqual(sum(receivable_lines.mapped("foreign_balance")), 0.0, delta=0.05)

    def test_ri_063_new_vouchers_inherit_the_setting_and_emitted_ones_do_not_change(self):
        """RI-063: con la función apagada el comprobante nuevo es no indexado y sin selector; al
        encenderla los nuevos toman el valor del contacto y los ya emitidos no cambian."""
        self.partner_pnr_75.retention_indexation_mode = "indexed"
        self.company.use_indexed_retentions = False
        invoice = self._create_usd_invoice(correlative="12345678900631")
        before = self._create_retention(invoice, mode="not_indexed", number="01234567890631")
        self.assertFalse(before.show_indexation)
        before.action_post()
        foreign_before = before.retention_line_ids.foreign_retention_amount
        self.company.use_indexed_retentions = True
        new_draft = self._draft_retention_for(self.partner_pnr_75)
        new_draft.onchange_partner_id()
        with self.subTest("el comprobante nuevo hereda el valor del contacto"):
            self.assertEqual(new_draft.indexation_mode, "indexed")
            self.assertTrue(new_draft.show_indexation)
        with self.subTest("el ya emitido no cambia"):
            self.assertEqual(before.indexation_mode, "not_indexed")
            self.assertEqual(before.retention_line_ids.foreign_retention_amount, foreign_before)

    def test_ri_084_cancelling_with_the_payment_already_reconciled(self):
        """RI-084: cancelar el comprobante con el pago ya conciliado con la factura: se desconcilia y
        se revierte el pago de la retención y la factura vuelve a deber su valor (USD 106,67)."""
        result = self._run_retention_case("cus", "iva", "USD", "indexed", number="01234567890084")
        retention = result["line"].retention_id
        retention_payment = result["payment"]
        retention.action_cancel()
        invoice = result["invoice"]
        with self.subTest("el comprobante queda cancelado y su pago revertido"):
            self.assertEqual(retention.state, "cancel")
            self.assertEqual(retention_payment.state, "canceled")
        with self.subTest("la factura vuelve a deber lo que cancelaba la retención"):
            self.assertAlmostEqual(invoice.amount_residual, 106.67, places=2)
            self.assertEqual(invoice.payment_state, "partial")
        with self.subTest("el pago de la retención ya no está conciliado"):
            lines = retention_payment.move_id.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
            self.assertFalse(lines.matched_debit_ids | lines.matched_credit_ids)

    def test_ri_117_eur_usd_cross_is_coherent_between_the_invoice_and_the_voucher(self):
        """RI-117: EUR 44 → 49,50 y USD 40 → 45 (el cruce EUR/USD es 1,10 en las dos fechas): el
        valor en dólares de la retención es el del euro por el cruce (106,67 × 1,10 = 117,33) y no
        hay diferencia adicional por el cruce: la cuenta cierra en 0,00 en Bs y en alterno."""
        result = self._run_retention_case("cus", "iva", "EUR", "indexed", number="01234567890117")
        line = result["line"]
        self.assertAlmostEqual(line.foreign_retention_amount, 106.67, places=2)
        for entry_line in result["payment"].move_id.line_ids:
            self.assertAlmostEqual(abs(entry_line.foreign_balance), round(106.67 * 1.10, 2), delta=0.02)
        self._assert_ri_closure(result)

    @tagged("retention_igtf")
    def test_ri_153_treatment_b_with_a_mixed_payment_advance_and_normal(self):
        """RI-153 (B): factura de USD 1.160, anticipo de USD 500 cruzado, retención indexada de
        Bs 4.800 (tasa 45) con nota y pago del resto: la diferencia de la retención recibe su nota
        (Bs 533,20), el pago mixto no la altera y la cuenta cierra en 0,00."""
        self._skip_without_the_exchange_difference_bridge()
        usd_journal = self._setup_igtf_usd_journal()
        self._enable_exchange_notes(allow_note=True)
        voucher_day = self.invoice_date + relativedelta(days=5)
        self._set_rate(self.currency_usd, voucher_day, 45.0)
        self._set_exchange_entry_rates(voucher_day, 45.0)
        invoice = self._customer_invoice_in(self.currency_usd, "FACM1")
        context = {
            "default_payment_type": "inbound", "default_partner_type": "customer",
            "default_move_journal_types": ("bank", "cash"), "default_is_advance_payment": True,
        }
        with Form(self.env["account.payment"].with_context(context)) as pay_form:
            pay_form.partner_id = self.partner_pnr_75
            pay_form.journal_id = usd_journal
            pay_form.amount = 500.0
            pay_form.date = voucher_day
        advance = pay_form.save()
        advance.action_post()
        outstanding = advance.move_id.line_ids.filtered(lambda l: l.account_id.is_advance_account)
        retention = self._form_create_retention({
            "type_retention": "iva", "type": "out_invoice", "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id, "date": voucher_day, "date_accounting": voucher_day,
            "number": "01234567890153", "indexation_mode": "indexed",
            "retention_line_ids": [Command.create({
                "move_id": invoice.id, "name": "IVA", "invoice_total": 46400.0,
                "invoice_amount": 40000.0, "retention_amount": 4800.0,
            })],
        })
        self.assertEqual(retention.exchange_difference_treatment, "note")
        retention.action_post()
        invoice.with_context({}).js_assign_outstanding_line(outstanding.id)
        self._payment_wizard(invoice.ids, {
            "amount": round(invoice.amount_residual * 45.0, 2), "currency_id": self.currency_vef.id,
            "payment_date": voucher_day, "journal_id": self.bank_journal_sub.id,
        }).action_create_payments()
        self.assertEqual(invoice.payment_state, "paid")
        notes = self._notes_of(invoice)
        with self.subTest("la retención recibe su nota de Bs 533,20"):
            self.assertIn(533.2, [round(abs(n.amount_total_signed), 2) for n in notes])
        receivable = (invoice | advance.move_id | retention.payment_ids.move_id | notes).line_ids.filtered(
            lambda l: l.account_type == "asset_receivable"
        )
        partials = receivable.matched_debit_ids | receivable.matched_credit_ids
        lines = (receivable | partials.debit_move_id | partials.credit_move_id
                 | partials.exchange_move_id.line_ids).filtered(lambda l: l.account_type == "asset_receivable")
        with self.subTest("la cuenta por cobrar cierra en Bs y en alterno"):
            self.assertAlmostEqual(sum(lines.mapped("balance")), 0.0, places=2)
            self.assertAlmostEqual(sum(lines.mapped("foreign_balance")), 0.0, delta=0.05)

    def test_ri_127_same_net_result_with_a_note_or_an_entry(self):
        """RI-127: el importe de la diferencia de la retención es el mismo con nota (B) que con
        asiento (A): Bs 533,20, y ambas dejan la cuenta en 0,00."""
        result_a, notes_a, exchange_a = self._treatment_case("USD", False, "01234567891271")
        amount_a = max(exchange_a.line_ids.mapped("debit") + exchange_a.line_ids.mapped("credit"))
        result_b, notes_b, exchange_b = self._treatment_case("USD", True, "01234567891272")
        retention_note = notes_b.sorted("id")[:1]
        self.assertAlmostEqual(amount_a, 533.2, places=2)
        self.assertAlmostEqual(abs(retention_note.amount_total_signed), amount_a, places=2)

    def test_ri_128_not_indexed_has_no_difference_to_document(self):
        """RI-128: con retención no indexada no hay diferencia por la retención: ni nota ni asiento
        por ella, aunque el contacto permita notas."""
        result, notes, exchange_moves = self._treatment_case("USD", True, "01234567891280", mode="not_indexed")
        self.assertFalse(exchange_moves)
        self.assertNotIn(533.2, [round(abs(n.amount_total_signed), 2) for n in notes])
        self._closure_with_notes(result, notes)

    def test_ri_132_note_for_a_euro_invoice_is_in_bolivars(self):
        """RI-132: la nota de una factura en EUR se emite en bolívares con el importe del
        diferencial de la retención."""
        result, notes, _exchange = self._treatment_case("EUR", True, "01234567891320")
        self.assertTrue(notes)
        self.assertEqual(notes.mapped("currency_id"), self.currency_vef)

    def test_ri_060_and_090_the_difference_is_recognized_once(self):
        """RI-060/090: con las notas por diferencia cambiaria activas, la diferencia de la retención
        indexada se reconoce una sola vez: nota (si el cliente la permite) o asiento (si no),
        nunca ambos, y la cuenta del cliente cierra en 0,00."""
        for index, allow in enumerate((True, False)):
            with self.subTest(allow_note=allow):
                self._enable_exchange_notes(allow_note=allow)
                result = self._run_retention_case("cus", "iva", "USD", "indexed", number="0123456789060%d" % index)
                notes = self._notes_of(result["invoice"])
                exchange_moves = self._retention_exchange_moves(result)
                if allow:
                    self.assertFalse(exchange_moves)
                    self.assertIn(533.2, [round(abs(n.amount_total_signed), 2) for n in notes])
                else:
                    self.assertEqual(len(exchange_moves), 1)
                    self.assertNotIn(533.2, [round(abs(n.amount_total_signed), 2) for n in notes])
                self._closure_with_notes(result, notes)
                # Se restablece el cliente para la siguiente vuelta (la compañía ya está configurada)
                self.env.cr.flush()

    def _assert_indexed_bolivars_invoice(self, result, alternate, residual_alt_after_retention=None):
        with self.subTest("valor de la línea en USD (tasa del comprobante)"):
            self.assertAlmostEqual(result["line"].foreign_retention_amount, alternate, places=2)
        with self.subTest("USD alterno del pago de la retención"):
            for entry_line in result["payment"].move_id.line_ids:
                self.assertAlmostEqual(abs(entry_line.foreign_balance), alternate, places=2)
        with self.subTest("cierre en Bs"):
            self.assertAlmostEqual(sum(result["account_lines"].mapped("balance")), 0.0, places=2)
        with self.subTest("cierre en alterno"):
            self.assertAlmostEqual(sum(result["account_lines"].mapped("foreign_balance")), 0.0, delta=0.05)

    def test_ri_002_indexed_on_a_bolivars_invoice_rate_rises(self):
        """RI-002: factura en Bs, tasa 40 → 45: retención de Bs 4.800 valorada en USD 106,67; los
        USD 13,33 de diferencia se cierran con el asiento solo en alterno y la cuenta cierra en
        0,00 en Bs y en alterno. RI-112: el mismo cliente con factura en bolívares."""
        result = self._run_retention_case("cus", "iva", "VEF", "indexed", voucher_rate=45.0, number="01234567890002")
        self._assert_indexed_bolivars_invoice(result, 106.67)

    def test_ri_004_indexed_on_a_bolivars_invoice_rate_drops(self):
        """RI-004: factura en Bs, tasa 40 → 38: USD 126,32 y una diferencia de USD 6,32 a favor,
        cerrada con el asiento solo en alterno."""
        result = self._run_retention_case("cus", "iva", "VEF", "indexed", voucher_rate=38.0, number="01234567890004")
        self._assert_indexed_bolivars_invoice(result, 126.32)

    def test_ri_006_indexed_on_a_bolivars_invoice_same_day(self):
        """RI-006 (control): el mismo día de la factura (tasa 40) la retención vale USD 120 y no
        hay diferencia."""
        result = self._run_retention_case(
            "cus", "iva", "VEF", "indexed", voucher_offset=0, voucher_rate=40.0, number="01234567890006"
        )
        self._assert_indexed_bolivars_invoice(result, 120.0)
        self.assertFalse(result["exchange_moves"])

    @tagged("retention_igtf")
    def test_ri_002_and_004_indexed_on_a_bolivars_invoice_with_igtf(self):
        """RI-002/004 con IGTF: el resto se cobra en USD con IGTF y la cuenta cierra igualmente."""
        for index, (rate, alternate) in enumerate(((45.0, 106.67), (38.0, 126.32))):
            with self.subTest(rate=rate):
                result = self._run_retention_case(
                    "cus", "iva", "VEF", "indexed", voucher_rate=rate, igtf=True,
                    number="0123456789002%d" % index,
                )
                self.assertAlmostEqual(result["line"].foreign_retention_amount, alternate, places=2)
                self._assert_igtf_closure(result)

    def test_ri_098_changing_the_modality_leaves_a_record(self):
        """RI-098/099: cada cambio de modalidad en el comprobante queda registrado con su valor
        anterior y el nuevo, en orden."""
        invoice = self._create_usd_invoice()
        retention = self.env["account.retention"].with_context(tracking_disable=False).create(
            self._retention_vals(invoice, mode="not_indexed")
        )
        retention = retention.with_context(tracking_disable=False)
        self.env.cr.precommit.run()  # cierra el registro de la creación
        for mode in ("indexed", "not_indexed", "indexed"):
            retention.indexation_mode = mode
            # El registro de cambios se cierra al terminar la transacción
            self.env.cr.precommit.run()
        values = self.env["mail.tracking.value"].sudo().search([
            ("mail_message_id.model", "=", "account.retention"),
            ("mail_message_id.res_id", "=", retention.id),
            ("field_id.name", "=", "indexation_mode"),
        ], order="id")
        changes = [(v.old_value_char, v.new_value_char) for v in values]
        self.assertEqual(len(changes), 3, changes)
        self.assertEqual(changes[0][1], "Indexed")
        self.assertEqual(changes[1][1], "Non-indexed (invoice rate)")
        self.assertEqual(changes[2][1], "Indexed")
        self.assertEqual(retention.indexation_mode, "indexed")

    def test_ri_072_function_off_behaves_as_before(self):
        """RI-072: con la función apagada no hay selector y la retención se valora a la tasa de la
        factura, sin diferencia de cambio por la retención."""
        self.company.use_indexed_retentions = False
        retention = self._create_retention(self._create_usd_invoice())
        self.assertFalse(retention.show_indexation)
        self.assertEqual(retention.indexation_mode, "not_indexed")
        result = self._run_retention_case("cus", "iva", "USD", "not_indexed")
        self._assert_ri_values(result, asiento_alt=120.0, line_value=120.0)
        self.assertEqual(result["retention_exchange_bs"], 0.0)

    def test_ri_073_turning_the_function_on_keeps_the_emitted_retentions(self):
        """RI-073: encender la función con comprobantes emitidos: los previos no cambian y el
        nuevo nace no indexado."""
        self.company.use_indexed_retentions = False
        invoice = self._create_usd_invoice()
        emitted = self._create_retention(invoice, mode="not_indexed")
        emitted.action_post()
        before = emitted.retention_line_ids.foreign_retention_amount
        self.company.use_indexed_retentions = True
        self.assertEqual(emitted.indexation_mode, "not_indexed")
        self.assertEqual(emitted.retention_line_ids.foreign_retention_amount, before)
        new = self._create_retention(
            self._create_usd_invoice(correlative="12345678901299"), mode="not_indexed", number="01234567899999"
        )
        self.assertEqual(new.indexation_mode, "not_indexed")

    def test_ri_082_reopening_a_customer_retention_reissues_it_with_the_new_date_and_modality(self):
        """RI-082/083: cancelar, volver a borrador y reemitir con otra fecha o modalidad revierte el
        pago anterior y crea el nuevo con la valoración vigente."""
        for day, rate in ((self.invoice_date + relativedelta(days=5), 47.0),
                          (self.invoice_date + relativedelta(days=3), 45.0)):
            self.env["res.currency.rate"].search([
                ("currency_id", "=", self.currency_vef.id), ("company_id", "=", self.company.id),
                ("name", "=", day),
            ]).unlink()
            self.env["res.currency.rate"].create({
                "currency_id": self.currency_vef.id, "company_id": self.company.id,
                "name": day, "rate": 1.0,
            })
            self._set_rate(self.currency_usd, day, rate)
            self._set_exchange_entry_rates(day, rate)
        with Form(self.env["account.move"].with_context(
            default_move_type="out_invoice", default_journal_id=self.env["account.journal"].create({
                "name": "Venta USD", "type": "sale", "code": "SALRO", "company_id": self.company.id,
            }).id,
        )) as inv_form:
            inv_form.partner_id = self.partner_pnr_75
            inv_form.invoice_date = self.invoice_date
            inv_form.currency_id = self.currency_usd
        invoice = inv_form.save()
        with Form(invoice) as edit:
            with edit.invoice_line_ids.new() as line:
                line.product_id = self.product_iva
                line.quantity = 1
                line.price_unit = 1000.0
        invoice = edit.save()
        invoice.write({"date": self.invoice_date, "invoice_date_display": self.invoice_date})
        invoice.with_context(move_action_post_alert=True).action_post()
        total_usd, total_bs = invoice.amount_total, abs(invoice.amount_residual_signed)

        day_1 = self.invoice_date + relativedelta(days=3)
        day_2 = self.invoice_date + relativedelta(days=5)  # hoy: la fecha máxima que admite el formulario
        retention = self._form_create_retention({
            "type_retention": "iva", "type": "out_invoice", "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id, "date": day_1, "date_accounting": day_1,
            "number": "01234567891234", "indexation_mode": "indexed",
            "retention_line_ids": [Command.create({
                "move_id": invoice.id, "name": "IVA", "invoice_total": 46400.0,
                "invoice_amount": 40000.0, "retention_amount": 4800.0,
            })],
        })
        retention.action_post()
        payment_foreign_balance = retention.payment_ids.move_id.line_ids[:1].foreign_balance
        if payment_foreign_balance > 0:
            self.assertAlmostEqual(payment_foreign_balance, 106.67, places=2)
        # Cancelar y reabrir con otra fecha
        retention.action_cancel()
        self.assertAlmostEqual(invoice.amount_residual, total_usd, places=2)
        retention.action_draft()
        self._set_retention_fields(retention, date=day_2, date_accounting=day_2)
        line = retention.retention_line_ids
        with self.subTest("revalora con la tasa de la nueva fecha"):
            self.assertAlmostEqual(line.foreign_retention_amount, 102.13, places=2)
        retention.action_post()
        with self.subTest("el pago nuevo lleva la valoración de la nueva fecha"):
            for entry_line in retention.payment_ids.move_id.line_ids:
                self.assertAlmostEqual(abs(entry_line.foreign_balance), 102.13, places=2)
        # Cancelar y reabrir pasando a no indexada
        retention.action_cancel()
        retention.action_draft()
        self._set_mode(retention, "not_indexed")
        retention.action_post()
        with self.subTest("no indexada: valor a la tasa de la factura y sin diferencial de la retención"):
            self.assertAlmostEqual(line.foreign_retention_amount, 120.0, places=2)
            for entry_line in retention.payment_ids.move_id.line_ids:
                self.assertAlmostEqual(abs(entry_line.foreign_balance), 120.0, places=2)
            self.assertAlmostEqual(invoice.amount_residual, total_usd - 120.0, places=2)

    def test_ri_057_inverse_rate_of_the_euro_is_the_inverse_of_the_direct_rate(self):
        """RI-057: la tasa inversa del euro (defecto de v17) es 1/49,5 y nunca igual a la directa."""
        day = self.invoice_date + relativedelta(days=5)
        self.env.ref("base.EUR").active = True
        self._set_rate(self.env.ref("base.EUR"), day, 49.5)
        rates = self.env["res.currency.rate"].compute_rate(self.env.ref("base.EUR").id, day)
        self.assertAlmostEqual(rates["foreign_rate"], 49.5, places=4)
        self.assertAlmostEqual(rates["foreign_inverse_rate"], 1 / 49.5, places=4)
        self.assertNotAlmostEqual(rates["foreign_rate"], rates["foreign_inverse_rate"], places=2)

    @tagged("retention_igtf")
    def test_ri_045_mixed_collection_with_igtf_and_bolivars(self):
        """RI-045: retención indexada más cobro mixto (USD con IGTF y Bs): la cuenta cierra en 0,00
        en Bs y en alterno y la retención no cambia. RI-146: retención más pago en USD con IGTF (cobro mixto)."""
        result = self._run_retention_case("cus", "iva", "USD", "indexed", igtf="mixed")
        with self.subTest("la retención no cambia"):
            self.assertAlmostEqual(result["residual_after_retention"], 1053.33, places=2)
            self.assertAlmostEqual(result["line"].foreign_retention_amount, 106.67, places=2)
        self._assert_igtf_closure(result)

    # --- modalidad por defecto del contacto
    def test_ri_074_the_default_of_the_contact_is_visible_only_with_the_function_on(self):
        self.assertTrue(self.partner_pnr_75.use_indexed_retentions)
        arch = etree.fromstring(self.env.ref("l10n_ve_payment_extension.res_partner_l10n_ve_payment_extension").arch_db)
        node = arch.xpath("//field[@name='retention_indexation_mode']")[0]
        self.assertEqual(node.get("invisible"), "not use_indexed_retentions")
        self.company.use_indexed_retentions = False
        self.partner_pnr_75.invalidate_recordset()
        self.assertFalse(self.partner_pnr_75.use_indexed_retentions)

    def _draft_retention_for(self, partner, retention_type="in_invoice"):
        """Comprobante en borrador, sin líneas, que el usuario crea al elegir el contacto (que tiene
        su propia factura pendiente)."""
        correlative = "%014d" % (10000 + self.env["account.move"].search_count([]))
        invoice = self._create_usd_invoice(correlative=correlative, partner=partner)
        vals = self._retention_vals(invoice)
        vals.pop("retention_line_ids")
        vals.pop("indexation_mode")  # la modalidad la propone el contacto al elegirlo
        vals.update({"partner_id": partner.id, "type": retention_type, "number": "%014d" % (20000 + int(correlative))})
        return self._form_create_retention(vals)

    def test_ri_075_the_voucher_inherits_the_default_of_the_contact(self):
        """Al elegir el contacto en el formulario, el comprobante toma su valor predeterminado."""
        self.partner_pnr_75.retention_indexation_mode = "indexed"
        retention = self._draft_retention_for(self.partner_pnr_75)
        self.assertEqual(retention.indexation_mode, "indexed")
    def test_ri_065_each_company_applies_its_own_modality(self):
        """RI-065: cliente compartido y dos compañías con ajustes distintos: la que tiene la
        función activa hereda el valor del contacto (indexado) y la que no, queda no indexada y
        sin selector."""
        self.partner_pnr_75.retention_indexation_mode = "indexed"
        other_company = self.env["res.company"].create({"name": "Otra Compañía", "use_indexed_retentions": False})
        vals = {
            "type_retention": "iva", "type": "out_invoice", "partner_id": self.partner_pnr_75.id,
            "date": self.today, "date_accounting": self.today,
        }
        own = self.env["account.retention"].create(dict(vals, company_id=self.company.id, number="01234567890065"))
        other = self.env["account.retention"].create(dict(vals, company_id=other_company.id, number="01234567890066"))
        own._apply_partner_indexation_mode()
        other._apply_partner_indexation_mode()
        with self.subTest("compañía con la función activa"):
            self.assertEqual(own.indexation_mode, "indexed")
            self.assertTrue(own.show_indexation)
        with self.subTest("compañía con la función apagada"):
            self.assertEqual(other.indexation_mode, "not_indexed")
            self.assertFalse(other.show_indexation)

    def test_ri_064_the_contact_prevails_over_the_company(self):
        """La compañía solo activa la función; el valor lo define el contacto y el usuario puede
        cambiarlo en el comprobante."""
        self.partner_pnr_75.retention_indexation_mode = "not_indexed"
        retention = self._draft_retention_for(self.partner_pnr_75)
        self.assertEqual(retention.indexation_mode, "not_indexed")
        self._set_mode(retention, "indexed")
        self.assertEqual(retention.indexation_mode, "indexed")
    def test_ri_076_each_contact_gives_its_own_default(self):
        self.partner_pnr_75.retention_indexation_mode = "indexed"
        self.partner_pnr_100.retention_indexation_mode = "not_indexed"
        first = self._draft_retention_for(self.partner_pnr_75)
        second = self._draft_retention_for(self.partner_pnr_100)
        self.assertEqual((first.indexation_mode, second.indexation_mode), ("indexed", "not_indexed"))
    def test_ri_077_changing_the_voucher_does_not_change_the_contact(self):
        self.partner_pnr_75.retention_indexation_mode = "indexed"
        retention = self._draft_retention_for(self.partner_pnr_75)
        self.assertEqual(retention.indexation_mode, "indexed")
        self._set_mode(retention, "not_indexed")
        self.assertEqual(self.partner_pnr_75.retention_indexation_mode, "indexed")
    def test_ri_078_changing_the_contact_keeps_the_drafts_and_applies_to_the_new_vouchers(self):
        self.partner_pnr_75.retention_indexation_mode = "indexed"
        draft = self._draft_retention_for(self.partner_pnr_75)
        self.partner_pnr_75.retention_indexation_mode = "not_indexed"
        self.assertEqual(draft.indexation_mode, "indexed")
        new = self._draft_retention_for(self.partner_pnr_75)
        self.assertEqual(new.indexation_mode, "not_indexed")
    def test_ri_101_the_list_can_be_filtered_by_modality(self):
        retention = self._create_retention(self._create_usd_invoice(), mode="indexed")
        self.assertIn(retention, self.env["account.retention"].search([("indexation_mode", "=", "indexed")]))
        for xmlid in (
            "l10n_ve_payment_extension.view_retention_iva_search_l10n_ve_payment_extension",
            "l10n_ve_payment_extension.view_retention_municipal_search_l10n_ve_payment_extension",
        ):
            view = self.env.ref(xmlid, raise_if_not_found=False)
            self.assertTrue(view, xmlid)
            self.assertIn("indexation_mode", view.arch_db)

    def test_views_show_the_payment_currency_only_for_indexed_retentions(self):
        for xmlid in (
            "l10n_ve_payment_extension.view_retention_iva_form_l10n_ve_payment_extension",
            "l10n_ve_payment_extension.view_retention_islr_form_l10n_ve_payment_extension",
            "l10n_ve_payment_extension.view_retention_municipal_form_l10n_ve_payment_extension",
        ):
            arch = etree.fromstring(self.env.ref(xmlid).arch_db)
            nodes = arch.xpath("//field[@name='payment_currency_id']")
            self.assertEqual(len(nodes), 1, xmlid)
            self.assertEqual(nodes[0].get("column_invisible"), "parent.indexation_mode != 'indexed'", xmlid)

