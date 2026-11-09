## 1. Implementación

- [x] 1.1 `SerialConnection.read()` reconoce ACK/NAK por el primer byte
- [x] 1.2 `sendCommand()` con `resendOnNoResponse`
- [x] 1.3 `_sendDocumentCommand()` con decisión por S2 para ítems, `q-` y `2XX`
- [x] 1.4 `_verifyRecoveredDocument()` antes de los pagos, solo tras una recuperación
- [x] 1.5 `abortTransaction()` anula con `7` y deja `9` de respaldo
- [x] 1.6 Mensajes nuevos en inglés con su traducción en `i18n/es_VE.po`

## 2. Verificación

- [x] 2.1 Tests Hoot: ítem registrado sin ACK, ítem no registrado, S2 que no
      cuadra, pago parcial sin ACK, anulación con `7`, lector con ACK pegado
      y parseo de una trama S2 real
- [x] 2.2 Medición en la MF de pruebas Z7C7046254: S2/S25 sin conteo de
      artículos, `9` con NAK y `7` anulando
- [ ] 2.3 Repetir en la MF de pruebas la reproducción del ticket con el
      cambio (el ítem sale una sola vez)
