import logging

_logger = logging.getLogger(__name__)


class S7PrinterData(object):
    _micr = ""

    def __init__(self, trama):
        if trama != None:
            if len(trama) > 0:
                try:
                    _arrayParameter = str(trama[1:-2]).split(chr(0x0A))  # (0X0A))
                    if _arrayParameter:
                        _arrayParameter[-1] = _arrayParameter[-1].rstrip(chr(0x03))
                    if len(_arrayParameter) >= 1:
                        self._setMICR(str(_arrayParameter[0][2:]))
                except (ValueError, IndexError) as e:
                    _logger.warning(
                        "S7PrinterData parse error: %s | tramalen=%s params=%s",
                        e, len(trama), len(_arrayParameter) if '_arrayParameter' in dir() else '?'
                    )
                    return

    def MICR(self):
        return self._micr

    def _setMICR(self, micr):
        self._micr = micr
