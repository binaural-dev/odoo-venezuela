import datetime
from odoo.addons.hw_drivers.iot_handlers.sdk.Util import Util


class ReportData(object):

    _numberOfLastZReport = 0
    _zReportDate = ""
    _zReportTime = ""
    _numberOfLastInvoice = 0
    _lastInvoiceDate = ""
    _lastInvoiceTime = ""
    _numberOfLastDebitNote = 0
    _numberOfLastCreditNote = 0
    _numberOfLastNonFiscal = 0

    _freeSalesTax = 0  # ventas
    _generalRate1Sale = 0
    _generalRate1Tax = 0
    _reducedRate2Sale = 0
    _reducedRate2Tax = 0
    _additionalRate3Sal = 0
    _additionalRate3Tax = 0

    _freeTaxDebit = 0  # Notas de Debito
    _generalRateDebit = 0
    _generalRateTaxDebit = 0
    _reducedRateDebit = 0
    _reducedRateTaxDebit = 0
    _additionalRateDebit = 0
    _additionalRateTaxDebit = 0

    _freeTaxDevolution = 0  # Notas de Credito
    _generalRateDevolution = 0
    _generalRateTaxDevolution = 0
    _reducedRateDevolution = 0
    _reducedRateTaxDevolution = 0
    _additionalRateDevolution = 0
    _additionalRateTaxDevolution = 0

    # IGTF
    _igtfRateSales = 0
    _igtfRateTaxSales = 0
    _igtfRateDebit = 0
    _igtfRateTaxDebit = 0
    _igtfRateDevolution = 0
    _igtfRateTaxDevolution = 0

    def __init__(self, trama):
        if trama != None:
            if len(trama) > 100:
                try:
                    _arrayParameter = str(trama[1:-1]).split(chr(0x0A))  # (0X0A))
                    if len(_arrayParameter) == 31:

                        self._numberOfLastZReport = int(_arrayParameter[0])
                        _hr = _arrayParameter[2][0:2]
                        _mn = _arrayParameter[2][2:4]
                        _dd = _arrayParameter[1][4:6]
                        _mm = _arrayParameter[1][2:4]
                        _aa = int(_arrayParameter[1][0:2]) + 2000
                        _Date = str(_dd) + "-" + str(_mm) + "-" + str(_aa)
                        _Time = str(_hr) + ":" + str(_mn)
                        self._zReportDate = _Date
                        self._zReportTime = _Time

                        self._numberOfLastInvoice = int(_arrayParameter[3])
                        _hr = _arrayParameter[5][0:2]
                        _mn = _arrayParameter[5][2:4]
                        _dd = _arrayParameter[4][4:6]
                        _mm = _arrayParameter[4][2:4]
                        _aa = int(_arrayParameter[4][0:2]) + 2000
                        _Date = str(_dd) + "-" + str(_mm) + "-" + str(_aa)
                        _Time = str(_hr) + ":" + str(_mn)
                        self._lastInvoiceDate = _Date
                        self._lastInvoiceTime = _Time

                        self._numberOfLastCreditNote = int(_arrayParameter[6])
                        self._numberOfLastDebitNote = int(_arrayParameter[7])
                        self._numberOfLastNonFiscal = int(_arrayParameter[8])
                        self._freeSalesTax = Util().DoValueDouble(_arrayParameter[9])
                        self._generalRate1Sale = Util().DoValueDouble(_arrayParameter[10])
                        self._generalRate1Tax = Util().DoValueDouble(_arrayParameter[11])
                        self._reducedRate2Sale = Util().DoValueDouble(_arrayParameter[12])
                        self._reducedRate2Tax = Util().DoValueDouble(_arrayParameter[13])
                        self._additionalRate3Sal = Util().DoValueDouble(_arrayParameter[14])
                        self._additionalRate3Tax = Util().DoValueDouble(_arrayParameter[15])
                        self._freeTaxDebit = Util().DoValueDouble(_arrayParameter[16])
                        self._generalRateDebit = Util().DoValueDouble(_arrayParameter[17])
                        self._generalRateTaxDebit = Util().DoValueDouble(_arrayParameter[18])
                        self._reducedRateDebit = Util().DoValueDouble(_arrayParameter[19])
                        self._reducedRateTaxDebit = Util().DoValueDouble(_arrayParameter[20])
                        self._additionalRateDebit = Util().DoValueDouble(_arrayParameter[21])
                        self._additionalRateTaxDebit = Util().DoValueDouble(_arrayParameter[22])
                        self._freeTaxDevolution = Util().DoValueDouble(_arrayParameter[23])
                        self._generalRateDevolution = Util().DoValueDouble(_arrayParameter[24])
                        self._generalRateTaxDevolution = Util().DoValueDouble(_arrayParameter[25])
                        self._reducedRateDevolution = Util().DoValueDouble(_arrayParameter[26])
                        self._reducedRateTaxDevolution = Util().DoValueDouble(_arrayParameter[27])
                        self._additionalRateDevolution = Util().DoValueDouble(_arrayParameter[28])
                        self._additionalRateTaxDevolution = Util().DoValueDouble(
                            _arrayParameter[29]
                        )

                    if len(_arrayParameter) == 21:  # (PP1F3,HSP7000,OKI,SRP350,TALLY1125,SRP270)

                        self._numberOfLastZReport = int(_arrayParameter[0])
                        _dd = _arrayParameter[1][4:6]
                        _mm = _arrayParameter[1][2:4]
                        _aa = int(_arrayParameter[1][0:2]) + 2000
                        _Date = str(_dd) + "-" + str(_mm) + "-" + str(_aa)
                        self._zReportDate = _Date

                        self._numberOfLastInvoice = int(_arrayParameter[2])
                        _hr = _arrayParameter[4][0:2]
                        _mn = _arrayParameter[4][2:4]
                        _dd = _arrayParameter[3][4:6]
                        _mm = _arrayParameter[3][2:4]
                        _aa = int(_arrayParameter[3][0:2]) + 2000
                        _Date = str(_dd) + "-" + str(_mm) + "-" + str(_aa)
                        _Time = str(_hr) + ":" + str(_mn)
                        self._lastInvoiceDate = _Date
                        self._lastInvoiceTime = _Time

                        self._freeSalesTax = Util().DoValueDouble(_arrayParameter[5])
                        self._generalRate1Sale = Util().DoValueDouble(_arrayParameter[6])
                        self._generalRate1Tax = Util().DoValueDouble(_arrayParameter[7])
                        self._reducedRate2Sale = Util().DoValueDouble(_arrayParameter[8])
                        self._reducedRate2Tax = Util().DoValueDouble(_arrayParameter[9])
                        self._additionalRate3Sal = Util().DoValueDouble(_arrayParameter[10])
                        self._additionalRate3Tax = Util().DoValueDouble(_arrayParameter[11])
                        self._freeTaxDevolution = Util().DoValueDouble(_arrayParameter[12])
                        self._generalRateDevolution = Util().DoValueDouble(_arrayParameter[13])
                        self._generalRateTaxDevolution = Util().DoValueDouble(_arrayParameter[14])
                        self._reducedRateDevolution = Util().DoValueDouble(_arrayParameter[15])
                        self._reducedRateTaxDevolution = Util().DoValueDouble(_arrayParameter[16])
                        self._additionalRateDevolution = Util().DoValueDouble(_arrayParameter[17])
                        self._additionalRateTaxDevolution = Util().DoValueDouble(
                            _arrayParameter[18]
                        )
                        self._numberOfLastCreditNote = int(_arrayParameter[19])

                    if len(_arrayParameter) == 22:  # (SRP-280)

                        self._numberOfLastZReport = int(_arrayParameter[0])
                        _hr = _arrayParameter[2][0:2]
                        _mn = _arrayParameter[2][2:4]
                        _dd = _arrayParameter[1][4:6]
                        _mm = _arrayParameter[1][2:4]
                        _aa = int(_arrayParameter[1][0:2]) + 2000
                        _Date = str(_dd) + "-" + str(_mm) + "-" + str(_dd)
                        _Time = str(_hr) + ":" + str(_mn)
                        self._zReportDate = _Date
                        self._zReportTime = _Time

                        self._numberOfLastInvoice = int(_arrayParameter[3])
                        _hr = _arrayParameter[5][0:2]
                        _mn = _arrayParameter[5][2:4]
                        _dd = _arrayParameter[4][0:2]
                        _mm = _arrayParameter[4][2:4]
                        _aa = int(_arrayParameter[4][4:6]) + 2000
                        _Date = str(_dd) + "-" + str(_mm) + "-" + str(_aa)
                        _Time = str(_hr) + ":" + str(_mn)
                        self._lastInvoiceDate = _Date
                        self._lastInvoiceTime = _Time

                        self._freeSalesTax = Util().DoValueDouble(_arrayParameter[6])
                        self._generalRate1Sale = Util().DoValueDouble(_arrayParameter[7])
                        self._generalRate1Tax = Util().DoValueDouble(_arrayParameter[8])
                        self._reducedRate2Sale = Util().DoValueDouble(_arrayParameter[9])
                        self._reducedRate2Tax = Util().DoValueDouble(_arrayParameter[10])
                        self._additionalRate3Sal = Util().DoValueDouble(_arrayParameter[11])
                        self._additionalRate3Tax = Util().DoValueDouble(_arrayParameter[12])
                        self._freeTaxDevolution = Util().DoValueDouble(_arrayParameter[13])
                        self._generalRateDevolution = Util().DoValueDouble(_arrayParameter[14])
                        self._generalRateTaxDevolution = Util().DoValueDouble(_arrayParameter[15])
                        self._reducedRateDevolution = Util().DoValueDouble(_arrayParameter[16])
                        self._reducedRateTaxDevolution = Util().DoValueDouble(_arrayParameter[17])
                        self._additionalRateDevolution = Util().DoValueDouble(_arrayParameter[18])
                        self._additionalRateTaxDevolution = Util().DoValueDouble(
                            _arrayParameter[19]
                        )
                        self._numberOfLastCreditNote = int(_arrayParameter[20])

                    if len(_arrayParameter) == 40:  # Bixolon SRP-812

                        self._numberOfLastZReport = int(_arrayParameter[0])
                        _hr = _arrayParameter[2][0:2]
                        _mn = _arrayParameter[2][2:4]
                        _dd = _arrayParameter[1][4:6]
                        _mm = _arrayParameter[1][2:4]
                        _aa = int(_arrayParameter[1][0:2]) + 2000
                        _Date = str(_dd) + "-" + str(_mm) + "-" + str(_aa)
                        _Time = str(_hr) + ":" + str(_mn)
                        self._zReportDate = _Date
                        self._zReportTime = _Time

                        self._numberOfLastInvoice = int(_arrayParameter[3])
                        _hr = _arrayParameter[5][0:2]
                        _mn = _arrayParameter[5][2:4]
                        _dd = _arrayParameter[4][4:6]
                        _mm = _arrayParameter[4][2:4]
                        _aa = int(_arrayParameter[4][0:2]) + 2000
                        _Date = str(_dd) + "-" + str(_mm) + "-" + str(_aa)
                        _Time = str(_hr) + ":" + str(_mn)
                        self._lastInvoiceDate = _Date
                        self._lastInvoiceTime = _Time

                        self._numberOfLastDebitNote = int(_arrayParameter[6])
                        self._numberOfLastCreditNote = int(_arrayParameter[7])
                        self._numberOfLastNonFiscal = int(_arrayParameter[8])

                        self._freeSalesTax = Util().DoValueDouble(_arrayParameter[9])
                        self._generalRate1Sale = Util().DoValueDouble(_arrayParameter[10])
                        self._generalRate1Tax = Util().DoValueDouble(_arrayParameter[11])
                        self._reducedRate2Sale = Util().DoValueDouble(_arrayParameter[12])
                        self._reducedRate2Tax = Util().DoValueDouble(_arrayParameter[13])
                        self._additionalRate3Sal = Util().DoValueDouble(_arrayParameter[14])
                        self._additionalRate3Tax = Util().DoValueDouble(_arrayParameter[15])
                        self._freeTaxDebit = Util().DoValueDouble(_arrayParameter[16])
                        self._generalRateDebit = Util().DoValueDouble(_arrayParameter[17])
                        self._generalRateTaxDebit = Util().DoValueDouble(_arrayParameter[18])
                        self._reducedRateDebit = Util().DoValueDouble(_arrayParameter[19])
                        self._reducedRateTaxDebit = Util().DoValueDouble(_arrayParameter[20])
                        self._additionalRateDebit = Util().DoValueDouble(_arrayParameter[21])
                        self._additionalRateTaxDebit = Util().DoValueDouble(_arrayParameter[22])
                        self._freeTaxDevolution = Util().DoValueDouble(_arrayParameter[23])
                        self._generalRateDevolution = Util().DoValueDouble(_arrayParameter[24])
                        self._generalRateTaxDevolution = Util().DoValueDouble(_arrayParameter[25])
                        self._reducedRateDevolution = Util().DoValueDouble(_arrayParameter[26])
                        self._reducedRateTaxDevolution = Util().DoValueDouble(_arrayParameter[27])
                        self._additionalRateDevolution = Util().DoValueDouble(_arrayParameter[28])
                        self._additionalRateTaxDevolution = Util().DoValueDouble(
                            _arrayParameter[29]
                        )
                        self._igtfRateSales = Util().DoValueDouble(_arrayParameter[33])
                        self._igtfRateTaxSales = Util().DoValueDouble(_arrayParameter[34])
                        self._igtfRateDebit = Util().DoValueDouble(_arrayParameter[35])
                        self._igtfRateTaxDebit = Util().DoValueDouble(_arrayParameter[36])
                        self._igtfRateDevolution = Util().DoValueDouble(_arrayParameter[37])
                        self._igtfRateTaxDevolution = Util().DoValueDouble(_arrayParameter[38])
                except (ValueError):
                    return

