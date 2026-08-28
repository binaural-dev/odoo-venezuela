from odoo import Command, fields
from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase


@tagged("l10n_ve_exchange_difference", "-at_install", "post_install")
class TestExchangeDifferenceWithIGTF(TransactionCase):
    """Fixture PROPIO de este archivo, autocontenido -- ya NO hereda de
    `IGTFTestCommon` (`l10n_ve_igtf/tests/test_igtf_common_partner_formal_VEF.py`).
    Ese fixture compartido tiene helpers (`get_or_create_account`, que
    busca por `code` SIN filtrar por compañía; `_create_invoice_usd`/
    `_create_invoice_vef`, que buscan "cualquier diario `type='sale'`" sin
    excluir diarios dedicados de ND) que en una base compartida y reusada
    entre corridas (`lloro`) colisionan con fixtures de OTROS archivos --
    confirmado empíricamente: la búsqueda de diario de venta de
    `IGTFTestCommon` encontraba el propio diario dedicado de ND de este
    módulo (`is_debit=True`, también `type='sale'`) y posteaba facturas
    normales ahí, numerándolas con la secuencia dedicada de la ND y
    produciendo `UniqueViolation` en `account_move_unique_name`.

    Este archivo replica el MISMO patrón de configuración de
    `IGTFTestCommon` (moneda alterna, tasas de hoy/ayer, IGTF activo con
    `igtf_percentage`/`customer_account_igtf_id`, diario de banco USD con
    `is_igtf=True`) pero con cuentas/diarios/impuestos propios (sufijo
    "XIGTF"), sin depender de ningún `search()` sin scope."""

    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")
        self.currency_vef = self.env.ref("base.VEF")
        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef.write({"rounding": 0.01, "decimal_places": 2, "active": True})
        self.currency_usd.write({"rounding": 0.01, "decimal_places": 2})

        # Tasas de hoy/ayer -- `rate` explícito en AMBAS entradas: el
        # `inverse` de `company_rate` (núcleo, `_inverse_company_rate`)
        # compone `rate = company_rate * last_rate[company]` usando la
        # tasa ya creada en el mismo batch como referencia si no se fija
        # `rate` directo (mismo bug ya documentado y corregido en
        # `IGTFTestCommon.setUp`, replicado aquí con el fix ya aplicado
        # desde el principio).
        self.rate = 390.2944
        self.currency_usd.write({
            "active": True,
            "rate_ids": [
                Command.create({
                    "name": fields.Date.today(),
                    "company_rate": 1 / self.rate,
                    "rate": 1 / self.rate,
                    "inverse_company_rate": self.rate,
                }),
                Command.create({
                    "name": fields.Date.subtract(fields.Date.today(), days=1),
                    "company_rate": 1 / 380.0,
                    "rate": 1 / 380.0,
                    "inverse_company_rate": 380.0,
                }),
            ],
        })

        self.company.write({
            "currency_id": self.currency_vef.id,
            "foreign_currency_id": self.currency_usd.id,
            "taxpayer_type": "formal",
            "country_id": self.company.country_id.id or self.env.ref("base.ve").id,
        })

        # Cuentas base -- creadas explícitas con `company_ids`, códigos
        # EXCLUSIVOS de este archivo (sufijo "XIGTF") para no colisionar
        # ni con las de `test_exchange_note_reversal.py` (sufijo "REV")
        # ni con las que crea `IGTFTestCommon` (sin sufijo) para los
        # tests de `l10n_ve_igtf` que sí siguen usando ese fixture.
        self.acc_receivable = self.env["account.account"].create({
            "name": "Cuentas por Cobrar Test IGTF Own",
            "code": "1101XIGTF",
            "account_type": "asset_receivable",
            "reconcile": True,
            "company_ids": [Command.set([self.company.id])],
        })
        self.acc_payable = self.env["account.account"].create({
            "name": "Cuentas por Pagar Test IGTF Own",
            "code": "2101XIGTF",
            "account_type": "liability_payable",
            "reconcile": True,
            "company_ids": [Command.set([self.company.id])],
        })
        self.acc_income = self.env["account.account"].create({
            "name": "Ingresos Test IGTF Own",
            "code": "4001XIGTF",
            "account_type": "income",
            "company_ids": [Command.set([self.company.id])],
        })
        self.acc_igtf_cli = self.env["account.account"].create({
            "name": "IGTF Clientes Test IGTF Own",
            "code": "236XIGTF",
            "account_type": "liability_current",
            "company_ids": [Command.set([self.company.id])],
        })
        self.account_bank_usd = self.env["account.account"].create({
            "name": "Banco USD Test IGTF Own",
            "code": "1002XIGTF",
            "account_type": "asset_cash",
            "company_ids": [Command.set([self.company.id])],
        })
        # `is_advance_account=True` -- exigido por
        # `account.payment._onchange_journal_id` (`l10n_ve_igtf/models/account_payment.py`)
        # en cuanto el diario usado es `is_igtf=True`: sin este flag en la
        # cuenta destino, el `Form` del pago revienta con `UserError`
        # ("the destination account must be is_advance_account") al
        # asignar el diario, antes de llegar siquiera a la lógica de
        # anticipos que este test prueba.
        self.advance_cust_acc = self.env["account.account"].create({
            "name": "Anticipo Clientes Test IGTF Own",
            "code": "21600XIGTF",
            "account_type": "liability_current",
            "reconcile": True,
            "is_advance_account": True,
            "company_ids": [Command.set([self.company.id])],
        })
        self.advance_supp_acc = self.env["account.account"].create({
            "name": "Anticipo Proveedores Test IGTF Own",
            "code": "13600XIGTF",
            "account_type": "asset_current",
            "reconcile": True,
            "is_advance_account": True,
            "company_ids": [Command.set([self.company.id])],
        })

        self.journal_anticipo = self.env["account.journal"].create({
            "name": "Anticipo Clientes Test IGTF Own",
            "code": "ANTIXIGT",
            "type": "general",
            "company_id": self.company.id,
        })

        self.company.write({
            "igtf_percentage": 3.0,
            "customer_account_igtf_id": self.acc_igtf_cli.id,
            "advance_customer_account_id": self.advance_cust_acc.id,
            "advance_supplier_account_id": self.advance_supp_acc.id,
            "advance_payment_igtf_journal_id": self.journal_anticipo.id,
        })

        manual_in = self.env.ref("account.account_payment_method_manual_in")
        manual_out = self.env.ref("account.account_payment_method_manual_out")

        self.bank_journal_usd = self.env["account.journal"].create({
            "name": "Banco USD Test IGTF Own",
            "code": "BUSDXIGT",
            "type": "bank",
            "currency_id": self.currency_usd.id,
            "company_id": self.company.id,
            "is_igtf": True,
            "default_account_id": self.account_bank_usd.id,
            "inbound_payment_method_line_ids": [(5, 0, 0), (0, 0, {
                "name": "Manual Inbound USD Test IGTF Own",
                "payment_method_id": manual_in.id,
                "payment_account_id": self.account_bank_usd.id,
            })],
            "outbound_payment_method_line_ids": [(5, 0, 0), (0, 0, {
                "name": "Manual Outbound USD Test IGTF Own",
                "payment_method_id": manual_out.id,
                "payment_account_id": self.account_bank_usd.id,
            })],
        })

        self.partner = self.env["res.partner"].create({
            "name": "Cliente IGTF Own",
            "vat": "J123XIGTF",
            "property_account_receivable_id": self.acc_receivable.id,
            "property_account_payable_id": self.acc_payable.id,
            "taxpayer_type": "formal",
            "default_advance_customer_account_id": self.advance_cust_acc.id,
            "default_advance_supplier_account_id": self.advance_supp_acc.id,
        })

        self.tax_group = self.env["account.tax.group"].create({
            "name": "IVA Test IGTF Own",
            "country_id": self.company.country_id.id,
        })
        exent = self.env["account.tax"].create({
            "name": "IVA exento Test IGTF Own",
            "amount": 0,
            "amount_type": "percent",
            "type_tax_use": "sale",
            "company_id": self.company.id,
            "tax_group_id": self.tax_group.id,
            "country_id": self.company.country_id.id,
        })
        # `supplier_taxes_id` explícito: sin esto, el default que arma
        # Odoo para ese campo en `create()` puede traer más de un
        # impuesto de compra al 0% en bases con varios configurados, y
        # `l10n_ve_accountant` (`_enforce_single_tax_vals`) rechaza
        # cualquier producto con más de un impuesto de compra asignado.
        exent_purchase = self.env["account.tax"].create({
            "name": "Compra exenta Test IGTF Own",
            "amount": 0,
            "amount_type": "percent",
            "type_tax_use": "purchase",
            "company_id": self.company.id,
            "tax_group_id": self.tax_group.id,
            "country_id": self.company.country_id.id,
        })
        self.company.exent_aliquot_sale = exent.id

        self.product = self.env["product.product"].create({
            "name": "Servicio Test IGTF Own",
            "type": "service",
            "list_price": 100,
            "property_account_income_id": self.acc_income.id,
            "taxes_id": [(6, 0, [exent.id])],
            "supplier_taxes_id": [(6, 0, exent_purchase.ids)],
        })

        # Diario de venta EXPLÍCITO -- NO se busca "cualquier diario
        # `type='sale'`" (el bug real que colisionaba con el diario
        # dedicado de ND creado más abajo, ambos `type='sale'`): se crea
        # uno propio y se usa directo como `default_journal_id` en
        # `_create_invoice_usd`/`_create_invoice_vef`.
        # `refund_sequence: True` -- desde el fix de B5 (revisión de
        # código), `_create_exchange_difference_note` YA NO autoprovisiona
        # `refund_sequence_id` en silencio sobre el diario de venta al
        # emitir una NC (rama de pérdida cambiaria): ahora exige que esté
        # configurado de antemano, igual que exige la secuencia dedicada
        # de ND. `od_journal_sequence.account_journal.create()` la
        # autogenera acá mismo cuando el diario nace con
        # `refund_sequence=True` (`type='sale'`).
        self.sale_journal = self.env["account.journal"].create({
            "name": "Ventas Test IGTF Own",
            "code": "VXIGTF",
            "type": "sale",
            "company_id": self.company.id,
            "refund_sequence": True,
        })

        # Cuentas de ganancia/pérdida cambiaria propias -- NO se asume
        # que `company.income_currency_exchange_account_id`/
        # `expense_currency_exchange_account_id` (campos nativos de
        # Odoo, Ajustes > Contabilidad > Cuentas por Defecto) ya vengan
        # configurados por el chart of accounts de la base: en al menos
        # un entorno real quedaron vacíos, dejando el producto de la
        # nota SIN cuenta y reventando el `CHECK`
        # `account_move_line_check_accountable_required_fields` de
        # Postgres al crear la ND/NC.
        self.acc_exchange_gain = self.env["account.account"].create({
            "name": "Ganancia Cambiaria Test IGTF",
            "code": "76001TIGTF",
            "account_type": "income_other",
            "company_ids": [Command.set([self.company.id])],
        })
        self.acc_exchange_loss = self.env["account.account"].create({
            "name": "Pérdida Cambiaria Test IGTF",
            "code": "66001TIGTF",
            "account_type": "expense",
            "company_ids": [Command.set([self.company.id])],
        })
        # `company.currency_exchange_journal_id` -- campo NATIVO de Odoo
        # (diario "Ganancia o Pérdida en Cambio"), exigido por el propio
        # núcleo (`_create_exchange_difference_moves`,
        # `account/models/account_move_line.py`) ANTES de que este
        # módulo intercepte la creación de la ND/NC: sin él configurado,
        # Odoo revienta con `UserError` aun con `l10n_ve_exchange_use_nd_nc`
        # ya activo. Distinto de las CUENTAS de ganancia/pérdida -- este
        # es el DIARIO donde Odoo registraría su asiento genérico si este
        # módulo no lo redirigiera.
        self.exchange_journal = self.env["account.journal"].create({
            "name": "Diferencial Cambiario Test IGTF",
            "type": "general",
            "code": "EXCHXIGT",
            "company_id": self.company.id,
        })
        self.company.write({
            "income_currency_exchange_account_id": self.acc_exchange_gain.id,
            "expense_currency_exchange_account_id": self.acc_exchange_loss.id,
            "currency_exchange_journal_id": self.exchange_journal.id,
        })

        self.note_product = self.env["product.product"].create({
            "name": "Diferencial Test IGTF",
            "type": "service",
            "taxes_id": [(6, 0, exent.ids)],
            "supplier_taxes_id": [(6, 0, exent_purchase.ids)],
            "property_account_income_id": self.acc_exchange_gain.id,
            "property_account_expense_id": self.acc_exchange_loss.id,
        })
        # `property_account_income_id`/`property_account_expense_id`
        # son campos "Properties" (`ir.property`, no columnas planas de
        # `product.template`): el valor pasado en `create()` queda
        # registrado para `self.env.company`, NO necesariamente para
        # `self.company` -- se re-escribe explícito con
        # `with_company(self.company)` para forzar el scope correcto sin
        # importar la compañía activa del entorno.
        self.note_product.with_company(self.company).write({
            "property_account_income_id": self.acc_exchange_gain.id,
            "property_account_expense_id": self.acc_exchange_loss.id,
        })
        self.company.l10n_ve_exchange_note_product_id = self.note_product.id

        self.note_pricelist = self.env["product.pricelist"].create({
            "name": "Diferencial Test IGTF (VEF)",
            "currency_id": self.company.currency_id.id,
        })
        self.company.l10n_ve_exchange_note_pricelist_id = self.note_pricelist.id

        # Diario dedicado de ND con secuencia propia -- requerido desde
        # el fix del bloqueante de numeración (ver
        # `test_exchange_note_reversal.setUpClass`): sin esto, cualquier
        # escenario de este archivo que termine en rama de GANANCIA (ND)
        # fallaría con UserError en vez de la nota.
        self.debit_note_sequence = self.env["ir.sequence"].create({
            "name": "ND Diferencial Cambiario Test IGTF",
            "code": "l10n.ve.exchange.debit.note.test.igtf",
            "company_id": self.company.id,
            "prefix": "NDDIFTIGTF/%(year)s/",
            "padding": 4,
        })
        self.debit_note_journal = self.env["account.journal"].create({
            "name": "ND Diferencial Cambiario Test IGTF",
            "type": "sale",
            "code": "NDDIFTIGTF",
            "company_id": self.company.id,
            "is_debit": True,
            "l10n_ve_exchange_debit_note_sequence_id": self.debit_note_sequence.id,
            # Ver `test_exchange_note_reversal.setUpClass` -- revertir una
            # ND ya no autoprovisiona `refund_sequence_id` en silencio.
            "refund_sequence": True,
        })
        # El toggle se activa DESPUÉS de que el diario dedicado (con
        # AMBAS secuencias) ya existe -- `_check_l10n_ve_exchange_debit_journal_sequences`
        # (`res_company.py`) valida esto al GUARDAR el toggle, no solo en
        # tiempo de conciliación.
        self.company.l10n_ve_exchange_use_nd_nc = True

    def _create_invoice_usd(self, amount, date=None):
        """Mismo patrón de dos pasos (`Form` para encabezado, segundo
        `Form` sobre el registro guardado para las líneas) que usaba
        `IGTFTestCommon._create_invoice_usd` -- pero con `self.sale_journal`
        (creado explícito arriba) en vez de buscar "cualquier diario
        `type='sale'`"."""
        with Form(self.env["account.move"].with_context(
            default_move_type="out_invoice", default_journal_id=self.sale_journal.id,
        )) as inv_form:
            inv_form.partner_id = self.partner
            inv_form.invoice_date = date or fields.Date.today()
            inv_form.currency_id = self.currency_usd
        invoice = inv_form.save()

        with Form(invoice) as inv_form_edit:
            with inv_form_edit.invoice_line_ids.new() as line:
                line.product_id = self.product
                line.quantity = 1
                line.price_unit = amount
        return inv_form_edit.save()

    def _create_invoice_vef(self, amount, date=None):
        with Form(self.env["account.move"].with_context(
            default_move_type="out_invoice", default_journal_id=self.sale_journal.id,
        )) as inv_form:
            inv_form.partner_id = self.partner
            inv_form.invoice_date = date or fields.Date.today()
            inv_form.currency_id = self.currency_vef
        invoice = inv_form.save()

        with Form(invoice) as inv_form_edit:
            with inv_form_edit.invoice_line_ids.new() as line:
                line.product_id = self.product
                line.quantity = 1
                line.price_unit = amount
        return inv_form_edit.save()

    def test_fixture_usd_rates_are_not_compounded(self):
        """Regresión para un bug real encontrado ORIGINALMENTE en el
        fixture compartido `IGTFTestCommon.setUp`: al crear dos
        `res.currency.rate` para USD en el MISMO `write()` (hoy con
        `rate`/`company_rate`/`inverse_company_rate` explícitos, ayer
        solo con `company_rate`/`inverse_company_rate`), el `inverse` del
        núcleo para `company_rate`
        (`base/models/res_currency.py::ResCurrencyRate._inverse_company_rate`)
        calculaba `rate = company_rate * last_rate[company]` usando la
        tasa de HOY (ya creada en el mismo batch) como `last_rate` --
        componiendo `(1/380) * (1/390.2944)` para la tasa de AYER en vez
        de `1/380`. Este fixture propio ya fija `rate` explícito en AMBAS
        entradas desde el principio -- este test verifica que ese fix se
        mantenga."""
        rates = self.env["res.currency.rate"].search([
            ("currency_id", "=", self.currency_usd.id),
            ("company_id", "in", [self.company.id, False]),
        ])
        rate_today = rates.filtered(lambda r: r.name == fields.Date.today())
        rate_yesterday = rates.filtered(
            lambda r: r.name == fields.Date.subtract(fields.Date.today(), days=1)
        )
        self.assertEqual(len(rate_today), 1)
        self.assertEqual(len(rate_yesterday), 1)

        self.assertAlmostEqual(rate_today.rate, 1 / self.rate, places=10)
        self.assertAlmostEqual(rate_today.company_rate, 1 / self.rate, places=10)

        self.assertAlmostEqual(rate_yesterday.rate, 1 / 380.0, places=10)
        self.assertAlmostEqual(rate_yesterday.company_rate, 1 / 380.0, places=10)

        yesterday = fields.Date.subtract(fields.Date.today(), days=1)
        invoice = self._create_invoice_usd(1000.00, date=yesterday)
        invoice.with_context(move_action_post_alert=True).action_post()
        inv_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        self.assertAlmostEqual(inv_line.balance, 380000.0, places=2)

    def test_grouped_payment_with_igtf_attributes_each_note_to_its_own_invoice(self):
        """Combina el fix de atribución en pagos agrupados (ver
        `test_exchange_note_reversal.test_grouped_payment_gain_direction_invoice_attribution_is_exact`)
        con IGTF real de por medio: un pago AGRUPADO en el diario
        `bank_journal_usd` (`is_igtf=True`), liquidando DOS facturas de
        montos DISTINTOS (100 y 500 USD) a la vez, en dirección de
        ganancia (donde Odoo suele atribuir el residual al lado del
        pago). El IGTF retenido sobre el pago combinado no debe alterar
        la atribución exacta de cada ND a su propia factura -- verificado
        con montos distintos (no dos facturas idénticas) para que un
        swap entre ellas sea detectable."""
        self.currency_usd.write({
            "rate_ids": [
                Command.create({"name": "2041-01-01", "company_rate": 1 / 36.0}),
                Command.create({"name": "2041-08-01", "company_rate": 1 / 40.0}),
            ],
        })

        invoice_1 = self._create_invoice_usd(100.0, date="2041-01-01")
        invoice_1.with_context(move_action_post_alert=True).action_post()
        invoice_2 = self._create_invoice_usd(500.0, date="2041-01-01")
        invoice_2.with_context(move_action_post_alert=True).action_post()
        invoices = invoice_1 | invoice_2

        lines_to_pay = invoices.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        action = lines_to_pay.action_register_payment()
        ctx = dict(action["context"], active_model="account.move.line", active_ids=lines_to_pay.ids)
        with Form(self.env["account.payment.register"].with_context(ctx)) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = "2041-08-01"
            pay_form.group_payment = True
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        payment = self.env["account.payment"].browse(action.get("res_id"))

        self.env.cr.flush()
        invoice_1.invalidate_recordset()
        invoice_2.invalidate_recordset()

        igtf_moves = self.env["account.move.line"].search([
            ("account_id", "=", self.acc_igtf_cli.id),
            ("partner_id", "=", self.partner.id),
        ])
        self.assertTrue(igtf_moves, "El cobro de IGTF debió seguir aplicándose con normalidad.")

        self.assertEqual(invoice_1.payment_state, "paid")
        self.assertEqual(invoice_2.payment_state, "paid")

        notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("l10n_ve_exchange_payment_id", "=", payment.move_id.id),
        ])
        self.assertEqual(
            len(notes), 2,
            "El pago agrupado con IGTF debió generar una ND/NC por cada factura.",
        )
        self.assertEqual(
            set(notes.mapped("l10n_ve_exchange_invoice_id").ids), {invoice_1.id, invoice_2.id},
            "Cada nota debe quedar vinculada a una factura distinta.",
        )

        note_1 = notes.filtered(lambda n: n.l10n_ve_exchange_invoice_id == invoice_1)
        note_2 = notes.filtered(lambda n: n.l10n_ve_exchange_invoice_id == invoice_2)
        self.assertAlmostEqual(note_1.amount_total, 400.0, places=1, msg="ND de la factura de 100 USD.")
        self.assertAlmostEqual(note_2.amount_total, 2000.0, places=1, msg="ND de la factura de 500 USD.")

        for note in notes:
            note_line = note.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
            self.assertTrue(note_line.reconciled, "Cada nota debió quedar cerrada, sin excepción.")
            self.assertTrue(self.company.currency_id.is_zero(note_line.amount_residual))

    def test_advance_payment_applied_to_two_invoices_each_gets_correct_note(self):
        """Vía "anticipo" (`is_advance_payment`, patrón usado en
        `l10n_ve_igtf/tests/test_igtf_partner_formal_VEF.py`): un único
        pago de ANTICIPO en USD se aplica, uno a la vez
        (`js_assign_outstanding_line`, el mecanismo real del widget de
        pagos para anticipos -- cada aplicación es su PROPIA
        conciliación, a diferencia del pago agrupado), a DOS facturas de
        montos distintos creadas DESPUÉS del anticipo. Confirma que
        reconciliaciones sucesivas contra el mismo anticipo no
        contaminan la atribución entre sí (cada una debe recibir su
        propia ND exacta), y que el guard de duplicados por (factura,
        pago) sigue distinguiendo cada aplicación como un evento propio
        aunque ambas compartan el mismo `payment.move_id`."""
        self.currency_usd.write({
            "rate_ids": [
                Command.create({"name": "2042-01-01", "company_rate": 1 / 36.0}),
                Command.create({"name": "2042-06-01", "company_rate": 1 / 40.0}),
            ],
        })

        advance_amount = 700.0
        context = {
            "default_payment_type": "inbound", "default_partner_type": "customer",
            "default_move_journal_types": ("bank", "cash"), "display_account_trust": True,
            "default_is_advance_payment": True,
        }
        with Form(self.env["account.payment"].with_context(context)) as pay_form:
            pay_form.partner_id = self.partner
            pay_form.journal_id = self.bank_journal_usd
            pay_form.date = "2042-06-01"
            pay_form.amount = advance_amount
        advance_payment = pay_form.save()
        advance_payment.action_post()

        invoice_1 = self._create_invoice_usd(100.0, date="2042-01-01")
        invoice_1.with_context(move_action_post_alert=True).action_post()
        invoice_2 = self._create_invoice_usd(500.0, date="2042-01-01")
        invoice_2.with_context(move_action_post_alert=True).action_post()

        outstanding_line = advance_payment.move_id.line_ids.filtered(
            lambda l: l.account_id == self.advance_cust_acc and l.credit > 0
        )
        self.assertTrue(outstanding_line, "El anticipo debió quedar con su línea de crédito disponible.")

        invoice_1.with_context({}).js_assign_outstanding_line(outstanding_line.id)
        self.env.cr.flush()

        outstanding_line.invalidate_recordset()
        self.assertFalse(
            outstanding_line.reconciled,
            "La línea del anticipo debía quedar con residual disponible tras la primera aplicación parcial.",
        )
        invoice_2.with_context({}).js_assign_outstanding_line(outstanding_line.id)
        self.env.cr.flush()

        invoice_1.invalidate_recordset()
        invoice_2.invalidate_recordset()

        notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("l10n_ve_exchange_invoice_id", "in", (invoice_1 + invoice_2).ids),
        ])
        self.assertEqual(
            len(notes), 2,
            "Cada aplicación del anticipo (una por factura) debió generar su propia ND.",
        )
        note_1 = notes.filtered(lambda n: n.l10n_ve_exchange_invoice_id == invoice_1)
        note_2 = notes.filtered(lambda n: n.l10n_ve_exchange_invoice_id == invoice_2)
        self.assertTrue(note_1, "La factura de 100 USD debió recibir su propia ND.")
        self.assertTrue(note_2, "La factura de 500 USD debió recibir su propia ND.")
        for note in notes:
            note_line = note.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
            self.assertTrue(note_line.reconciled, "Cada nota debió quedar cerrada, sin excepción.")

    def test_exchange_difference_note_alongside_igtf_payment_different_dates(self):
        """Factura en USD (`_create_invoice_usd`) emitida AYER, pagada
        HOY -- mismo monto, mismo diario `bank_journal_usd`
        (`is_igtf=True`) -- en dos tasas de cambio distintas (380.0 ayer,
        `self.rate` = 390.2944 hoy, ya configuradas en `setUp`).

        Nota: una factura en VES (moneda de COMPAÑÍA) NUNCA genera
        diferencial cambiario sin importar en qué moneda ni fecha se
        pague -- su monto en VES está fijo, no fluctúa con la tasa (a
        diferencia de una factura en USD, cuyo equivalente en VES sí
        cambia según la tasa del día). Por eso este test usa factura en
        USD (igual que la ND/NC base ya probada en
        `test_exchange_note_reversal.test_exchange_difference_settled_by_real_note_via_register_payment`),
        para que SÍ exista diferencial real que conviva con IGTF."""
        yesterday = fields.Date.subtract(fields.Date.today(), days=1)
        invoice_amount = 1000.00

        invoice = self._create_invoice_usd(invoice_amount, date=yesterday)
        invoice.with_context(move_action_post_alert=True).action_post()
        inv_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        payment = self.env["account.payment"].browse(action.get("res_id"))

        self.env.cr.flush()

        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()

        igtf_moves = self.env["account.move.line"].search([
            ("account_id", "=", self.acc_igtf_cli.id),
            ("partner_id", "=", self.partner.id),
        ])
        self.assertTrue(igtf_moves, "El cobro de IGTF debió seguir aplicándose con normalidad.")

        self.assertEqual(invoice.payment_state, "paid")
        self.assertTrue(inv_line.reconciled)
        self.assertTrue(self.company.currency_id.is_zero(inv_line.amount_residual))

        notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("l10n_ve_exchange_invoice_id", "=", invoice.id),
        ])
        self.assertEqual(
            len(notes), 1,
            "Debió crearse exactamente una ND/NC de diferencial cambiario aun con IGTF de por medio.",
        )
        note = notes[0]
        self.assertEqual(note.state, "posted")
        note_line = note.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        self.assertTrue(note_line.reconciled)
        self.assertTrue(self.company.currency_id.is_zero(note_line.amount_residual))

        self.assertNotIn(self.acc_igtf_cli, note.line_ids.account_id)

        # La tasa SUBIÓ de 380.0 (factura, ayer) a 390.2944 (pago, hoy) --
        # el equivalente en Bs de la factura en USD aumenta, así que la
        # compañía GANA (ND, no NC). El monto es exactamente
        # 1000 USD * (390.2944 - 380.0) = 10.294,40 Bs.
        self.assertEqual(note.move_type, "out_invoice")
        self.assertEqual(note.debit_origin_id, invoice)
        self.assertFalse(note._is_exchange_credit_note())
        self.assertTrue(note._is_exchange_debit_note())
        self.assertAlmostEqual(note.amount_total, 10294.40, places=2)
        self.assertAlmostEqual(note.invoice_line_ids.price_unit, 10294.40, places=2)
        self.assertEqual(note.invoice_line_ids.account_id, self.company.income_currency_exchange_account_id)
        self.assertEqual(note.date, fields.Date.today())

    def test_igtf_base_computation_correct_with_exchange_note_present(self):
        """Regresión para `l10n_ve_igtf.models.account_move.compute_bi_igtf`
        (`l10n_ve_igtf/models/account_move.py`): el campo que identifica
        los movimientos "de pago" contra los que calcular la base de
        IGTF cambió de `reconciled_lines_ids.mapped('move_id')` a
        `matched_debit_ids.debit_move_id | matched_credit_ids.credit_move_id`.
        Esta prueba no asume CUÁL es la diferencia exacta entre ambas
        expresiones -- en su lugar verifica el resultado observable que
        le importa al usuario: que la base de IGTF calculada
        (`foreign_bi_igtf`) siga siendo correcta aun con la ND/NC de
        diferencial conviviendo en la misma conciliación."""
        yesterday = fields.Date.subtract(fields.Date.today(), days=1)
        invoice = self._create_invoice_usd(1000.00, date=yesterday)
        invoice.with_context(move_action_post_alert=True).action_post()
        inv_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        self.env["account.payment"].browse(action.get("res_id"))
        self.env.cr.flush()

        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()

        note = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("l10n_ve_exchange_invoice_id", "=", invoice.id),
        ])
        self.assertEqual(len(note), 1, "Debió crearse la ND/NC de diferencial (mismo escenario del test base).")

        igtf_moves = self.env["account.move.line"].search([
            ("account_id", "=", self.acc_igtf_cli.id),
            ("partner_id", "=", self.partner.id),
        ])
        self.assertTrue(igtf_moves, "El cobro de IGTF debió aplicarse con normalidad.")
        igtf_charged = sum(igtf_moves.mapped(lambda l: abs(l.amount_currency)))

        self.assertAlmostEqual(
            igtf_charged, 1000.00 * (self.company.igtf_percentage / 100.0), places=2,
            msg="El IGTF realmente cobrado debió ser el 3% del monto pagado "
            "(1000 USD), sin verse afectado por la ND/NC de diferencial.",
        )

        invoice.invalidate_recordset()

        # NO se asierta `foreign_bi_igtf == 1000.0` (lo que uno esperaría
        # ingenuamente): `compute_bi_igtf` (`l10n_ve_igtf/models/account_move.py`)
        # tiene una limitación PREEXISTENTE, ajena a este módulo, cuando
        # factura y pago caen en fechas con tasas de cambio DISTINTAS:
        # `foreign_bi_igtf` termina en `1000 * (380/390.2944)` en vez de
        # `1000.0`. Se PINEA ese valor exacto para que cualquier cambio
        # futuro en ese cálculo quede detectado acá -- no se investiga ni
        # se corrige `compute_bi_igtf` en sí (fuera del alcance de
        # TI-14119).
        expected_foreign_bi_igtf = 1000.00 * (380.0 / self.rate)
        self.assertAlmostEqual(
            invoice.foreign_bi_igtf, expected_foreign_bi_igtf, places=2,
            msg="La base de IGTF en moneda extranjera debió mantener el mismo "
            "valor (con la misma limitación preexistente y documentada de "
            "`compute_bi_igtf`) con la ND/NC de diferencial presente en la "
            "conciliación -- si este valor cambió, o bien `compute_bi_igtf` "
            "cambió, o bien la presencia de la ND/NC ahora sí lo distorsiona "
            "de otra forma.",
        )

    def test_ves_invoice_paid_in_usd_generates_rounding_exchange_difference_note(self):
        """Complemento del test anterior: una factura en VES (moneda de
        COMPAÑÍA), pagada en USD con IGTF de por medio, en fechas y tasas
        distintas. El monto adeudado en VES no tiene exposición cambiaria
        propia, pero al conciliarla contra un pago en USD, Odoo igual
        calcula un residual de redondeo de la conversión. El alcance de
        este módulo es replicar CUALQUIER asiento de diferencial que Odoo
        genere para una factura de cliente como ND/NC real -- también
        este caso, sin excepción."""
        yesterday = fields.Date.subtract(fields.Date.today(), days=1)
        invoice_amount = 500000.00

        invoice = self._create_invoice_vef(invoice_amount, date=yesterday)
        invoice.with_context(move_action_post_alert=True).action_post()
        inv_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        self.env["account.payment"].browse(action.get("res_id"))

        self.env.cr.flush()

        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()

        igtf_moves = self.env["account.move.line"].search([
            ("account_id", "=", self.acc_igtf_cli.id),
            ("partner_id", "=", self.partner.id),
        ])
        self.assertTrue(igtf_moves, "El cobro de IGTF debió seguir aplicándose con normalidad.")

        self.assertTrue(inv_line.reconciled, "La factura debió quedar completamente conciliada.")
        self.assertTrue(self.company.currency_id.is_zero(inv_line.amount_residual))

        notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("l10n_ve_exchange_invoice_id", "=", invoice.id),
        ])
        self.assertEqual(
            len(notes), 1,
            "El residual de redondeo de conciliar la factura en Bs contra un pago "
            "en USD debió documentarse como ND/NC, igual que cualquier otro "
            "diferencial de una factura de cliente.",
        )
        note_line = notes.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        self.assertTrue(note_line.reconciled, "La nota debió quedar cerrada por su propia conciliación.")

    def test_invoice_closed_by_advance_cross_and_note_does_not_end_up_reversed(self):
        """Regresión concreta para el bloqueante "la factura cerrada vía
        un cruce de anticipo + NC de diferencial quedaba `reversed` en
        vez de `paid`" (revisión de seguimiento sobre `9dabb347`).

        El "cruce de anticipo" real de `l10n_ve_igtf`
        (`_reconcile_move_with_payment_difference`,
        `l10n_ve_igtf/models/account_move.py`) concilia la factura
        contra un `account.move` armado a mano -- `move_type='entry'`,
        SIN `origin_payment_id` (no es un `account.payment` real, es un
        asiento que traslada un anticipo ya existente a la cuenta por
        cobrar). Este test no monta el flujo completo del wizard de
        anticipos -- reproduce directo la propiedad ESTRUCTURAL que
        importa (un `entry` sin `origin_payment_id`, conciliado por
        `.reconcile()` contra la factura), que es exactamente lo que
        dispara el bug sin importar por qué mecanismo de UI se llegue.

        Sin este módulo, este mismo escenario (anticipo + diferencial)
        SIEMPRE resolvía a `payment_state='paid'`, porque el asiento
        genérico nativo de Odoo también es `move_type='entry'` -- nunca
        introduce `'out_refund'` en la combinación de tipos que el
        núcleo evalúa para decidir si una factura fue "revertida". La NC
        real que este módulo emite en su lugar SÍ lo introduce -- y sin
        la corrección de `_compute_payment_state`
        (`l10n_ve_exchange_difference/models/account_move.py`), el
        núcleo concluye erróneamente que la factura se revirtió.

        NOTA sobre `bi_igtf`/`igtf_top_aply`: se investigó si esta
        misma corrección también rescataba la base imponible de IGTF de
        `l10n_ve_igtf.compute_bi_igtf` en este escenario (hipótesis
        documentada en una versión anterior de este test y del spec).
        Verificado EMPÍRICAMENTE que NO aplica: siempre que el bug de
        `payment_state` puede dispararse (factura cerrada SIN ningún
        pago real en TODO su historial de conciliación), la fórmula de
        `compute_bi_igtf` (que reduce el tope exactamente por la
        porción cerrada con movimientos sin línea de IGTF, y no
        contribuye nada a `bi_igtf` desde un movimiento que tampoco
        tiene línea de IGTF) da 0 de todas formas -- CON o SIN la
        corrección de `payment_state`, porque nunca hay un pago real
        del cual sacar base imponible. El único efecto real y
        verificado de este fix es `payment_state` en sí mismo."""
        self.currency_usd.write({
            "rate_ids": [
                Command.create({"name": "2043-01-01", "company_rate": 1 / 40.0}),
                Command.create({"name": "2043-08-01", "company_rate": 1 / 36.0}),
            ],
        })

        invoice = self._create_invoice_usd(1000.00, date="2043-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        inv_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        # Cruce de anticipo simplificado -- mismo `move_type='entry'` sin
        # `origin_payment_id` que produce `_reconcile_move_with_payment_difference`,
        # en el mismo diario/cuenta de anticipo que usa ese mecanismo
        # real, pero construido directo para no depender del wizard
        # completo de Enterprise/anticipos.
        advance_cross = self.env["account.move"].create({
            "move_type": "entry",
            "journal_id": self.journal_anticipo.id,
            "partner_id": self.partner.id,
            "date": "2043-08-01",
            "currency_id": self.currency_usd.id,
            "line_ids": [
                Command.create({
                    "account_id": self.acc_receivable.id, "partner_id": self.partner.id,
                    "currency_id": self.currency_usd.id, "amount_currency": -1000.0,
                    "debit": 0.0, "credit": 36000.0,
                }),
                Command.create({
                    "account_id": self.advance_cust_acc.id, "partner_id": self.partner.id,
                    "currency_id": self.currency_usd.id, "amount_currency": 1000.0,
                    "debit": 36000.0, "credit": 0.0,
                }),
            ],
        })
        advance_cross.action_post()
        self.assertFalse(
            advance_cross.origin_payment_id,
            "Precondición del escenario: el cruce NO debe tener un account.payment real detrás.",
        )
        cross_line = advance_cross.line_ids.filtered(lambda l: l.account_id == self.acc_receivable)

        (inv_line + cross_line).reconcile()
        self.env.cr.flush()

        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()

        self.assertTrue(inv_line.reconciled, "La factura debió quedar completamente conciliada.")
        self.assertTrue(self.company.currency_id.is_zero(inv_line.amount_residual))

        note = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("l10n_ve_exchange_invoice_id", "=", invoice.id),
        ])
        self.assertEqual(
            len(note), 1,
            "El residual de diferencial del cruce de anticipo debió documentarse con una NC.",
        )
        self.assertTrue(note._is_exchange_credit_note(), "Con estas tasas correspondía la rama de pérdida (NC).")

        # El fix en sí: sin él, esto da 'reversed'.
        self.assertEqual(
            invoice.payment_state, "paid",
            "La factura se cerró por completo (anticipo + NC de diferencial) -- "
            "debió quedar 'paid', no 'reversed'.",
        )
