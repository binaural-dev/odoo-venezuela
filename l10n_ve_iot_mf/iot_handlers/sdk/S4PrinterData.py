import logging
from odoo.addons.iot_drivers.iot_handlers.sdk.Util import Util

_logger = logging.getLogger(__name__)


class S4PrinterData(object):
    def __init__(self, trama):
        if trama != None:
            if len(trama) > 0:
                self._allMeansOfPayment = ""
                try:
                    _arrayParameter = str(trama[1:-1]).split(chr(0x0A))
                    if _arrayParameter:
                        _arrayParameter[-1] = _arrayParameter[-1].rstrip(chr(0x03))
                    if len(_arrayParameter) > 1:
                        _numberOfMeansOfPayment = len(_arrayParameter) - 1
                        _iteration = 0
                        _valor = 0
                        while _iteration < _numberOfMeansOfPayment:
                            _cadena = _arrayParameter[_iteration]
                            if _iteration == 0:
                                _valor = str(_cadena[2:])
                            else:
                                _valor = str(_cadena)
                            self._allMeansOfPayment += (
                                "\nMedio de Pago "
                                + str(_iteration + 1)
                                + " : "
                                + str(Util().DoValueDouble(_valor))
                            )
                            _iteration += 1
                        self._setAllMeansOfPayment(self._allMeansOfPayment)
                except (ValueError, IndexError) as e:
                    _logger.warning(
                        "S4PrinterData parse error: %s | tramalen=%s params=%s",
                        e, len(trama), len(_arrayParameter) if '_arrayParameter' in dir() else '?'
                    )
                    return

    def AllMeansOfPayment(self):
        return self._allMeansOfPayment

    def _setAllMeansOfPayment(self, pAllMeansOfPayment):
        self._allMeansOfPayment = pAllMeansOfPayment
