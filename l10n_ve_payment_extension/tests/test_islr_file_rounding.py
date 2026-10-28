from odoo import Command, fields
from odoo.tests import tagged
from odoo.tools.float_utils import float_round

from .test_withholding_common_VEF import RetentionTestCommon


@tagged("post_install", "-at_install", "islr_file_rounding")
class TestIslrFileRounding(RetentionTestCommon):
    """El importe del fichero ISLR se redondea con el criterio de Odoo.

    `round()` de Python redondea al par -`round(0.125, 2)` da 0.12- mientras
    todo el resto del sistema redondea al alza. Es el fichero que se declara
    al SENIAT: el sesgo no se cancela, crece con el numero de operaciones.

    0.125 se eligio porque es EXACTO en binario, asi que el empate es real y
    no un artefacto de la representacion: los dos criterios difieren de
    verdad y el test discrimina.
    """

    def setUp(self):
        hoy = fields.Date.today()
        self.env["res.currency.rate"].search([
            ("currency_id", "=", self.env.ref("base.USD").id),
            ("name", "in", [hoy, fields.Date.subtract(hoy, days=1)]),
        ]).unlink()
        super().setUp()
        if "subsidiary" in self.company._fields:
            self.company.subsidiary = False

    def _retention_line(self, amount, with_currency=True):
        retention = self.env["account.retention"].create({
            "type_retention": "islr",
            "type": "in_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(),
            "date_accounting": fields.Date.today(),
        })
        if not with_currency:
            retention.foreign_currency_id = False
        line = self.env["account.retention.line"].create({
            "retention_id": retention.id,
            "name": "ISLR",
            "foreign_invoice_amount": amount,
            "invoice_amount": amount,
        })
        return line

    def _amount(self, line, is_vef_currency=True):
        wizard = self.env["wizard.retention.islr"].create({"report": "islr"})
        return wizard._islr_operation_amount(line, is_vef_currency)

    def test_half_is_rounded_up_not_to_even(self):
        line = self._retention_line(0.125)
        valor = self._amount(line)
        self.assertAlmostEqual(
            valor, 0.13, places=6,
            msg="El fichero del SENIAT debe redondear al alza, no al par.",
        )
        # La prueba de que el test discrimina: el criterio anterior daba otra
        # cosa sobre este mismo numero.
        self.assertNotAlmostEqual(round(0.125, 2), valor, places=6)

    def test_line_without_currency_does_not_break_the_file(self):
        """`foreign_currency_id` es un related nullable.

        Con `currency.round()` esto reventaba con `Expected singleton` y
        tumbaba la generacion del fichero completo, no una linea.
        """
        line = self._retention_line(0.125, with_currency=False)
        self.assertFalse(line.foreign_currency_id)
        valor = self._amount(line)
        self.assertAlmostEqual(valor, 0.13, places=6)

    def test_both_branches_use_the_same_criterion(self):
        """La rama en divisa y la de compañía no pueden diferir de criterio."""
        line = self._retention_line(0.125)
        esperado = float_round(0.125, precision_digits=2, rounding_method="HALF-UP")
        self.assertAlmostEqual(esperado, 0.13, places=6)
        # Las dos ramas -divisa y moneda de compania- con el mismo criterio.
        self.assertAlmostEqual(self._amount(line, True), esperado, places=6)
        self.assertAlmostEqual(self._amount(line, False), esperado, places=6)
