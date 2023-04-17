class S7PrinterData(object):
    _micr = ""

    def __init__(self, trama):
        if trama != None:
            if len(trama) > 0:
                try:
                    _arrayParameter = str(trama[1:-2]).split(chr(0x0A))  # (0X0A))
                    if len(_arrayParameter) >= 1:
                        self._setMICR(str(_arrayParameter[0][2:]))
                except (ValueError):
                    return

    def MICR(self):
        return self._micr

    def _setMICR(self, micr):
        self._micr = micr
