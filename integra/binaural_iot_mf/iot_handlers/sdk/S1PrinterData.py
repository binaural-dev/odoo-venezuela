import datetime
from odoo.addons.hw_drivers.iot_handlers.sdk.Util import Util


class S1PrinterData(object):
    _cashierNumber = 0
    _totalDailySales = 0
    _lastInvoiceNumber = 0
    _quantityOfInvoicesToday = 0
    _lastDebtNoteNumber = 0
    _quantityDebtNoteToday = 0
    _lastNCNumber = 0
    _quantityOfNCToday = 0
    _numberNonFiscalDocuments = 0
    _quantityNonFiscalDocuments = 0
    _auditReportsCounter = 0
    _fiscalReportsCounter = 0
    _dailyClosureCounter = 0
    _rif = ""
    _registeredMachineNumber = ""
    _currentPrinterDate = ""
    _currentPrinterTime = ""

    def __init__(self, trama):
        if trama != None:
            if len(trama) > 100:  # and len(trama)<116): #116
                try:
                    _arrayParameter = str(trama[1:-1]).split(chr(0x0A))
                    if len(_arrayParameter) <= 15:
                        self._setCashierNumber(_arrayParameter[0][2:])
                        self._setTotalDailySales(Util().DoValueDouble(_arrayParameter[1]))
                        self._setLastInvoiceNumber(int(_arrayParameter[2]))
                        self._setQuantityOfInvoicesToday(int(_arrayParameter[3]))
                        self._setNumberNonFiscalDocuments(int(_arrayParameter[4]))
                        self._setQuantityNonFiscalDocuments(int(_arrayParameter[5]))
                        self._setDailyClosureCounter(int(_arrayParameter[6]))
                        self._setFiscalReportsCounter(int(_arrayParameter[7]))
                        self._setRif(_arrayParameter[8])
                        self._setRegisteredMachineNumber(_arrayParameter[9])

                        _hr = _arrayParameter[10][0:2]
                        _mn = _arrayParameter[10][2:4]
                        _sg = _arrayParameter[10][4:6]

                        _dd = _arrayParameter[11][0:2]
                        _mm = _arrayParameter[11][2:4]
                        _aa = int(_arrayParameter[11][4:6]) + 2000

                        _printerDate = str(_dd) + "-" + str(_mm) + "-" + str(_aa)
                        _printerTime = str(_hr) + ":" + str(_mn) + ":" + str(_sg)

                        self._setCurrentPrinterTime(_printerTime)
                        self._setCurrentPrinterDate(_printerDate)
                        self._setLastNCNumber(int(_arrayParameter[12]))
                        self._setQuantityOfNCToday(int(_arrayParameter[13]))
                    else:
                        self._setCashierNumber(_arrayParameter[0][2:])
                        self._setTotalDailySales(Util().DoValueDouble(_arrayParameter[1]))
                        self._setLastInvoiceNumber(int(_arrayParameter[2]))
                        self._setQuantityOfInvoicesToday(int(_arrayParameter[3]))
                        self._setLastDebtNoteNumber(int(_arrayParameter[4]))
                        self._setQuantityDebtNoteToday(int(_arrayParameter[5]))
                        self._setLastNCNumber(int(_arrayParameter[6]))
                        self._setQuantityOfNCToday(int(_arrayParameter[7]))
                        self._setNumberNonFiscalDocuments(int(_arrayParameter[8]))
                        self._setQuantityNonFiscalDocuments(int(_arrayParameter[9]))
                        self._setAuditReportsCounter(int(_arrayParameter[10]))
                        self._setDailyClosureCounter(int(_arrayParameter[11]))
                        self._setRif(_arrayParameter[12])
                        self._setRegisteredMachineNumber(_arrayParameter[13])

                        _hr = _arrayParameter[14][0:2]
                        _mn = _arrayParameter[14][2:4]
                        _sg = _arrayParameter[14][4:6]

                        _dd = _arrayParameter[15][0:2]
                        _mm = _arrayParameter[15][2:4]
                        _aa = int(_arrayParameter[15][4:6]) + 2000

                        _printerDate = str(_dd) + "-" + str(_mm) + "-" + str(_aa)
                        _printerTime = str(_hr) + ":" + str(_mn) + ":" + str(_sg)

                        self._setCurrentPrinterTime(_printerTime)
                        self._setCurrentPrinterDate(_printerDate)
                except (ValueError):
                    return

    def CashierNumber(self):
        return self._cashierNumber

    def _setCashierNumber(self, cashierNumber):
        self._cashierNumber = cashierNumber

    def TotalDailySales(self):
        return self._totalDailySales

    def _setTotalDailySales(self, totalDailySales):
        self._totalDailySales = totalDailySales

    def LastInvoiceNumber(self):
        return self._lastInvoiceNumber

    def _setLastInvoiceNumber(self, lastInvoiceNumber):
        self._lastInvoiceNumber = lastInvoiceNumber

    def QuantityOfInvoicesToday(self):
        return self._quantityOfInvoicesToday

    def _setQuantityOfInvoicesToday(self, quantityOfInvoicesToday):
        self._quantityOfInvoicesToday = quantityOfInvoicesToday

    def LastDebtNoteNumber(self):
        return self._lastDebtNoteNumber

    def _setLastDebtNoteNumber(self, lastDebtNoteNumber):
        self._lastDebtNoteNumber = lastDebtNoteNumber

    def QuantityDebtNoteToday(self):
        return self._quantityDebtNoteToday

    def _setQuantityDebtNoteToday(self, quantityDebtNoteToday):
        self._quantityDebtNoteToday = quantityDebtNoteToday

    def NumberNonFiscalDocuments(self):
        return self._numberNonFiscalDocuments

    def _setNumberNonFiscalDocuments(self, numberNonFiscalDocuments):
        self._numberNonFiscalDocuments = numberNonFiscalDocuments

    def QuantityNonFiscalDocuments(self):
        return self._quantityNonFiscalDocuments

    def _setQuantityNonFiscalDocuments(self, quantityNonFiscalDocuments):
        self._quantityNonFiscalDocuments = quantityNonFiscalDocuments

    def DailyClosureCounter(self):
        return self._dailyClosureCounter

    def _setDailyClosureCounter(self, dailyClosureCounter):
        self._dailyClosureCounter = dailyClosureCounter

    def AuditReportsCounter(self):
        return self._auditReportsCounter

    def _setAuditReportsCounter(self, auditReportsCounter):
        self._auditReportsCounter = auditReportsCounter

    def FiscalReportsCounter(self):
        return self._fiscalReportsCounter

    def _setFiscalReportsCounter(self, fiscalReportsCounter):
        self._fiscalReportsCounter = fiscalReportsCounter

    def Rif(self):
        return self._rif

    def _setRif(self, rif):
        self._rif = rif

    def RegisteredMachineNumber(self):
        return self._registeredMachineNumber

    def _setRegisteredMachineNumber(self, registeredMachineNumber):
        self._registeredMachineNumber = registeredMachineNumber

    def CurrentPrinterDate(self):
        return self._currentPrinterDate

    def _setCurrentPrinterDate(self, currentPrinterDate):
        self._currentPrinterDate = currentPrinterDate

    def CurrentPrinterTime(self):
        return self._currentPrinterTime

    def _setCurrentPrinterTime(self, currentPrinterTime):
        self._currentPrinterTime = currentPrinterTime

    def LastNCNumber(self):
        return self._lastNCNumber

    def _setLastNCNumber(self, lastNCNumber):
        self._lastNCNumber = lastNCNumber

    def QuantityOfNCToday(self):
        return self._quantityOfNCToday

    def _setQuantityOfNCToday(self, quantityOfNCToday):
        self._quantityOfNCToday = quantityOfNCToday
