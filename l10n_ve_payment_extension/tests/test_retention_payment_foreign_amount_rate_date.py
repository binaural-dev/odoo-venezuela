from odoo import fields
from odoo.tests import Form, tagged

from .retention_flow_helpers import RetentionFlowHelpers
from .test_withholding_common_VEF import RetentionTestCommon

DOC_TYPES = ("out_invoice", "out_refund", "out_debit", "in_invoice", "in_refund", "in_debit")
RETENTION_TYPES = ("iva", "islr", "municipal")


@tagged("post_install", "-at_install", "retention_payment_foreign_amount_rate_date")
class TestRetentionPaymentForeignAmountRateDate(RetentionFlowHelpers, RetentionTestCommon):
    """El importe alterno (`foreign_amount`) del pago de una retencion debe
    coincidir con el monto alterno de las lineas de su asiento.

    El asiento valora sus lineas con la fecha de la factura retenida
    (`account.move.line._get_foreign_rate_date`); el pago, en cambio, tomaba
    `payment.date`, que es la fecha contable de la retencion. Con tasas
    distintas en ambas fechas el campo quedaba distinto al asiento.

    Cada prueba crea el documento y la retencion con `Form` (la retencion
    desde la accion de su menu, como lo hace el usuario) y compara contra el
    asiento publicado. Hay una prueba por cada combinacion de tipo de
    retencion (IVA, ISLR, municipal) y tipo de documento (factura, nota de
    credito y nota de debito, de cliente y de proveedor)."""

    RATE_DOC_DATE = 380.0
    RATE_ACCOUNTING_DATE = 400.0

    def setUp(self):
        super().setUp()
        self.accounting_date = fields.Date.today()
        self.doc_date = fields.Date.subtract(self.accounting_date, days=3)
        self._set_rates(self.RATE_DOC_DATE, self.RATE_ACCOUNTING_DATE)
        self.company.write({
            "municipal_supplier_retention_journal_id": self.bank_journal_sup_ret.id,
            "municipal_customer_retention_journal_id": self.bank_journal_sup_ret.id,
        })
        # ISLR de cliente: el concepto se busca con el tipo de persona de la
        # propia compania; con el de las lineas de concepto de prueba.
        self.company.partner_id.type_person_id = self.islr_concept_line.type_person_id

    # ------------------------------------------------------------------ #
    # Fixtures
    # ------------------------------------------------------------------ #
    def _convert_to_usd(self, amount_ves, rate):
        return self.currency_usd.round(amount_ves / rate)

    # ------------------------------------------------------------------ #
    # Verificacion comun
    # ------------------------------------------------------------------ #
    def _assert_foreign_amount_matches_move(self, move_type, retention_type):
        document = self._document(move_type, retention_type)
        retention = self._retention_from_form(retention_type, document)
        retention.action_post()

        payment = retention.payment_ids
        self.assertEqual(len(payment), 1, "Un pago por la unica factura retenida.")
        move = payment.move_id

        # La fecha contable del pago y de su asiento no cambia.
        self.assertEqual(payment.date, self.accounting_date)
        self.assertEqual(move.date, self.accounting_date)

        # El importe alterno es el del asiento (todas sus lineas, a la misma tasa).
        self.assertTrue(payment.foreign_amount)
        foreign_balances = move.line_ids.mapped("foreign_balance")
        self.assertTrue(all(foreign_balances))
        for line in move.line_ids:
            self.assertAlmostEqual(
                abs(line.foreign_balance), payment.foreign_amount, places=2,
                msg="El importe alterno del pago debe ser el monto alterno de "
                    "las lineas del asiento de la retencion.",
            )

        # Y es el monto en bolivares convertido con la tasa de la fecha del
        # documento retenido, no con la de la fecha contable de la retencion.
        self.assertAlmostEqual(
            payment.foreign_amount,
            self._convert_to_usd(payment.amount, self.rate_doc_date),
            places=2,
        )
        self.assertNotAlmostEqual(
            payment.foreign_amount,
            self._convert_to_usd(payment.amount, self.rate_accounting_date),
            places=2,
            msg="Las dos tasas deben dar importes distintos para que la prueba distinga.",
        )

    # ------------------------------------------------------------------ #
    # Casos puntuales
    # ------------------------------------------------------------------ #
    def test_tasa_baja_entre_fechas_tambien_es_congruente(self):
        """El campo no depende del sentido en que se movio la tasa."""
        self._set_rates(400.0, 380.0)
        self._assert_foreign_amount_matches_move("out_invoice", "iva")

    def test_tasa_baja_proveedor_islr(self):
        self._set_rates(400.0, 380.0)
        self._assert_foreign_amount_matches_move("in_invoice", "islr")

    def test_tasa_baja_proveedor_municipal(self):
        self._set_rates(400.0, 380.0)
        self._assert_foreign_amount_matches_move("in_invoice", "municipal")

    def test_misma_tasa_en_ambas_fechas_no_cambia_nada(self):
        self._set_rates(390.0, 390.0)
        document = self._document("out_invoice", "iva")
        retention = self._retention_from_form("iva", document)
        retention.action_post()
        payment = retention.payment_ids
        for line in payment.move_id.line_ids:
            self.assertAlmostEqual(abs(line.foreign_balance), payment.foreign_amount, places=2)

    def test_pago_que_no_es_retencion_conserva_su_fecha(self):
        """Fuera de retenciones el calculo no cambia: sigue usando
        `payment.date`, aunque haya una factura con otra fecha de tasa."""
        payment = self.env["account.payment"].create({
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": self.partner_pnr_75.id,
            "amount": 1000.0,
            "currency_id": self.currency_vef.id,
            "journal_id": self.bank_journal_sub.id,
            "date": self.accounting_date,
        })
        self.assertFalse(payment._get_retention_foreign_rate_date())
        self.assertAlmostEqual(
            payment.foreign_amount,
            self._convert_to_usd(1000.0, self.rate_accounting_date),
            places=2,
        )

    def test_foreign_amount_se_recalcula_al_asociar_las_lineas(self):
        """El pago se crea sin lineas y estas se asocian despues
        (`_create_payments_from_lines`): el campo debe quedar con la fecha de
        la factura una vez asociadas, y no con la del pago."""
        document = self._document("out_invoice", "iva")
        retention = self._retention_from_form("iva", document)
        retention.action_post()
        payment = retention.payment_ids
        stale = self._convert_to_usd(payment.amount, self.rate_accounting_date)
        self.assertNotAlmostEqual(payment.foreign_amount, stale, places=2)
        self.assertAlmostEqual(
            payment.foreign_amount,
            self._convert_to_usd(payment.amount, self.rate_doc_date),
            places=2,
        )


    # ------------------------------------------------------------------ #
    # Comparacion con pagos normales (creados con Form)
    # ------------------------------------------------------------------ #
    def _assert_entry_matches_foreign_amount(self, payment):
        """El monto alterno de cada linea del asiento es el importe alterno
        mostrado en el pago."""
        for line in payment.move_id.line_ids:
            self.assertAlmostEqual(
                abs(line.foreign_balance), payment.foreign_amount, places=2,
                msg="El importe alterno del pago debe ser el de su asiento.",
            )

    def _normal_payment_from_form(self, payment_type, amount):
        """Pago normal creado con `Form` del propio pago, en VEF y con la
        fecha contable `accounting_date`."""
        is_inbound = payment_type == "inbound"
        with Form(self.env["account.payment"].with_context(
            default_payment_type=payment_type,
            default_partner_type="customer" if is_inbound else "supplier",
        )) as form:
            form.partner_id = self.partner_pnr_75
            form.journal_id = self.bank_journal_sub
            form.currency_id = self.currency_vef
            form.amount = amount
            form.date = self.accounting_date
        payment = form.save()
        payment.action_post()
        return payment

    def test_pago_normal_creado_con_form_cliente_usa_la_fecha_del_pago(self):
        payment = self._normal_payment_from_form("inbound", 100000.0)
        self.assertAlmostEqual(
            payment.foreign_amount,
            self._convert_to_usd(100000.0, self.rate_accounting_date),
            places=2,
        )
        self._assert_entry_matches_foreign_amount(payment)

    def test_pago_normal_creado_con_form_proveedor_usa_la_fecha_del_pago(self):
        payment = self._normal_payment_from_form("outbound", 100000.0)
        self.assertAlmostEqual(
            payment.foreign_amount,
            self._convert_to_usd(100000.0, self.rate_accounting_date),
            places=2,
        )
        self._assert_entry_matches_foreign_amount(payment)

    def test_pago_normal_con_asistente_de_registro_de_pago(self):
        """Pago de la factura desde el asistente "Registrar pago" (Form), con
        fecha de pago distinta a la de la factura: lo mostrado debe ser el
        monto alterno de su asiento."""
        invoice = self._document("out_invoice", "iva")
        with Form(self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=invoice.ids,
        )) as wizard:
            wizard.payment_date = self.accounting_date
            wizard.amount = 100000.0
        payment = wizard.save()._create_payments()
        self.assertEqual(payment.date, self.accounting_date)
        self.assertFalse(payment.is_retention)
        self._assert_entry_matches_foreign_amount(payment)

    def test_misma_retencion_y_pago_normal_cada_uno_cuadra_con_su_asiento(self):
        """Mismos bolivares, mismo dia: el pago normal se valora a la tasa de
        su fecha y la retencion a la de la factura retenida; el campo de
        cada uno es el de su propio asiento."""
        document = self._document("out_invoice", "iva")
        retention = self._retention_from_form("iva", document)
        retention.action_post()
        retention_payment = retention.payment_ids
        normal_payment = self._normal_payment_from_form("inbound", retention_payment.amount)

        self._assert_entry_matches_foreign_amount(retention_payment)
        self._assert_entry_matches_foreign_amount(normal_payment)
        self.assertAlmostEqual(
            retention_payment.foreign_amount,
            self._convert_to_usd(retention_payment.amount, self.rate_doc_date),
            places=2,
        )
        self.assertAlmostEqual(
            normal_payment.foreign_amount,
            self._convert_to_usd(normal_payment.amount, self.rate_accounting_date),
            places=2,
        )
        self.assertNotAlmostEqual(
            retention_payment.foreign_amount, normal_payment.foreign_amount, places=2,
        )


def _make_test(move_type, retention_type):
    def test(self):
        self._assert_foreign_amount_matches_move(move_type, retention_type)
    test.__doc__ = (
        "Retencion %s sobre %s: el importe alterno del pago es el de su asiento."
        % (retention_type.upper(), move_type)
    )
    return test


for _retention_type in RETENTION_TYPES:
    for _move_type in DOC_TYPES:
        setattr(
            TestRetentionPaymentForeignAmountRateDate,
            "test_%s_%s" % (_retention_type, _move_type),
            _make_test(_move_type, _retention_type),
        )
