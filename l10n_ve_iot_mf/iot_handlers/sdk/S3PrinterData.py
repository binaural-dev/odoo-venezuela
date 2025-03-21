from odoo.addons.hw_drivers.iot_handlers.sdk.Util import Util


class S3PrinterData(object):
    _typeTax1 = 0
    _tax1 = 0
    _typeTax2 = 0
    _tax2 = 0
    _typeTax3 = 0
    _tax3 = 0
    _typeTaxIGTF = 0
    _taxIgtf = 0
    _systemFlags = []

    def __init__(self, trama):
        if trama != None:
            if len(trama) > 0:
                try:
                    _arrayParameter = str(trama[1:-1]).split(chr(0x0A))  # (0X0A))
                    if len(_arrayParameter) > 1:

                        self._setTypeTax1(_arrayParameter[0][2])
                        self._setTax1(Util().DoValueDouble(_arrayParameter[0][3:]))
                        self._setTypeTax2(_arrayParameter[1][0])
                        self._setTax2(Util().DoValueDouble(_arrayParameter[1][1:]))
                        self._setTypeTax3(_arrayParameter[2][0])
                        self._setTax3(Util().DoValueDouble(_arrayParameter[2][1:]))
                        self._setTypeTaxIGTF(_arrayParameter[3][0])
                        self._setTaxIgtf(Util().DoValueDouble(_arrayParameter[3][1:]))

                        _flagsQuantity = int(len(_arrayParameter[3]) / 2)
                        self._systemFlags = []
                        _index = 0
                        _iteration = 0
                        while _iteration < _flagsQuantity:
                            self._systemFlags.append(
                                int(_arrayParameter[3][_index : _index + 2])
                            )  # _index, 2 #[_iteration]
                            _index = _index + 2
                            _iteration += 1
                        self._setSystemFlags(self._systemFlags)
                except (ValueError):
                    return

    def TypeTax1(self):
        return self._typeTax1

    def Tax1(self):
        return self._tax1

    def TypeTax2(self):
        return self._typeTax2

    def Tax2(self):
        return self._tax2

    def TypeTax3(self):
        return self._typeTax3

    def Tax3(self):
        return self._tax3

    def TypeTaxIGTF(self):
        return self._typeTaxIGTF

    def TaxIgtf(self):
        return self._taxIgtf

    def AllSystemFlags(self):
        return self._systemFlags

    def _setTypeTax1(self, typeTax1):
        self._typeTax1 = typeTax1

    def _setTax1(self, tax1):
        self._tax1 = tax1

    def _setTypeTax2(self, typeTax2):
        self._typeTax2 = typeTax2

    def _setTax2(self, tax2):
        self._tax2 = tax2

    def _setTypeTax3(self, typeTax3):
        self._typeTax3 = typeTax3

    def _setTax3(self, tax3):
        self._tax3 = tax3

    def _setTypeTaxIGTF(self, typeTaxIgtf):
        self._typeTaxIGTF = typeTaxIgtf

    def _setTaxIgtf(self, taxIgtf):
        self._taxIgtf = taxIgtf

    def _setSystemFlags(self, pSystemFlags):  # []
        self._systemFlags = pSystemFlags
