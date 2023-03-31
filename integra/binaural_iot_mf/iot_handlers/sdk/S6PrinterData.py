class S6PrinterData(object):
    _bit_Facturacion = ""
    _bit_Slip = ""
    _bit_Validacion = ""

    def __init__(self, trama):
        if trama != None:
            if len(trama) > 0:
                _arrayParameter = str(trama[1:-1]).split(chr(0x0A))
                if len(_arrayParameter) > 1:
                    try:
                        self._setBit_Facturacion(str(_arrayParameter[0][2:]))
                        self._setBit_Slip(_arrayParameter[1])
                        self._setBit_Validacion(_arrayParameter[2])
                    except (ValueError):
                        return

    def Bit_Facturacion(self):
        return self._bit_Facturacion

    def Bit_Slip(self):
        return self._bit_Slip

    def Bit_Validacion(self):
        return self._bit_Validacion

    def _setBit_Facturacion(self, bitFacturacion):
        self._bit_Facturacion = bitFacturacion

    def _setBit_Slip(self, bitSlip):
        self._bit_Slip = bitSlip

    def _setBit_Validacion(self, bitValidacion):
        self._bit_Validacion = bitValidacion
