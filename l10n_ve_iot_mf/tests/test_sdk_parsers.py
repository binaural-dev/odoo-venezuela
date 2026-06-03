from odoo.tests import TransactionCase, tagged
from odoo.addons.l10n_ve_iot_mf.iot_handlers.sdk.Util import Util
from odoo.addons.l10n_ve_iot_mf.iot_handlers.sdk.AcumuladosX import AcumuladosX
from odoo.addons.l10n_ve_iot_mf.iot_handlers.sdk.S1PrinterData import S1PrinterData


@tagged("post_install", "-at_install", "l10n_ve_iot_mf")
class TestSDKUtil(TransactionCase):

    def test_do_value_double_normal(self):
        """'12345' debe convertirse a 123.45."""
        result = Util.DoValueDouble("12345")
        self.assertEqual(result, 123.45)

    def test_do_value_double_zero(self):
        """'00000' debe convertirse a 0.0."""
        result = Util.DoValueDouble("00000")
        self.assertEqual(result, 0.0)

    def test_do_value_double_small(self):
        """'5' debe convertirse a 0.05."""
        result = Util.DoValueDouble("5")
        self.assertEqual(result, 0.05)

    def test_do_value_double_one_digit(self):
        """'1' debe convertirse a 0.01."""
        result = Util.DoValueDouble("1")
        self.assertEqual(result, 0.01)

    def test_do_value_double_large(self):
        """'1234567' debe convertirse a 12345.67."""
        result = Util.DoValueDouble("1234567")
        self.assertEqual(result, 12345.67)

    def test_do_value_double_empty_string(self):
        """Cadena vacía debe retornar 0.0."""
        result = Util.DoValueDouble("")
        self.assertEqual(result, 0.0)

    def test_do_value_double_non_numeric(self):
        """Cadena no numérica debe retornar 0.0."""
        result = Util.DoValueDouble("abcd")
        self.assertEqual(result, 0.0)

    def test_do_value_double_none(self):
        """None debe retornar 0.0."""
        result = Util.DoValueDouble(None)
        self.assertEqual(result, 0.0)

    def test_do_value_double_negative_string(self):
        """'123' debe retornar 1.23 (signo no manejado)."""
        result = Util.DoValueDouble("123")
        self.assertEqual(result, 1.23)


@tagged("post_install", "-at_install", "l10n_ve_iot_mf")
class TestSDKAcumuladosX(TransactionCase):

    def test_acumulados_x_defaults(self):
        """AcumuladosX debe inicializar atributos en 0."""
        ax = AcumuladosX()
        self.assertEqual(ax._freeTax, 0)
        self.assertEqual(ax._generalRate1, 0)
        self.assertEqual(ax._generalRate1Tax, 0)
        self.assertEqual(ax._reducedRate2, 0)
        self.assertEqual(ax._reducedRate2Tax, 0)
        self.assertEqual(ax._additionalRate3, 0)
        self.assertEqual(ax._additionalRate3Tax, 0)


@tagged("post_install", "-at_install", "l10n_ve_iot_mf")
class TestSDKS1PrinterData(TransactionCase):

    def test_s1_printer_data_defaults(self):
        """S1PrinterData debe tener valores por defecto."""
        s1 = S1PrinterData()
        self.assertEqual(s1._cashierNumber, 0)
        self.assertEqual(s1._totalDailySales, 0)
        self.assertEqual(s1._lastInvoiceNumber, 0)
        self.assertEqual(s1._quantityOfInvoicesToday, 0)
        self.assertEqual(s1._lastDebtNoteNumber, 0)
        self.assertEqual(s1._quantityDebtNoteToday, 0)
        self.assertEqual(s1._lastNCNumber, 0)
        self.assertEqual(s1._quantityOfNCToday, 0)
        self.assertEqual(s1._numberNonFiscalDocuments, 0)
        self.assertEqual(s1._quantityNonFiscalDocuments, 0)
        self.assertEqual(s1._auditReportsCounter, 0)
        self.assertEqual(s1._fiscalReportsCounter, 0)
        self.assertEqual(s1._dailyClosureCounter, 0)
        self.assertEqual(s1._rif, "")
        self.assertEqual(s1._registeredMachineNumber, "")
        self.assertEqual(s1._currentPrinterDate, "")
        self.assertEqual(s1._currentPrinterTime, "")
