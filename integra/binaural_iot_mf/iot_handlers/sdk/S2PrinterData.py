import datetime
from odoo.addons.hw_drivers.iot_handlers.sdk.Util import Util


class S2PrinterData(object):
    _subTotalBases = 0
    _subTotalTax = 0
    _baseTasaIgtf = 0
    _amountPayable = 0
    _numberPaymentsMade = 0
    _typeDocument = 0
    _quantityArticles = 0
    _condition = 0

    def __init__(self, trama):
        if trama != None:
            if len(trama) > 69:
                try:
                    _arrayParameter = str(trama[1:-1]).split(chr(0x0A))
                    if len(_arrayParameter) > 1:
                        self._setSubTotalBases(Util().DoValueDouble(_arrayParameter[0][3:]))
                        self._setSubTotalTax(Util().DoValueDouble(_arrayParameter[1][1:]))
                        self._setBaseTasaIgtf(Util().DoValueDouble(_arrayParameter[2][1:]))
                        self._setQuantityArticles(int(_arrayParameter[3]))
                        self._setAmountPayable(Util().DoValueDouble(_arrayParameter[4][1:]))
                        self._setNumberPaymentsMade(int(_arrayParameter[5]))
                        self._setTypeDocument(int(_arrayParameter[6]))
                except (ValueError):
                    return

    def SubTotalBases(self):
        return self._subTotalBases

    def SubTotalTax(self):
        return self._subTotalTax

    def BaseTasaIgtf(self):
        return self._baseTasaIgtf

    def AmountPayable(self):
        return self._amountPayable

    def NumberPaymentsMade(self):
        return self._numberPaymentsMade

    def QuantityArticles(self):
        return self._quantityArticles

    def TypeDocument(self):
        return self._typeDocument

    def Condition(self):
        return self._condition

    def _setQuantityArticles(self, value):
        self._quantityArticles = value

    def _setTypeDocument(self, type):
        self._typeDocument = type

    def _setCondition(self, condition):
        self._condition = condition

    def _setSubTotalBases(self, subTotalBases):
        self._subTotalBases = subTotalBases

    def _setSubTotalTax(self, subTotalTax):
        self._subTotalTax = subTotalTax

    def _setBaseTasaIgtf(self, baseTasaIgtf):
        self._baseTasaIgtf = baseTasaIgtf

    def _setAmountPayable(self, amountPayable):
        self._amountPayable = amountPayable

    def _setNumberPaymentsMade(self, numberPaymentsMade):
        self._numberPaymentsMade = numberPaymentsMade
