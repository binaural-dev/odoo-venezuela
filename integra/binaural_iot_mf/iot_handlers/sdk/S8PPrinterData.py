class S8PPrinterData(object):
    _piedeTicket1 = ""
    _piedeTicket2 = ""
    _piedeTicket3 = ""
    _piedeTicket4 = ""
    _piedeTicket5 = ""
    _piedeTicket6 = ""
    _piedeTicket7 = ""
    _piedeTicket8 = ""

    def __init__(self, trama):
        if trama != None:
            _footer = trama.split("\n")
            if len(_footer) > 0:
                self._setPiedeTicket1(_footer[0][4:])
                self._setPiedeTicket2(_footer[1])
                self._setPiedeTicket3(_footer[2])
                self._setPiedeTicket4(_footer[3])
                self._setPiedeTicket5(_footer[4])
                self._setPiedeTicket6(_footer[5])
                self._setPiedeTicket7(_footer[6])
                self._setPiedeTicket8(_footer[7][:-2])

    def Footer1(self):
        return self._piedeTicket1

    def Footer2(self):
        return self._piedeTicket2

    def Footer3(self):
        return self._piedeTicket3

    def Footer4(self):
        return self._piedeTicket4

    def Footer5(self):
        return self._piedeTicket5

    def Footer6(self):
        return self._piedeTicket6

    def Footer7(self):
        return self._piedeTicket7

    def Footer8(self):
        return self._piedeTicket8

    def _setPiedeTicket1(self, PiedeTicket1):
        self._piedeTicket1 = PiedeTicket1

    def _setPiedeTicket2(self, PiedeTicket2):
        self._piedeTicket2 = PiedeTicket2

    def _setPiedeTicket3(self, PiedeTicket3):
        self._piedeTicket3 = PiedeTicket3

    def _setPiedeTicket4(self, PiedeTicket4):
        self._piedeTicket4 = PiedeTicket4

    def _setPiedeTicket5(self, PiedeTicket5):
        self._piedeTicket5 = PiedeTicket5

    def _setPiedeTicket6(self, PiedeTicket6):
        self._piedeTicket6 = PiedeTicket6

    def _setPiedeTicket7(self, PiedeTicket7):
        self._piedeTicket7 = PiedeTicket7

    def _setPiedeTicket8(self, PiedeTicket8):
        self._piedeTicket8 = PiedeTicket8
