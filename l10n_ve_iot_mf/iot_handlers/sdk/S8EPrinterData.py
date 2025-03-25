class S8EPrinterData(object):
    _encabezado1 = ""
    _encabezado2 = ""
    _encabezado3 = ""
    _encabezado4 = ""
    _encabezado5 = ""
    _encabezado6 = ""
    _encabezado7 = ""
    _encabezado8 = ""

    def __init__(self, trama):
        if trama != None:
            _header = trama.split("\n")
            if len(_header) > 0:
                self._setEncabezado1(_header[0][3:])
                self._setEncabezado2(_header[1])
                self._setEncabezado3(_header[2])
                self._setEncabezado4(_header[3])
                self._setEncabezado5(_header[4])
                self._setEncabezado6(_header[5])
                self._setEncabezado7(_header[6])
                self._setEncabezado8(_header[7][:-2])

    def Header1(self):
        return self._encabezado1

    def Header2(self):
        return self._encabezado2

    def Header3(self):
        return self._encabezado3

    def Header4(self):
        return self._encabezado4

    def Header5(self):
        return self._encabezado5

    def Header6(self):
        return self._encabezado6

    def Header7(self):
        return self._encabezado7

    def Header8(self):
        return self._encabezado8

    def _setEncabezado1(self, Encabezado1):
        self._encabezado1 = Encabezado1

    def _setEncabezado2(self, Encabezado2):
        self._encabezado2 = Encabezado2

    def _setEncabezado3(self, Encabezado3):
        self._encabezado3 = Encabezado3

    def _setEncabezado4(self, Encabezado4):
        self._encabezado4 = Encabezado4

    def _setEncabezado5(self, Encabezado5):
        self._encabezado5 = Encabezado5

    def _setEncabezado6(self, Encabezado6):
        self._encabezado6 = Encabezado6

    def _setEncabezado7(self, Encabezado7):
        self._encabezado7 = Encabezado7

    def _setEncabezado8(self, Encabezado8):
        self._encabezado8 = Encabezado8
