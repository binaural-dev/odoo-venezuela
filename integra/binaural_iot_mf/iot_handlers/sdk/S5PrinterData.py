class S5PrinterData(object):
    _rif = ""
    _registeredMachineNumber = ""
    _auditMemoryNumber = 0
    _auditMemoryTotalCapacity = 0
    _auditMemoryFreeCapacity = 0
    _numberRegisteredDocuments = 0

    def __init__(self, trama):
        if trama != None:
            if len(trama) > 0:
                try:
                    _arrayParameter = str(trama[1:-1]).split(chr(0x0A))
                    if len(_arrayParameter) >= 5:
                        self._setRIF(_arrayParameter[0][2:])
                        self._setRegisteredMachineNumber(_arrayParameter[1])
                        self._setNumberMemoryAudit(int(_arrayParameter[2]))
                        self._setCapacityTotalMemoryAudit(int(_arrayParameter[3]))
                        self._setAuditMemoryFreeCapacity(int(_arrayParameter[4]))
                        self._setNumberDocumentRegisters(int(_arrayParameter[5]))
                except (ValueError):
                    return

    def RIF(self):
        return self._rif

    def RegisteredMachineNumber(self):
        return self._registeredMachineNumber

    def AuditMemoryNumber(self):
        return self._auditMemoryNumber

    def AuditMemoryTotalCapacity(self):
        return self._auditMemoryTotalCapacity

    def AuditMemoryFreeCapacity(self):
        return self._auditMemoryFreeCapacity

    def NumberRegisteredDocuments(self):
        return self._numberRegisteredDocuments

    def _setRIF(self, RIF):
        self._rif = RIF

    def _setRegisteredMachineNumber(self, registeredMachineNumber):
        self._registeredMachineNumber = registeredMachineNumber

    def _setNumberMemoryAudit(self, numberMemoryAudit):
        self._auditMemoryNumber = numberMemoryAudit

    def _setCapacityTotalMemoryAudit(self, capacityTotalMemoryAudit):
        self._auditMemoryTotalCapacity = capacityTotalMemoryAudit

    def _setAuditMemoryFreeCapacity(self, pAuditMemoryFreeCapacity):
        self._auditMemoryFreeCapacity = pAuditMemoryFreeCapacity

    def _setNumberDocumentRegisters(self, numberDocumentRegisters):
        self._numberRegisteredDocuments = numberDocumentRegisters
